import pytest
from unittest.mock import MagicMock, patch
import sys

# [Target Modules]
from src.loader.loader_service import LoaderService

# [Dependencies & Interfaces]
from src.common.exceptions import ConfigurationError, LoaderError
from src.common.dtos import ExtractedDTO

# ========================================================================================
# [Fixtures & Mocks]
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_isolation():
    """Service Class의 로거 격리 픽스처 (로그 출력 차단)."""
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield mock_get_logger

@pytest.fixture
def mock_config_manager():
    """ConfigManager 싱글톤 로드를 격리하고 Policy 반환값을 제어하는 픽스처"""
    with patch("src.loader.loader_service.ConfigManager") as mock_cm_cls:
        mock_config_instance = MagicMock()
        mock_policy = MagicMock()
        
        # S3Loader 초기화에 필요한 설정값 Mocking
        mock_policy.s3 = {"bucket_name": "test-s3-bucket"}
        mock_policy.region = "ap-northeast-2"
        mock_config_instance.get_loader.return_value = mock_policy
        
        mock_cm_cls.load.return_value = mock_config_instance
        yield mock_config_instance

@pytest.fixture
def mock_s3_loader_cls():
    """동적 임포트(Lazy Loading)되는 S3Loader 모듈을 격리하기 위한 픽스처"""
    mock_s3_instance = MagicMock()
    mock_s3_instance.load.return_value = True
    
    mock_s3_cls = MagicMock(return_value=mock_s3_instance)
    
    # 가상의 S3 모듈 환경 구성 (sys.modules 패치)
    mock_module = MagicMock()
    mock_module.S3Loader = mock_s3_cls
    
    with patch.dict("sys.modules", {"src.loader.providers.s3_loader": mock_module}):
        yield mock_s3_cls

@pytest.fixture
def valid_dto():
    """타입 검증을 통과하기 위한 ExtractedDTO Mock 객체"""
    dto = MagicMock(spec=ExtractedDTO)
    dto.meta = {"job_id": "TEST_001"}
    return dto

# ========================================================================================
# 1. 데이터 무결성 검증 (Validation)
# ========================================================================================

def test_dto_e_01_invalid_dto_type(mock_config_manager):
    """[DTO-E-01] [Type] 잘못된 DTO 타입 전달 시 LoaderError 발생 및 조기 차단"""
    # GIVEN: 유효한 타겟(aws)으로 서비스 생성, 입력값은 잘못된 Dict 타입
    service = LoaderService(target_loader="aws")
    invalid_payload = {"data": "dummy"}
    
    # WHEN & THEN: execute_load 호출 시 타입 검증에 실패하여 LoaderError 발생
    with pytest.raises(LoaderError) as exc_info:
        service.execute_load(invalid_payload)
        
    assert "잘못된 DTO 타입 전달" in exc_info.value.message

# ========================================================================================
# 2. 지연 초기화 및 캐싱 (Lazy Loading & Caching)
# ========================================================================================

def test_load_01_aws_cold_start(mock_config_manager, mock_s3_loader_cls, valid_dto):
    """[LOAD-01] [State] 최초 호출 시 동적 임포트를 통해 S3Loader를 생성하고 캐싱함"""
    # GIVEN: 캐시가 비어있는 초기 상태의 서비스
    service = LoaderService(target_loader="aws")
    assert "aws" not in service._loader_cache
    
    # WHEN: 최초 적재 위임 수행
    result = service.execute_load(valid_dto)
    
    # THEN: 
    # 1. S3Loader가 올바른 설정값으로 1회 초기화됨
    mock_s3_loader_cls.assert_called_once_with(
        bucket_name="test-s3-bucket", 
        region="ap-northeast-2"
    )
    # 2. 인스턴스가 캐시에 정상 등록됨
    assert "aws" in service._loader_cache
    assert result is True

def test_load_02_aws_fast_path(mock_config_manager, mock_s3_loader_cls, valid_dto):
    """[LOAD-02] [State] 두 번째 호출부터는 객체 생성 없이 캐시된 인스턴스를 재사용함"""
    # GIVEN: 1회 실행을 통해 캐시에 로더를 활성화시킨 상태
    service = LoaderService(target_loader="aws")
    service.execute_load(valid_dto)
    mock_s3_loader_cls.reset_mock() # 첫 번째 호출 카운트 초기화
    
    # WHEN: 연달아 두 번째로 적재 호출 수행
    result = service.execute_load(valid_dto)
    
    # THEN:
    # 생성자가 다시 호출되지 않아야 함 (Fast-Path 캐시 히트)
    mock_s3_loader_cls.assert_not_called()
    assert result is True

# ========================================================================================
# 3. 설정 및 타겟 검증 (Configuration & Exception Bypass)
# ========================================================================================

def test_conf_e_01_unsupported_target(mock_config_manager, valid_dto):
    """[CONF-E-01] [BVA] 미지원 타겟 명시 시 예외 래핑을 우회(Bypass)하여 ConfigurationError 발생"""
    # GIVEN: 지원하지 않는 플랫폼('gcp')으로 초기화
    service = LoaderService(target_loader="gcp")
    
    # WHEN & THEN: LoaderError로 감싸지지 않고 순수 ConfigurationError가 상위로 전파됨
    with pytest.raises(ConfigurationError, match="지원하지 않는 로더 타겟입니다"):
        service.execute_load(valid_dto)

# ========================================================================================
# 4. 예외 격리 및 래핑 (Exception Handling)
# ========================================================================================

def test_err_01_unexpected_error_wrapping(mock_config_manager, valid_dto):
    """[ERR-01] [Exception] 지연 초기화 중 발생하는 알 수 없는 에러를 LoaderError로 강제 래핑"""
    # GIVEN: 설정 로드 중 예측 불가능한 시스템 에러(KeyError) 발생 가정
    service = LoaderService(target_loader="aws")
    mock_config_manager.get_loader.side_effect = KeyError("Invalid Config Key")
    
    # WHEN & THEN: 발생한 에러가 LoaderError로 래핑되어 추적성이 확보되어야 함
    with pytest.raises(LoaderError) as exc_info:
        service.execute_load(valid_dto)
        
    assert "로더 지연 초기화 중 오류 발생" in exc_info.value.message
    assert isinstance(exc_info.value.original_exception, KeyError)
    assert exc_info.value.should_retry is False

# ========================================================================================
# 5. 정상 실행 (Execution)
# ========================================================================================

def test_exec_01_delegation_success(mock_config_manager, mock_s3_loader_cls, valid_dto):
    """[EXEC-01] [Standard] 타겟 로더의 반환값을 올바르게 리턴하며 성공적으로 위임함"""
    # GIVEN: 내부 S3Loader의 load() 메서드가 True를 반환하도록 준비됨 (Fixture)
    service = LoaderService(target_loader="aws")
    
    # WHEN: 실행
    result = service.execute_load(valid_dto)
    
    # THEN: 최종 반환값이 True이며 하위 객체의 load가 정확히 1회 호출됨
    assert result is True
    cached_instance = service._loader_cache["aws"]
    cached_instance.load.assert_called_once_with(valid_dto)