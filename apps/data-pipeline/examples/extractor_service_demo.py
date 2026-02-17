"""
[Extractor Service 통합 데모 (Integration Demo)]

이 스크립트는 `ExtractorService`가 하위 모듈(Factory, Auth, Http)을 올바르게 중재하고,
데이터 수집 요청을 정상적으로 수행하는지 검증합니다.

데이터 흐름 (Data Flow):
Client -> ExtractorService (Facade) -> Factory -> Extractor -> ExtractedDTO (Normalized)

검증 시나리오:
1. Lifecycle: `async with`를 통한 HTTP 세션 자동 관리.
2. Normalization: 이종 Provider(KIS, UPBIT 등)의 응답 코드가 'success'로 통일되는지 확인.
3. Override: 런타임 파라미터 주입이 정상 동작하는지 확인.
4. Batch: 다건 병렬 처리 및 부분 성공(Partial Success) 동작 확인.
"""
import sys
import asyncio
from typing import Union
from pathlib import Path

# [System Path Setup]
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

# [Internal Modules]
from src.common.config import ConfigManager
from src.common.log import LogManager
from src.extractor.extractor_service import ExtractorService
from src.common.dtos import ExtractedDTO

# 전역 로거
logger = None

def log_result(job_id: str, result: Union[ExtractedDTO, Exception]):
    """
    결과 로깅 함수 (Factory Demo Style)
    
    복잡한 구조 대신, 성공/실패 여부와 데이터 요약만 간결하게 출력합니다.
    Service Layer가 이미 응답을 정규화(Normalization)했으므로 로직이 단순합니다.
    """
    if isinstance(result, ExtractedDTO):
        # Service Layer가 'status_code'를 확인하여 'status: success'로 변환해 둠
        if result.meta.get("status") == "success":
            # 데이터가 길면 100자로 자름
            summary = str(result.data)[:100] + "..." if result.data else "Empty Data"
            source = result.meta.get('source', 'Unknown')
            logger.info(f"✅ [{job_id}] Success | Source: {source} | Data: {summary}")
        else:
            logger.error(f"❌ [{job_id}] Logic Failure | Meta: {result.meta}")

    elif isinstance(result, Exception):
        logger.error(f"❌ [{job_id}] System Error: {str(result)}")
    else:
        logger.warning(f"❓ [{job_id}] Unknown Result Type: {type(result)}")

async def main():
    global logger
    
    # 1. Config & Log Init
    try:
        config = ConfigManager.get_config("extractor_demo")
        logger = LogManager.get_logger("ServiceDemo")
        logger.info(">>> [Start] Extractor Service Demo initialized.")
    except Exception as e:
        print(f"[Critical] Failed to load configuration: {e}")
        return

    # 2. Service Context Lifecycle
    # Service가 내부적으로 Connection Pool을 생성하고 관리합니다.
    logger.info(">>> [Step 1] Initializing Service Context...")
    
    async with ExtractorService(config) as service:
        
        # ---------------------------------------------------------
        # Scenario A: Single Job (KIS) - Response Normalization Check
        # ---------------------------------------------------------
        logger.info(">>> [Step 2] Executing Single Job (KIS)")
        try:
            # KIS는 원본 코드가 '0'이지만, Service가 'success'로 변환해야 함
            result = await service.extract_job("test_kis_connectivity")
            log_result("test_kis_connectivity", result)
        except Exception as e:
            logger.error(f"❌ Critical Error: {e}")

        # ---------------------------------------------------------
        # Scenario B: Parameter Override (FRED)
        # ---------------------------------------------------------
        logger.info(">>> [Step 3] Executing Job with Override (FRED)")
        override_params = {
            "observation_start": "2023-01-01",
            "observation_end": "2023-12-31"
        }
        try:
            result = await service.extract_job("test_fred_connectivity", override_params)
            log_result("test_fred_connectivity", result)
        except Exception as e:
            logger.error(f"❌ Critical Error: {e}")

        # ---------------------------------------------------------
        # Scenario C: Batch Processing (UPBIT, ECOS, Invalid)
        # ---------------------------------------------------------
        logger.info(">>> [Step 4] Executing Batch (Partial Success Check)")
        batch_requests = [
            "test_upbit_connectivity", 
            "test_ecos_connectivity",
            "invalid_ghost_job_id"  # 실패 유도 (Partial Success 검증용)
        ]
        
        # 병렬 실행
        results = await service.extract_batch(batch_requests)

        for i, res in enumerate(results):
            job_name = batch_requests[i]
            log_result(job_name, res)

    logger.info("=" * 60)
    logger.info(">>> [End] Service Context Closed. Demo Completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Demo stopped by user.")