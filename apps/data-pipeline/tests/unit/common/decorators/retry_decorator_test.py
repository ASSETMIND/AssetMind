import pytest
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY, AsyncMock  # AsyncMock 추가

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
    from retry_decorator import RetryDecorator

# --------------------------------------------------------------------------
# 0. Constants & Configuration
# --------------------------------------------------------------------------

# Mocking 대상 경로 (retry_decorator.py 내부 의존성)
TARGET_MODULE = "src.common.decorators.retry_decorator" if "src.common.decorators.retry_decorator" in sys.modules else "retry_decorator"

TARGET_LOG_MANAGER = f"{TARGET_MODULE}.LogManager"
TARGET_TIME_SLEEP = "time.sleep"
TARGET_ASYNC_SLEEP = "asyncio.sleep"

# --------------------------------------------------------------------------
# 1. Fixtures (Test Environment Setup)
# --------------------------------------------------------------------------

@pytest.fixture
def mock_dependencies():
    """
    [Dependencies Mock]
    LogManager, time.sleep, asyncio.sleep을 Mocking하여
    외부 의존성 및 시간 지연을 격리합니다.
    """
    # [FIX] asyncio.sleep에 대해 new_callable=AsyncMock 사용
    # 기존처럼 asyncio.Future()를 직접 생성하지 않아 경고가 제거됨
    with patch(TARGET_LOG_MANAGER) as MockLogManager, \
         patch(TARGET_TIME_SLEEP) as MockTimeSleep, \
         patch(TARGET_ASYNC_SLEEP, new_callable=AsyncMock) as MockAsyncSleep:
        
        # 1. Logger Mock 설정
        mock_logger_instance = MagicMock()
        MockLogManager.get_logger.return_value = mock_logger_instance
        
        # 2. AsyncMock은 기본적으로 awaitable하므로 별도의 Future 설정 불필요
        
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
        # Given
        deps = mock_dependencies
        mock_func = MagicMock(return_value="Success")
        mock_func.__qualname__ = "TestFunc_Sync"
        
        @RetryDecorator(max_retries=3)
        def wrapped(*args): return mock_func(*args)

        # When
        result = wrapped(10, 20)

        # Then
        assert result == "Success"
        deps["Logger"].warning.assert_not_called()
        deps["TimeSleep"].assert_not_called()

    @pytest.mark.asyncio
    async def test_tc002_async_happy_path(self, mock_dependencies):
        """[TC-002] Async 함수: 첫 시도 성공 시 Await 정상 처리 및 반환"""
        # Given
        deps = mock_dependencies
        
        async def async_echo(msg):
            return f"Async {msg}"
        
        decorator = RetryDecorator(max_retries=3)
        wrapped = decorator(async_echo)

        # When
        result = await wrapped("test")

        # Then
        assert result == "Async test"
        deps["Logger"].warning.assert_not_called()
        deps["AsyncSleep"].assert_not_called()

    def test_tc003_sync_retry_recovery(self, mock_dependencies):
        """[TC-003] Sync 함수: 2회 실패 후 3회차 성공 (복구)"""
        # Given
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=[ValueError("Fail 1"), ValueError("Fail 2"), "Success"])
        mock_func.__qualname__ = "TestFunc_Recovery"
        
        decorated = RetryDecorator(max_retries=3)(mock_func)

        # When
        result = decorated()

        # Then
        assert result == "Success"
        assert mock_func.call_count == 3
        assert deps["TimeSleep"].call_count == 2
        assert deps["Logger"].warning.call_count == 2

    @pytest.mark.asyncio
    async def test_tc004_async_retry_recovery(self, mock_dependencies):
        """[TC-004] Async 함수: 1회 실패 후 2회차 성공 (복구)"""
        # Given
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=[ValueError("Fail 1"), "Success"])
        
        async def async_target():
            val = mock_func()
            if isinstance(val, Exception): raise val
            return val
            
        decorated = RetryDecorator(max_retries=3)(async_target)

        # When
        result = await decorated()

        # Then
        assert result == "Success"
        assert mock_func.call_count == 2
        assert deps["AsyncSleep"].call_count == 1

    # ==========================================
    # Category: Boundary Analysis (Limits)
    # ==========================================

    def test_tc005_boundary_zero_retries(self, mock_dependencies):
        """[TC-005] Max Retries=0: 실패 시 재시도 없이 즉시 예외 발생"""
        # Given
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=ValueError("Immediate Fail"))
        mock_func.__qualname__ = "TestFunc_Zero"
        
        decorated = RetryDecorator(max_retries=0)(mock_func)

        # When & Then
        with pytest.raises(ValueError, match="Immediate Fail"):
            decorated()
        
        assert mock_func.call_count == 1
        deps["TimeSleep"].assert_not_called()

    def test_tc006_boundary_max_delay_cap(self, mock_dependencies):
        """[TC-006] Max Delay Cap: 계산된 대기 시간이 상한선을 초과하지 않음"""
        # Given
        max_delay = 0.5
        decorator = RetryDecorator(max_delay=max_delay, backoff_factor=100.0, jitter=True)

        # When
        delay = decorator._calculate_delay(attempt=10)

        # Then
        assert delay <= max_delay + 0.1

    def test_tc007_boundary_backoff_calculation(self, mock_dependencies):
        """[TC-007] Backoff Logic: 지수 증가 공식(Base * Factor^(Attempt-1)) 검증"""
        # Given
        base, factor = 1.0, 2.0
        decorator = RetryDecorator(base_delay=base, backoff_factor=factor, jitter=False)

        # When
        delay = decorator._calculate_delay(attempt=3)

        # Then
        assert delay == 4.0

    # ==========================================
    # Category: Null & Type Safety
    # ==========================================

    def test_tc008_args_passthrough(self, mock_dependencies):
        """[TC-008] 인자 전달: *args, **kwargs가 원본 함수로 손실 없이 전달됨"""
        # Given
        mock_func = MagicMock(return_value="OK")
        mock_func.__qualname__ = "TestFunc_Args"
        decorated = RetryDecorator()(mock_func)

        # When
        decorated(1, "B", key="value")

        # Then
        mock_func.assert_called_once_with(1, "B", key="value")

    def test_tc009_return_value_passthrough(self, mock_dependencies):
        """[TC-009] 반환값 보존: None 또는 복잡한 객체도 그대로 반환"""
        # Given
        complex_obj = {"k": [1, 2, 3]}
        mock_func = MagicMock(return_value=complex_obj)
        mock_func.__qualname__ = "TestFunc_Ret"
        decorated = RetryDecorator()(mock_func)

        # When
        result = decorated()

        # Then
        assert result is complex_obj

    def test_tc010_default_configuration(self, mock_dependencies):
        """[TC-010] 기본 설정: 인자 없이 초기화 시 기본값(Retries=3 등) 적용"""
        # Given & When
        decorator = RetryDecorator()

        # Then
        assert decorator.max_retries == 3
        assert decorator.base_delay == 1.0

    # ==========================================
    # Category: Logical Exceptions
    # ==========================================

    def test_tc011_exception_exhaustion(self, mock_dependencies):
        """[TC-011] 재시도 소진: 모든 시도 실패 시 마지막 예외 전파"""
        # Given
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=RuntimeError("Final Error"))
        mock_func.__qualname__ = "TestFunc_Exhaust"
        
        decorated = RetryDecorator(max_retries=2)(mock_func)

        # When & Then
        with pytest.raises(RuntimeError, match="Final Error"):
            decorated()
        
        assert mock_func.call_count == 3
        deps["Logger"].error.assert_called_once()

    def test_tc012_exception_selective_match(self, mock_dependencies):
        """[TC-012] 선택적 예외: 지정된 예외(ValueError)만 재시도 수행"""
        # Given
        mock_func = MagicMock(side_effect=[ValueError("Target"), "Success"])
        mock_func.__qualname__ = "TestFunc_Selective"
        
        decorated = RetryDecorator(max_retries=3, exceptions=ValueError)(mock_func)

        # When
        result = decorated()

        # Then
        assert result == "Success"
        assert mock_func.call_count == 2

    def test_tc013_exception_selective_mismatch(self, mock_dependencies):
        """[TC-013] 예외 불일치: 지정되지 않은 예외(KeyError) 발생 시 즉시 중단"""
        # Given
        mock_func = MagicMock(side_effect=KeyError("Not Target"))
        mock_func.__qualname__ = "TestFunc_Mismatch"
        
        decorated = RetryDecorator(exceptions=ValueError)(mock_func)

        # When & Then
        with pytest.raises(KeyError):
            decorated()
        
        assert mock_func.call_count == 1

    def test_tc014_exception_multiple_types(self, mock_dependencies):
        """[TC-014] 다중 예외: Tuple로 지정된 여러 예외 타입 지원"""
        # Given
        mock_func = MagicMock(side_effect=[KeyError("Target 2"), "Success"])
        mock_func.__qualname__ = "TestFunc_Multiple"
        
        decorated = RetryDecorator(exceptions=(ValueError, KeyError))(mock_func)

        # When
        result = decorated()

        # Then
        assert result == "Success"
        assert mock_func.call_count == 2

    # ==========================================
    # Category: Resource & State
    # ==========================================

    def test_tc015_jitter_randomness(self, mock_dependencies):
        """[TC-015] Jitter: 동일 조건에서도 대기 시간에 무작위성 부여 확인"""
        # Given
        decorator = RetryDecorator(base_delay=1.0, jitter=True)

        # When
        delay1 = decorator._calculate_delay(1)
        delay2 = decorator._calculate_delay(1)

        # Then
        assert delay1 != delay2
        assert abs(delay1 - delay2) <= 0.1

    def test_tc016_logging_retry_warning(self, mock_dependencies):
        """[TC-016] 로깅(Warning): 재시도 시점에 정확한 로그 기록"""
        # Given
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=[ValueError("E"), "Success"])
        mock_func.__qualname__ = "TestFunc_LogWarn"
        
        decorated = RetryDecorator(max_retries=1)(mock_func)

        # When
        decorated()

        # Then
        deps["Logger"].warning.assert_called()
        log_msg = deps["Logger"].warning.call_args[0][0]
        assert "RETRY" in log_msg
        assert "TestFunc_LogWarn" in log_msg

    def test_tc017_logging_giveup_error(self, mock_dependencies):
        """[TC-017] 로깅(Error): 최종 포기 시점에 정확한 로그 기록"""
        # Given
        deps = mock_dependencies
        mock_func = MagicMock(side_effect=ValueError("Fatal"))
        mock_func.__qualname__ = "TestFunc_LogErr"
        
        decorated = RetryDecorator(max_retries=1)(mock_func)

        # When
        with pytest.raises(ValueError):
            decorated()

        # Then
        deps["Logger"].error.assert_called()
        log_msg = deps["Logger"].error.call_args[0][0]
        assert "GAVE UP" in log_msg
        assert "TestFunc_LogErr" in log_msg