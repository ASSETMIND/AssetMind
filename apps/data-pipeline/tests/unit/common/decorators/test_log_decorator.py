import pytest
import asyncio
from unittest.mock import MagicMock, patch

# [Target Module]
import src.common.decorators.log_decorator as decorator_module
from src.common.decorators.log_decorator import log_decorator, LoggingDecorator
from src.common.exceptions import ETLError

# ========================================================================================
# [Fixtures & Mocks]
# ========================================================================================

@pytest.fixture
def mock_logger():
    """LogManager를 패치하여 logger의 행위를 가로채는 픽스처"""
    with patch("src.common.decorators.log_decorator.LogManager.get_logger") as mock_get_logger:
        logger_instance = MagicMock()
        mock_get_logger.return_value = logger_instance
        yield logger_instance

@pytest.fixture
def mock_context():
    """Request ID 컨텍스트를 제어하는 픽스처"""
    with patch("src.common.decorators.log_decorator.request_id_ctx") as mock_ctx, \
         patch("src.common.decorators.log_decorator.LogManager.set_context") as mock_set_ctx:
        # 기본 상태 셋팅
        mock_ctx.get.return_value = "system"
        yield mock_ctx, mock_set_ctx

# ========================================================================================
# 1. 기능적 성공 (Functional Success)
# ========================================================================================

def test_sync_01_success(mock_logger, mock_context):
    # Given: 데코레이터가 적용된 일반 동기 함수
    @log_decorator(logger_name="test_sync")
    def sync_func(a, b):
        return a + b

    # When: 함수를 호출하면
    result = sync_func(1, 2)
    
    # Then: 정상 반환되며 START/END 로그가 정확하게 기록됨
    assert result == 3
    mock_logger.info.assert_any_call(
        f'[{sync_func.__qualname__}] START | Params: {{"arg_0": "1", "arg_1": "2"}}'
    )
    end_log = mock_logger.info.call_args_list[-1][0][0]
    assert "END | Time:" in end_log
    assert "Result: 3" in end_log

@pytest.mark.asyncio
async def test_async_01_success(mock_logger, mock_context):
    # Given: 데코레이터가 적용된 비동기 함수
    @log_decorator(logger_name="test_async")
    async def async_func(val):
        await asyncio.sleep(0.01)
        return val

    # When: 코루틴을 await로 호출하면
    result = await async_func("async_test")
    
    # Then: 정상 반환되며 START/END 로그가 정확하게 기록됨
    assert result == "async_test"
    mock_logger.info.assert_any_call(
        f'[{async_func.__qualname__}] START | Params: {{"arg_0": "async_test"}}'
    )
    end_log = mock_logger.info.call_args_list[-1][0][0]
    assert "END | Time:" in end_log
    assert "Result: async_test" in end_log

# ========================================================================================
# 2. 보안 및 견고성 (Security & Robustness)
# ========================================================================================

def test_sec_01_pii_masking(mock_logger, mock_context):
    # Given: 민감 정보 키워드를 포함하는 인자를 받는 함수
    @log_decorator()
    def auth_func(user, password, access_key):
        return True

    # When: 평문 비밀번호 및 토큰을 포함하여 함수 호출 시
    auth_func("user1", password="secret_password", access_key="jwt_token")
    start_log = mock_logger.info.call_args_list[0][0][0]
    
    # Then: 민감 정보는 마스킹 처리되어 로그에 평문이 노출되지 않음
    assert "secret_password" not in start_log
    assert "jwt_token" not in start_log
    assert "***** (MASKED)" in start_log

def test_sec_02_normal_kwargs_serialization(mock_logger, mock_context):
    """ _sanitize_args의 일반 키워드(else 분기) 커버리지 달성용 테스트 """
    # Given: 민감하지 않은 일반 키워드 인자를 받는 함수
    @log_decorator()
    def safe_kwargs_func(a, role="user"):
        return True

    # When: 일반 키워드 인자를 명시하여 함수 호출 시
    safe_kwargs_func("user1", role="admin")
    start_log = mock_logger.info.call_args_list[0][0][0]
    
    # Then: 일반 키워드 값은 마스킹되지 않고 그대로 직렬화되어 로깅됨
    assert "admin" in start_log
    assert "MASKED" not in start_log

def test_robust_01_serialization_failure(mock_logger, mock_context):
    # Given: __str__ 호출 시 예외를 발생시키는 손상된 객체
    class BadObj:
        def __str__(self):
            raise RuntimeError("Toxic Object")

    @log_decorator()
    def unsafe_func(obj):
        return "Survived"

    # When: 이 객체를 인자로 넘겨 함수를 호출하면
    result = unsafe_func(BadObj())
    
    # Then: 앱이 멈추지 않고 비즈니스 로직 정상 수행 및 직렬화 실패 경고 기록됨
    assert result == "Survived"
    mock_logger.warning.assert_called_with(
        f"[{unsafe_func.__qualname__}] START | Params: (Serialization Failed)"
    )

