import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

# [Target Modules]
from src.transformer.processors.abstract_transformer import AbstractTransformer
from src.common.exceptions import TransformerError, ConfigurationError, ETLError
from src.common.config import ConfigManager

# ========================================================================================
# [Mocks & Stubs]
# ========================================================================================

class DummyTransformer(AbstractTransformer):
    """AbstractTransformer의 템플릿 메서드를 테스트하기 위한 구체 클래스 구현체"""
    
    def __init__(self, config: ConfigManager):
        super().__init__(config)
        self.mock_return_value = None
        self.mock_exception = None

    def _validate(self, data: pd.DataFrame) -> None:
        # 상위 추상 클래스의 추상 메서드 내부 구문(pass)을 실행시켜 커버리지 누락(123번 라인) 해결
        super()._validate(data)

    def _apply_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        # 상위 추상 클래스의 추상 메서드 내부 구문(pass)을 실행시켜 커버리지 누락(138번 라인) 해결
        super()._apply_transform(data)
        
        if self.mock_exception:
            raise self.mock_exception
        if self.mock_return_value is not None:
            return self.mock_return_value
        return data.copy()

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture
def mock_logger_isolation():
    """로거 격리 및 호출 검증을 위한 픽스처"""
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger

@pytest.fixture
def mock_config():
    """의존성 주입을 위한 ConfigManager Mock"""
    return MagicMock(spec=ConfigManager)

@pytest.fixture
def dummy_transformer(mock_config, mock_logger_isolation):
    """기본 설정이 주입된 DummyTransformer 인스턴스"""
    return DummyTransformer(config=mock_config)

@pytest.fixture
def sample_df():
    """기본 테스트용 DataFrame"""
    return pd.DataFrame({'col1': [1, 2, 3]})

# ========================================================================================
# 1. 초기화 (Initialization)
# ========================================================================================

def test_init_01_config_missing():
    """[INIT-01] [BVA] config 인자에 None 주입 시 ConfigurationError 발생"""
    # GIVEN: 필수 의존성인 ConfigManager가 누락된 상황 (None 주입)
    invalid_config = None
    
    # WHEN & THEN: AbstractTransformer(또는 하위 클래스) 초기화 시도 시 ConfigurationError 발생 검증
    with pytest.raises(ConfigurationError, match="ConfigManager 인스턴스가 필요합니다"):
        DummyTransformer(config=invalid_config)

# ========================================================================================
# 2. 정상 흐름 (Happy Path) & 3. 경계값 (BVA)
# ========================================================================================

def test_trans_01_happy_path(dummy_transformer, sample_df):
    """[TRANS-01] [Standard] 정상적인 DataFrame 주입 시 에러 없이 DataFrame 반환"""
    # GIVEN: 정상적인 데이터가 포함된 DataFrame (sample_df 픽스처)
    
    # WHEN: 템플릿 메서드인 transform() 실행
    result = dummy_transformer.transform(sample_df)
    
    # THEN: 반환값이 유효한 DataFrame이며, 기존 컬럼 구조가 유지되는지 검증
    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert list(result.columns) == ['col1']

def test_bva_01_empty_dataframe(dummy_transformer):
    """[BVA-01] [BVA] 빈 데이터프레임 주입 시 에러 없이 빈 데이터프레임 반환"""
    # GIVEN: 데이터가 비어있는(Empty) DataFrame
    empty_df = pd.DataFrame()
    
    # WHEN: 템플릿 메서드인 transform() 실행
    result = dummy_transformer.transform(empty_df)
    
    # THEN: 에러 발생 없이 빈 DataFrame이 그대로 반환되는지 검증
    assert isinstance(result, pd.DataFrame)
    assert result.empty

# ========================================================================================
# 4. 타입 무결성 (Type Integrity)
# ========================================================================================

def test_type_01_invalid_return_type(dummy_transformer, sample_df):
    """[TYPE-01] [Defense] _apply_transform이 DataFrame이 아닌 타입을 반환하면 예외 발생"""
    # GIVEN: 하위 변환 로직이 DataFrame이 아닌 타입(List)을 반환하도록 Mocking
    dummy_transformer.mock_return_value = [1, 2, 3]
    
    # WHEN: 변환 파이프라인 transform() 실행
    with pytest.raises(TransformerError) as exc_info:
        dummy_transformer.transform(sample_df)
        
    # THEN: 타입 불일치를 감지하고 TransformerError를 발생시키는지 검증
    assert "반환 타입 오류" in str(exc_info.value)
    assert "DataFrame이 아닙니다" in str(exc_info.value)

# ========================================================================================
# 5. 예외 처리 (Exception Handling)
# ========================================================================================

def test_err_01_known_etl_error_passthrough(dummy_transformer, sample_df):
    """[ERR-01] [Branch] 로직 내부에서 ETLError 발생 시 래핑 없이 그대로 상위 전파"""
    # GIVEN: 하위 변환 로직 수행 중 이미 규격화된 도메인 에러(ETLError) 발생 상황 Mocking
    dummy_transformer.mock_exception = ETLError("Known Domain Error")
    
    # WHEN: 변환 파이프라인 transform() 실행
    with pytest.raises(ETLError, match="Known Domain Error") as exc_info:
        dummy_transformer.transform(sample_df)
        
    # THEN: 예외가 TransformerError로 래핑되지 않고 원본(ETLError) 그대로 전파됨을 검증
    assert type(exc_info.value) is ETLError 

def test_err_02_unknown_error_wrapping(dummy_transformer, sample_df):
    """[ERR-02] [Branch] 네이티브 에러(KeyError) 발생 시 TransformerError로 래핑되어 전파"""
    # GIVEN: 하위 변환 로직 수행 중 예상치 못한 네이티브 에러(KeyError) 발생 상황 Mocking
    dummy_transformer.mock_exception = KeyError("missing_column")
    
    # WHEN: 변환 파이프라인 transform() 실행
    with pytest.raises(TransformerError) as exc_info:
        dummy_transformer.transform(sample_df)
        
    # THEN: 예외가 TransformerError로 래핑되며, original_exception에 원본 예외가 보존됨을 검증
    assert "예기치 않은 네이티브 오류 발생" in str(exc_info.value)
    assert isinstance(exc_info.value.original_exception, KeyError)

def test_log_01_error_logging(dummy_transformer, sample_df, mock_logger_isolation):
    """[LOG-01] [State] 예기치 않은 에러 발생 시 내부 catch 블록의 logger.error가 호출되는지 검증"""
    # GIVEN: 하위 변환 로직 수행 중 예상치 못한 에러(ValueError) 발생 상황 Mocking
    dummy_transformer.mock_exception = ValueError("Bad Value")
    expected_msg_fragment = "[DummyTransformer] 변환 로직 수행 중 예기치 않은 오류 발생 | Error: Bad Value"
    
    # WHEN: 변환 파이프라인 transform()을 실행하여 try-except의 Exception 블록 유도
    with pytest.raises(TransformerError):
        dummy_transformer.transform(sample_df)
        
    # THEN: 커스텀 로거의 error 메서드가 호출되었으며, 예상된 에러 메시지가 인자로 전달되었는지 검증
    assert mock_logger_isolation.error.called
    
    call_args_list = mock_logger_isolation.error.call_args_list
    found_expected_log = any(
        expected_msg_fragment in args[0][0] for args in call_args_list
    )
    assert found_expected_log, f"Expected log message containing '{expected_msg_fragment}' was not found."