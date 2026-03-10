import pytest
from unittest.mock import MagicMock, patch
from typing import Any

# [Target Modules]
from src.loader.providers.abstract_loader import AbstractLoader

# [Dependencies & Interfaces]
from src.common.dtos import ExtractedDTO
from src.common.exceptions import (
    ETLError, LoaderError, LoaderValidationError, ConfigurationError
)

# ========================================================================================
# [Mocks & Stubs]
# ========================================================================================

class MockExtractedDTO(ExtractedDTO):
    """테스트용 격리된 DTO 클래스"""
    def __init__(self, data: Any = None):
        self.data = data

class ConcreteMockLoader(AbstractLoader):
    """
    AbstractLoader의 템플릿 메서드(load)를 테스트하기 위한 최소 구현체.
    내부 속성을 통해 _validate_dto와 _apply_load의 반환값 및 예외 발생을 동적으로 제어합니다.
    """
    def __init__(self, config):
        super().__init__(config)
        # 제어용 상태 변수
        self.mock_validate_result = True
        self.mock_apply_result = True
        self.mock_apply_exception = None

    def _validate_dto(self, dto: ExtractedDTO) -> bool:
        return self.mock_validate_result

    def _apply_load(self, dto: ExtractedDTO) -> bool:
        if self.mock_apply_exception:
            raise self.mock_apply_exception
        return self.mock_apply_result

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_isolation():
    """Service Class의 로거 격리 픽스처 (로그 출력 차단)."""
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield mock_get_logger

@pytest.fixture
def mock_config():
    """ConfigManager 객체 모방"""
    config_obj = MagicMock()
    return config_obj

@pytest.fixture
def mock_loader(mock_config):
    """기본 설정이 주입된 ConcreteMockLoader 인스턴스"""
    return ConcreteMockLoader(config=mock_config)

@pytest.fixture
def mock_dto():
    """기본 DTO 인스턴스"""
    return MockExtractedDTO(data={"key": "value"})

# ========================================================================================
# 1. 초기화 및 자원 방어 테스트 (Initialization & Boundary)
# ========================================================================================

def test_init_01_config_none_defense():
    """[INIT-01] [BVA] ConfigManager 인스턴스 대신 None 주입 시 조기 차단 검증"""
    # Given: Config 객체가 None인 상태
    invalid_config = None
    
    # When & Then: 인스턴스 생성 시 ConfigurationError 발생 확인
    with pytest.raises(ConfigurationError, match="ConfigManager 인스턴스가 필요합니다"):
        ConcreteMockLoader(config=invalid_config)

def test_init_02_normal_creation(mock_config):
    """[INIT-02] [Standard] 정상적인 Config 주입 시 객체 생성 성공 검증"""
    # Given: 정상적인 ConfigManager 인스턴스 (Fixture 제공)
    
    # When: 객체 생성
    loader = ConcreteMockLoader(config=mock_config)
    
    # Then: 에러 없이 정상 생성되며, 내부 설정이 올바르게 할당되었는지 확인
    assert loader._config == mock_config
    assert loader._logger is not None

# ========================================================================================
# 2. 정상 흐름 및 비즈니스 로직 (Functional Success)
# ========================================================================================

def test_load_01_success(mock_loader, mock_dto):
    """[LOAD-01] [Standard] 검증과 적재 로직이 모두 성공했을 때 True 반환"""
    # Given: 검증과 적재가 모두 True를 반환하도록 상태 설정
    mock_loader.mock_validate_result = True
    mock_loader.mock_apply_result = True
    
    # When: 파이프라인 실행
    result = mock_loader.load(mock_dto)
    
    # Then: 최종 결과로 True를 반환해야 함
    assert result is True

def test_load_02_fail_in_logic(mock_loader, mock_dto):
    """[LOAD-02] [Standard] 검증은 통과했으나 적재 비즈니스 로직상 실패 시 False 반환"""
    # Given: 검증은 True이나, 적재 알고리즘에서 의도적으로 False 반환
    mock_loader.mock_validate_result = True
    mock_loader.mock_apply_result = False
    
    # When: 파이프라인 실행
    result = mock_loader.load(mock_dto)
    
    # Then: 런타임 에러가 아닌 정상 로직 실패이므로 False 반환
    assert result is False

