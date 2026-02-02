"""
속도 제한 데코레이터 모듈 (Rate Limiting Decorator Module)

외부 API 호출 시 과도한 요청으로 인한 차단(429 Too Many Requests)을 방지하기 위해
클라이언트 사이드에서 능동적으로 요청 속도를 제어(Throttling)합니다.

주요 기능:
- Token Bucket 알고리즘 변형을 사용하여, 정해진 시간(period) 내의 호출 횟수(limit)를 제어.
- Limit 초과 시 예외를 발생시키지 않고, 안전한 시점까지 대기(Sleep) 후 자동 실행.
- Global Scope: 여러 함수가 동일한 API Key를 공유할 경우, 'bucket_key'를 통해 제한을 공유.
- Hybrid Support: 동기(time.sleep) 및 비동기(await asyncio.sleep) 함수 모두 지원.

Trade-off:
- Latency: 제한 초과 시 대기 시간만큼 응답 속도가 느려질 수 있음.
- Memory: 호출 타임스탬프를 메모리에 저장하므로, 매우 긴 period나 높은 limit 설정 시 메모리 사용량 주의.
"""

import time
import asyncio
import functools
import inspect
from collections import deque
from typing import Dict, Optional, Callable

# [Dependency] 로깅 모듈
try:
    from src.common.log import LogManager
except ImportError:
    import logging
    LogManager = None 

# ==============================================================================
# [Inner Class] Rate Limit Bucket
# ==============================================================================
class RateLimitBucket:
    """개별 제한 구역(Bucket)의 상태를 관리하는 클래스.
    
    특정 API Key나 도메인 단위로 호출 기록(Timestamp)을 저장합니다.
    """
    def __init__(self, limit: int, period: float):
        self.limit = limit
        self.period = period
        # 호출 시간을 기록하는 덱 (오래된 기록부터 자동 삭제를 위해 사용)
        self.timestamps = deque()
        # 비동기 환경에서의 Race Condition 방지를 위한 Lock
        self._async_lock = asyncio.Lock()
        # 동기 환경용 Lock (필요 시 확장 가능, 현재는 GIL 및 로직으로 커버)

    def _cleanup(self, now: float):
        """유효 기간(period)이 지난 타임스탬프를 제거합니다."""
        while self.timestamps and self.timestamps[0] <= now - self.period:
            self.timestamps.popleft()

    def get_wait_time(self) -> float:
        """현재 호출이 가능한지 확인하고, 대기해야 할 시간을 반환합니다.
        
        Returns:
            float: 0.0이면 즉시 실행 가능, 0.0보다 크면 해당 초(seconds)만큼 대기 필요.
        """
        now = time.time()
        self._cleanup(now)

        if len(self.timestamps) < self.limit:
            self.timestamps.append(now)
            return 0.0
        
        # 제한에 도달한 경우: 가장 오래된 호출 기록이 만료될 때까지 대기
        earliest = self.timestamps[0]
        wait_time = (earliest + self.period) - now
        
        # 부동소수점 오차 등을 고려하여 최소 대기 시간 보정
        if wait_time < 0:
            wait_time = 0.0
            
        # 대기 후 실행된다고 가정하고 타임스탬프를 미리 추가 (실제 실행 시점은 now + wait_time)
        self.timestamps.append(now + wait_time)
        return wait_time


# ==============================================================================
# [Global State] Bucket Manager
# ==============================================================================
# 여러 데코레이터가 동일한 'bucket_key'(예: "KIS_API")를 사용할 경우 상태를 공유하기 위함.
_buckets: Dict[str, RateLimitBucket] = {}


def _get_bucket(bucket_key: str, limit: int, period: float) -> RateLimitBucket:
    """버킷 키에 해당하는 관리 객체를 반환하거나 새로 생성합니다."""
    if bucket_key not in _buckets:
        _buckets[bucket_key] = RateLimitBucket(limit, period)
    return _buckets[bucket_key]


# ==============================================================================
# [Main Decorator] rate_limit
# ==============================================================================
class RateLimitDecorator:
    """함수 실행 속도를 제어하는 데코레이터.

    Attributes:
        limit (int): 기간 내 최대 허용 호출 횟수.
        period (float): 기간 (초 단위).
        bucket_key (str, optional): 제한을 공유할 고유 키. 
                                    None일 경우 함수 이름(Qualified Name)을 사용.
    """

    def __init__(self, limit: int = 10, period: float = 1.0, bucket_key: Optional[str] = None):
        self.limit = limit
        self.period = period
        self.bucket_key = bucket_key

    def __call__(self, func: Callable) -> Callable:
        # 버킷 키가 없으면 함수의 고유 경로 사용 (함수별 독립 제한)
        if not self.bucket_key:
            self.bucket_key = func.__qualname__

        if inspect.iscoroutinefunction(func):
            return self._create_async_wrapper(func)
        return self._create_sync_wrapper(func)

    def _log_throttling(self, func_name: str, wait_time: float):
        """대기가 발생했을 때만 로그를 남깁니다 (Debug 레벨)."""
        if LogManager and wait_time > 0.1:
            logger = LogManager.get_logger("RateLimit")
            logger.debug(
                f"[{func_name}] Throttling active: Sleeping for {wait_time:.4f}s "
                f"(Bucket: {self.bucket_key})"
            )

    # --------------------------------------------------------------------------
    # [Wrapper 1] Sync Wrapper
    # --------------------------------------------------------------------------
    def _create_sync_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bucket = _get_bucket(self.bucket_key, self.limit, self.period)
            
            # 대기 시간 계산
            wait_time = bucket.get_wait_time()
            
            if wait_time > 0:
                self._log_throttling(func.__qualname__, wait_time)
                time.sleep(wait_time)
            
            return func(*args, **kwargs)
        return wrapper

    # --------------------------------------------------------------------------
    # [Wrapper 2] Async Wrapper
    # --------------------------------------------------------------------------
    def _create_async_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            bucket = _get_bucket(self.bucket_key, self.limit, self.period)
            
            # 비동기 락을 사용하여 타임스탬프 계산의 원자성 보장
            async with bucket._async_lock:
                wait_time = bucket.get_wait_time()

            if wait_time > 0:
                self._log_throttling(func.__qualname__, wait_time)
                await asyncio.sleep(wait_time)
            
            return await func(*args, **kwargs)
        return wrapper

# Alias
rate_limit = RateLimitDecorator