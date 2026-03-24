"""
데이터 파이프라인(ETL) 및 비동기 API 서버 환경에서 함수(동기/비동기) 실행 전후의 로깅, 성능 측정(Latency), 
예외 처리 규칙 강제, 그리고 분산 추적을 위한 실행 컨텍스트(Request ID) 관리를 자동화하는 데코레이터입니다.
src.common.log 모듈에 의존하여 ELK/Datadog 등 중앙 집중식 로그 시스템에 최적화된 로그 페이로드를 생성합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 타겟 함수 호출 및 인자(args, kwargs) 유입
2. Context Injection: Thread-local/ContextVar 기반 Request ID 확인 및 부재 시 자동 주입
3. Sanitization: 입력 인자 내 PII(민감 정보) 마스킹 및 직렬화 안전성 확보 후 Start 로그(INFO/DEBUG) 출력
4. Execution: 동기/비동기 타겟 함수 실행 및 성능 타이머 측정
5. Output: 
   - 성공 시: 반환값을 Truncation 처리하여 길이를 제한한 후 End 로그 출력 및 원본 결과 반환
   - 실패 시: 발생한 예외를 표준 시스템 에러(ETLError)로 래핑하여 Error 로그 출력 후 정책에 따라 Re-raise 또는 Suppress

주요 기능:
- Hybrid Execution Support: `inspect`를 통한 동기(def)/비동기(async def) 함수 자동 감지 및 분기 처리.
- Context Auto-Injection: 멱등성(Idempotent)을 보장하는 Request ID 자동 생성 및 흐름 추적 지원.
- PII Masking: 사전에 정의된 민감 키워드를 식별하여 평문 로깅을 원천 차단하는 데이터 마스킹.
- Smart Truncation: 대용량 데이터(Pandas DataFrame, 대형 JSON/List 등) 로깅 시 OOM 및 로그 병목 방지를 위한 길이 제한.
- Error Handling Policy: 예외 발생 시 표준 규격으로 구조화(Structured) 후 전파 혹은 억제(Suppress) 선택 기능.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 장점: 보일러플레이트 코드를 완벽히 제거(DRY 원칙)하고, 개발자가 비즈니스 로직에만 집중할 수 있는 환경을 제공함. 에러 발생 시 규격화된 포맷을 강제하여 모니터링 알람(Datadog/ELK) 파싱 신뢰성을 극대화함.
- 단점: Python의 `inspect`, `functools.wraps` 사용과 매 호출 시 발생하는 인자 직렬화(`str()` 변환 및 마스킹) 로직으로 인해 마이크로초(us) 단위의 Reflection/Serialization 오버헤드가 발생함. `__str__` 연산이 극도로 무거운 객체가 인자로 전달될 경우 병목이 발생할 수 있음.
- 근거: 데이터 파이프라인과 비동기 API 생태계에서는 수 마이크로초의 성능 최적화보다 PII 유출 방지(컴플라이언스 준수), 디버깅 가능성(Observability), 그리고 시스템 파편화 방지가 압도적으로 중요함. 방어적 프로그래밍 관점에서 안정성과 가독성을 위해 해당 오버헤드를 수용하는 것이 타당함.
"""

import functools
import inspect
import json
import time
from typing import Any, Callable, Dict, Optional, Set, Tuple

from src.common.exceptions import ETLError
from src.common.log import LogManager, request_id_ctx

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# [설계 의도] 보안 강화를 위해 PII(개인식별정보) 및 인증 정보를 상수로 분리.
# 하드코딩된 로직을 배제하고 향후 설정 파일(Config) 주입 형태로 확장하기 용이하도록 구성.
SENSITIVE_KEYS: Set[str] = {
    "password", "passwd", "secret", "token", "apikey", "access_key", 
    "auth", "credential", "private", "card_number"
}

# [설계 의도] ELK Stack, Datadog 등 로그 수집 에이전트의 파싱 부하 및 비용 증가를 막기 위해
# 단일 로그 라인의 최대 길이를 강제 제한하는 안전장치(Guardrail).
DEFAULT_TRUNCATE_LIMIT: int = 2000

