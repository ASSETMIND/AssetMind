"""
[local_s3_loader 모듈]

[모듈 목적 및 상세 설명]
오버 엔지니어링(Mocking 등)을 배제하고, LocalStack 환경에서 S3Loader의 데이터 적재 파이프라인(검증->압축->업로드)이 정상적으로 동작하는지 확인하는 직관적인 실행 스크립트입니다.

[전체 데이터 흐름 설명 (Input -> Output)]
SimpleRunner -> [Dummy DTO 생성] -> [S3Loader.load() 실행] -> [LocalStack S3 Bucket 적재] -> Boolean (성공 여부 반환)

주요 기능:
- [기능 1] LocalStack 연동을 위한 환경변수 최상단 주입
- [기능 2] ConfigManager의 get() 메서드 부재 에러를 회피하기 위한 SimpleDictConfig 주입
- [기능 3] 파이프라인(S3Loader) 적재 단일 실행 및 로깅

Trade-off: 장점 - 외부 라이브러리(unittest.mock) 의존성 없이 덕 타이핑(Duck Typing)을 활용하여 직관적으로 코드를 구성했습니다. 단점 - 실제 운영 환경의 ConfigManager를 완벽히 사용하지는 않습니다. 근거 - 현재의 단일 목적은 '파이프라인을 통한 LocalStack 정상 적재 확인'이므로, 복잡한 결합도를 낮추고 가장 단순한 형태의 딕셔너리 래퍼를 주입하는 것이 유지보수와 목적 달성에 부합합니다.
"""

# 1. Imports
import os
import logging
from typing import Any, Dict

# [설계 의도] Boto3가 내부적으로 환경변수를 읽기 전, 스크립트 최상단에서 강제로 LocalStack 설정 주입
os.environ["LOCAL_S3_ENDPOINT"] = "http://localhost:4566"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-2"

from src.common.dtos import ExtractedDTO
from src.common.config import ConfigManager
from src.loader.providers.s3_loader import S3Loader
from src.common.exceptions import ETLError

# 2. Constants & Configuration
TEST_BUCKET_NAME: str = "toss-datalake-raw-zone-prd"
TEST_REGION: str = "ap-northeast-2"

# 3. Custom Exceptions
class PipelineExecutionError(ETLError):
    """단순 파이프라인 실행 중 발생하는 예외를 처리하기 위한 커스텀 에러"""
    pass

# 4. Main Class/Functions
class SimpleDictConfig:
    """ConfigManager의 인터페이스 불일치(.get() 부재)를 해결하기 위한 단순 래퍼 클래스.
    
    [설계 의도] 복잡한 Mock 대신 Python의 덕 타이핑을 활용하여 S3Loader가 기대하는 
    get() 인터페이스만 단순하게 제공합니다.
    """
    def get(self, key: str, default: Any = None) -> Any:
        mapping: Dict[str, str] = {
            "aws.region": TEST_REGION,
            "aws.s3.bucket_name": TEST_BUCKET_NAME
        }
        return mapping.get(key, default)


def run_simple_pipeline() -> None:
    """파이프라인 적재 여부를 확인하는 메인 실행 함수입니다."""
    
    # 기본 로거 설정
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger("PipelineRunner")

    try:
        logger.info("1. 전역 시스템 초기화 (LogManager 에러 방지)")
        # 워닝이 발생하더라도 LogManager 내부 에러를 막기 위해 전역 메모리에 띄움
        ConfigManager.get_config(task_name="local_pipeline_test")

        logger.info("2. 더미 데이터(DTO) 및 심플 설정 객체 준비")
        dummy_data: Dict[str, Any] = {"ticker": "AAPL", "price": 170.50}
        dummy_dto = ExtractedDTO(
            data=dummy_data,
            meta={"provider": "test_api", "job_id": "us_stock"}
        )
        
        # 실제 ConfigManager 대신 get()을 가진 SimpleDictConfig를 우회 주입
        simple_config = SimpleDictConfig()

        logger.info("3. S3Loader 초기화 및 파이프라인(load) 실행")
        loader = S3Loader(config=simple_config) # type: ignore
        
        is_success = loader.load(dummy_dto)
        
        if is_success:
            logger.info("✅ 파이프라인 실행 완료: LocalStack S3에 데이터가 성공적으로 적재되었습니다.")
        else:
            logger.error("❌ 파이프라인 적재 실패 (False 반환)")

    except Exception as e:
        logger.error(f"❌ 파이프라인 실행 중 치명적 오류 발생: {e}", exc_info=True)
        raise PipelineExecutionError("파이프라인 단일 실행 실패") from e


if __name__ == "__main__":
    run_simple_pipeline()