"""
[모듈 제목]
Data Pipeline Orchestration Service Module

[모듈 목적 및 상세 설명]
ETL(Extract -> Transform -> Load) 프로세스 중 복잡한 변환(Transform) 과정을 생략하고, 
외부 API로부터 원본 데이터를 수집(Extract)하여 타겟 스토리지(S3 등)에 즉시 적재(Load)하는 
EL(Extract -> Load) 데이터 파이프라인의 최상위 오케스트레이터입니다.
설정 파일(YAML)에 정의된 정책을 기반으로 배치 작업을 제어하며, 하위 계층(Extractor, Loader)의 
생명주기와 예외 처리를 중앙에서 총괄합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Config(Job List): 지정된 파이프라인 태스크(task_name)에 속한 수집 작업(Job) 목록 로드.
2. Orchestration: `PipelineService.run_batch()` 호출을 통해 전체 배치 파이프라인 가동.
3. Extraction: ExtractorService를 위임 호출하여 비동기 네트워크 통신으로 데이터 병렬 수집 (ExtractedDTO 획득).
4. Loading: LoaderService를 위임 호출하여 수집된 데이터를 스토리지에 동기/스레드 병렬 적재.
5. Output: 전체 실행 결과(성공, 실패 통계 및 개별 상세 내역)가 포함된 Result Report 딕셔너리 반환.

주요 기능:
- [Batch Orchestration] Config에 정의된 다수의 수집 작업을 식별하고 비동기 병렬 실행 체계 구성.
- [Lifecycle Management] 하위 서비스(Extractor 등)가 사용하는 HTTP Connection Pool 등의 자원 활성화 및 해제를 중앙에서 제어.
- [Fault Tolerance] 개별 작업 단위의 장애(수집 API 타임아웃, S3 업로드 실패 등)가 전체 파이프라인을 중단시키지 않도록 예외를 완벽히 격리(Isolation).
- [Async-Sync Impedance Matching] 동기(Sync) 방식으로 동작하는 로더를 백그라운드 스레드(`asyncio.to_thread`)에 위임하여 비동기 메인 이벤트 루프의 블로킹(Blocking) 현상 방지.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. Staged Execution (단계별 실행) vs Streaming Pipeline:
   - 장점: 수집('E') 단계가 모두 완료된 결과물(DTO) 리스트를 바탕으로 적재('L') 단계를 수행하는 구조는 메모리 상에서 상태 관리가 매우 단순하며, 오류 발생 시 실패 지점이 수집인지 적재인지 명확히 파악됨.
   - 단점: 전체 배치 수집 데이터를 메모리에 한 번 적재한 후 다음 단계로 넘어가므로, 극단적인 대용량 처리 시 컨테이너의 OOM(Out of Memory) 리스크가 존재함.
   - 근거: 외부 API 연동 특성상 1회 호출 페이로드가 수십 MB 수준으로 제한적이고, 현재 아키텍처에서는 극단적 메모리 최적화보다 파이프라인의 운영 안정성(Stability)과 격리된 디버깅(Fault Isolation) 환경 확보가 압도적으로 중요하므로 Staged 방식을 채택함.
2. Asyncio.gather() Error Handling (`return_exceptions=True`):
   - 장점: 하위 태스크의 예외가 상위 런타임을 크래시(Crash)시키지 않고 결과 객체로 안전하게 반환됨.
   - 단점: 반환된 결과 리스트를 순회하며 Exception 타입을 직접 필터링 및 분기 처리해야 하는 보일러플레이트 로직이 추가됨.
   - 근거: 단 하나의 API 장애로 인해 다른 99개의 정상 API 적재가 통째로 취소되는 상황(All-or-Nothing)을 피하고 데이터 가용성을 극대화하기 위해 부분 성공(Best-Effort) 전략을 강제함.
"""

import asyncio
from typing import List, Dict, Any, Optional, Union

from src.common.config import ConfigManager
from src.common.log import LogManager
from src.common.dtos import ExtractedDTO, TransformedDTO
from src.common.exceptions import ConfigurationError, ETLError, ExtractorError, LoaderError, TransformerError
from src.common.decorators.log_decorator import log_decorator

from .extractor.extractor_service import ExtractorService
from .loader.loader_service import LoaderService

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# [설계 의도] 매직 스트링(Magic String) 하드코딩을 방지하고 파이프라인 전역의 
# 상태 코드(Status Code) 일관성을 유지하기 위해 상수로 정의합니다.
STATUS_SUCCESS: str = "SUCCESS"
STATUS_FAIL_EXTRACT: str = "FAIL_EXTRACT"
STATUS_FAIL_LOAD: str = "FAIL_LOAD"
STATUS_SYSTEM_ERROR: str = "CRITICAL_SYSTEM_ERROR"
STATUS_EMPTY: str = "EMPTY_JOBS"

