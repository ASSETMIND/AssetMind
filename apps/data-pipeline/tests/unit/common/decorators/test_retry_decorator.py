import pytest
import asyncio
import sys
import time
import importlib
import builtins
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY, AsyncMock

# --------------------------------------------------------------------------
# Environment Setup (Path Injection)
# --------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

# --------------------------------------------------------------------------
# Import Real Objects & Target Class
# --------------------------------------------------------------------------
try:
    from src.common.decorators.retry_decorator import RetryDecorator
except ImportError:
    from src.common.decorators.retry_decorator import RetryDecorator

# --------------------------------------------------------------------------
# 0. Constants & Configuration
# --------------------------------------------------------------------------
TARGET_MODULE = "src.common.decorators.retry_decorator"
TARGET_LOG_MANAGER = f"{TARGET_MODULE}.LogManager"
TARGET_TIME_SLEEP = "time.sleep"
TARGET_ASYNC_SLEEP = "asyncio.sleep"

# --------------------------------------------------------------------------
# 1. Fixtures (Test Environment Setup)
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_dependencies():
    """
    [Dependencies Mock]
    LogManager, time.sleep, asyncio.sleep을 Mocking하여
    외부 의존성 및 시간 지연을 격리합니다.
    """
    with patch(TARGET_LOG_MANAGER) as MockLogManager, \
         patch(TARGET_TIME_SLEEP) as MockTimeSleep, \
         patch(TARGET_ASYNC_SLEEP, new_callable=AsyncMock) as MockAsyncSleep:
        
        # 1. Logger Mock 설정
        mock_logger_instance = MagicMock()
        MockLogManager.get_logger.return_value = mock_logger_instance
        
        yield {
            "LogManager": MockLogManager,
            "Logger": mock_logger_instance,
            "TimeSleep": MockTimeSleep,
            "AsyncSleep": MockAsyncSleep
        }

# --------------------------------------------------------------------------
# 2. Test Cases
# --------------------------------------------------------------------------

