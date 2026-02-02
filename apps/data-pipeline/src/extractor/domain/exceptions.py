class ExtractorError(Exception):
    """Extractor 모듈의 최상위 사용자 정의 예외 클래스.
    
    모든 하위 예외는 이 클래스를 상속받아야 하며,
    try-except 블록에서 이 예외를 잡으면 Extractor 관련 모든 오류를 처리할 수 있습니다.
    """
    pass

class NetworkError(ExtractorError):
    """네트워크 통신 실패 시 발생하는 예외 (연결 시간 초과, DNS 오류 등)."""
    pass

class AuthError(ExtractorError):
    """API 인증 실패 시 발생하는 예외 (토큰 만료, 키 오류 등)."""
    pass

class ParseError(ExtractorError):
    """응답 데이터 파싱 실패 시 발생하는 예외 (잘못된 JSON 형식 등)."""
    pass

class RateLimitError(ExtractorError):
    """API 호출 횟수 제한(Rate Limit) 초과 시 발생하는 예외."""
    pass