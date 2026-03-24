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
    AbstractLoader의 템플릿 메서드(load) 흐름과 예외 래핑을 테스트하기 위한 최소 구현체.
    내부 상태 변수를 통해 _validate_dto와 _apply_load의 반환값 및 예외를 완벽히 통제합니다.
    """
    def __init__(self):
        # [근본 원인 해결] AbstractLoader는 인자를 받지 않으며 자체적으로 Config를 로드합니다.
        super().__init__()
        # 흐름 제어용 상태 변수
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
    """Service Class의 로거 격리 픽스처 (로그 출력 차단 및 테스트 환경 노이즈 제거)."""
    with patch("src.loader.providers.abstract_loader.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield mock_get_logger

@pytest.fixture
def mock_config_manager():
    """ConfigManager.load 정적 메서드 의존성을 격리하여 네트워크/디스크 I/O 차단."""
    with patch("src.loader.providers.abstract_loader.ConfigManager.load") as mock_load:
        mock_config = MagicMock()
        mock_load.return_value = mock_config
        yield mock_load

@pytest.fixture
def mock_loader(mock_config_manager):
    """의존성이 완벽히 격리된 상태의 ConcreteMockLoader 인스턴스 반환."""
    return ConcreteMockLoader()

@pytest.fixture
def mock_dto():
    """테스트에서 공통으로 사용할 빈 DTO 인스턴스 반환."""
    return MockExtractedDTO(data={"key": "value"})

# ========================================================================================
# 1. 초기화 및 자원 방어 테스트 (Initialization & Boundary)
# ========================================================================================

def test_init_01_config_load_error(mock_config_manager):
    """[INIT-01] [BVA] 설정 파일 로드 실패 시 파이프라인 초기화 조기 차단 검증"""
    # GIVEN: ConfigManager.load 호출 시 ConfigurationError가 발생하도록 모킹
    mock_config_manager.side_effect = ConfigurationError("loader.yml 파일을 찾을 수 없습니다.")
    
    # WHEN & THEN: 로더 인스턴스 생성 시 예외가 무시되지 않고 정상적으로 발생해야 함
    with pytest.raises(ConfigurationError, match="loader.yml 파일을 찾을 수 없습니다."):
        ConcreteMockLoader()

def test_init_02_normal_creation(mock_config_manager):
    """[INIT-02] [Standard] 정상적인 설정 환경에서 로더 객체 생성 및 속성 할당 검증"""
    # GIVEN: ConfigManager가 정상적인 mock 설정 객체를 반환하는 상태
    
    # WHEN: 로더 객체 인스턴스화
    loader = ConcreteMockLoader()
    
    # THEN: 부모 클래스의 __init__ 로직에 의해 config와 _logger가 올바르게 주입됨
    assert loader.config == mock_config_manager.return_value
    assert loader._logger is not None

# ========================================================================================
# 2. 정상 흐름 및 비즈니스 로직 (Functional Success)
# ========================================================================================

def test_load_01_success(mock_loader, mock_dto):
    """[LOAD-01] [Standard] 검증과 적재 로직이 모두 성공했을 때 True 반환 검증"""
    # GIVEN: 검증 훅과 적재 훅이 모두 정상적으로 True를 반환하도록 설정
    mock_loader.mock_validate_result = True
    mock_loader.mock_apply_result = True
    
    # WHEN: 템플릿 메서드 파이프라인(load) 실행
    result = mock_loader.load(mock_dto)
    
    # THEN: 에러 없이 최종 결과로 True 반환
    assert result is True

def test_load_02_fail_in_logic(mock_loader, mock_dto):
    """[LOAD-02] [Standard] 적재 비즈니스 로직상 실패(False) 시 예외 없이 False 반환 검증"""
    # GIVEN: 무결성 검증은 통과했으나, 물리적 적재(_apply_load)에서 논리적 실패(False) 발생
    mock_loader.mock_validate_result = True
    mock_loader.mock_apply_result = False
    
    # WHEN: 템플릿 메서드 파이프라인(load) 실행
    result = mock_loader.load(mock_dto)
    
    # THEN: 시스템 에러가 아니므로 False 반환 유지
    assert result is False

# ========================================================================================
# 3. 데이터 및 타입 무결성 방어 (Type Defense & Validation)
# ========================================================================================

def test_fail_v_01_validation_failure(mock_loader, mock_dto):
    """[FAIL-V-01] [MC/DC] DTO 사전 무결성 검증 실패 시 Fail-Fast 및 예외 발생 검증"""
    # GIVEN: DTO 검증 로직이 불합격(False) 판정을 내리도록 강제
    mock_loader.mock_validate_result = False
    
    # WHEN & THEN: 무의미한 I/O 진행을 차단하고 LoaderValidationError를 발생시켜야 함
    with pytest.raises(LoaderValidationError) as exc_info:
        mock_loader.load(mock_dto)
        
    assert "DTO 무결성 검증을 통과하지 못했습니다" in str(exc_info.value.message)

def test_fail_t_01_invalid_return_type(mock_loader, mock_dto):
    """[FAIL-T-01] [Type Defense] 하위 적재기가 bool이 아닌 값을 반환할 때의 런타임 방어 검증"""
    # GIVEN: 개발자 실수로 인해 적재 훅이 bool이 아닌 문자열을 반환하도록 오염됨
    mock_loader.mock_validate_result = True
    mock_loader.mock_apply_result = "Success"  # Type Violation
    
    # WHEN & THEN: 파이썬의 동적 타이핑 취약점을 방어하고 LoaderError 발생
    with pytest.raises(LoaderError) as exc_info:
        mock_loader.load(mock_dto)
        
    assert "반환 타입 오류" in exc_info.value.message
    assert "bool 타입이 아닙니다" in exc_info.value.message

# ========================================================================================
# 4. 결함 격리 및 예외 매핑 (Exception Mapping)
# ========================================================================================

def test_err_k_01_known_error_propagation(mock_loader, mock_dto):
    """[ERR-K-01] [Exception Mapping] 하위 계층에서 규격화한 도메인 에러(ETLError)의 통과 검증"""
    # GIVEN: 적재 로직 중 명시적인 도메인 에러(ETLError) 발생 시뮬레이션
    expected_error = ETLError("Already Handled Domain Error")
    mock_loader.mock_apply_exception = expected_error
    
    # WHEN & THEN: 중복 래핑 없이 원본 ETLError 구조를 보존하여 상위로 전파
    with pytest.raises(ETLError) as exc_info:
        mock_loader.load(mock_dto)
        
    assert exc_info.value is expected_error

def test_err_u_01_unknown_error_wrapping(mock_loader, mock_dto):
    """[ERR-U-01] [Exception Mapping] 예측 불가능한 네이티브 예외(Exception)의 도메인 에러 래핑 검증"""
    # GIVEN: 적재 로직 중 네트워크 단절과 같은 알 수 없는 네이티브 예외(ValueError) 발생
    raw_error = ValueError("Invalid Native Format Detected")
    mock_loader.mock_apply_exception = raw_error
    
    # WHEN & THEN: 파이프라인 공통 예외인 LoaderError로 안전하게 래핑
    with pytest.raises(LoaderError) as exc_info:
        mock_loader.load(mock_dto)
        
    wrapped_error = exc_info.value
    # 검증 1: 래핑된 공통 에러 메시지
    assert "예기치 않은 오류가 발생했습니다" in wrapped_error.message
    # 검증 2: 근본 원인(Root Cause) 추적을 위해 원본 예외가 보존되어야 함
    assert wrapped_error.original_exception is raw_error
    # 검증 3: 로깅 편의성을 위한 세부 데이터 보존
    assert wrapped_error.details["loader"] == "ConcreteMockLoader"
    assert "Invalid Native Format Detected" in wrapped_error.details["raw_error"]

# ========================================================================================
# 5. 추상 메서드 선언부 커버리지 (Abstract Methods Coverage)
# ========================================================================================

def test_abst_01_abstract_methods_pass():
    """[ABST-01] [Structural] AbstractLoader 내부 추상 메서드의 pass 블록 커버리지 확보"""
    # GIVEN: 추상 클래스 AbstractLoader 원본
    # WHEN: 클래스 레벨에서 추상 메서드를 강제 호출 (self 매개변수에 None 전달)
    # THEN: 구현부가 pass로 비어있으므로 아무런 예외(NotImplementedError 포함) 없이 종료되어야 함
    
    AbstractLoader._validate_dto(None, None)
    AbstractLoader._apply_load(None, None)