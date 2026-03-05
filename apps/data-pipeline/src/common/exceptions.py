"""
[예외 처리 모듈 (Custom Exceptions)]

ETL 파이프라인 전역에서 발생하는 예외를 정의하고, 구조화된 로깅(Structured Logging)을 지원하는 모듈입니다.
LogManager(log.py)와 결합하여 ELK/Datadog 등의 시스템에서 즉시 쿼리 가능한 형태의 데이터를 제공합니다.

설계 원칙:
1. Pure Data Carrier: 시간(Timestamp) 로직은 배제하고, 에러의 문맥(Context) 정보 보존에 집중합니다.
2. Noise Reduction: 로그 가독성을 해치는 대용량 데이터(Raw HTML 등)는 자동 축약(Truncate)합니다.
3. Hierarchy: ETL 각 단계(Extract, Transform, Load)를 명확히 구분합니다.

데이터 흐름:
Exception 발생 -> to_dict() 호출 -> LogManager가 JSON 직렬화 및 시간(KST/UTC) 태깅 -> 로그 저장
"""

from typing import List, Optional, Dict, Any, Tuple

# ==============================================================================
# 1. Global Base Exception
# ==============================================================================

class ETLError(Exception):
    """ETL 파이프라인의 최상위 추상 예외 클래스.
    
    모든 커스텀 예외는 이 클래스를 상속받아야 합니다.
    Python의 기본 Exception을 확장하여 '재시도 정책'과 '구조화된 데이터' 기능을 추가합니다.
    """

    def __init__(
        self, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        should_retry: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        self.should_retry = should_retry

    def __str__(self) -> str:
        """[Console Debugging] 개발자가 터미널에서 보게 될 텍스트 형식."""
        # 터미널 가독성을 위해 핵심 정보만 한 줄로 요약
        base = f"[{self.__class__.__name__}] {self.message}"
        if self.original_exception:
            base += f" (Caused by: {type(self.original_exception).__name__})"
        return base

    def to_dict(self) -> Dict[str, Any]:
        """[Log System] LogManager가 JSON으로 기록할 때 호출하는 메서드.
        
        시간(timestamp) 정보는 LogManager가 주입하므로 여기서는 제외합니다.
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "should_retry": self.should_retry,
            "cause": str(self.original_exception) if self.original_exception else None
        }


# ==============================================================================
# 2. Global Shared Errors
# ==============================================================================

class ConfigurationError(ETLError):
    """필수 설정값 누락 등 환경 설정 오류 (재시도 불가)."""
    def __init__(self, message: str, key_name: Optional[str] = None):
        details = {"key_name": key_name} if key_name else {}
        super().__init__(message, details=details, should_retry=False)


# ==============================================================================
# 3. Layer-Specific Base Exceptions
# ==============================================================================

class ExtractorError(ETLError):
    """[E] 데이터 수집 단계 예외 Base."""
    pass

class TransformerError(ETLError):
    """[T] 데이터 변환 단계 예외 Base."""
    pass

class LoaderError(ETLError):
    """[L] 데이터 적재 단계 예외 Base."""
    pass


# ==============================================================================
# 4. Extractor Layer Detailed Exceptions
# ==============================================================================

class NetworkConnectionError(ExtractorError):
    """DNS 실패, 타임아웃 등 물리적 연결 오류 (재시도 권장)."""
    def __init__(self, message: str, url: Optional[str] = None, original_exception: Optional[Exception] = None):
        details = {"url": url} if url else {}
        super().__init__(message, details=details, original_exception=original_exception, should_retry=True)


class HttpError(ExtractorError):
    """HTTP 4xx, 5xx 응답 오류.
    
    [Log Noise Reduction]
    HTML 본문 전체를 로깅하면 로그 시스템 용량을 초과하거나 가독성을 해치므로,
    response_body는 최대 500자로 제한(Truncate)합니다.
    """
    
    # 상수로 정의하여 유지보수성 확보
    MAX_BODY_LOG_LENGTH = 500 

    def __init__(
        self, 
        message: str, 
        status_code: int, 
        response_body: Optional[str] = None,
        should_retry: bool = False
    ):
        # Body가 너무 길 경우 안전하게 잘라냄
        preview = "Empty"
        if response_body:
            if len(response_body) > self.MAX_BODY_LOG_LENGTH:
                preview = response_body[:self.MAX_BODY_LOG_LENGTH] + "...(truncated)"
            else:
                preview = response_body

        details = {
            "status_code": status_code,
            "response_body_preview": preview  # 전체 바디 대신 프리뷰만 저장
        }
        super().__init__(message, details=details, should_retry=should_retry)


class RateLimitError(HttpError):
    """429 Too Many Requests (재시도 필수)."""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(message, status_code=429, should_retry=True)
        self.retry_after = retry_after
        self.details["retry_after"] = retry_after


class AuthError(HttpError):
    """401/403 인증 실패 (재시도 불가)."""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message, status_code=status_code, should_retry=False)


# ==============================================================================
# 5. Transformer Layer Detailed Exceptions
# ==============================================================================

class MergeKeyNotFoundError(TransformerError):
    """병합 기준 키(Join Keys)가 대상 데이터프레임에 존재하지 않을 때 발생하는 예외.
    
    DataMerger 실행 전 DataFrame 검증 단계에서 누락된 키를 
    조기에 발견하여, 잘못된 조인으로 인한 데이터 유실이나 메모리 낭비를 방지합니다.
    """

    def __init__(self, message: str, missing_keys: List[str], target_df_name: str) -> None:
        # missing_keys를 Set이 아닌 List로 받는 이유: 
        # Python의 Set 구조는 기본적으로 JSON 직렬화(Serialization)를 지원하지 않으므로,
        # LogManager(ELK/Datadog 연동)에서 에러 없이 바로 파싱할 수 있도록 List 타입을 강제합니다.
        details = {
            "missing_keys": missing_keys,
            "target_df_name": target_df_name
        }
        
        # 데이터 누락은 재시도(Retry)한다고 해결되는 일시적 네트워크 에러가 아니므로
        # should_retry=False로 설정하여 무한 루프나 불필요한 리소스 낭비를 원천 차단합니다.
        super().__init__(message, details=details, should_retry=False)


class MergeColumnCollisionError(TransformerError):
    """조인 키가 아닌 동일한 이름의 컬럼이 두 데이터프레임에 존재할 때 발생하는 예외.
    
    Pandas가 자동으로 `_x`, `_y` 등의 접미사(Suffix)를 붙여 원본 스키마를 
    은밀하게 변형하는 것을 방지하기 위한 방어적 예외입니다.
    """

    def __init__(self, message: str, colliding_columns: List[str]) -> None:
        details = {
            "colliding_columns": colliding_columns
        }
        
        super().__init__(message, details=details, should_retry=False)


class MergeCardinalityError(TransformerError):
    """병합 과정에서 데이터(Row)가 폭발적으로 증가하거나 복제될 때 발생하는 예외.
    
    1:1 또는 N:1 병합을 의도했으나, 조인 키의 중복으로 인해 M:N 조인이 발생하여 
    원본 데이터가 왜곡되는(Row 수가 늘어나는) 현상을 차단합니다.
    """

    def __init__(self, message: str, expected_relation: str, left_shape: Tuple[int, int], right_shape: Tuple[int, int]) -> None:
        # shape 정보를 기록할 때 단순히 row count만 남기지 않고 Tuple 형태(행, 열)를 통째로 보존함으로써, 
        # 컬럼 수가 함께 변형되었는지 여부를 디버깅 단계에서 추적할 수 있게 합니다.
        details = {
            "expected_relation": expected_relation,
            "left_shape": left_shape,
            "right_shape": right_shape
        }
        
        super().__init__(message, details=details, should_retry=False)


class MergeExecutionError(TransformerError):
    """데이터프레임 병합 연산 중 발생하는 예측 불가한 런타임 예외.
    
    컬럼 타입 불일치(dtype mismatch), 메모리 초과(MemoryError) 등 
    pandas의 merge() 호출 과정에서 발생하는 에러를 포착하고 원본 예외를 보존합니다.
    """

    def __init__(self, message: str, join_type: str, original_exception: Optional[Exception] = None) -> None:
        details = {
            "join_type": join_type
        }
        
        super().__init__(
            message, 
            details=details, 
            original_exception=original_exception, 
            should_retry=False
        )

# ==============================================================================
# 6. Loader Layer Detailed Exceptions
# ==============================================================================