# ========================================================================================
# 3. 데이터 및 타입 무결성 방어 (Type Defense & Validation)
# ========================================================================================

def test_fail_v_01_validation_failure(mock_loader, mock_dto):
    """[FAIL-V-01] [MC/DC] DTO 검증 실패 시 파이프라인 중단 및 예외 발생"""
    # Given: 검증 로직이 False를 반환하도록 강제 설정
    mock_loader.mock_validate_result = False
    
    # When & Then: LoaderValidationError 발생 검증
    with pytest.raises(LoaderValidationError) as exc_info:
        mock_loader.load(mock_dto)
        
    assert "DTO 무결성 검증을 통과하지 못했습니다" in str(exc_info.value.message)

def test_fail_t_01_invalid_return_type(mock_loader, mock_dto):
    """[FAIL-T-01] [Type Defense] 구체 클래스가 bool이 아닌 값을 반환할 경우의 동적 타입 방어"""
    # Given: 적재 알고리즘이 실수로 bool이 아닌 값(예: 문자열)을 반환하도록 오염
    mock_loader.mock_validate_result = True
    mock_loader.mock_apply_result = "Success"  # Type Violation
    
    # When & Then: 반환 타입 위반이 LoaderError로 차단되는지 검증
    with pytest.raises(LoaderError) as exc_info:
        mock_loader.load(mock_dto)
        
    assert "반환 타입 오류" in exc_info.value.message
    assert "bool 타입이 아닙니다" in exc_info.value.message

# ========================================================================================
# 4. 결함 격리 및 예외 매핑 (Exception Mapping)
# ========================================================================================

def test_err_k_01_known_error_propagation(mock_loader, mock_dto):
    """[ERR-K-01] [Exception Mapping] 이미 도메인 규격화된 ETLError는 중복 래핑 없이 통과"""
    # Given: 하위 클래스가 명시적인 파이프라인 에러(ETLError 하위 구현체 포함) 발생
    expected_error = ETLError("Already Handled Domain Error")
    mock_loader.mock_apply_exception = expected_error
    
    # When & Then: 예외가 다른 타입으로 변질되지 않고 그대로 상위 전파됨을 검증
    with pytest.raises(ETLError) as exc_info:
        mock_loader.load(mock_dto)
        
    assert exc_info.value is expected_error

def test_err_u_01_unknown_error_wrapping(mock_loader, mock_dto):
    """[ERR-U-01] [Exception Mapping] 예측 불가한 네이티브 예외 발생 시 도메인 규격(LoaderError)으로 래핑"""
    # Given: 네트워크 단절이나 OOM 등 예측 불가능한 네이티브 예외 발생
    raw_error = ValueError("Invalid Native Format Detected")
    mock_loader.mock_apply_exception = raw_error
    
    # When & Then: Exception -> LoaderError 구조화 래핑 검증
    with pytest.raises(LoaderError) as exc_info:
        mock_loader.load(mock_dto)
        
    wrapped_error = exc_info.value
    # 1. 래핑된 에러 메시지 확인
    assert "예기치 않은 오류 발생" in wrapped_error.message
    # 2. 원본 예외가 보존되었는지 (Root Cause Tracking 가능 여부) 확인
    assert wrapped_error.original_exception is raw_error
    # 3. 상세 정보에 로더 이름과 에러 내용이 담겼는지 확인
    assert wrapped_error.details["loader"] == "ConcreteMockLoader"
    assert "Invalid Native Format Detected" in wrapped_error.details["raw_error"]

# ========================================================================================
# 5. 추상 메서드 선언부 커버리지 (Abstract Methods Coverage)
# ========================================================================================

def test_abst_01_abstract_methods_pass(mock_loader, mock_dto):
    """[ABST-01] [Structural] 추상 메서드 내부의 pass 달성 검증"""
    # Given: 부모 추상 클래스(AbstractLoader)의 원본 참조
    # When & Then: 인스턴스를 통해 부모의 추상 메서드를 직접 호출하여 
    # NotImplementedError 등 예외 없이 정상적으로 pass 블록이 실행되는지 확인합니다.
    
    AbstractLoader._validate_dto(mock_loader, mock_dto)
    AbstractLoader._apply_load(mock_loader, mock_dto)
    
    # 별도의 assert가 없어도, 위 코드가 에러 없이 실행되면 Branch/Statement Coverage를 달성합니다.