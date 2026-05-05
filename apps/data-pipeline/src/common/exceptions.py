"""
[예외 처리 모듈 (Custom Exceptions)]

ETL 파이프라인 전역(Extract, Transform, Load)에서 발생하는 예외를 정의하고, 구조화된 로깅(Structured Logging)을 지원하는 모듈입니다.
LogManager(log.py)와 결합하여 ELK/Datadog 등의 시스템에서 즉시 쿼리 가능한 형태의 데이터를 제공합니다.

주요 기능:
- Pure Data Carrier: 시간(Timestamp) 로직은 배제하고, 에러의 문맥(Context) 정보 보존에 집중합니다.
- Noise Reduction: 로그 가독성을 해치는 대용량 데이터(Raw HTML 등)는 자동 축약(Truncate)합니다.
- Layer Hierarchy: ETL 각 단계(Extract, Transform, Load)를 명확히 구분하여 장애 격리(Fault Isolation)를 수행합니다.
- Retry Policy Encapsulation: 각 예외 클래스 내부에 재시도 가능 여부(should_retry)를 내장하여 파이프라인의 회복 탄력성을 높입니다.

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

class LoaderValidationError(LoaderError):
    """AbstractLoader의 DTO 검증(_validate_dto) 과정에서 발생하는 예외.
    
    적재 단계로 넘어온 ExtractedDTO 객체의 필수 데이터가 누락되었거나
    스키마가 불일치할 때 발생합니다. 데이터 정합성 문제이므로 재시도하지 않습니다.
    """

    def __init__(
        self, 
        message: str, 
        invalid_fields: List[str], 
        dto_name: str = "ExtractedDTO"
    ) -> None:
        """LoaderValidationError 초기화.

        Args:
            message: 에러 상세 메시지.
            invalid_fields: 유효성 검사를 통과하지 못한 필드명 목록. JSON 직렬화를 위해 List 사용.
            dto_name: 검증에 실패한 DTO 객체의 이름 (기본값: ExtractedDTO).
        """
        details = {
            "invalid_fields": invalid_fields,
            "dto_name": dto_name
        }
        
        # 데이터 누락/형식 오류는 네트워크 재시도로 해결되지 않으므로 should_retry=False
        super().__init__(message, details=details, should_retry=False)


class ZstdCompressionError(LoaderError):
    """S3Loader의 zstd 스트림 압축(_compress_to_zstd_stream) 중 발생하는 예외.
    
    메모리 부족(OOM)이나 바이너리 데이터 인코딩 실패 등 압축 과정의 시스템/데이터 에러를 포착합니다.
    """

    def __init__(
        self, 
        message: str, 
        data_size_bytes: Optional[int] = None, 
        original_exception: Optional[Exception] = None
    ) -> None:
        """ZstdCompressionError 초기화.

        Args:
            message: 에러 상세 메시지.
            data_size_bytes: 압축을 시도했던 원본 데이터의 크기(Byte). OOM 디버깅 용도.
            original_exception: 발생한 원본 예외 (zstandard 에러 등).
        """
        details = {
            "data_size_bytes": data_size_bytes
        }
        
        # 압축 실패는 대부분 메모리나 데이터 손상 문제이므로 즉각적인 재시도보다는 알림이 필요함
        super().__init__(
            message, 
            details=details, 
            original_exception=original_exception, 
            should_retry=False
        )


class S3UploadError(LoaderError):
    """S3Loader의 S3 적재(_upload_stream, _execute_multipart_upload) 중 발생하는 예외.
    
    Boto3 클라이언트 네트워크 타임아웃, 권한 거부(Access Denied), 
    또는 멀티파트 업로드 실패 시 발생하며 원인에 따라 재시도를 수행해야 합니다.
    """

    def __init__(
        self, 
        message: str, 
        bucket_name: str, 
        s3_key: str, 
        upload_id: Optional[str] = None, 
        is_multipart: bool = False,
        original_exception: Optional[Exception] = None
    ) -> None:
        """S3UploadError 초기화.

        Args:
            message: 에러 상세 메시지.
            bucket_name: 대상 S3 버킷 이름.
            s3_key: 적재를 시도한 S3 Object Key.
            upload_id: 멀티파트 업로드 시 부여된 고유 ID (실패 시 Abort 처리를 위한 추적용).
            is_multipart: 멀티파트 업로드 여부.
            original_exception: Boto3 등에서 발생한 원본 예외 (botocore.exceptions.ClientError 등).
        """
        details = {
            "bucket_name": bucket_name,
            "s3_key": s3_key,
            "upload_id": upload_id,
            "is_multipart": is_multipart
        }
        
        # S3 업로드 실패의 대부분은 일시적인 네트워크 불안정이나 스로틀링(Throttling)이므로 재시도 권장
        # 단, 권한 에러(403)의 경우 Exception Handler 단에서 original_exception을 분석하여 Retry를 중단하도록 설계함
        super().__init__(
            message, 
            details=details, 
            original_exception=original_exception, 
            should_retry=True
        )

# ==============================================================================
# 7. Reader Layer Detailed Exceptions
# ==============================================================================

class ReaderError(ETLError):
    """[R] 데이터 읽기(Reader) 단계 예외 Base."""
    pass


class ReaderInitializationError(ReaderError):
    """AbstractReader 및 하위 구현체의 초기화 실패 시 발생하는 예외.
    
    클라이언트(Boto3, psycopg2 등) 생성 실패, 환경 변수 누락 등
    데이터를 읽기 전 단계에서 발생하는 구성 오류를 처리합니다.
    """

    def __init__(
        self,
        message: str,
        provider_name: str,
        original_exception: Optional[Exception] = None
    ) -> None:
        details = {
            "provider_name": provider_name
        }
        super().__init__(
            message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class DataReadStreamError(ReaderError):
    """스트리밍 방식으로 데이터를 읽는 과정에서 발생하는 예외.
    
    S3 파일 객체 파싱 에러, 네트워크 단절로 인한 스트림 끊김,
    또는 압축 해제(Zstd) 실패 등 런타임 데이터 I/O 오류를 포착합니다.
    """

    def __init__(
        self,
        message: str,
        source_path: str,
        chunk_index: Optional[int] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        details = {
            "source_path": source_path,
            "chunk_index": chunk_index
        }
        # 스트림 읽기 중 발생한 일시적 네트워크 에러일 수 있으므로 재시도를 허용함
        super().__init__(
            message,
            details=details,
            original_exception=original_exception,
            should_retry=True
        )


class UnsupportedFormatError(ReaderError):
    """Reader가 지원하지 않는 파일 포맷이나 스키마를 만났을 때 발생하는 예외.
    
    예를 들어, S3ZstdStreamingReader가 .parquet 파일을 처리하려고 하거나,
    PostgresReader가 예상치 못한 테이블 스키마를 반환받았을 때 발생합니다.
    """

    def __init__(
        self,
        message: str,
        expected_format: str,
        actual_format: str
    ) -> None:
        details = {
            "expected_format": expected_format,
            "actual_format": actual_format
        }
        super().__init__(message, details=details, should_retry=False)