# ==============================================================================
# [Main Class] PipelineService
# ==============================================================================
class PipelineService:
    """EL(Extract-Load) 파이프라인의 전체 흐름을 제어하고 관리하는 최상위 오케스트레이터 클래스.

    Attributes:
        _task_name (str): 실행할 파이프라인 작업의 고유 이름 (설정 맵핑용).
        _config (ConfigManager): 애플리케이션 전역 설정 관리자 인스턴스.
        _logger (logging.Logger): 클래스별 격리된 구조화 로깅을 위한 로거.
        _extractor_service (ExtractorService): 데이터 수집(E) 계층의 Facade 서비스.
        _loader_service (LoaderService): 데이터 적재(L) 계층의 Facade 서비스.
    """

    def __init__(self, task_name: str):
        """PipelineService 인스턴스를 초기화하고 하위 서비스들을 준비합니다.

        Args:
            task_name (str): 실행할 작업 설정 파일의 이름 (예: 'fred_daily').

        Raises:
            ConfigurationError: task_name이 유효하지 않거나 설정 객체를 불러오지 못할 경우.
            AssertionError: task_name이 올바른 문자열 규격을 충족하지 못한 경우.
        """
        # [설계 의도] Entry Point에서의 방어적 프로그래밍. 잘못된 입력(None, 빈 문자열 등)으로 인해
        # 파이프라인이 오작동하는 것을 인스턴스화 시점에 조기 차단(Fail-Fast)함.
        assert isinstance(task_name, str) and task_name.strip(), "task_name은 비어있을 수 없는 문자열이어야 합니다."

        self._task_name = task_name
        self._config = ConfigManager.load("pipeline")
        self._logger = LogManager.get_logger(self.__class__.__name__)
        
        try:
            self._task_policy = self._config.get_pipeline(task_name)
        except ConfigurationError as e:
            raise ConfigurationError(f"[{task_name}] 파이프라인 설정을 로드할 수 없습니다. {e}") from e

        # [설계 의도] 하위 서비스 인스턴스를 즉시 초기화하여 참조를 확보함.
        # 실제 무거운 I/O 작업(네트워크 커넥션 생성 등)은 Context Manager(__aenter__)와 
        # Lazy Loading 단에서 수행되므로 초기화 비용은 극히 낮음.
        self._extractor_service = ExtractorService()
        self._loader_service = LoaderService(target_loader=self._task_policy.target_loader)

    async def __aenter__(self) -> "PipelineService":
        """Async Context Manager 진입 훅(Hook). 하위 시스템(주로 네트워크 커넥션) 자원을 활성화합니다.
        
        Returns:
            PipelineService: 자원 할당이 완료된 현재 인스턴스.
        """
        # [설계 의도] 수집 서비스의 HTTP 커넥션 풀을 파이프라인 시작 시점에 명시적으로 열어줌.
        await self._extractor_service.__aenter__()
        self._logger.info(f"[{self._task_name}] PipelineService 리소스 활성화 완료.")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async Context Manager 종료 훅(Hook). 하위 시스템 자원을 안전하게 해제합니다.
        
        Args:
            exc_type (Any): 발생한 예외의 타입 (정상 종료 시 None).
            exc_val (Any): 발생한 예외 객체.
            exc_tb (Any): 트레이스백 정보.
        """
        # [설계 의도] 파이프라인의 성공/실패 여부와 무관하게 사용이 끝난 소켓 리소스를 
        # 운영체제에 확실하게 반환하여 메모리 누수를 원천 방지함.
        await self._extractor_service.__aexit__(exc_type, exc_val, exc_tb)
        self._logger.info(f"[{self._task_name}] PipelineService 리소스 해제 완료.")

    @log_decorator()
    async def run_batch(self) -> Dict[str, Any]:
        """설정에 정의된 모든 API 수집 및 타겟 스토리지 적재 작업을 일괄 실행합니다.

        전체 흐름:
            1. Job 식별 -> 2. 병렬 데이터 수집 (Async) -> 3. 병렬 데이터 적재 (Thread/Async) -> 4. 집계

        Returns:
            Dict[str, Any]: 실행 결과 통계 (총 건수, 성공, 실패 및 개별 상세 내역 구조체).
        """
        # 1. Job 식별
        # [설계 의도] 파이프라인에 할당된 작업이 없을 경우 불필요한 I/O 진행을 막고 즉시 조기 종료.
        job_ids = self._task_policy.extract_jobs
        if not job_ids:
            return {"status": STATUS_EMPTY, "total": 0, "success": 0, "fail": 0, "details": []}

        # 2. [Extract 단계] 병렬 비동기 수집
        # [설계 의도] I/O Bound 작업인 외부 API 호출을 동시성(Concurrency)으로 처리하여 시간 대폭 단축.
        extracted = await self._extractor_service.extract_batch(job_ids)

        # 3. [Load 단계] 변환(Transform) 생략 후 즉시 병렬 적재
        load_tasks = []
        for job_id, result in zip(job_ids, extracted):
            if isinstance(result, Exception):
                # 수집 단계에서 실패한 작업은 적재 단계로 넘어가지 않고 에러 리포트로 분류.
                load_tasks.append(self._failed_extract(job_id, result))
            else:
                # 수집이 완료된 정상 DTO만 적재 태스크 큐에 할당.
                load_tasks.append(self._safe_load(job_id, result))

        # 적재 작업 병렬 실행 (내부적으로 스레드 풀에서 동작)
        loaded = await asyncio.gather(*load_tasks, return_exceptions=True)

        # 4. 결과 집계
        # [설계 의도] 각 작업의 최종 Status를 파싱하여 스케줄러(Airflow 등)가 
        # 파이프라인의 성공 여부를 판단할 수 있도록 규격화된 메타데이터 반환.
        success_count = sum(1 for r in loaded if isinstance(r, dict) and r.get("status") == STATUS_SUCCESS)
        fail_count = len(job_ids) - success_count
        
        summary = {
            "task_name": self._task_name,
            "total": len(job_ids),
            "success": success_count,
            "fail": fail_count,
            "details": loaded
        }

        self._logger.info(f"파이프라인 실행 요약 지표 - 총 {len(job_ids)}건 중 {success_count}건 성공, {fail_count}건 실패")
        
        return summary

    async def _failed_extract(self, job_id: str, exception: Exception) -> Dict[str, Any]:
        """수집(Extract) 단계에서 발생한 예외를 파이프라인 표준 결과 포맷으로 정규화합니다.
        
        Args:
            job_id (str): 실패한 작업의 고유 식별자.
            exception (Exception): 발생한 원본 예외 객체.
            
        Returns:
            Dict[str, Any]: 에러 내용이 규격화된 상태 딕셔너리.
        """
        # [설계 의도] 시스템 내 정의된 ETLError를 상속받은 경우 구조화된 딕셔너리(to_dict)를 활용하여
        # 에러 분석의 해상도를 높이고, 일반 예외의 경우에도 포맷을 일치시킴.
        error_info = exception.to_dict() if isinstance(exception, ETLError) else {"message": str(exception)}
        
        return {
            "job_id": job_id,
            "status": STATUS_FAIL_EXTRACT,
            "error_info": error_info
        }

    async def _safe_load(self, job_id: str, dto: ExtractedDTO) -> Dict[str, Any]:
        """단일 수집 완료 DTO에 대한 데이터 적재를 안전하게 격리하여 수행합니다.
        
        Args:
            job_id (str): 현재 처리 중인 Job의 고유 식별자.
            dto (ExtractedDTO): 수집이 성공적으로 완료된 원본 데이터 객체.
            
        Returns:
            Dict[str, Any]: 단일 Job의 적재 처리 최종 상태가 담긴 딕셔너리.
        """
        try:
            # [설계 의도] Impedance Matching 방어 로직.
            # LoaderService.execute_load는 동기(Sync) 블로킹 함수입니다. 이를 비동기 루프에서 직접 호출하면
            # 전체 파이프라인이 멈추게 되므로, asyncio.to_thread를 사용하여 워커 스레드 풀로 I/O 연산을 위임합니다.
            is_loaded = await asyncio.to_thread(self._loader_service.execute_load, dto)
            
            if is_loaded:
                return {"job_id": job_id, "status": STATUS_SUCCESS, "error_info": None}
            else:
                return {"job_id": job_id, "status": STATUS_FAIL_LOAD, "error_info": {"message": "Loader returned False"}}

        except LoaderError as le:
            # [설계 의도] 기 정의된 적재 도메인 에러(S3UploadError, ZstdCompressionError 등)를 포착하여 규격 유지.
            return {
                "job_id": job_id, 
                "status": STATUS_FAIL_LOAD, 
                "error_info": le.to_dict()
            }
            
        except Exception as e:
            # [설계 의도] 방어적 프로그래밍. 예측하지 못한 시스템 치명적 오류(MemoryError 등) 캐치 및 표준화(to_dict).
            unexpected_error = ETLError(
                message=f"적재 중 알 수 없는 치명적 오류 발생: {str(e)}", 
                original_exception=e
            )
            return {
                "job_id": job_id, 
                "status": STATUS_SYSTEM_ERROR, 
                "error_info": unexpected_error.to_dict()
            }