"""
[모듈 제목]
Bronze Layer (EL) Extraction & Loading Pipeline Service

[모듈 목적 및 상세 설명]
메달리온 아키텍처의 최하단인 브론즈 레이어를 전담하는 구체 파이프라인 클래스입니다.
추상 인터페이스(`AbstractPipeline`)를 상속받아 외부 Open API 원천 데이터의 
비동기 일괄 수집(Extract)과 데이터 레이크 S3로의 Zstd 스트리밍 압축 적재(Load) 파이프라인을 오케스트레이션합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Job Loading: 부모 생성자가 파싱한 `extract_jobs` 목록 획득.
2. Resource Context: 비동기 진입 시 하위 ExtractorService의 HTTP 세션 풀 오픈.
3. Execution: 외부 연동망으로부터 동시성 비동기 I/O 기반 데이터 추출 (ExtractedDTO 생산).
4. Storage Loading: 동기식 로더 서비스를 백그라운드 워커 스레드풀로 매핑 위임하여 압축 적재 완료.
"""

import asyncio
import datetime
from typing import Any, Dict, Optional, Union

from src.common.decorators.log_decorator import log_decorator
from src.common.dtos import ExtractedDTO, TransformedDTO
from src.common.exceptions import ETLError, LoaderError
from src.loader.loader_service import LoaderService
from src.pipeline.abstract_pipeline import AbstractPipeline
from src.extractor.extractor_service import ExtractorService

# 글로벌 상태 코드 상수 규격 유지
STATUS_SUCCESS = "SUCCESS"
STATUS_FAIL_EXTRACT = "FAIL_EXTRACT"
STATUS_FAIL_LOAD = "FAIL_LOAD"
STATUS_SYSTEM_ERROR = "CRITICAL_SYSTEM_ERROR"
STATUS_EMPTY = "EMPTY_JOBS"


class BronzePipeline(AbstractPipeline):
    """외부 소스 연동 및 원천 바이너리 적재를 전담하는 브론즈 데이터 레이어 서비스 계층."""

    def __init__(self, task_name: str) -> None:
        """부모의 초기화 체인을 구동하고 브론즈 전용 하위 컴포넌트들을 바인딩합니다."""
        super().__init__(task_name=task_name)
        
        # [설계 의도] 컴포넌트 인스턴스 선언을 격리하여 메모리 효율화 유도.
        self._extractor_service = ExtractorService()
        self._loader_service = LoaderService(target_loader=self._task_policy.target_loader)

    async def __aenter__(self) -> "BronzePipeline":
        """비동기 컨텍스트 진입 생명주기에 맞추어 HTTP 커넥션 풀 등의 소켓 자원을 개방합니다."""
        await super().__aenter__()
        await self._extractor_service.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """물리적 예외 발생 여부와 무관하게 오픈된 네트워크 커넥션을 소멸시켜 OS 리소스 유실을 차단합니다."""
        await self._extractor_service.__aexit__(exc_type, exc_val, exc_tb)
        await super().__aexit__(exc_type, exc_val, exc_tb)

    @log_decorator()
    async def run_batch(self, execution_date: Optional[str] = None, extract_mode: str = "TODAY") -> Dict[str, Any]:
        """브론즈 레이어에 할당된 API 수집 태스크들을 스레드 및 코루틴 Concurrency 기반으로 고속 병렬 처리합니다."""
        job_ids = self._task_policy.extract_jobs
        if not job_ids:
            return {"status": STATUS_EMPTY, "total": 0, "success": 0, "fail": 0, "details": []}

        if not execution_date:
            execution_date = datetime.now().strftime("%Y%m%d")

        runtime_params = {"EXECUTION_DATE": execution_date, "EXTRACT_MODE": extract_mode.upper()}
        job_requests = [(job_id, runtime_params) for job_id in job_ids]

        # [Extract] 외부망 비동기 병렬 수집
        extracted = await self._extractor_service.extract_batch(job_requests)

        # [Load] 수집 결과 적재 위임 태스크 빌드
        load_tasks = []
        for job_id, result in zip(job_ids, extracted):
            if isinstance(result, Exception):
                load_tasks.append(self._failed_extract(job_id, result))
            else:
                load_tasks.append(self._safe_load(job_id, result))

        # 적재 작업 병렬 실행 (asyncio.to_thread 풀 소모)
        loaded = await asyncio.gather(*load_tasks, return_exceptions=True)

        success_count = sum(1 for r in loaded if isinstance(r, dict) and r.get("status") == STATUS_SUCCESS)
        fail_count = len(job_ids) - success_count
        
        summary = {
            "task_name": self._task_name,
            "execution_date": execution_date,
            "extract_mode": extract_mode,
            "total": len(job_ids),
            "success": success_count,
            "fail": fail_count,
            "details": loaded
        }
        self._logger.info(f"브론즈 파이프라인 가동 완료 - 총 {len(job_ids)}건 중 {success_count}건 성공")
        return summary

    async def _failed_extract(self, job_id: str, exception: Exception) -> Dict[str, Any]:
        """수집 단계 실패 지표 정규화."""
        error_info = exception.to_dict() if isinstance(exception, ETLError) else {"message": str(exception)}
        return {"job_id": job_id, "status": STATUS_FAIL_EXTRACT, "error_info": error_info}

    async def _safe_load(self, job_id: str, dto: Union[ExtractedDTO, TransformedDTO]) -> Dict[str, Any]:
        """워커 스레드로 동기 블로킹 연산을 양도하여 비동기 루프를 보호하고 데이터를 적재합니다."""
        try:
            is_loaded = await asyncio.to_thread(self._loader_service.execute_load, dto)
            if is_loaded:
                return {"job_id": job_id, "status": STATUS_SUCCESS, "error_info": None}
            return {"job_id": job_id, "status": STATUS_FAIL_LOAD, "error_info": {"message": "Loader returned False"}}
        except LoaderError as le:
            return {"job_id": job_id, "status": STATUS_FAIL_LOAD, "error_info": le.to_dict()}
        except Exception as e:
            unexpected_error = ETLError(message=f"브론즈 적재 중 미정의 오류: {str(e)}", original_exception=e)
            return {"job_id": job_id, "status": STATUS_SYSTEM_ERROR, "error_info": unexpected_error.to_dict()}