# ========================================================================================
# 3. 경계값 및 데이터 검증 (Boundary & Data)
# ========================================================================================

def test_bva_01_truncate_limit_return(mock_logger, mock_context):
    # Given: 한계치를 초과하는 긴 문자열을 반환하는 함수
    limit = 100
    @log_decorator(truncate_limit=limit)
    def big_return_func():
        return "A" * 500

    # When: 함수 호출 후
    big_return_func()
    end_log = mock_logger.info.call_args_list[-1][0][0]
    
    # Then: 결과 로그가 한계치까지만 잘리고 truncated 표시가 포함됨
    assert "Result: " + ("A" * limit) + "... (truncated" in end_log

def test_bva_02_container_limit_exceeded(mock_logger, mock_context):
    # Given: 제한 길이를 초과하는 리스트 데이터
    @log_decorator()
    def list_func(data):
        pass

    long_list = list(range(100)) 
    
    # When: 해당 리스트를 인자로 함수 호출 시
    list_func(long_list)

    start_log = mock_logger.info.call_args_list[0][0][0]
    
    # Then: 길이(len)가 기록되고 내용 일부는 생략(...)됨
    assert "[list len=100]" in start_log
    assert "..." in start_log

def test_bva_03_container_limit_safe(mock_logger, mock_context):
    # Given: 제한 길이 이내의 짧은 리스트 데이터
    @log_decorator()
    def list_func(data):
        pass

    short_list = [1, 2, 3]
    
    # When: 함수 호출 시
    list_func(short_list)

    start_log = mock_logger.info.call_args_list[0][0][0]
    
    # Then: 생략 없이 온전히 기록됨
    assert "[list len=3]" in start_log
    assert "..." not in start_log 

def test_bva_04_string_limit_exceeded(mock_logger, mock_context):
    # Given: 100자를 초과하는 스칼라 문자열 
    @log_decorator()
    def str_func(text):
        pass

    long_str = "B" * 150
    
    # When: 해당 문자열로 함수 호출 시
    str_func(long_str)

    start_log = mock_logger.info.call_args_list[0][0][0]
    
    # Then: 문자열 일부가 잘리고 잘림 표시가 남음
    assert "(truncated, total=150)" in start_log

def test_bva_05_dataframe_duck_typing(mock_logger, mock_context):
    # Given: DataFrame을 흉내 낸 Duck Typing용 클래스
    class DataFrame:
        def __init__(self, shape):
            self.shape = shape
    
    df_instance = DataFrame(shape=(100, 5))

    mock_pd = MagicMock()
    mock_pd.DataFrame = DataFrame
    
    with patch.object(decorator_module, 'pd', mock_pd, create=True):
        @log_decorator()
        def process_df(data):
            return data

        # When: 해당 객체를 인자로 받고 그대로 반환할 때
        process_df(df_instance)

    start_log = mock_logger.info.call_args_list[0][0][0]
    end_log = mock_logger.info.call_args_list[1][0][0]
    
    # Then: 직렬화 대신 형태(shape)만 로그에 요약됨
    assert "DataFrame" in start_log
    assert "(100, 5)" in start_log
    assert "DataFrame" in end_log
    assert "(100, 5)" in end_log

# ========================================================================================
# 4. 예외 및 정책 제어 (Exception Control) - Sync & Async
# ========================================================================================

def test_err_01_sync_unknown_wrapping(mock_logger, mock_context):
    # Given: 일반 ValueError를 발생시키는 동기 함수
    @log_decorator()
    def crash_func():
        raise ValueError("DB Err")

    # When & Then: 호출 시 ETLError로 래핑되어 전파되고 에러 로깅됨
    with pytest.raises(ETLError) as exc_info:
        crash_func()
    
    assert exc_info.value.original_exception.__class__ == ValueError
    mock_logger.error.assert_called_once()
    assert "FAILED | Time:" in mock_logger.error.call_args[0][0]

def test_err_02_sync_known_error_handling(mock_logger, mock_context):
    # Given: 이미 정의된 도메인 예외(ETLError) 발생
    original_err = ETLError(message="Extract Fail", should_retry=True)

    @log_decorator()
    def fail_func():
        raise original_err

    # When & Then: 중복 래핑 없이 원본 예외가 그대로 전파됨
    with pytest.raises(ETLError) as exc_info:
        fail_func()

    assert exc_info.value is original_err 
    mock_logger.error.assert_called_once()
    assert "FAILED | Time:" in mock_logger.error.call_args[0][0]
    assert "Retry: True" in mock_logger.error.call_args[0][0]

