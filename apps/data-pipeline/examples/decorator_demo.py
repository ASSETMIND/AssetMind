"""
Unified Decorator Demonstration

이 스크립트는 LoggingDecorator와 RetryDecorator의 기능을 검증하는 통합 데모입니다.
불필요한 비동기 복잡성을 제거하고, 동기(Sync) 방식으로 실행되도록 리팩토링되었습니다.

Usage:
    if __name__ == "__main__": 블록 내의 함수 호출 주석을 해제하여 실행합니다.
"""

import sys
import asyncio
import logging
import time
import yaml
from pathlib import Path
from typing import Dict, Any

# [System Path Setup] 프로젝트 루트 경로 추가
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from src.common.decorators import retry, log_decorator, rate_limit
from src.common.config import get_config
from src.common.log import LogManager


# ==============================================================================
# [Helper] Console Pretty Printer
# ==============================================================================
def setup_human_readable_logging(task_name: str):
    """콘솔 로그를 ELK용 JSON 대신 사람이 읽기 편한 텍스트 포맷으로 변경합니다."""
    target_logger = logging.getLogger(task_name)
    human_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S"
    )
    
    formatted = False
    for handler in target_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setFormatter(human_formatter)
            formatted = True
            
    if not formatted:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(human_formatter)
        target_logger.addHandler(console)


# ==============================================================================
# [Service] Demo Service Class (Simulation)
# ==============================================================================
class DemoService:
    """로깅 및 재시도 데모를 위한 시뮬레이션 서비스 클래스"""

    def __init__(self):
        self.retry_counters = {}

    def _increment(self, key: str):
        self.retry_counters[key] = self.retry_counters.get(key, 0) + 1
        return self.retry_counters[key]

    # --------------------------------------------------------------------------
    # Part 1. Logging Demo Methods
    # --------------------------------------------------------------------------
    @log_decorator(logger_name="decorator_demo")
    def simple_sync_task(self, user_id: int, action: str):
        print(f"      ▶ [Logic] Sync processing for user {user_id}...")
        return f"Done({action})"

    @log_decorator(logger_name="decorator_demo", truncate_limit=30)
    def sensitive_data_task(self, username: str, password: str, token: str):
        print(f"      ▶ [Logic] Authenticating {username} (Check Masking)...")
        # 긴 토큰 반환 -> Truncate 확인
        return "Access_Token_" + "x" * 100

    @log_decorator(logger_name="decorator_demo", suppress_error=True)
    def error_suppression_task(self):
        print("      ▶ [Logic] This job will fail but system survives...")
        raise KeyError("Expected Optional Error")

    # --------------------------------------------------------------------------
    # Part 2. Retry Demo Methods
    # --------------------------------------------------------------------------
    @retry(max_retries=3, base_delay=0.5, logger_name="decorator_demo")
    @log_decorator(logger_name="decorator_demo")
    def retry_sync_recovery(self, threshold: int, data: str):
        count = self._increment("sync_retry")
        print(f"      ▶ [Logic] Sync Attempt #{count} (Target: >{threshold})")
        
        if count <= threshold:
            raise ConnectionError(f"Network Fail #{count}")
        return f"Recovered({data})"

    # 비동기 함수는 async def로 유지해야 비동기 데코레이터를 테스트할 수 있음
    @retry(max_retries=2, base_delay=0.5, logger_name="decorator_demo")
    @log_decorator(logger_name="decorator_demo")
    async def retry_async_exhaust(self, trigger_timeout: bool):
        count = self._increment("async_retry")
        print(f"      ▶ [Logic] Async Attempt #{count} (Will Timeout: {trigger_timeout})")
        
        if trigger_timeout:
            await asyncio.sleep(0.1) # 비동기 대기 시뮬레이션
            raise TimeoutError("Async Timeout")
        return "Success"
    
    # --------------------------------------------------------------------------
    # Part 3. Rate Limit Demo Methods
    # --------------------------------------------------------------------------
    # [Sync] 동기 함수 제한 테스트
    @rate_limit(limit=5, period=1.0, bucket_key="sync_bucket")
    @log_decorator(logger_name="decorator_demo")
    def rate_limited_sync_task(self, index: int):
        return f"SyncAck({index})"

    # [Async] 비동기 함수 제한 테스트 
    @rate_limit(limit=5, period=1.0, bucket_key="async_bucket")
    @log_decorator(logger_name="decorator_demo")
    async def rate_limited_async_task(self, index: int):
        # 비동기 로직 시뮬레이션 (약간의 지연)
        await asyncio.sleep(0.01) 
        return f"AsyncAck({index})"


# ==============================================================================
# [Execution] Runners (Synchronous)
# ==============================================================================
def run_logging_demo(service: DemoService):
    """[Demo 1] 로깅 데코레이터 기능 검증 (Logging, Masking, Context)"""
    print("\n" + "="*60)
    print(" >>> [Demo 1] Logging Capabilities Verification")
    print("="*60)
    
    # 1. Basic Sync
    print("\n[Case 1] Basic Sync Logging")
    res = service.simple_sync_task(user_id=101, action="login")
    print(f"   => Result: {res}")

    # 2. PII Masking & Truncation
    print("\n[Case 2] Security: PII Masking & Truncation")
    res = service.sensitive_data_task(
        username="admin", 
        password="super_secret_pw", 
        token="jwt_token_header.payload.signature"
    )
    print(f"   => Result: {res} (Check log for truncation)")

    # 3. Error Suppression
    print("\n[Case 3] Error Handling: Suppress Error")
    res = service.error_suppression_task()
    if res is None:
        print("   => Success: Error suppressed, returned None.")


