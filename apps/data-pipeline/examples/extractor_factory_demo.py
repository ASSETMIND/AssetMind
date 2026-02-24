"""
Extractor Factory 통합 테스트 스크립트 (Integration Test Suite)

이 스크립트는 `ExtractorFactory`를 통해 생성된 각 Provider별 수집기(Extractor)가
설정(Config), 인증(Auth), 네트워크(Http) 계층과 완벽하게 통합되어 동작하는지 검증합니다.

데이터 흐름 (Data Flow):
Load Config -> Init Shared HttpClient -> Factory.create_extractor() -> Extractor.extract() -> Verify Response

주요 검증 항목:
1. Factory: 올바른 클래스(KISExtractor 등)가 인스턴스화되는가?
2. Auth: 각 전략(OAuth2, JWT)이 토큰을 정상 발급/주입하는가?
3. Http: 실제 외부 API와 통신하여 200 OK 응답을 받는가?
4. Performance: `asyncio.gather`를 통해 다중 작업이 병렬로 처리되는가?
"""

import sys
import asyncio
from pathlib import Path

# [System Path Setup]
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

# [Internal Modules]
from src.common.config import get_config, ConfigManager
from src.common.log import LogManager
from src.extractor.adapters.http_client import AsyncHttpAdapter
from src.extractor.domain.dtos import RequestDTO
from src.extractor.extractor_factory import ExtractorFactory
from src.extractor.domain.exceptions import ExtractorError

# 전역 로거 (Global Logger)
logger = None

async def run_integration_test(
    job_id: str, 
    http_client: AsyncHttpAdapter, 
    config: ConfigManager
):
    """개별 수집 작업(Job)에 대한 통합 테스트를 수행합니다.

    Factory를 통해 수집기를 생성하고, 실제 API를 호출하여 응답 규격을 검증합니다.

    Args:
        job_id (str): 테스트할 작업 식별자 (YAML Policy Key).
        http_client (AsyncHttpAdapter): 공유 HTTP 클라이언트.
        config (ConfigManager): 통합 설정 객체.
    """
    logger.info(f">>> Testing Job: {job_id}")

    try:
        # 1. [Factory] 수집기 인스턴스 생성 (Dependency Injection)
        # Factory가 Config의 Provider 타입을 보고 올바른 구현체(KISExtractor 등)를 생성하고,
        # 필요한 인증 전략(AuthStrategy)을 자동으로 주입하는지 검증합니다.
        extractor = ExtractorFactory.create_extractor(job_id, http_client, config)
        logger.info(f"✅ Factory Created Instance: {extractor.__class__.__name__} for {job_id}")

        # 2. [Prepare] 요청 파라미터 준비
        # YAML 설정 파일에 정의된 기본 파라미터를 로드합니다.
        policy = config.extraction_policy.get(job_id)
        request_params = policy.params.copy()

        # 3. [Execution] 수집 실행 (Extract)
        # RequestDTO 생성 -> 유효성 검증 -> 인증 토큰 발급 -> API 호출 과정을 수행합니다.
        request_dto = RequestDTO(
            job_id=job_id,
            params=request_params
        )
        
        response = await extractor.extract(request_dto)

        # 4. [Verification] 결과 검증
        # HTTP 200 OK 또는 비즈니스 로직상 성공(Status: success)인지 확인합니다.
        is_success = (
            response.meta.get("status") == "success" or 
            str(response.meta.get("status_code")) in ["200", "0", "OK"]
        )

        if is_success:
            # 데이터가 너무 길 수 있으므로 앞부분만 요약하여 출력
            summary = str(response.data)[:100] + "..." if response.data else "Empty Data"
            logger.info(f"✅ Extraction Success | Source: {response.meta.get('source')} | Data Sample: {summary}")
        else:
            logger.error(f"❌ Logical Failure | Meta: {response.meta}")

    except ExtractorError as e:
        logger.error(f"❌ Functional Error (Expected Domain Exception) in {job_id}: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected System Error in {job_id}: {e}", exc_info=True)


async def main():
    """테스트 메인 진입점 (Entry Point).
    
    설정을 로드하고 HTTP 세션을 생성한 뒤, 정의된 테스트 작업들을 병렬로 실행합니다.
    """
    global logger

    # 1. Config & Log Init
    try:
        config = get_config("extractor_demo")
        logger = LogManager.get_logger("IntegrationTest")
        logger.info(">>> [Start] Extractor Integration Test Suite initialized.")
    except Exception as e:
        print(f"[Critical] Failed to load configuration: {e}")
        return

    # 2. Http Client Context
    # TCP Connection 재사용(Connection Pooling)을 위해 하나의 세션을 모든 테스트 작업이 공유합니다.
    async with AsyncHttpAdapter(timeout=15) as http_client:
        
        # 3. Test Cases Definition
        # YAML 파일에 정의된 Policy 중 테스트할 대상 목록
        test_jobs = [
            "test_kis_connectivity",
            "test_fred_connectivity",
            "test_ecos_connectivity",
            "test_upbit_connectivity"
        ]

        # 4. Parallel Execution Setup
        # I/O Bound 작업의 효율성을 위해 asyncio.gather를 사용하여 병렬로 실행합니다.
        tasks = []
        for job_id in test_jobs:
            if job_id in config.extraction_policy:
                tasks.append(run_integration_test(job_id, http_client, config))
            else:
                logger.warning(f"⚠️ Policy not found in Config: {job_id}")

        # 5. Run Tasks
        if tasks:
            logger.info(f"🚀 Starting {len(tasks)} integration tests in parallel...")
            await asyncio.gather(*tasks)
        else:
            logger.warning("No valid tasks to run.")

    logger.info("=" * 60)
    logger.info(">>> [End] All Integration Tests Completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Test stopped by user.")