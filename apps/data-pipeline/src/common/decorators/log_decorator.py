"""
로깅 데코레이터 모듈 (Logging Decorator Module)

함수(동기/비동기) 실행 전후의 로깅, 성능 측정(Latency), 예외 처리,
그리고 실행 컨텍스트(Request ID) 관리를 자동화하는 데코레이터를 제공합니다.

데이터 파이프라인(ETL) 및 비동기 API 서버 환경에서의 사용을 가정하여 설계되었습니다.
이 모듈은 `src.common.log` 모듈에 의존성을 가집니다.

주요 기능:
- Hybrid Support: 일반 함수(def)와 비동기 함수(async def) 자동 감지 및 지원.
- Context Auto-Injection: 실행 컨텍스트가 없을 경우 자동으로 Request ID 생성 (Idempotent).
- PII Masking: 민감 정보(비밀번호, 토큰 등) 자동 마스킹 처리.
- Smart Truncation: 대용량 반환값(DataFrame, 긴 JSON 등) 로그 길이 제한.
- Error Handling Policy: 예외 발생 시 로깅 후 재발생(Re-raise) 또는 무시(Suppress) 선택 가능.

Trade-off:
- Reflection Cost: `inspect` 모듈 사용으로 인한 미세한 오버헤드가 있으나,
  개발 생산성과 코드 중복 제거(DRY)의 이점이 이를 상회함.
- Serialization Safety: 모든 인자를 `str()`로 변환하여 로깅하므로, 
  `__str__` 비용이 높은 객체가 인자로 전달될 경우 성능 영향이 있을 수 있음.
"""

import functools
import inspect
import time
import json
from typing import Any, Callable, Dict, Optional, Set, Tuple, Union

# [Dependency]
# 프로젝트 루트에서 실행된다고 가정하고 절대 경로를 사용합니다.
# ImportError 발생 시, PYTHONPATH 설정을 확인해야 합니다.
try:
    from src.common.log import LogManager, request_id_ctx
except ImportError:
    # 단위 테스트 등에서 상대 경로로 접근해야 할 경우를 위한 예외 처리
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parents[3]))  # src 상위로 경로 추가
    from src.common.log import LogManager, request_id_ctx

from src.common.exceptions import ETLError

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# 로깅 시 마스킹 처리할 민감 키워드 세트 (소문자 기준)
# 보안 강화를 위해 하드코딩된 키워드를 관리합니다.
SENSITIVE_KEYS: Set[str] = {
    "password", "passwd", "secret", "token", "apikey", "access_key", 
    "auth", "credential", "private", "card_number"
}

# 로그에 남길 문자열 최대 길이 (초과 시 Truncate)
# ELK Stack 등 로그 수집기의 부하를 줄이기 위해 제한을 둡니다.
DEFAULT_TRUNCATE_LIMIT: int = 2000


