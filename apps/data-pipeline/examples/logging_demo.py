"""
로깅 데코레이터 사용 예제 및 검증 (Logging Decorator Demo).

이 스크립트는 `src.common.decorators.log_decorator`의 주요 기능을 시연합니다.
동기(Sync), 비동기(Async) 함수 적용 방법과 예외 처리(Error Handling),
민감 데이터 마스킹(PII Masking) 기능을 확인할 수 있습니다.

Usage:
    프로젝트 루트 디렉토리에서 아래 명령어로 실행하세요.
    $ python examples/logging_demo.py
"""

import sys
import asyncio
import time
from pathlib import Path
from typing import Dict, Any

# [System Path Setup]
# examples 폴더에서 src 모듈을 import 하기 위해 프로젝트 루트 경로를 동적으로 추가합니다.
# 이는 TensorFlow 예제 코드들이 소스 설치 전 로컬 테스트를 위해 사용하는 패턴입니다.
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

try:
    from src.common.decorators import log_decorator
    from src.common.config import get_config
    from src.common.log import LogManager
except ImportError as e:
    print(f"\n[ERROR] 모듈을 찾을 수 없습니다. 프로젝트 루트에서 실행했는지 확인하세요.\nDetails: {e}")
    sys.exit(1)


# ==============================================================================
# [Section 1] Basic Usage: Synchronous Functions
# ==============================================================================
# 가장 기본적인 사용법입니다. 함수 위에 데코레이터를 붙이면
# 자동으로 [START], [END] 로그와 실행 시간(Latency)이 기록됩니다.
@log_decorator(logger_name="DEMO_SYNC")
def basic_sync_task(user_id: int, action: str) -> str:
    """일반적인 동기 함수에 로깅을 적용하는 예시입니다."""
    print(f"   [Logic] Processing user {user_id} action: {action}")
    time.sleep(0.1)  # 작업 시간 시뮬레이션
    return f"Action '{action}' completed"


# ==============================================================================
# [Section 2] Advanced Usage: Asynchronous Functions
# ==============================================================================
# `async def` 함수도 별도 변경 없이 동일한 데코레이터를 사용합니다.
# 데코레이터가 내부적으로 코루틴을 감지하여 await 처리를 수행합니다.
@log_decorator(logger_name="DEMO_ASYNC")
async def fetch_data_async(url: str, retries: int = 3) -> Dict[str, Any]:
    """비동기 함수(I/O 바운드 작업)에 로깅을 적용하는 예시입니다."""
    print(f"   [Logic] Fetching data from {url}...")
    await asyncio.sleep(0.2)  # 비동기 I/O 시뮬레이션
    return {"status": 200, "url": url, "data": "payload"}


# ==============================================================================
# [Section 3] Data Safety: PII Masking & Truncation
# ==============================================================================
# 로그에 남으면 안 되는 민감 정보(비밀번호 등)와
# 로그 용량을 초과하는 대용량 반환값을 처리하는 방법을 보여줍니다.
@log_decorator(logger_name="DEMO_SECURITY", truncate_limit=20)
def sensitive_task(username: str, password: str, token: str) -> str:
    """
    민감 정보 마스킹 및 반환값 길이 제한 예시.
    
    특징:
    1. 'password', 'token' 등의 파라미터는 로그에 '*****'로 기록됩니다.
    2. 반환값이 truncate_limit(20자)를 넘으면 자동으로 잘립니다.
    """
    print(f"   [Logic] Authenticating {username}...")
    # 매우 긴 토큰을 반환한다고 가정
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." * 10


# ==============================================================================
# [Section 4] Reliability: Error Handling Policies
# ==============================================================================
# 예외 발생 시 동작 방식을 제어하는 `suppress_error` 옵션 사용법입니다.

@log_decorator(logger_name="DEMO_FAIL_FAST", suppress_error=False)
def critical_job():
    """[Default] 에러 발생 시 로그를 남기고, 예외를 다시 발생(Re-raise)시킵니다."""
    print("   [Logic] Critical job started (Will Fail)")
    raise ValueError("Critical System Failure!")

@log_decorator(logger_name="DEMO_RESILIENT", suppress_error=True)
def optional_job():
    """[Option] 에러 발생 시 로그만 남기고, None을 반환하여 프로그램 중단을 막습니다."""
    print("   [Logic] Optional job started (Will Fail safely)")
    raise KeyError("Missing Optional Key")


# ==============================================================================
# [Main Execution]
# ==============================================================================
async def main():
    """모든 예제 시나리오를 순차적으로 실행하고 검증합니다."""
    
    print("\n" + "="*80)
    print(" >>> Logging Decorator Demo")
    print("="*80)

    try:
        get_config(task_name="logging_demo")
        print(" [Init] Configuration loaded successfully.")
    except Exception as e:
        print(f" [Error] Failed to load configuration: {e}")
        print("         Please ensure 'configs/logging_demo.yml' exists.")
        return

    # 0. Logger 초기화
    LogManager()

    # Scenario 1: Sync Function
    print("\n[1/4] Running Synchronous Task...")
    result = basic_sync_task(user_id=101, action="click_button")
    print(f"   -> Result: {result}")

    # Scenario 2: Async Function
    print("\n[2/4] Running Asynchronous Task...")
    result = await fetch_data_async("https://api.tensorflow.org", retries=5)
    print(f"   -> Result: {result}")

    # Scenario 3: Security & Truncation
    print("\n[3/4] Running Sensitive Task (Check Logs for Masking)...")
    result = sensitive_task(username="admin", password="my_secret_pw", token="access_key")
    print(f"   -> Result: {result} (Truncated in logs?)")

    # Scenario 4: Error Handling
    print("\n[4/4] Running Error Handling Scenarios...")
    
    # 4-1. Suppress Error (Resilient)
    print("   Running Optional Job (Should handle error internally)...")
    res = optional_job()
    if res is None:
        print("   -> Success: Error was suppressed and returned None.")

    # 4-2. Fail Fast (Critical)
    print("   Running Critical Job (Should crash)...")
    try:
        critical_job()
    except ValueError as e:
        print(f"   -> Success: Caught expected exception: {e}")

    print("\n" + "="*80)
    print(" ✅ All demos completed successfully.")
    print("    Please check the console logs above to verify formats.")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Windows 환경의 EventLoop 정책 호환성 처리 (Python 3.8+ on Windows)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())