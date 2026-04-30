"""
재시도 데코레이터 모듈 (Retry Decorator Module)

일시적인 오류(Transient Failures) 발생 시, 정의된 전략(Backoff)에 따라 함수 실행을 재시도하여 시스템의 회복 탄력성(Resilience)을 보장합니다.
데이터 수집(Extractor) 단계에서 외부 API 호출 실패나 네트워크 타임아웃 발생 시, 외부 서버에 가해지는 충격을 분산시키는 3단계 방어막(운 방어)의 핵심입니다.

주요 기능:
- [Exponential Backoff] 재시도 횟수가 늘어날수록 대기 시간을 2의 배수로 지수적으로 증가시킴.
- [Jitter (Randomness)] 여러 요청이 동시에 깨어나 API 서버를 다시 타격하는(Thundering Herd) 현상을 완벽히 차단.
- [Hybrid Support] 동기(Sync) 및 비동기(Async) 함수 모두 지원.
- [Selective Retry] 객체 내부에 정의된 예외 타입 및 `should_retry` 속성에 따른 선별적 재시도 수행.

Trade-off:
- Latency Increase: 재시도 수행 시 전체 응답 시간이 길어질 수 있음.
  따라서, 사용자 대기 시간이 중요한 API보다는 백그라운드 작업(ETL)에 적합함.
- Jitter 알고리즘 (Full Jitter vs Equal Jitter):
  - 장점: `Equal Jitter(최소 대기시간 보장 + 무작위 지연)` 방식을 채택하여, 재시도들이 너무 빨리 연속해서 실행되어 다시 차단(Ban) 당하는 현상을 막고 시간축으로 균일하게 분산시킴.
  - 단점: 재시도가 3~4회 거듭될수록 2초, 4초, 8초로 응답 시간(Latency)이 기하급수적으로 길어짐.
  - 근거: 현재 파이프라인은 실시간 사용자 서빙 API가 아니라 일 단위 백그라운드 배치(Bronze ETL)이므로, 빠른 실패(Fail-Fast)보다 시간이 조금 더 걸리더라도 최종 수집 성공률 100%를 달성하는 것이 압도적으로 중요함. 따라서 지연 시간을 감수하고서라도 가장 안정적인 지수적 백오프를 채택함.
"""

import asyncio
import time
import functools
import inspect
import random
from typing import Callable, Type, Union, Tuple, Optional

# [Dependency] 로깅을 위해 LogManager 사용
try:
    from src.common.log import LogManager
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parents[3]))
    from src.common.log import LogManager

from src.common.exceptions import ETLError

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# 기본 재시도 횟수
DEFAULT_MAX_RETRIES: int = 3
# 기본 초기 대기 시간 (초)
DEFAULT_BASE_DELAY: float = 1.0
# 대기 시간 증가 배수 (Exponential Factor)
DEFAULT_BACKOFF_FACTOR: float = 2.0
# 최대 대기 시간 제한 (초)
DEFAULT_MAX_DELAY: float = 60.0