# ==============================================================================
# [Helper Functions] Data Sanitization
# ==============================================================================
def _sanitize_args(args: Tuple, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """함수 인자에서 민감 정보를 마스킹하여 반환합니다.

    JSON 직렬화 가능성을 보장하기 위해 모든 값을 문자열로 변환합니다.

    Args:
        args (Tuple): 위치 인자 튜플.
        kwargs (Dict[str, Any]): 키워드 인자 딕셔너리.

    Returns:
        Dict[str, Any]: 로깅용으로 정제된 인자 맵.
    """
    sanitized = {}
    
    # 위치 인자는 'arg_N' 형식으로 키 생성
    for i, arg in enumerate(args):
        sanitized[f"arg_{i}"] = str(arg)

    # 키워드 인자는 키 이름을 검사하여 마스킹 적용
    for key, value in kwargs.items():
        if key.lower() in SENSITIVE_KEYS:
            sanitized[key] = "***** (MASKED)"
        else:
            sanitized[key] = str(value)
            
    return sanitized


def _truncate_output(value: Any, limit: int) -> str:
    """반환값이 너무 클 경우 로그 가독성을 위해 길이를 제한합니다.

    Args:
        value (Any): 함수의 반환값.
        limit (int): 최대 허용 길이.

    Returns:
        str: 잘린 문자열.
    """
    s_value = str(value)
    if len(s_value) > limit:
        return s_value[:limit] + f"... (truncated, total_len={len(s_value)})"
    return s_value


# ==============================================================================
# [Main Class] LoggingDecorator
# ==============================================================================
class LoggingDecorator:
    """함수 실행 로깅 및 컨텍스트 관리를 위한 데코레이터 클래스.
    
    Attributes:
        logger_name (Optional[str]): 로거 이름. 지정하지 않으면 모듈 경로 사용.
        suppress_error (bool): True일 경우, 예외 발생 시 로그만 남기고 None 반환.
                               False일 경우(기본값), 로그를 남기고 예외를 다시 발생(Re-raise).
        truncate_limit (int): 반환값 로깅 길이 제한.
    """

    def __init__(
        self, 
        logger_name: Optional[str] = None, 
        suppress_error: bool = False,
        truncate_limit: int = DEFAULT_TRUNCATE_LIMIT
    ):
        """데코레이터 설정 초기화.

        Args:
            logger_name (str, optional): 사용할 로거 이름. Defaults to None.
            suppress_error (bool): 에러 전파 방지 여부. Defaults to False.
            truncate_limit (int): 로그 길이 제한. Defaults to 2000.
        """
        self.logger_name = logger_name
        self.suppress_error = suppress_error
        self.truncate_limit = truncate_limit

    def __call__(self, func: Callable) -> Callable:
        """데코레이터 진입점. 대상 함수가 코루틴인지 확인하여 적절한 래퍼를 반환합니다.
        
        Args:
            func (Callable): 데코레이팅할 대상 함수.

        Returns:
            Callable: 래핑된 함수.
        """
        # 대상 함수의 모듈 경로를 파악하여 기본 로거 이름으로 활용
        # 예: src.extractor.service
        if not self.logger_name:
            self.logger_name = func.__module__

        # 비동기 함수(Async) 감지 -> Async Wrapper 사용
        if inspect.iscoroutinefunction(func):
            return self._create_async_wrapper(func)
        
        # 동기 함수(Sync) -> Sync Wrapper 사용
        return self._create_sync_wrapper(func)

    def _ensure_context(self) -> None:
        """현재 컨텍스트(Request ID)를 확인하고, 없으면 새로 생성합니다 (Idempotent).
        
        현재 Request ID가 초기값('system')인 경우에만 새로운 UUID를 생성하여 주입합니다.
        이미 상위 호출자(Caller)에 의해 ID가 설정되어 있다면 이를 유지합니다.
        """
        current_id = request_id_ctx.get()
        
        # 'system'은 log.py에서 정의한 기본값(Context 초기 상태)
        if current_id == "system":
            LogManager.set_context()

    def _log_entry(self, logger, func_name, args, kwargs):
        """함수 진입(Start) 로그를 기록합니다."""
        try:
            sanitized_input = _sanitize_args(args, kwargs)
            # ensure_ascii=False: 한글 깨짐 방지
            params_str = json.dumps(sanitized_input, ensure_ascii=False)
            logger.info(f"[{func_name}] START | Params: {params_str}")
        except Exception:
            # 로깅 과정의 에러가 비즈니스 로직을 방해해서는 안 됨
            logger.warning(f"[{func_name}] START | Params: (Serialization Failed)")

    def _log_exit(self, logger, func_name, result, elapsed_time):
        """함수 정상 종료(Success) 로그를 기록합니다."""
        truncated_result = _truncate_output(result, self.truncate_limit)
        logger.info(
            f"[{func_name}] END | Time: {elapsed_time:.4f}s | "
            f"Result: {truncated_result}"
        )

    def _log_error(self, logger, func_name, error, elapsed_time):
        """에러 발생(Failure) 로그를 기록합니다 (Structured Logging 적용)."""
        if isinstance(error, ETLError):
            # [Rationale] ETLError 계열은 to_dict()를 통해 ELK/Datadog 최적화 데이터를 제공함
            error_info = error.to_dict()
            error_msg = (
                f"[{func_name}] FAILED | Time: {elapsed_time:.4f}s | "
                f"Type: {error_info['error_type']} | "
                f"Retry: {error_info['should_retry']} | "
                f"Details: {json.dumps(error_info['details'], ensure_ascii=False)}"
            )
        else:
            # 일반 Exception 처리
            error_msg = (
                f"[{func_name}] FAILED | Time: {elapsed_time:.4f}s | "
                f"Error: {type(error).__name__} - {str(error)}"
            )

        logger.error(error_msg, exc_info=True)
    # --------------------------------------------------------------------------
    # [Wrapper 1] Sync Wrapper (일반 함수용)
    # --------------------------------------------------------------------------
    def _create_sync_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 매 호출마다 로거 인스턴스를 가져옵니다 (싱글톤이므로 비용 저렴)
            logger = LogManager.get_logger(self.logger_name)
            func_name = func.__qualname__
            
            # 1. Context Check (Auto-Generation)
            self._ensure_context()
            
            # 2. Start Log
            self._log_entry(logger, func_name, args, kwargs)
            
            start_time = time.perf_counter()
            try:
                # 3. Execution
                result = func(*args, **kwargs)
                
                # 4. Success Log
                elapsed = time.perf_counter() - start_time
                self._log_exit(logger, func_name, result, elapsed)
                return result
                
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                
                # [Design Intent] 이미 ETLError인 경우 그대로 사용, 아닐 경우 래핑하여 문맥(Context) 추가
                if not isinstance(e, ETLError):
                    e = ETLError(
                        message=f"Unhandled exception in {func_name}",
                        details={"raw_error": str(e)},
                        original_exception=e,
                        should_retry=False
                    )
                
                self._log_error(logger, func_name, e, elapsed)
                
                if self.suppress_error:
                    return None
                raise e # 래핑된 또는 원본 ETLError 전파

        return wrapper

    # --------------------------------------------------------------------------
    # [Wrapper 2] Async Wrapper (비동기 함수용)
    # --------------------------------------------------------------------------
    def _create_async_wrapper(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = LogManager.get_logger(self.logger_name)
            func_name = func.__qualname__
            
            # 1. Context Check
            self._ensure_context()
            
            # 2. Start Log
            self._log_entry(logger, func_name, args, kwargs)
            
            start_time = time.perf_counter()
            try:
                # 3. Execution (Await)
                result = await func(*args, **kwargs)
                
                # 4. Success Log
                elapsed = time.perf_counter() - start_time
                self._log_exit(logger, func_name, result, elapsed)
                return result
                
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                if not isinstance(e, ETLError):
                    e = ETLError(
                        message=f"Unhandled exception in {func_name}",
                        details={"raw_error": str(e)},
                        original_exception=e
                    )
                self._log_error(logger, func_name, e, elapsed)
                
                if self.suppress_error:
                    return None
                
                raise e

        return wrapper

# 사용 편의성을 위한 Alias
log_decorator = LoggingDecorator