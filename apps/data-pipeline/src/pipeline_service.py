"""
[파이프라인 서비스 (Pipeline Service)]

ETL(Extract -> Transform -> Load) 전체 프로세스를 조율(Orchestration)하는 상위 서비스입니다.
설정 파일(YAML)에 정의된 정책을 기반으로 배치 작업을 실행하며,
각 단계별 서비스(Extractor, Transformer, Loader)의 생명주기를 관리합니다.

데이터 흐름 (Data Flow):
Config(Job List) -> ExtractorService (E) -> [ResponseDTO] -> (Transformer - Pass) -> (Loader - Pass) -> Result Report

주요 기능:
- [Batch Orchestration] Config에 정의된 모든 수집 작업을 식별하고 실행.
- [Lifecycle Management] 하위 서비스(Extractor 등)의 연결 생성 및 종료 관리.
- [Fault Tolerance] 개별 작업 실패가 전체 파이프라인을 중단시키지 않도록 격리.
- [Future Extensibility] Transformer/Loader 추가 시 코드 변경 최소화 구조.

Trade-off:
- Staged Execution (Phase별 실행) vs Stream Processing:
    - 현재는 'E' 단계가 완료된 후 후속 작업을 진행하는 구조임.
    - 장점: 구현이 단순하고 디버깅이 쉬움. 배치 처리에 적합.
    - 단점: 메모리 사용량이 높을 수 있음 (전체 데이터를 메모리에 적재).
    - 근거: 초기 단계이며 데이터 규모가 명확하지 않으므로 안정적인 Staged 방식을 채택.
"""

import asyncio
from typing import List, Dict, Any, Optional, Union

from src.common.config import get_config
from src.common.log import LogManager
from src.common.dtos import ExtractedDTO, TransformedDTO

from .extractor.extractor_service import ExtractorService
# TODO : 추후 구현될 서비스들의 인터페이스 타입 힌팅 (Forward Declaration)
# from .transformer.transformer_service import TransformerService
# from .loader.loader_service import LoaderService

class PipelineService:
    """ETL 파이프라인을 실행하고 관리하는 오케스트레이터 클래스.

    Attributes:
        _config (ConfigManager): 애플리케이션 설정 객체.
        _extractor_service (ExtractorService): 데이터 수집 서비스.
        _transformer_service (TransformerService): 데이터 변환 서비스.
        _loader_service (LoaderService): 데이터 적재 서비스.
    """

    def __init__(self, task_name: str):
        """PipelineService를 초기화합니다.

        Args:
            task_name (str): 실행할 작업 설정 파일의 이름 (예: 'extractor_demo').
        """
        # 1. Config Loading
        self._config = get_config(task_name)
        self._logger = LogManager.get_logger("PipelineService")
        
        # 2. Service Initialization
        # TODO : 현재는 Extractor만 존재하지만, 추후 Transformer/Loader도 여기서 초기화
        self._extractor_service = ExtractorService(self._config)
        self._transformer_service = None 
        self._loader_service = None

    async def __aenter__(self) -> "PipelineService":
        """Context Manager 진입: 하위 서비스들의 리소스(Connection Pool) 초기화."""
        await self._extractor_service.__aenter__()
        self._logger.info("PipelineService 리소스가 초기화되었습니다.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context Manager 종료: 하위 서비스들의 리소스 정리."""
        await self._extractor_service.__aexit__(exc_type, exc_val, exc_tb)
        self._logger.info("PipelineService 리소스가 해제되었습니다.")

    async def run_batch(self) -> Dict[str, Any]:
        """설정에 정의된 모든 작업을 배치로 실행합니다.

        과정:
            1. Config에서 Job ID 목록 추출.
            2. ExtractorService를 통한 병렬 수집 (Extract).
            3. (Future) TransformerService를 통한 변환 (Transform).
            4. (Future) LoaderService를 통한 적재 (Load).

        Returns:
            Dict[str, Any]: 실행 결과 요약 (성공/실패 수 및 상세 내역)
        """
        # 1. 실행할 작업 ID 식별
        job_ids = list(self._config.extraction_policy.keys())
        if not job_ids:
            self._logger.warning("설정 파일에 정의된 작업이 없습니다.")
            return {"status": "empty", "total": 0}

        self._logger.info(f"배치 파이프라인 시작 (대상: {len(job_ids)}건")

        # 2. [1단계: 수집] 병렬 실행
        extraction_results = await self._extractor_service.extract_batch(job_ids)

        success_count = 0
        fail_count = 0
        details = []
        
        # 3. [2단계: 변환] -> [3단계: 적재] 파이프라인 흐름 제어
        for i, result in enumerate(extraction_results):
            job_id = job_ids[i]
            job_result = {"job_id": job_id, "status": "PENDING", "error": None}

            # Case A: 수집 단계 실패
            if isinstance(result, Exception):
                self._logger.error(f"Job '{job_id}' 수집 실패: {result}")
                job_result["status"] = "FAIL_EXTRACT"
                job_result["error"] = str(result)
                fail_count += 1
                details.append(job_result)
                continue

            # Case B: 수집 성공 -> 변환 및 적재 진행
            try:
                # --- 2단계: 변환 (Mock) ---
                # ExtractedDTO -> TransformedDTO
                transformed_dto = await self._mock_transform(result)

                # --- 3단계: 적재 (Mock) ---
                # TransformedDTO -> None (Action)
                await self._mock_load(transformed_dto)
                
                # 모든 단계 성공
                job_result["status"] = "SUCCESS"
                success_count += 1

            except Exception as e:
                # 변환/적재 단계 실패
                self._logger.error(f"Job '{job_id}' 변환/적재 실패: {e}")
                job_result["status"] = "FAIL_TRANSFORM_LOAD"
                job_result["error"] = str(e)
                fail_count += 1
            
            details.append(job_result)

        # 4. 최종 결과 집계
        summary = {
            "total": len(job_ids),
            "success": success_count,
            "fail": fail_count,
            "details": details
        }
        
        self._logger.info(
            f"배치 완료 >>> 성공: {success_count}, 실패: {fail_count}"
        )
        
        return summary

    async def _mock_transform(self, extracted: ExtractedDTO) -> TransformedDTO:
        """[Mock] 변환 로직: ExtractedDTO를 받아 TransformedDTO로 변환.
        
        현재는 별도 가공 없이 데이터를 그대로 넘깁니다 (Pass-through).
        """
        # 실제 로직: Pandas 변환, 정규화 등 수행
        return TransformedDTO(
            data=extracted.data,
            meta=extracted.meta  # 메타데이터 유지 또는 갱신
        )

    async def _mock_load(self, transformed: TransformedDTO) -> None:
        """[Mock] 적재 로직: TransformedDTO를 저장소에 적재.
        
        현재는 로그 출력으로 대체합니다.
        """
        # 실제 로직: DB Insert, File Save 등
        status = transformed.meta.get('status', 'unknown')
        source = transformed.meta.get('source', 'unknown')
        # 데이터가 있으면 로깅
        if transformed.data:
            self._logger.debug(f"[적재 완료] Source: {source}, Status: {status}")