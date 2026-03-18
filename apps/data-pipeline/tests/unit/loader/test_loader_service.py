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
def mock_config():
    """ConfigManager 격리 객체"""
    config = MagicMock()
    # 기본적으로 "s3" 타겟을 반환하도록 설정
    config.get.return_value = "s3"
    return config

@pytest.fixture
def loader_service(mock_config):
    """기본 설정이 주입된 LoaderService 인스턴스"""
    return LoaderService(mock_config)

@pytest.fixture
def mock_s3_module():
    """동적 임포트(Lazy Loading)되는 S3Loader 모듈을 격리하기 위한 픽스처"""
    mock_s3_instance = MagicMock()
    mock_s3_instance.load.return_value = True
    
    mock_s3_cls = MagicMock(return_value=mock_s3_instance)
    
    # 가상의 모듈 객체 생성
    mock_module = MagicMock()
    mock_module.S3Loader = mock_s3_cls
    
    # sys.modules를 패치하여 실제 파일이 없어도 Import가 성공하도록 조작
    with patch.dict("sys.modules", {"src.loader.providers.s3_loader": mock_module}):
        yield mock_s3_cls

@pytest.fixture
def valid_dto():
    """타입 검증을 통과하기 위한 ExtractedDTO Mock 객체"""
    dto = MagicMock(spec=ExtractedDTO)
    dto.meta = {"job_id": "TEST_001"}
    return dto

# ========================================================================================
# 1. 객체 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_successful_initialization(mock_config):
    """[INIT-01] [Standard] 정상적인 Config 객체 주입 시 성공적으로 초기화됨"""
    # Given: 유효한 config 객체 (Fixture)
    
    # When: 서비스 인스턴스 생성
    service = LoaderService(mock_config)
    
    # Then: 캐시 공간이 정상적으로 빈 딕셔너리로 준비됨
    assert isinstance(service._loader_cache, dict)
    assert len(service._loader_cache) == 0

def test_init_e_01_missing_config_defense():
    """[INIT-E-01] [BVA] ConfigManager가 None일 경우 ConfigurationError 발생 (조기 차단)"""
    # Given: None 값의 config
    invalid_config = None
    
    # When & Then: 인스턴스화 시도 시 에러 발생
    with pytest.raises(ConfigurationError, match="ConfigManager가 누락되었습니다"):
        LoaderService(invalid_config)

# ========================================================================================
# 2. 데이터 무결성 테스트 (Validation)
# ========================================================================================

def test_dto_e_01_invalid_dto_type(loader_service):
    """[DTO-E-01] [Type] 잘못된 DTO 타입 전달 시 LoaderError 발생 및 조기 종료"""
    # Given: DTO가 아닌 일반 딕셔너리
    invalid_payload = {"data": "dummy"}
    
    # When & Then: execute_load 호출 시 방어 로직 작동
    with pytest.raises(LoaderError) as exc_info:
        loader_service.execute_load(invalid_payload)
        
    assert "잘못된 DTO 타입 전달" in exc_info.value.message
    assert exc_info.value.should_retry is False

# ========================================================================================
# 3. 지연 초기화 및 캐싱 성능 테스트 (Lazy Loading & Caching)
# ========================================================================================

def test_load_01_cold_start_lazy_loading(loader_service, mock_s3_module, valid_dto):
    """[LOAD-01] [State] 최초 호출 시 동적 임포트를 통해 객체를 생성하고 캐시에 등록함 (Cold-Start)"""
    # Given: 캐시가 비어있는 상태
    assert "s3" not in loader_service._loader_cache
    
    # When: execute_load 최초 호출
    result = loader_service.execute_load(valid_dto)
    
    # Then: 
    # 1. S3Loader 클래스가 1회 초기화됨
    mock_s3_module.assert_called_once_with(config=loader_service._config)
    # 2. 캐시에 인스턴스가 저장됨
    assert "s3" in loader_service._loader_cache
    # 3. load 메서드가 정상 반환됨
    assert result is True

