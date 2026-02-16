"""
[속도 제한 데코레이터 (Rate Limiting Decorator)]

외부 API 호출 시 Throttling 정책을 준수하며, 임계치 초과 시 구조화된 예외를 발생시키는 모듈입니다.
exceptions.py의 RateLimitError와 결합하여 재시도 정책 및 모니터링 데이터를 제공합니다.

전체 데이터 흐름:
함수 호출 -> Bucket 상태 확인 -> [대기 시간 < 임계치]: Sleep 후 실행 -> [대기 시간 > 임계치]: RateLimitError 발생

주요 기능:
- Fail-fast Throttling: 무한 대기를 방지하고 max_wait_seconds 초과 시 즉시 에러 응답.
- Structured Error Context: RateLimitError 발생 시 retry_after 및 bucket 정보를 details에 주입.
- Hybrid Logic: 동기(time.sleep) 및 비동기(asyncio.sleep) 환경을 완벽히 지원.

Trade-off:
- 장점: 무의미한 스레드/태스크 점유를 방지하여 시스템 가용성을 높이고, 에러 로그의 가독성을 극대화함.
- 단점: 대기 시간 계산 및 Lock 관리에 따른 미세한 오버헤드 발생.
- 근거: 분산 환경에서 클라이언트 사이드 Throttling은 서버의 429 응답을 예방하는 필수적인 방어 기제임.
"""

import time
import asyncio
import functools
import inspect
import json
from collections import deque
from typing import Dict, Optional, Callable, Any

# [Dependency] 로컬 모듈 및 커스텀 예외
from src.common.exceptions import ETLError, RateLimitError

try:
    from src.common.log import LogManager
except ImportError:
    import logging
    LogManager = None


# ==============================================================================
# 3. Constants & Configuration
# ==============================================================================

# 기본 최대 대기 허용 시간 (초)
DEFAULT_MAX_WAIT_SECONDS: float = 30.0


# ==============================================================================
# [Inner Class] Rate Limit Bucket
# ==============================================================================

class RateLimitBucket:
    """개별 제한 구역(Bucket)의 상태를 관리하는 클래스."""

    def __init__(self, limit: int, period: float):
        self.limit = limit
        self.period = period
        self.timestamps = deque()
        self._async_lock = asyncio.Lock()

    def _cleanup(self, now: float):
        """유효 기간이 지난 타임스탬프를 제거합니다."""
        while self.timestamps and self.timestamps[0] <= now - self.period:
            self.timestamps.popleft()

    def get_wait_time(self) -> float:
        """현재 호출 시 대기해야 할 시간을 계산합니다.
        
        Returns:
            float: 대기 시간(초). 즉시 실행 가능 시 0.0 반환.
        """
        now = time.time()
        self._cleanup(now)

        if len(self.timestamps) < self.limit:
            self.timestamps.append(now)
            return 0.0
        
        earliest = self.timestamps[0]
        wait_time = (earliest + self.period) - now
        
        if wait_time < 0:
            wait_time = 0.0
            
        self.timestamps.append(now + wait_time)
        return wait_time


# ==============================================================================
# [Global State] Bucket Manager
# ==============================================================================

_buckets: Dict[str, RateLimitBucket] = {}

def _get_bucket(bucket_key: str, limit: int, period: float) -> RateLimitBucket:
    """공유 버킷 인스턴스를 반환하거나 생성합니다."""
    if bucket_key not in _buckets:
        _buckets[bucket_key] = RateLimitBucket(limit, period)
    return _buckets[bucket_key]


# ==============================================================================
# 5. Main Class (RateLimitDecorator)
# ==============================================================================

class RateLimitDecorator:
    """구조화된 예외 처리가 포함된 속도 제한 데코레이터."""

    def __init__(
        self, 
        limit: int = 10, 
        period: float = 1.0, 
        bucket_key: Optional[str] = None,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS
    ):
        """
        Args:
            limit (int): 허용 호출 횟수.
            period (float): 제한 기간(초).
            bucket_key (str, optional): 제한 공유 키.
            max_wait_seconds (float): 최대 대기 허용 시간. 초과 시 RateLimitError 발생.
        """
        self.limit = limit
        self.period = period
        self.bucket_key = bucket_key
        self.max_wait_seconds = max_wait_seconds

    def __call__(self, func: Callable) -> Callable:
        if not self.bucket_key:
            self.bucket_key = func.__qualname__

        if inspect.iscoroutinefunction(func):
            return self._create_async_wrapper(func)
        return self._create_sync_wrapper(func)

    def _log_throttling(self, func_name: str, wait_time: float):
        """대기 발생 시 디버그 로그를 남깁니다."""
        if LogManager and wait_time > 0.1:
            logger = LogManager.get_logger("RateLimit")
            logger.debug(f"[{func_name}] Throttling: Waiting {wait_time:.2f}s (Bucket: {self.bucket_key})")

    def _handle_wait_time(self, wait_time: float, func_name: str) -> None:
        """대기 시간을 체크하고 임계치 초과 시 RateLimitError를 발생시킵니다.
        
        Raises:
            RateLimitError: 대기 시간이 max_wait_seconds를 초과할 경우 발생.
        """
        # 설계 의도: Fail-fast 원칙에 따라 무의미한 자원 점유 방지
        if wait_time > self.max_wait_seconds:
            raise RateLimitError(
                message=f"Local rate limit threshold exceeded. Max allowed wait: {self.max_wait_seconds}s",
                retry_after=int(wait_time)
            )
        
        if wait_time > 0:
            self._log_throttling(func_name, wait_time)

    # --------------------------------------------------------------------------
    # [Wrapper 1] Sync Wrapper
    # --------------------------------------------------------------------------
    def _create_sync_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                bucket = _get_bucket(self.bucket_key, self.limit, self.period)
                wait_time = bucket.get_wait_time()
                
                self._handle_wait_time(wait_time, func.__qualname__)
                if wait_time > 0:
                    time.sleep(wait_time)
                
                return func(*args, **kwargs)
            
            except RateLimitError as e:
                # 설계 의도: 명확한 에러 전파를 위해 버킷 정보를 컨텍스트에 추가
                e.details.update({"bucket_key": self.bucket_key})
                raise e
            except Exception as e:
                # 설계 의도: 정의되지 않은 에러는 최상위 ETLError로 래핑하여 규격 준수
                raise ETLError(
                    message=f"Unexpected error in rate limit decorator: {str(e)}",
                    original_exception=e,
                    details={"bucket_key": self.bucket_key}
                ) from e
        return wrapper

    # --------------------------------------------------------------------------
    # [Wrapper 2] Async Wrapper
    # --------------------------------------------------------------------------
    def _create_async_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                bucket = _get_bucket(self.bucket_key, self.limit, self.period)
                
                # 설계 의도: 비동기 락을 통해 대기 시간 계산의 원자성(Atomicity) 보장
                async with bucket._async_lock:
                    wait_time = bucket.get_wait_time()

                self._handle_wait_time(wait_time, func.__qualname__)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
                return await func(*args, **kwargs)
            
            except RateLimitError as e:
                e.details.update({"bucket_key": self.bucket_key})
                raise e
            except Exception as e:
                raise ETLError(
                    message=f"Unexpected error in async rate limit decorator: {str(e)}",
                    original_exception=e,
                    details={"bucket_key": self.bucket_key}
                ) from e
        return wrapper

# Alias
rate_limit = RateLimitDecorator