class TestRetryDecorator:

    # ==========================================
    # Category: Happy Path (Normal Execution)
    # ==========================================

    def test_tc001_sync_happy_path(self, mock_dependencies):
        """[TC-001] Sync 함수: 첫 시도 성공 시 재시도 없이 결과 반환"""
        deps = mock_dependencies
        mock_func = MagicMock(return_value="Success")
        mock_func.__qualname__ = "TestFunc_Sync"
        
        @RetryDecorator(max_retries=3)
        def wrapped(*args): return mock_func(*args)

        result = wrapped(10, 20)

        assert result == "Success"
        deps["Logger"].warning.assert_not_called()
        deps["TimeSleep"].assert_not_called()

    @pytest.mark.asyncio
    async def test_tc002_async_happy_path(self, mock_dependencies):
        """[TC-002] Async 함수: 첫 시도 성공 시 Await 정상 처리 및 반환"""
        deps = mock_dependencies
        
        async def async_echo(msg):
            return f"Async {msg}"
        
        decorator = RetryDecorator(max_retries=3)
        wrapped = decorator(async_echo)

        result = await wrapped("test")

        assert result == "Async test"
        deps["Logger"].warning.assert_not_called()
        deps["AsyncSleep"].assert_not_called()

    def test_tc003_sync_retry_recovery(self, mock_dependencies):
        """[TC-003] Sync 함수: 2회 실패 후 3회차 성공 (복구)"""
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=[ValueError("Fail 1"), ValueError("Fail 2"), "Success"])
        mock_func.__qualname__ = "TestFunc_Recovery"
        
        decorated = RetryDecorator(max_retries=3)(mock_func)

        result = decorated()

        assert result == "Success"
        assert mock_func.call_count == 3
        assert deps["TimeSleep"].call_count == 2
        assert deps["Logger"].warning.call_count == 2

    @pytest.mark.asyncio
    async def test_tc004_async_retry_recovery(self, mock_dependencies):
        """[TC-004] Async 함수: 1회 실패 후 2회차 성공 (복구)"""
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=[ValueError("Fail 1"), "Success"])
        
        async def async_target():
            val = mock_func()
            if isinstance(val, Exception): raise val
            return val
            
        decorated = RetryDecorator(max_retries=3)(async_target)

        result = await decorated()

        assert result == "Success"
        assert mock_func.call_count == 2
        assert deps["AsyncSleep"].call_count == 1

    # ==========================================
    # Category: Boundary Analysis (Limits)
    # ==========================================

    def test_tc005_boundary_zero_retries(self, mock_dependencies):
        """[TC-005] Max Retries=0: 실패 시 재시도 없이 즉시 예외 발생"""
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=ValueError("Immediate Fail"))
        mock_func.__qualname__ = "TestFunc_Zero"
        
        decorated = RetryDecorator(max_retries=0)(mock_func)

        with pytest.raises(ValueError, match="Immediate Fail"):
            decorated()
        
        assert mock_func.call_count == 1
        deps["TimeSleep"].assert_not_called()

    def test_tc006_boundary_max_delay_cap(self, mock_dependencies):
        """[TC-006] Max Delay Cap: 계산된 대기 시간이 상한선을 초과하지 않음"""
        max_delay = 0.5
        decorator = RetryDecorator(max_delay=max_delay, backoff_factor=100.0, jitter=True)

        delay = decorator._calculate_delay(attempt=10)

        assert delay <= max_delay + 0.1

    def test_tc007_boundary_backoff_calculation(self, mock_dependencies):
        """[TC-007] Backoff Logic: 지수 증가 공식(Base * Factor^(Attempt-1)) 검증 (Jitter False)"""
        base, factor = 1.0, 2.0
        decorator = RetryDecorator(base_delay=base, backoff_factor=factor, jitter=False)

        # Attempt 1: 1.0 * (2.0 ^ 0) = 1.0
        assert decorator._calculate_delay(1) == 1.0
        # Attempt 2: 1.0 * (2.0 ^ 1) = 2.0
        assert decorator._calculate_delay(2) == 2.0
        # Attempt 3: 1.0 * (2.0 ^ 2) = 4.0
        assert decorator._calculate_delay(3) == 4.0

    # ==========================================
    # Category: Null & Type Safety
    # ==========================================

    def test_tc008_args_passthrough(self, mock_dependencies):
        """[TC-008] 인자 전달: *args, **kwargs가 원본 함수로 손실 없이 전달됨"""
        mock_func = MagicMock(return_value="OK")
        mock_func.__qualname__ = "TestFunc_Args"
        decorated = RetryDecorator()(mock_func)

        decorated(1, "B", key="value")

        mock_func.assert_called_once_with(1, "B", key="value")

    def test_tc009_return_value_passthrough(self, mock_dependencies):
        """[TC-009] 반환값 보존: None 또는 복잡한 객체도 그대로 반환"""
        complex_obj = {"k": [1, 2, 3]}
        mock_func = MagicMock(return_value=complex_obj)
        mock_func.__qualname__ = "TestFunc_Ret"
        decorated = RetryDecorator()(mock_func)

        result = decorated()

        assert result is complex_obj

    def test_tc010_default_configuration(self, mock_dependencies):
        """[TC-010] 기본 설정: 인자 없이 초기화 시 기본값(Retries=3 등) 적용"""
        decorator = RetryDecorator()

        assert decorator.max_retries == 3
        assert decorator.base_delay == 1.0

    # ==========================================
    # Category: Logical Exceptions
    # ==========================================

    def test_tc011_sync_exception_exhaustion(self, mock_dependencies):
        """[TC-011] Sync 재시도 소진: 모든 시도 실패 시 마지막 예외 전파"""
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=RuntimeError("Final Error"))
        mock_func.__qualname__ = "TestFunc_Exhaust"
        
        decorated = RetryDecorator(max_retries=2)(mock_func)

        with pytest.raises(RuntimeError, match="Final Error"):
            decorated()
        
        assert mock_func.call_count == 3
        deps["Logger"].error.assert_called_once()

    def test_tc012_exception_selective_match(self, mock_dependencies):
        """[TC-012] 선택적 예외: 지정된 예외(ValueError)만 재시도 수행"""
        mock_func = MagicMock(side_effect=[ValueError("Target"), "Success"])
        mock_func.__qualname__ = "TestFunc_Selective"
        
        decorated = RetryDecorator(max_retries=3, exceptions=ValueError)(mock_func)

        result = decorated()

        assert result == "Success"
        assert mock_func.call_count == 2

    def test_tc013_exception_selective_mismatch(self, mock_dependencies):
        """[TC-013] 예외 불일치: 지정되지 않은 예외(KeyError) 발생 시 즉시 중단"""
        mock_func = MagicMock(side_effect=KeyError("Not Target"))
        mock_func.__qualname__ = "TestFunc_Mismatch"
        
        decorated = RetryDecorator(exceptions=ValueError)(mock_func)

        with pytest.raises(KeyError):
            decorated()
        
        assert mock_func.call_count == 1

    def test_tc014_exception_multiple_types(self, mock_dependencies):
        """[TC-014] 다중 예외: Tuple로 지정된 여러 예외 타입 지원"""
        mock_func = MagicMock(side_effect=[KeyError("Target 2"), "Success"])
        mock_func.__qualname__ = "TestFunc_Multiple"
        
        decorated = RetryDecorator(exceptions=(ValueError, KeyError))(mock_func)

        result = decorated()

        assert result == "Success"
        assert mock_func.call_count == 2

    # ==========================================
    # Category: Resource & State
    # ==========================================

    def test_tc015_jitter_randomness(self, mock_dependencies):
        """[TC-015] Jitter: 동일 조건에서도 대기 시간에 무작위성 부여 확인"""
        decorator = RetryDecorator(base_delay=1.0, jitter=True)

        delay1 = decorator._calculate_delay(1)
        delay2 = decorator._calculate_delay(1)

        assert delay1 != delay2
        assert abs(delay1 - delay2) <= 0.1

    def test_tc016_logging_retry_warning(self, mock_dependencies):
        """[TC-016] 로깅(Warning): 재시도 시점에 정확한 로그 기록"""
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=[ValueError("E"), "Success"])
        mock_func.__qualname__ = "TestFunc_LogWarn"
        
        decorated = RetryDecorator(max_retries=1)(mock_func)

        decorated()

        deps["Logger"].warning.assert_called()
        log_msg = deps["Logger"].warning.call_args[0][0]
        assert "RETRY" in log_msg
        assert "TestFunc_LogWarn" in log_msg

    def test_tc017_logging_giveup_error(self, mock_dependencies):
        """[TC-017] 로깅(Error): 최종 포기 시점에 정확한 로그 기록"""
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=ValueError("Fatal"))
        mock_func.__qualname__ = "TestFunc_LogErr"
        
        decorated = RetryDecorator(max_retries=1)(mock_func)

        with pytest.raises(ValueError):
            decorated()

        deps["Logger"].error.assert_called()
        log_msg = deps["Logger"].error.call_args[0][0]
        assert "GAVE UP" in log_msg
        assert "TestFunc_LogErr" in log_msg

    # ==========================================
    # Category: Missing Branch Coverage (Async Exhaustion)
    # ==========================================

    @pytest.mark.asyncio
    async def test_tc018_async_exhaustion(self, mock_dependencies):
        """[TC-018] Async 재시도 소진: 비동기 함수 실패 시 GiveUp 분기 검증"""
        deps = mock_dependencies
        mock_func = AsyncMock(side_effect=RuntimeError("Async Fatal"))
        mock_func.__qualname__ = "AsyncFunc_Exhaust"
        
        decorated = RetryDecorator(max_retries=2)(mock_func)

        with pytest.raises(RuntimeError, match="Async Fatal"):
            await decorated()

        assert mock_func.call_count == 3  
        deps["Logger"].error.assert_called_once()
        assert "GAVE UP" in deps["Logger"].error.call_args[0][0]

    def test_tc019_default_logger_name(self, mock_dependencies):
        """[TC-019] Default Logger Name: 이름 미지정 시 func.__module__ 사용 검증"""
        deps = mock_dependencies
        
        @RetryDecorator()
        def my_func(): pass
        
        my_func()
        
        expected_name = my_func.__module__
        deps["LogManager"].get_logger.assert_called_with(expected_name)

    def test_tc020_import_fallback(self):
        """
        [TC-020] Import Fallback Logic:
        'src.common.log' 모듈 Import 실패 시 sys.path 수정 후 재시도하는 로직 검증.
        [주의] 이 테스트는 sys.modules를 변경하므로, 이후 실행되는 테스트는 
        재로드된 모듈을 사용하도록 주의해야 합니다.
        """
        target_module_name = "src.common.decorators.retry_decorator"

        if target_module_name in sys.modules:
            del sys.modules[target_module_name]

        original_import = builtins.__import__
        class State:
            failed_once = False

        def side_effect_import(name, *args, **kwargs):
            if name == "src.common.log" and not State.failed_once:
                State.failed_once = True
                raise ImportError("Forced ImportError")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=side_effect_import):
            import src.common.decorators.retry_decorator
            importlib.reload(src.common.decorators.retry_decorator)

        assert target_module_name in sys.modules
        
        if target_module_name in sys.modules:
            del sys.modules[target_module_name]
        import src.common.decorators.retry_decorator

    # ==========================================
    # Category: Missing Branch Coverage (Final 3%)
    # ==========================================

    def test_tc021_custom_logger_name_init(self, mock_dependencies):
        """
        [TC-021] Custom Logger Name Init:
        생성자에서 logger_name을 명시적으로 주입했을 때, 
        __call__ 내부의 'if not self.logger_name' 분기가 False가 되는지 검증.
        (Coverage: 87->90)
        """
        # [CRITICAL FIX] tc020에서 모듈이 리로드되었으므로, 현재 sys.modules에 있는
        # 최신 클래스를 가져와야 Mock Patch가 정상 적용된 LogManager를 사용할 수 있습니다.
        from src.common.decorators.retry_decorator import RetryDecorator as CurrentRetryDecorator
        
        deps = mock_dependencies
        custom_name = "MyCustomLogger"
        
        @CurrentRetryDecorator(logger_name=custom_name)
        def my_func(): pass
        
        my_func()
        
        deps["LogManager"].get_logger.assert_called_with(custom_name)

    @pytest.mark.asyncio
    async def test_tc022_negative_retries_loop_skip(self):
        """
        [TC-022] Negative Max Retries (Loop Skip):
        max_retries를 -1로 설정하여 for 루프(Sync/Async)가 
        한 번도 실행되지 않고 건너뛰는(Skip) 분기를 검증.
        (Coverage: 144->164, 179->195)
        """
        # [CRITICAL FIX] 동일하게 최신 모듈의 클래스를 로컬 Import하여 사용합니다.
        from src.common.decorators.retry_decorator import RetryDecorator as CurrentRetryDecorator
        
        # 1. Sync Function
        @CurrentRetryDecorator(max_retries=-1)
        def sync_skip(): return "ok"
        
        with pytest.raises(TypeError):
            sync_skip()
            
        # 2. Async Function
        @CurrentRetryDecorator(max_retries=-1)
        async def async_skip(): return "ok"
        
        with pytest.raises(TypeError):
            await async_skip()