def test_load_02_fast_path_caching(loader_service, mock_s3_module, valid_dto):
    """[LOAD-02] [State] 두 번째 호출부터는 객체 생성 없이 캐시된 인스턴스를 재사용함 (Fast-Path)"""
    # Given: 최초 호출을 통해 캐시에 로더를 등록시킴
    loader_service.execute_load(valid_dto)
    mock_s3_module.reset_mock() # 호출 횟수 초기화
    
    # When: 두 번째로 연속 호출 (수만 건의 데이터가 들어오는 상황 가정)
    result = loader_service.execute_load(valid_dto)
    
    # Then:
    # 1. S3Loader 클래스의 인스턴스화(생성자 호출)가 발생하지 않아야 함!
    mock_s3_module.assert_not_called()
    # 2. 캐시 히트로 인해 바로 결과가 반환됨
    assert result is True

# ========================================================================================
# 4. 설정값 검증 및 폴백 테스트 (Fallback & Configuration)
# ========================================================================================

def test_conf_01_default_fallback(loader_service, mock_config, mock_s3_module, valid_dto):
    """[CONF-01] [BVA] 설정값 누락 시 기본값(s3)으로 Fallback 처리되어 정상 동작함"""
    # Given: config.get() 호출 시 키워드 인자로 전달된 기본값을 반환하도록 Mocking
    mock_config.get.side_effect = lambda key, default: default
    
    # When: 적재 실행
    loader_service.execute_load(valid_dto)
    
    # Then: 기본 타겟인 "s3"가 캐시에 저장되고 사용됨
    assert "s3" in loader_service._loader_cache

def test_conf_e_01_unsupported_target(loader_service, mock_config, valid_dto):
    """[CONF-E-01] [MC/DC] 지원하지 않는 타겟 명시 시 ConfigurationError 발생"""
    # Given: 타겟이 "mysql"로 설정됨
    mock_config.get.return_value = "mysql"
    
    # When & Then
    with pytest.raises(ConfigurationError, match="지원하지 않는 로더 타겟입니다"):
        loader_service.execute_load(valid_dto)

# ========================================================================================
# 5. 예외 격리 및 래핑 테스트 (Exception Handling)
# ========================================================================================

def test_err_01_lazy_init_exception_wrapping(loader_service, mock_s3_module, valid_dto):
    """[ERR-01] [Exception Wrapping] 지연 로딩 중 발생하는 예상치 못한 에러를 LoaderError로 래핑함"""
    # Given: S3Loader 초기화 시점에 ImportError 발생을 강제함
    mock_s3_module.side_effect = ImportError("No module named 'boto3'")
    
    # When & Then: Raw Exception(ImportError)이 상위로 유출되지 않고 LoaderError로 래핑되어야 함
    with pytest.raises(LoaderError) as exc_info:
        loader_service.execute_load(valid_dto)
        
    assert "로더 지연 초기화 중 치명적 오류 발생" in exc_info.value.message
    assert "boto3" in str(exc_info.value.details["error"])
    assert exc_info.value.should_retry is False
    assert isinstance(exc_info.value.original_exception, ImportError)

def test_exec_01_full_successful_execution(loader_service, mock_s3_module, valid_dto):
    """[EXEC-01] [Standard] 정상 워크플로우를 타며 내부 로더의 반환값을 올바르게 리턴함"""
    # Given: 내부 로더 객체의 load() 메서드가 True를 반환하도록 Mocking 완료 (Fixture 내부)
    
    # When: 실행
    result = loader_service.execute_load(valid_dto)
    
    # Then:
    assert result is True
    # 내부 로더의 load() 메서드에 DTO가 올바르게 전달되었는지 확인
    cached_instance = loader_service._loader_cache["s3"]
    cached_instance.load.assert_called_once_with(valid_dto)