# ==============================================================================
# [Helper Functions] Data Sanitization
# ==============================================================================
def _is_dataframe(obj: Any) -> bool:
    """객체가 Pandas DataFrame인지 식별합니다.

    Args:
        obj (Any): 검사할 Python 객체.

    Returns:
        bool: DataFrame일 경우 True, 아닐 경우 False.
    """
    # [설계 의도] pandas 모듈을 직접 import하면 모듈 로딩 타임 지연 및 메모리 낭비가 발생함.
    # 따라서 Duck Typing 방식을 사용하여 객체의 메타데이터(클래스명, 속성)만으로 가볍고 안전하게 검사함.
    return obj.__class__.__name__ == "DataFrame" and hasattr(obj, "shape")

def _serialize_value(value: Any, string_limit: int = 100, container_preview_limit: int = 50) -> str:
    """객체의 타입에 따라 최적화된 로깅용 문자열을 생성합니다.

    Args:
        value (Any): 직렬화할 원본 객체.
        string_limit (int, optional): 스칼라 문자열의 최대 허용 길이. Defaults to 100.
        container_preview_limit (int, optional): 컨테이너 타입의 미리보기 최대 허용 길이. Defaults to 50.

    Returns:
        str: 로깅에 적합하도록 정제 및 축약된 문자열.
    """
    # [설계 의도] 다양한 데이터 타입이 로거에 전달되어 json 직렬화 에러를 유발하는 것을 방지하기 위해,
    # 로깅 전용 안전한 문자열 포맷으로 변환하는 방어적 래핑 적용.
    
    # 1. Pandas DataFrame 처리 (최우선)
    if _is_dataframe(value):
        return f"[DataFrame shape={value.shape}]"
    
    # 2. 컨테이너 타입 (List, Dict, Set, Tuple) 처리
    if isinstance(value, (list, dict, set, tuple)):
        count = len(value)
        s_value = str(value)
        prefix = f"[{type(value).__name__} len={count}] : "
        
        if len(s_value) > container_preview_limit:
            return prefix + s_value[:container_preview_limit] + "..."
        return prefix + s_value

    # 3. 일반 스칼라 타입 (String, Int, Float 등) 처리
    s_value = str(value)
    if len(s_value) > string_limit:
        return s_value[:string_limit] + f"... (truncated, total={len(s_value)})"
    
    return s_value