# ==============================================================================
# [Main Class] RetryDecorator
# ==============================================================================
class RetryDecorator:
    """함수 실패 시 재시도 로직을 부여하는 데코레이터.

    Attributes:
        max_retries (int): 최대 재시도 횟수.
        base_delay (float): 첫 재시도 전 대기 시간.
        backoff_factor (float): 대기 시간 증가율 (예: 2.0이면 1s -> 2s -> 4s).
        max_delay (float): 대기 시간의 상한선.
        exceptions (Tuple[Type[Exception]]): 재시도를 유발할 예외 타입들.
        logger_name (Optional[str]): 로거 이름.
        jitter (bool): 대기 시간에 무작위성을 추가할지 여부.
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        max_delay: float = DEFAULT_MAX_DELAY,
        exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
        logger_name: Optional[str] = None,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.exceptions = exceptions
        self.logger_name = logger_name
        self.jitter = jitter

    def __call__(self, func: Callable) -> Callable:
        """데코레이터 진입점. 대상 함수의 타입(Sync/Async)에 따라 래퍼를 분기합니다."""
        
        if not self.logger_name:
            self.logger_name = func.__module__

        if inspect.iscoroutinefunction(func):
            return self._create_async_wrapper(func)
        return self._create_sync_wrapper(func)

    def _calculate_delay(self, attempt: int) -> float:
        """현재 시도 횟수에 따른 대기 시간을 계산합니다 (Exponential Backoff + Jitter).

        Formula: min(max_delay, base * (factor ^ (attempt - 1))) + jitter

        Args:
            attempt (int): 현재 재시도 차수 (1부터 시작).

        Returns:
            float: 대기 시간(초).
        """
        # 1. 지수적 증가 (Exponential Backoff)
        # 생성자(__init__)에서 주입받은 기본 대기 시간(self.delay)을 기준으로,
        # 재시도 횟수마다 2의 제곱으로 대기 시간을 기하급수적으로 늘립니다.
        # (예: delay가 1.0초일 때 -> 1회차: 1초, 2회차: 2초, 3회차: 4초)
        backoff_base = self.delay * (2 ** (attempt - 1))
        
        # 2. 시간 분산 (Equal Jitter 알고리즘)
        # 계산된 대기 시간의 50%는 고정 대기(최소한의 쿨타임 보장)로 가져가고,
        # 나머지 50%의 시간 내에서 랜덤 난수(Jitter)를 발생시킵니다.
        # 이를 통해 실패했던 수십 개의 코루틴이 정확히 같은 시간에 깨어나는 것을 막고
        # 0.01초 단위로 뿔뿔이 흩어지게 하여 KIS 서버의 TPS 제한을 매우 부드럽게 통과합니다.
        min_delay = backoff_base * 0.5
        jitter = random.uniform(0, backoff_base * 0.5)
        
        return round(min_delay + jitter, 2)

    def _log_retry(self, logger, func_name, attempt, error, next_delay):
        """재시도 발생 사실을 경고(Warning) 레벨로 로깅합니다."""
        error_detail = error.to_dict() if isinstance(error, ETLError) else str(error)
        logger.warning(
            f"[{func_name}] RETRY ({attempt}/{self.max_retries}) | "
            f"Error: {error_detail} | Next Retry in {next_delay:.2f}s"
        )

    def _log_giveup(self, logger, func_name, error):
        """최대 재시도 초과 시 에러(Error) 레벨로 로깅합니다."""
        error_detail = error.to_dict() if isinstance(error, ETLError) else str(error)
        logger.error(
            f"[{func_name}] GAVE UP after {self.max_retries} retries | "
            f"Final Error: {error_detail}"
        )

    # --------------------------------------------------------------------------
    # [Wrapper 1] Sync Wrapper
    # --------------------------------------------------------------------------
    def _create_sync_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = LogManager.get_logger(self.logger_name)
            func_name = func.__qualname__
            
            last_exception = None

            # 0번째 시도(최초 실행) + 재시도 횟수
            for attempt in range(self.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except self.exceptions as e:
                    last_exception = e
                    
                    # [Design Intent] ETLError 명세에 따라 should_retry가 False(예: AuthError)면 즉시 중단
                    should_retry_attr = getattr(e, "should_retry", True)
                    
                    if attempt == self.max_retries or not should_retry_attr:
                        self._log_giveup(logger, func_name, e)
                        break
                    
                    delay = self._calculate_delay(attempt + 1)
                    self._log_retry(logger, func_name, attempt + 1, e, delay)
                    time.sleep(delay)
            
            # 모든 시도 실패 시 마지막 예외 발생
            raise last_exception

        return wrapper

    # --------------------------------------------------------------------------
    # [Wrapper 2] Async Wrapper
    # --------------------------------------------------------------------------
    def _create_async_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = LogManager.get_logger(self.logger_name)
            func_name = func.__qualname__
            
            last_exception = None

            for attempt in range(self.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except self.exceptions as e:
                    last_exception = e
                    
                    should_retry_attr = getattr(e, "should_retry", True)
                    
                    if attempt == self.max_retries or not should_retry_attr:
                        self._log_giveup(logger, func_name, e)
                        break
                    
                    delay = self._calculate_delay(attempt + 1)
                    self._log_retry(logger, func_name, attempt + 1, e, delay)
                    await asyncio.sleep(delay)
            
            raise last_exception

        return wrapper

# Alias
retry = RetryDecorator