def run_retry_demo(service: DemoService, experiments: Dict[str, Any]):
    """[Demo 2] 재시도 데코레이터 기능 검증 (Retry, Backoff, Recovery)"""
    print("\n" + "="*60)
    print(" >>> [Demo 2] Resilience (Retry) Pattern Verification")
    print("="*60)

    # 1. Sync Recovery
    print("\n[Case 1] Sync Job: Retry & Recovery")
    data = experiments.get("sync_retry", {"fail_threshold": 2, "input_payload": "Default"})
    try:
        res = service.retry_sync_recovery(
            threshold=data.get("fail_threshold"),
            data=data.get("input_payload")
        )
        print(f"   => Final Result: {res}")
    except Exception as e:
        print(f"   => Unexpected Failure: {e}")

    # 2. Async Exhaustion (비동기 함수 테스트)
    # [Design Decision] 전체를 비동기로 만들지 않고, 필요한 부분만 asyncio.run으로 실행
    print("\n[Case 2] Async Job: Retry Exhaustion (Fail Fast)")
    data = experiments.get("async_exhaust", {"trigger_timeout": True})
    
    try:
        # 비동기 함수 호출을 위해 일시적으로 이벤트 루프 사용
        asyncio.run(service.retry_async_exhaust(
            trigger_timeout=data.get("trigger_timeout")
        ))
    except TimeoutError:
        print("   => Success: Correctly raised TimeoutError after max retries.")
    except Exception as e:
        print(f"   => Wrong Exception: {e}")

def run_rate_limit_demo(service: DemoService, experiments: Dict[str, Any]):
    """[Demo 3] 속도 제한 데코레이터 검증 (동기 & 비동기)"""
    print("\n" + "="*60)
    print(" >>> [Demo 3] Rate Limiting Verification")
    print("="*60)

    # 3-1. Sync Throttling Test
    print("\n[Case 1] Synchronous Rate Limiting")
    config = experiments.get("rate_limit_sync", {"limit": 5, "period": 1.0, "iterations": 10})
    limit, period, iterations = config["limit"], config["period"], config["iterations"]
    
    print(f"      Settings: {limit} calls / {period} sec (Total: {iterations})")

    start_time = time.perf_counter()
    for i in range(1, iterations + 1):
        try:
            req_start = time.perf_counter()
            result = service.rate_limited_sync_task(index=i)
            elapsed = time.perf_counter() - req_start
            
            status = "⚡ Fast" if elapsed < 0.1 else f"🐢 Throttled ({elapsed:.2f}s)"
            print(f"   Sync Request #{i:02d} | {status} | Result: {result}")
        except Exception as e:
            print(f"   Sync Request #{i:02d} | ❌ Failed: {e}")

    total_time = time.perf_counter() - start_time
    print(f"   => Sync Total Time: {total_time:.4f}s")

    # 3-2. Async Throttling Test
    print("\n[Case 2] Asynchronous Rate Limiting")
    config = experiments.get("rate_limit_async", {"limit": 5, "period": 1.0, "iterations": 10})
    limit, period, iterations = config["limit"], config["period"], config["iterations"]
    
    print(f"      Settings: {limit} calls / {period} sec (Total: {iterations})")

    # 비동기 요청을 순차적으로 보내며 Throttling 확인
    async def _async_runner():
        start_t = time.perf_counter()
        for i in range(1, iterations + 1):
            try:
                req_start = time.perf_counter()
                result = await service.rate_limited_async_task(index=i)
                elapsed = time.perf_counter() - req_start
                
                status = "⚡ Fast" if elapsed < 0.1 else f"🐢 Throttled ({elapsed:.2f}s)"
                print(f"   Async Request #{i:02d} | {status} | Result: {result}")
            except Exception as e:
                print(f"   Async Request #{i:02d} | ❌ Failed: {e}")
        return time.perf_counter() - start_t

    # asyncio.run으로 비동기 러너 실행
    total_time = asyncio.run(_async_runner())
    print(f"   => Async Total Time: {total_time:.4f}s")
    
    if total_time >= period:
        print("   => Success: Throttling Logic Activated for both Sync/Async.")
    else:
        print("   => Warning: Too fast! Throttling might not have worked.")


# ==============================================================================
# [Main Entry Point]
# ==============================================================================
if __name__ == "__main__":
    task_name = "decorator_demo"
    print(f" >>> Initializing System for '{task_name}'...")

    # 1. Config & Logger Init
    try:
        get_config(task_name=task_name)
        LogManager()
        # setup_human_readable_logging(task_name) # 필요 시 해제
        print(f" [Init] System initialized successfully.\n")
    except Exception as e:
        print(f" [Critical Error] {e}")
        sys.exit(1)

    # 2. Load YAML
    try:
        with open("configs/decorator_demo.yml", "r") as f:
            yaml_data = yaml.safe_load(f)
            experiments = yaml_data.get("experiments", {})
    except Exception:
        experiments = {}

    service = DemoService()

    # --------------------------------------------------------------------------
    # [Select Demo] Uncomment the function you want to run
    # --------------------------------------------------------------------------
    
    #run_logging_demo(service)
    #run_retry_demo(service, experiments)
    run_rate_limit_demo(service, experiments)

    print("\n" + "="*60)
    print(" ✅ All Demonstrations Completed.")
    print("="*60 + "\n")