def _sanitize_args(args: Tuple, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """함수 인자에서 민감 정보(PII)를 식별하고 마스킹 처리하여 반환합니다.

    Args:
        args (Tuple): 원본 함수의 위치 인자(Positional Arguments) 튜플.
        kwargs (Dict[str, Any]): 원본 함수의 키워드 인자(Keyword Arguments) 딕셔너리.

    Returns:
        Dict[str, Any]: JSON 직렬화가 보장되며 PII가 마스킹된 인자 맵.
    """
    # [설계 의도] 개인정보(PII)나 인증 토큰이 평문으로 로그 시스템에 적재되는 컴플라이언스 위반을
    # 원천 차단하기 위해, 키워드 기반 필터링을 함수 진입점 최전방(Entry Point)에 배치함.
    sanitized = {}
    
    # 위치 인자는 파라미터명을 런타임에 알기 어려우므로 'arg_N' 형식의 인덱스 키로 매핑
    for i, arg in enumerate(args):
        sanitized[f"arg_{i}"] = _serialize_value(arg)

    # 키워드 인자는 사전에 정의된 SENSITIVE_KEYS와 대조하여 마스킹 적용
    for key, value in kwargs.items():
        if key.lower() in SENSITIVE_KEYS:
            sanitized[key] = "***** (MASKED)"
        else:
            sanitized[key] = _serialize_value(value)
            
    return sanitized


def _truncate_output(value: Any, limit: int) -> str:
    """반환값이 너무 클 경우 로그 시스템의 부하 및 가독성 저하를 막기 위해 길이를 제한합니다.

    Args:
        value (Any): 함수의 반환값(결과 데이터).
        limit (int): 최대 허용 문자열 길이.

    Returns:
        str: 제한 길이에 맞게 잘린(Truncated) 문자열.
    """
    if _is_dataframe(value):
        return f"[DataFrame shape={value.shape}]"

    s_value = str(value)
    if len(s_value) > limit:
        return s_value[:limit] + f"... (truncated, total_len={len(s_value)})"
    return s_value


# ==============================================================================
# [Main Class] LoggingDecorator
# ==============================================================================
class LoggingDecorator:
    """함수 실행의 생명주기 로깅 및 실행 컨텍스트(Context) 관리를 담당하는 핵심 데코레이터.
    
    Attributes:
        logger_name (Optional[str]): 초기화 시 할당된 로거 이름. 미지정 시 모듈 경로로 대체.
        suppress_error (bool): 에러 발생 시 시스템 패닉을 막고 None을 반환할지 여부를 결정하는 플래그.
        truncate_limit (int): 반환값 로깅의 최대 길이 제한 설정값.
    """

    def __init__(
        self, 
        logger_name: Optional[str] = None, 
        suppress_error: bool = False,
        truncate_limit: int = DEFAULT_TRUNCATE_LIMIT
    ):
        """데코레이터 클래스의 정책 설정 및 초기화를 수행합니다.

        Args:
            logger_name (Optional[str], optional): 명시적으로 사용할 로거 인스턴스 이름. Defaults to None.
            suppress_error (bool, optional): True일 경우 예외 발생 시 전파하지 않고 억제함. Defaults to False.
            truncate_limit (int, optional): 반환 결과 로그의 최대 길이. Defaults to DEFAULT_TRUNCATE_LIMIT.
        """
        self.logger_name = logger_name
        self.suppress_error = suppress_error
        self.truncate_limit = truncate_limit

    def __call__(self, func: Callable) -> Callable:
        """데코레이터 호출 진입점으로, 타겟 함수의 특성(Sync/Async)을 파악하여 알맞은 래퍼를 반환합니다.
        
        Args:
            func (Callable): 데코레이팅할 원본 타겟 함수.

        Returns:
            Callable: 동기 또는 비동기 환경에 맞게 래핑된 클로저 함수.
        """
        # [설계 의도] 로거 이름을 하드코딩하지 않고 런타임에 __module__ 메타데이터를 추출하여
        # 자동으로 네임스페이스를 분리함으로써 추적성(Traceability)을 확보함.
        if not self.logger_name:
            self.logger_name = func.__module__

        # [설계 의도] 단일 데코레이터 클래스로 동기(def)/비동기(async def) 생태계를 모두 커버하여 
        # API 개발자와 데이터 엔지니어의 인지 부하(Cognitive Load)를 줄임.
        if inspect.iscoroutinefunction(func):
            return self._create_async_wrapper(func)
        
        return self._create_sync_wrapper(func)

    def _ensure_context(self) -> None:
        """실행 컨텍스트(Request ID)의 존재를 검증하고 필요 시 자동 생성합니다.
        
        [설계 의도]
        분산 시스템 환경에서 하나의 요청(Request) 흐름을 끝까지 추적하기 위해 Request ID가 필수적임.
        이미 상위 호출자(Middleware 등)가 ID를 발급했다면 이를 재사용(Idempotent)하고, 
        독립적으로 실행된 데몬/워커 스레드일 경우 자체적으로 초기화하여 고아(Orphan) 로그 생성을 방지함.
        """
        current_id = request_id_ctx.get()
        
        if current_id == "system":
            LogManager.set_context()

    def _log_entry(self, logger, func_name: str, args: Tuple, kwargs: Dict[str, Any]) -> None:
        """함수 진입 시점의 흐름 및 입력 파라미터를 로깅합니다.

        Args:
            logger: 활성화된 로거 인스턴스.
            func_name (str): 실행 중인 타겟 함수명.
            args (Tuple): 입력된 위치 인자.
            kwargs (Dict[str, Any]): 입력된 키워드 인자.
        """
        # [설계 의도] 생명주기(흐름 파악)는 INFO 레벨로 출력하여 운영 환경에서의 가시성을 확보하고,
        # 용량이 크고 상세한 파라미터 데이터는 DEBUG 레벨로 은닉하여 스토리지 비용을 최적화함.
        logger.info(f"[{func_name}] START")
        
        try:
            sanitized_input = _sanitize_args(args, kwargs)
            params_str = json.dumps(sanitized_input, ensure_ascii=False)
            logger.debug(f"[{func_name}] Params: {params_str}")
        except Exception:
            # 파라미터 직렬화 실패가 메인 비즈니스 로직에 영향을 주지 않도록 방어(Fail-safe)
            logger.debug(f"[{func_name}] Params: (Serialization Failed)")

    def _log_exit(self, logger, func_name: str, result: Any, elapsed_time: float) -> None:
        """함수 정상 종료 시점의 흐름, 처리 시간(Latency) 및 결과를 로깅합니다.

        Args:
            logger: 활성화된 로거 인스턴스.
            func_name (str): 실행이 완료된 타겟 함수명.
            result (Any): 타겟 함수의 반환값.
            elapsed_time (float): 함수 실행에 소요된 총 시간(초).
        """
        logger.info(f"[{func_name}] END | Time: {elapsed_time:.4f}s")
        
        truncated_result = _truncate_output(result, self.truncate_limit)
        logger.debug(f"[{func_name}] Result: {truncated_result}")

    def _log_error(self, logger, func_name: str, error: Exception, elapsed_time: float) -> None:
        """함수 실행 중 에러 발생 시 예외 정보를 구조화하여 로깅합니다.

        Args:
            logger: 활성화된 로거 인스턴스.
            func_name (str): 실패한 타겟 함수명.
            error (Exception): 발생한 예외 객체.
            elapsed_time (float): 예외 발생까지 소요된 시간(초).
        """
        # [설계 의도] 시스템 내 정의된 비즈니스 예외(ETLError) 여부를 파악하여, 
        # 구조화된 형태(to_dict)로 로그를 남김으로써 Datadog/ELK 기반의 대시보드 및 얼럿 파싱을 용이하게 함.
        if isinstance(error, ETLError):
            error_info = error.to_dict()
            error_msg = (
                f"[{func_name}] FAILED | Time: {elapsed_time:.4f}s | "
                f"Type: {error_info['error_type']} | "
                f"Retry: {error_info['should_retry']} | "
                f"Details: {json.dumps(error_info['details'], ensure_ascii=False)}"
            )
        else:
            error_msg = (
                f"[{func_name}] FAILED | Time: {elapsed_time:.4f}s | "
                f"Error: {type(error).__name__} - {str(error)}"
            )

        logger.error(error_msg, exc_info=True)

    # --------------------------------------------------------------------------
    # [Wrapper 1] Sync Wrapper (일반 함수용)
    # --------------------------------------------------------------------------
    def _create_sync_wrapper(self, func: Callable) -> Callable:
        """동기형(Synchronous) 함수에 대한 데코레이터 래퍼를 생성합니다."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = LogManager.get_logger(self.logger_name)
            func_name = func.__qualname__
            
            self._ensure_context()
            self._log_entry(logger, func_name, args, kwargs)
            
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                
                elapsed = time.perf_counter() - start_time
                self._log_exit(logger, func_name, result, elapsed)
                return result
                
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                
                # [설계 의도] 내장 Exception(예: KeyError, TypeError)이 발생하더라도 
                # 시스템 표준 에러 규격인 ETLError로 래핑하여 다운스트림의 에러 처리 일관성을 보장함.
                if not isinstance(e, ETLError):
                    e = ETLError(
                        message=f"{func_name} 실행 중 예기치 못한 오류 발생",
                        details={"raw_error": str(e)},
                        original_exception=e,
                        should_retry=False
                    )
                
                self._log_error(logger, func_name, e, elapsed)
                
                if self.suppress_error:
                    return None
                raise e

        return wrapper

    # --------------------------------------------------------------------------
    # [Wrapper 2] Async Wrapper (비동기 함수용)
    # --------------------------------------------------------------------------
    def _create_async_wrapper(self, func: Callable) -> Callable:
        """비동기형(Asynchronous/Coroutine) 함수에 대한 데코레이터 래퍼를 생성합니다."""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = LogManager.get_logger(self.logger_name)
            func_name = func.__qualname__
            
            self._ensure_context()
            self._log_entry(logger, func_name, args, kwargs)
            
            start_time = time.perf_counter()
            try:
                # [설계 의도] Event Loop 제어권을 반환하기 위해 await 키워드 사용
                result = await func(*args, **kwargs)
                
                elapsed = time.perf_counter() - start_time
                self._log_exit(logger, func_name, result, elapsed)
                return result
                
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                
                if not isinstance(e, ETLError):
                    e = ETLError(
                        message=f"{func_name} 실행 중 예기치 못한 오류 발생",
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