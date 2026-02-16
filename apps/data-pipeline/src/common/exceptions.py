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

from typing import Optional, Dict, Any

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



# ==============================================================================
# 6. Loader Layer Detailed Exceptions
# ==============================================================================