def test_err_03_sync_suppress_error(mock_logger, mock_context):
    # Given: 에러 억제 옵션이 켜진 상태에서 예외 발생
    @log_decorator(suppress_error=True)
    def suppress_func():
        raise RuntimeError("Fatal")

    # When: 함수 호출 시
    result = suppress_func()
    
    # Then: 예외는 밖으로 전파되지 않고 None을 반환하며 로깅됨
    assert result is None
    mock_logger.error.assert_called_once()

@pytest.mark.asyncio
async def test_err_04_async_unknown_wrapping(mock_logger, mock_context):
    # Given: 일반 ValueError를 발생시키는 비동기 코루틴
    @log_decorator()
    async def crash_func_async():
        raise ValueError("Async DB Err")

    # When & Then: 비동기 호출 시에도 ETLError로 래핑되어 전파됨
    with pytest.raises(ETLError) as exc_info:
        await crash_func_async()
    
    assert exc_info.value.original_exception.__class__ == ValueError
    mock_logger.error.assert_called_once()

@pytest.mark.asyncio
async def test_err_05_async_known_error_handling(mock_logger, mock_context):
    # Given: 이미 정의된 도메인 예외(ETLError) 발생 (비동기)
    original_err = ETLError(message="Async Fail", should_retry=False)

    @log_decorator()
    async def fail_func_async():
        raise original_err

    # When & Then: 비동기 호출 시에도 중복 래핑 없이 원본 예외 전파
    with pytest.raises(ETLError) as exc_info:
        await fail_func_async()

    assert exc_info.value is original_err
    mock_logger.error.assert_called_once()
    assert "Retry: False" in mock_logger.error.call_args[0][0]

@pytest.mark.asyncio
async def test_err_06_async_suppress_error(mock_logger, mock_context):
    # Given: 에러 억제 옵션이 켜진 비동기 코루틴
    @log_decorator(suppress_error=True)
    async def suppress_func_async():
        raise RuntimeError("Async Fatal")

    # When: 코루틴 호출 시
    result = await suppress_func_async()
    
    # Then: 예외 억제 후 None 반환
    assert result is None
    mock_logger.error.assert_called_once()

# ========================================================================================
# 5. 상태 제어 (Context State)
# ========================================================================================

def test_ctx_01_inject_new_context(mock_logger, mock_context):
    # Given: 현재 컨텍스트(Request ID)가 초기값(system)일 때
    mock_ctx, mock_set_ctx = mock_context
    mock_ctx.get.return_value = "system"

    @log_decorator()
    def dummy():
        pass

    # When: 데코레이팅된 함수 호출
    dummy()
    
    # Then: 신규 컨텍스트를 주입하는 set_context가 호출됨
    mock_set_ctx.assert_called_once()

def test_ctx_02_keep_existing_context(mock_logger, mock_context):
    # Given: 현재 컨텍스트에 상위 호출자의 Request ID가 이미 셋팅되어 있을 때
    mock_ctx, mock_set_ctx = mock_context
    mock_ctx.get.return_value = "req-uuid-1234"

    @log_decorator()
    def dummy():
        pass

    # When: 함수 호출
    dummy()
    
    # Then: 멱등성 보장 (기존 ID를 보존하며 신규 주입 함수는 호출되지 않음)
    mock_set_ctx.assert_not_called()

# ========================================================================================
# 6. 추가 엣지 케이스 보완 (Branch Coverage 100% 달성용)
# ========================================================================================

def test_edge_01_log_entry_exception_coverage(mock_logger, mock_context):
    """ _log_entry 내부의 악성 직렬화 오류 처리 분기 완벽 검증 """
    # Given: kwargs 뿐만 아니라 args 에도 악성 객체 포함
    class BadObj:
        def __str__(self):
            raise Exception("Toxic")
            
    @log_decorator()
    def edge_func(*args, **kwargs):
        return True
        
    # When: args 에 악성 객체 주입
    edge_func(BadObj())
    
    # Then: 비즈니스 로직은 보호되어 True 를 반환하고, Warning 로깅됨
    mock_logger.warning.assert_called_with(
        f"[{edge_func.__qualname__}] START | Params: (Serialization Failed)"
    )

def test_edge_02_log_error_regular_exception_coverage(mock_logger, mock_context):
    """ _log_error 내부의 일반 Exception 분기(else 분기) 완벽 검증 """
    # Given: LoggingDecorator 인스턴스를 직접 생성하고 일반적인 예외 객체 준비
    decorator = LoggingDecorator()
    mock_error = ValueError("Standard Error Test")
    
    # When: 파이프라인 래퍼를 거치지 않고 직접 _log_error 에 일반 예외 주입
    decorator._log_error(mock_logger, "edge_func", mock_error, 0.1234)
    
    # Then: ETLError 처리가 아닌, 일반 예외 포맷(else 분기)으로 로그가 남음
    mock_logger.error.assert_called_once()
    error_msg = mock_logger.error.call_args[0][0]
    
    assert "FAILED | Time: 0.1234s" in error_msg
    assert "Error: ValueError - Standard Error Test" in error_msg