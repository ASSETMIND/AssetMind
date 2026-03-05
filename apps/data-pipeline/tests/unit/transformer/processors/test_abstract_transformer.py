import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

# [Target Modules]
from src.transformer.processors.abstract_transformer import AbstractTransformer

# [Dependencies & Interfaces]
from src.common.exceptions import ConfigurationError, TransformerError, ETLError

# ========================================================================================
# [Mocks & Stubs]
# ========================================================================================

class StubTransformer(AbstractTransformer):
    """테스트용 구체 클래스 (Stub)
    
    추상 클래스의 흐름을 테스트하기 위해 동작을 세밀하게 제어(Spy/Mocking)할 수 있도록 구현했습니다.
    """
    def __init__(self, config):
        super().__init__(config)
        self.validate_call_count = 0
        self.apply_call_count = 0
        
        # 동작 제어를 위한 변수
        self.error_to_raise_in_validate = None
        self.error_to_raise_in_apply = None
        self.mock_return_value = None

    def _validate(self, data: pd.DataFrame) -> None:
        self.validate_call_count += 1
        if self.error_to_raise_in_validate:
            raise self.error_to_raise_in_validate

    def _apply_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        self.apply_call_count += 1
        if self.error_to_raise_in_apply:
            raise self.error_to_raise_in_apply
        
        if self.mock_return_value is not None:
            return self.mock_return_value
        return data  # 기본 동작: 원본 반환

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
    return MagicMock()

@pytest.fixture
def valid_df():
    """정상적인 구조의 DataFrame 반환"""
    return pd.DataFrame({"col1": [1, 2, 3], "col2": ["A", "B", "C"]})

@pytest.fixture
def empty_df():
    """로우(Row)가 없는 빈 DataFrame 반환"""
    return pd.DataFrame(columns=["col1", "col2"])

@pytest.fixture
def stub_transformer(mock_config):
    """기본 설정이 주입된 StubTransformer 인스턴스"""
    return StubTransformer(mock_config)

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_valid_config(mock_config):
    """[INIT-01] [Standard] 유효한 ConfigManager 모의 객체로 초기화 시 인스턴스 정상 생성"""
    # When
    transformer = StubTransformer(mock_config)
    
    # Then
    assert transformer.config == mock_config
    assert transformer.logger is not None

def test_init_02_missing_config():
    """[INIT-02] [BVA] config 객체가 None인 상태로 초기화 시 에러 방어"""
    # When & Then
    with pytest.raises(ConfigurationError, match="초기화 실패: ConfigManager 인스턴스가 필요합니다"):
        StubTransformer(None)

# ========================================================================================
# 2. 파이프라인 흐름 및 데이터 검증 테스트 (Flow & Data Verification)
# ========================================================================================

def test_flow_01_happy_path(stub_transformer, valid_df):
    """[FLOW-01] [State Transition] 모든 단계가 성공할 때 템플릿 메서드 호출 순서 검증"""
    # When
    result_df = stub_transformer.transform(valid_df)
    
    # Then
    assert stub_transformer.validate_call_count == 1
    assert stub_transformer.apply_call_count == 1
    assert isinstance(result_df, pd.DataFrame)
    assert result_df.equals(valid_df)

def test_data_01_empty_dataframe(stub_transformer, empty_df):
    """[DATA-01] [BVA] 로우가 없는 빈 DataFrame이 들어와도 에러 없이 통과"""
    # When
    result_df = stub_transformer.transform(empty_df)
    
    # Then
    assert result_df.empty
    assert stub_transformer.validate_call_count == 1

def test_data_02_invalid_return_type(stub_transformer, valid_df):
    """[DATA-02] [Robustness] _apply_transform이 DataFrame이 아닌 값 반환 시 에러 방어"""
    # Given: 반환값을 pd.Series로 강제 조작
    stub_transformer.mock_return_value = pd.Series([1, 2, 3])
    
    # When & Then
    with pytest.raises(TransformerError, match="반환 타입 오류: DataFrame이 아닙니다") as exc_info:
        stub_transformer.transform(valid_df)
        
    assert exc_info.value.should_retry is False

# ========================================================================================
# 3. 예외 처리 테스트 (Error Handling)
# ========================================================================================

def test_err_01_domain_error_passthrough(stub_transformer, valid_df):
    """[ERR-01] [Fault Injection] _validate 중 도메인 에러(ETLError) 발생 시 래핑 없이 통과"""
    # Given
    domain_error = ETLError("비즈니스 로직 위반")
    stub_transformer.error_to_raise_in_validate = domain_error
    
    # When & Then
    with pytest.raises(ETLError) as exc_info:
        stub_transformer.transform(valid_df)
        
    # 원본 에러가 그대로 던져졌는지 확인
    assert exc_info.value is domain_error

def test_err_02_unknown_error_wrapping(stub_transformer, valid_df):
    """[ERR-02] [Fault Injection] _apply_transform 중 알 수 없는 에러 발생 시 래핑하여 전파"""
    # Given
    raw_error = MemoryError("OOM 발생")
    stub_transformer.error_to_raise_in_apply = raw_error
    
    # When & Then
    with pytest.raises(TransformerError, match="예기치 않은 오류 발생") as exc_info:
        stub_transformer.transform(valid_df)
        
    # 에러 래핑 상태 검증
    transformer_err = exc_info.value
    assert transformer_err.should_retry is False
    assert transformer_err.original_exception is raw_error
    assert transformer_err.details["raw_error"] == "OOM 발생"

# ========================================================================================
# 4. 상태 및 멱등성 테스트 (State & Idempotency)
# ========================================================================================

def test_stat_01_idempotency_on_multiple_calls(stub_transformer, valid_df, empty_df):
    """[STAT-01] [State] 동일한 인스턴스를 여러 번 호출해도 독립적으로 성공하며 상태 비저장성 유지"""
    # When: 서로 다른 데이터로 연속 호출
    result_1 = stub_transformer.transform(valid_df)
    result_2 = stub_transformer.transform(empty_df)
    
    # Then
    assert stub_transformer.validate_call_count == 2
    assert stub_transformer.apply_call_count == 2
    
    assert isinstance(result_1, pd.DataFrame)
    assert not result_1.empty
    
    assert isinstance(result_2, pd.DataFrame)
    assert result_2.empty

# ========================================================================================
# 5. 기반 메서드 테스트 (Base Method Specification)
# ========================================================================================

def test_base_01_abstract_methods_execution(stub_transformer, valid_df):
    """[BASE-01] [Standard] 추상 클래스에 정의된 기본 메서드(pass)가 예외 없이 호출되는지 검증"""
    # When
    AbstractTransformer._validate(stub_transformer, valid_df)
    result = AbstractTransformer._apply_transform(stub_transformer, valid_df)
    
    # Then
    assert result is None