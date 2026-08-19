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

class ReaderError(ETLError):
    """[R] 데이터 읽기(Reader) 단계 예외 Base."""
    pass

class BuilderError(ETLError):
    """[B] Builder 계층에서 발생하는 예외를 정의하는 커스텀 에러 클래스."""
    pass

class PreprocessorError(ETLError):
    """[P] Preprocessor 계층에서 발생하는 예외를 정의하는 커스텀 에러 클래스."""
    pass

class ModelError(ETLError):
    """[M] 모델링, 평가, XAI 및 백테스팅 단계 예외 Base."""
    pass

class FeatureError(ETLError):
    """[F] 피처 엔지니어링 및 정상성 변환 단계 예외 Base."""
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

class TransformerInitializationError(ETLError):
    """Transformer 구체 클래스의 지연 초기화, 동적 임포트, 정책 바인딩 중 발생하는 오류.
    
    [설계 의도] 
    데이터를 실제로 변환(Transform)하기 전, 파이프라인 준비 단계에서 발생하는 
    오류를 `TransformerError`(런타임 변환 오류)와 분리하여 추적성(Observability)을 높입니다.
    """
    
    def __init__(
        self, 
        message: str, 
        original_exception: Exception = None
    ):
        """
        Args:
            message (str): 에러 발생 상세 사유.
            original_exception (Exception, optional): 근본 원인이 된 파이썬 네이티브 예외.
        """
        super().__init__(
            message=message, 
            should_retry=False, # 초기화 에러는 코드/설정 문제이므로 재시도(Retry)하지 않음
            original_exception=original_exception
        )

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

class ReaderServiceError(ReaderError):
    """ReaderService 계층의 파라미터 유효성 및 라우팅 단계에서 발생하는 예외.
    
    데이터 I/O 물리 계층(AbstractReader)으로 넘어가기 전, Entry Point에서 
    잘못된 스토리지 식별자나 유효하지 않은 source_path가 유입되는 것을 차단합니다.
    """

    def __init__(
        self,
        message: str,
        target_reader: Optional[str] = None,
        invalid_path: Optional[str] = None
    ) -> None:
        details = {}
        if target_reader:
            details["target_reader"] = target_reader
        if invalid_path:
            details["invalid_path"] = invalid_path
            
        # 파라미터 누락/오류는 재시도해도 실패하므로 should_retry=False로 강제함
        super().__init__(
            message,
            details=details,
            should_retry=False
        )

# ==============================================================================
# 8. Builder Layer Detailed Exceptions
# ==============================================================================

class BuilderDataMismatchError(BuilderError):
    """Builder 연산 중 입력 데이터프레임과 식별자의 정합성이 맞지 않을 때 발생하는 예외."""

    def __init__(
        self,
        message: str,
        df_count: int,
        job_count: int
    ) -> None:
        details = {
            "df_count": df_count,
            "job_count": job_count
        }
        # 물리적 데이터 불일치는 재시도해도 무조건 실패하므로 should_retry=False 강제
        super().__init__(
            message,
            details=details,
            should_retry=False
        )


class BuilderServiceError(BuilderError):
    """BuilderService 계층의 사전 검증 및 파이프라인 제어 중 발생하는 예외."""
    
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        details = {}
        if original_exception:
            details["original_exception_type"] = type(original_exception).__name__
            
        super().__init__(message, details=details, should_retry=False)

# ==============================================================================
# 9. Preprocessor Layer Detailed Exceptions
# ==============================================================================

class EmptyInputDataError(PreprocessorError):
    """입력 금융 시계열 데이터프레임이 완전히 비어있을 때 발생하는 예외 클래스.
    
    데이터 수집 누락이나 업스트림 파이프라인 중단으로 인해 유입된 데이터가 0건일 때 발생하며,
    정적 파일 유실/오류이므로 재시도하지 않습니다.
    """

    def __init__(self, message: str) -> None:
        """EmptyInputDataError 초기화."""
        super().__init__(message=message, details={}, should_retry=False)


class InsufficientLookbackWindowError(PreprocessorError):
    """유입된 거래일수가 설정된 슬라이딩 윈도우 크기보다 작아 통계적 진단이 불가능할 때 발생하는 예외 클래스.
    
    컨텍스트 확보를 위한 물리 거래일수가 미달인 상태로 슬라이딩 연산 강행 시 발생하는 
    윈도우 슬라이싱 아웃오브바운드 오류를 차단합니다.
    """

    def __init__(self, message: str, current_length: int, required_window_size: int) -> None:
        """InsufficientLookbackWindowError 초기화.

        Args:
            message (str): 에러 상세 메시지.
            current_length (int): 실제 유입된 원본 시계열의 물리적 총 거래일수.
            required_window_size (int): 아키텍처상 요구되는 필수 슬라이딩 룩백 윈도우 크기.
        """
        details = {
            "current_length": current_length,
            "required_window_size": required_window_size
        }
        super().__init__(message=message, details=details, should_retry=False)

class ImputationExecutionError(PreprocessorError):
    """결측치 보간 태스크 레이어(Imputation Task Layer) 연산 중 발생하는 런타임 예외.

    하위 보간 알고리즘(LOCF, 로그 수익률 추세 확장, 이동평균 평균 회귀, 칼만 필터)의 판다스/넘파이/수리
    연산 과정에서 발생하는 예기치 못한 행렬 차원 비정합성, 선형대수 연산 불능(Singular Matrix Error),
    타입 불일치 및 메모리 장애 상황을 포착하고 원본 예외와 핵심 컨텍스트(자산 코드 목록, 임퓨터 타입)를
    유실 없이 상위 오케스트레이터로 전파하기 위해 디자인된 방어적 예외 클래스입니다.
    """

    def __init__(
        self,
        message: str,
        imputer_type: str,
        target_assets: List[str],
        original_exception: Optional[Exception] = None
    ) -> None:
        """ImputationExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            imputer_type (str): 에러가 발생한 구체적 보간 알고리즘 컴포넌트 명칭 
            target_assets (List[str]): 결측치 보간 도중 문제가 발생한 대상 자산 코드 목록.
            original_exception (Exception, optional): 하위 라이브러리에서 발생하여 근본 원인이 된 원본 시스템 예외 객체.
        """
        details = {
            "imputer_type": imputer_type,
            "target_assets": target_assets
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )

class OutlierDiagnosisExecutionError(PreprocessorError):
    """이상치 진단 태스크 레이어(Outlier Diagnosis Task Layer) 연산 중 발생하는 런타임 예외.

    하위 이상치 탐지 알고리즘 전략(IQR, Z-Score, Isolation Forest)의 판다스/넘파이/사이킷런
    연산 과정에서 발생하는 행렬 차원 비정합성, 모델 피팅 에러, 난수 고정 실패 및 메모리 장애
    상황을 포착하여 원본 예외와 핵심 컨텍스트를 유실 없이 상위 오케스트레이터로 전파합니다.
    """

    def __init__(
        self,
        message: str,
        strategy_type: str,
        original_exception: Optional[Exception] = None
    ) -> None:
        """OutlierDiagnosisExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            strategy_type (str): 에러가 발생한 구체적인 이상치 탐지 전략 컴포넌트 명칭.
            original_exception (Exception, optional): 하위 라이브러리에서 발생하여 근본 원인이 된 원본 시스템 예외 객체.
        """
        details = {
            "strategy_type": strategy_type
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class OutlierRefinementExecutionError(PreprocessorError):
    """이상치 정제 태스크 레이어(Outlier Refinement Task Layer) 연산 중 발생하는 런타임 예외.

    이상치 진단 리포트의 불리언 마스크를 기반으로 원본 행렬을 알고리즘적 결측치(NaN)로 치환하거나,
    지정된 상하한 임계값으로 조정(Clipping)하는 판다스 벡터 연산 및 셰이프 매칭 과정에서 발생하는
    예기치 못한 장애 상황을 포착하고 전파합니다.
    """

    def __init__(
        self,
        message: str,
        refinement_policy: str,
        original_exception: Optional[Exception] = None
    ) -> None:
        """OutlierRefinementExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            refinement_policy (str): 에러가 발생한 구체적인 이상치 정제 처리 정책 명칭.
            original_exception (Exception, optional): 하위 판다스 연산 레이어에서 발생한 원본 예외 객체.
        """
        details = {
            "refinement_policy": refinement_policy
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )

class PreprocessorFactoryError(PreprocessorError):
    """PreprocessorFactory 계층에서 하이퍼파라미터 조건 바인딩 및 태스크 객체 생성 중 발생하는 예외.
    
    설정 파일(.yml)의 파라미터 타입 불일치나 지원하지 않는 전략 문자열이 유입되었을 때 발생하며,
    컴포넌트 조립 단계의 정적 오류이므로 재시도(Retry)하지 않습니다.
    """
    
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        """PreprocessorFactoryError 초기화.

        Args:
            message (str): 에러 발생 상세 사유 메시지.
            original_exception (Exception, optional): 근본 원인이 된 시스템 혹은 판다스/넘파이 원본 예외 객체.
        """
        details = {}
        if original_exception:
            details["original_exception_type"] = type(original_exception).__name__
            
        super().__init__(
            message=message, 
            details=details, 
            original_exception=original_exception, 
            should_retry=False
        )

class PreprocessorServiceError(PreprocessorError):
    """PreprocessorService 계층의 설정 파싱 및 태스크 오케스트레이션 단계에서 발생하는 예외.
    
    하위 판다스/넘파이 연산 계층에서 발생하는 예측 불가능한 시스템 장애(MemoryError 등)를 포착하여
    콘텍스트를 누수 없이 보존하며, 재시도(Retry)가 불가능한 정적 오류로 취급합니다.
    """
    
    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        """PreprocessorServiceError 초기화.

        Args:
            message (str): 에러 발생 상세 사유 메시지.
            original_exception (Exception, optional): 근본 원인이 된 하위 시스템의 원본 예외 객체.
        """
        details = {}
        if original_exception:
            details["original_exception_type"] = type(original_exception).__name__
            
        super().__init__(
            message=message, 
            details=details, 
            original_exception=original_exception, 
            should_retry=False
        )

# ==============================================================================
# 10. Modeler Layer Detailed Exceptions
# ==============================================================================

class ModelNotFittedError(ModelError):
    """모델 학습(fit)이 완료되지 않은 상태에서 추론, 평가 또는 XAI 연산을 시도할 때 발생하는 예외.
    
    미학습 모델 인스턴스에 의한 예측값 왜곡 및 잘못된 파이프라인 구동을 사전에 차단하기 위한 방어적 예외입니다.
    """

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        operation_type: Optional[str] = None
    ) -> None:
        """ModelNotFittedError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            model_name (Optional[str]): 학습되지 않은 상태로 호출된 모델 컴포넌트 명칭.
            operation_type (Optional[str]): 실행을 시도한 메서드 명칭 (예: predict, evaluate, calculate_shap_values).
        """
        # [설계 의도] 호출된 모델명과 연산 유형을 명시하여 미학습 인스턴스 참조 지점을 로그 시스템에서 신속히 식별함
        details = {}
        if model_name:
            details["model_name"] = model_name
        if operation_type:
            details["operation_type"] = operation_type

        super().__init__(
            message=message,
            details=details,
            should_retry=False
        )


class ModelTrainingExecutionError(ModelError):
    """모델 학습(fit) 또는 튜닝 실행 중 연산 실패, 수리적 발산, 데이터 타입 불일치가 발생할 때 발생하는 예외.
    
    알고리즘 내부 학습 실패나 경사하강법 폭주 등 런타임 오류를 포착하여 원본 예외와 함께 상위 오케스트레이터로 전파합니다.
    """

    def __init__(
        self,
        message: str,
        model_name: str,
        hyperparameters: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        """ModelTrainingExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            model_name (str): 학습을 수행 중이던 모델 컴포넌트 명칭.
            hyperparameters (Optional[Dict[str, Any]]): 학습 시 주입된 하이퍼파라미터 설정 정보.
            original_exception (Optional[Exception]): 근본 원인이 된 라이브러리(scikit-learn, XGBoost, PyTorch 등) 원본 예외 객체.
        """
        # [설계 의도] 하이퍼파라미터 조합을 details에 포함시켜 실패한 파라미터 영역을 디버깅 단계에서 즉시 재현할 수 있도록 함
        details = {
            "model_name": model_name,
            "hyperparameters": hyperparameters or {}
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class ModelEvaluationExecutionError(ModelError):
    """모델 성능 지표(RMSE, MAE, MDA 등) 계산 및 예측값 정렬/차원 검증 도중 발생하는 예외.
    
    입력 X_test와 y_test 간의 행 인덱스 비정합성이나 수리적 평가 지표 연산 불능 상태를 차단합니다.
    """

    def __init__(
        self,
        message: str,
        model_name: str,
        metric_name: Optional[str] = None,
        y_true_shape: Optional[Tuple[int, ...]] = None,
        y_pred_shape: Optional[Tuple[int, ...]] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        """ModelEvaluationExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            model_name (str): 평가 대상 모델 컴포넌트 명칭.
            metric_name (Optional[str]): 연산 실패가 발생한 산출 지표 명칭 (예: RMSE, MAE, MDA).
            y_true_shape (Optional[Tuple[int, ...]]): 실제 정답 라벨 데이터의 형상(Shape).
            y_pred_shape (Optional[Tuple[int, ...]]): 모델 예측 결과 데이터의 형상(Shape).
            original_exception (Optional[Exception]): 근본 원인이 된 원본 시스템/numpy 예외 객체.
        """
        # [설계 의도] 형상 정보(Tuple)를 기록하여 시계열 인덱스 차원 불일치나 누락으로 인한 지표 오산출을 명확히 진단함
        details = {
            "model_name": model_name,
            "metric_name": metric_name,
            "y_true_shape": y_true_shape,
            "y_pred_shape": y_pred_shape
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class ModelArtifactError(ModelError):
    """모델 아티팩트(.pkl, .pt 등)의 파일 저장(save_artifact) 및 복원(load_artifact) 과정에서 발생하는 예외.
    
    파일 경로 부재, 직렬화 실패, 권한 오류 또는 체크포인트 무결성 손상을 포착합니다.
    """

    def __init__(
        self,
        message: str,
        artifact_path: str,
        operation_type: str,
        original_exception: Optional[Exception] = None
    ) -> None:
        """ModelArtifactError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            artifact_path (str): 아티팩트 저장 또는 로드를 시도한 물리 파일 경로.
            operation_type (str): 수행 중이던 I/O 작업 유형 ('save' 또는 'load').
            original_exception (Optional[Exception]): pickle, joblib, torch I/O 등에서 발생한 원본 예외.
        """
        # [설계 의도] 파일 시스템 경로와 작업 유형을 보존하여 스토리지 권한/경로오류 및 체크포인트 파일 손상을 즉시 구분함
        details = {
            "artifact_path": artifact_path,
            "operation_type": operation_type
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class ShapCalculationError(ModelError):
    """XAI(Explainable AI) 해석을 위한 SHAP Value 산출 및 Explainer 객체 실행 중 발생하는 예외.
    
    트리/선형 알고리즘별 Explainer 호환성 오류, 행렬 차원 문제, 메모리 초과 현상을 포착합니다.
    """

    def __init__(
        self,
        message: str,
        model_name: str,
        explainer_type: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        """ShapCalculationError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            model_name (str): SHAP 해석 대상 모델 명칭.
            explainer_type (Optional[str]): 사용된 SHAP Explainer 종류 (예: TreeExplainer, LinearExplainer, KernelExplainer).
            original_exception (Optional[Exception]): shap 라이브러리 연산 중 발생한 원본 예외.
        """
        # [설계 의도] SHAP Explainer 호환성 여부를 파악할 수 있도록 모델 및 Explainer 유형을 details에 저장함
        details = {
            "model_name": model_name,
            "explainer_type": explainer_type
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class HyperparameterOptimizationError(ModelError):
    """Optuna 기반 하이퍼파라미터 최적화(HPO) 실행 중 검색 공간(Search Space) 설정 오류나 Trial 중단 시 발생하는 예외.
    
    Stage 1 / Stage 2 HPO 과정에서의 Trial 수렴 실패나 잘못된 파라미터 탐색 범위를 포착합니다.
    """

    def __init__(
        self,
        message: str,
        study_name: str,
        trial_number: Optional[int] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        """HyperparameterOptimizationError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            study_name (str): Optuna Study 식별 명칭.
            trial_number (Optional[int]): 장애가 발생한 특정 Trial 회차 번호.
            original_exception (Optional[Exception]): Optuna 내부 또는 하위 목적함수에서 발생한 원본 예외.
        """
        # [설계 의도] Study 및 실패한 Trial 번호를 추적하여 특정 하이퍼파라미터 조합에서의 예외 상황을 신속히 고립시킴
        details = {
            "study_name": study_name,
            "trial_number": trial_number
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class EnsembleExecutionError(ModelError):
    """이종 앙상블(Weighted/Stacking) 모델 결합, 가중치 산출 및 서브 모델 병합 연산 중 발생하는 예외.
    
    서브 모델 간 예측값 차원 불일치, 가중치 최적화 실패, 스태킹 메타 모델 피팅 오류를 포착합니다.
    """

    def __init__(
        self,
        message: str,
        ensemble_type: str,
        sub_model_names: Optional[List[str]] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        """EnsembleExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            ensemble_type (str): 앙상블 기법 유형 (예: WeightedEnsemble, StackingEnsemble).
            sub_model_names (Optional[List[str]]): 앙상블을 구성하는 하위 서브 모델 명칭 목록.
            original_exception (Optional[Exception]): 앙상블 결합 연산 중 발생한 원본 예외.
        """
        # [설계 의도] JSON 직렬화를 위해 서브 모델 목록을 List 타입으로 유지하고 앙상블 결합 방식 컨텍스트를 보존함
        details = {
            "ensemble_type": ensemble_type,
            "sub_model_names": sub_model_names or []
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class BacktestExecutionError(ModelError):
    """Champion-Challenger 백테스팅(Out-of-Sample / TimeSeriesSplit), 금융 지표 산출, 대응표본 t-검정 도중 발생하는 예외.
    
    일자별 오차 차이 계산 불능, t-검정 데이터 부족, Sharpe Ratio 산출 중 분모 0 오류 상황을 포착합니다.
    """

    def __init__(
        self,
        message: str,
        backtest_period: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        """BacktestExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            backtest_period (Optional[str]): 백테스팅이 진행 중이던 날짜/시계열 구간 정보.
            original_exception (Optional[Exception]): 통계 검정(scipy) 또는 금융 지표 연산 중 발생한 원본 예외.
        """
        # [설계 의도] 통계 검정 실패 및 금융 지표 왜곡이 발생한 백테스팅 시계열 구간을 보존하여 시계열 데이터 결함 원인을 추적함
        details = {
            "backtest_period": backtest_period
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )

# ==============================================================================
# 11. Feature Layer Detailed Exceptions
# ==============================================================================

class FeatureInitializationError(FeatureError):
    """Feature Factory 및 Config 매핑 단계에서 파라미터 바인딩이나 Task 객체 생성 중 발생하는 예외.
    
    설정 파일(.yml) 내 파라미터 타입 불일치나 존재하지 않는 피처 Task 명칭 유입 시 발생하며,
    컴포넌트 조립 단계의 정적 오류이므로 재시도(Retry)하지 않습니다.
    """

    def __init__(
        self,
        message: str,
        task_name: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ) -> None:
        """FeatureInitializationError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            task_name (Optional[str]): 초기화에 실패한 피처 태스크 명칭.
            original_exception (Optional[Exception]): 근본 원인이 된 원본 시스템 예외.
        """
        # [설계 의도] 초기화 실패 태스크를 details 사전으로 관리하여 파이프라인 기동 전 바인딩 오류를 명확히 진단함
        details = {}
        if task_name:
            details["task_name"] = task_name

        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class RequiredColumnNotFoundError(FeatureError):
    """피처 산출에 필요한 필수 원본 컬럼(가격, 거래량, 금리 등)이 데이터프레임에 존재하지 않을 때 발생하는 예외.
    
    Lookback 윈도우 계산 전 입력 데이터의 스키마 무결성을 검증하여,
    잘못된 컬럼 참조로 인한 계산 중단이나 데이터 오염을 조기에 차단합니다.
    """

    def __init__(
        self,
        message: str,
        missing_columns: List[str],
        task_name: Optional[str] = None
    ) -> None:
        """RequiredColumnNotFoundError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            missing_columns (List[str]): 누락된 필수 컬럼명 목록 (JSON 직렬화를 위해 List 사용).
            task_name (Optional[str]): 컬럼 누락이 감지된 피처 태스크 명칭.
        """
        # [설계 의도] 누락된 컬럼 목록을 List로 정형화하여 LogManager를 통한 JSON 직렬화 시 파싱 오류를 방지함
        details = {
            "missing_columns": missing_columns,
            "task_name": task_name or "UnknownTask"
        }
        super().__init__(
            message=message,
            details=details,
            should_retry=False
        )


class FeatureCalculationExecutionError(FeatureError):
    """피처 엔지니어링 태스크(Task) 연산 중 발생하는 런타임 수리/통계 예외.
    
    롤링 윈도우 시계열 연산, 롤링 왜도/첨도 계산, 이동평균 이격도 산출 시 발생하는
    0으로 나누기(ZeroDivision), 수리적 발산, 행렬 차원 비정합성을 포착하여 원본 예외와 함께 전파합니다.
    """

    def __init__(
        self,
        message: str,
        feature_name: str,
        task_name: str,
        original_exception: Optional[Exception] = None
    ) -> None:
        """FeatureCalculationExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            feature_name (str): 산출 실패가 발생한 구체적인 피처 컬럼 명칭.
            task_name (str): 연산을 수행 중이던 피처 태스크 컴포넌트 명칭.
            original_exception (Optional[Exception]): 근본 원인이 된 pandas/numpy/scipy 원본 예외.
        """
        # [설계 의도] 실패한 피처 컬럼 및 태스크 명칭을 details에 세분화하여 디버깅 시 연산 실패 지점을 즉시 격리함
        details = {
            "feature_name": feature_name,
            "task_name": task_name
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )

class DatasetSplitExecutionError(FeatureError):
    """시계열 데이터셋 분할(Dataset Split) 및 Purged Gap 격리 구동 중 발생하는 예외.

    Gold Feature Engineering 완료 데이터프레임을 Train, Validation, Test, Inference 파티션으로
    시간 순서에 따라 분할할 때 스키마 불일치, 유효 데이터 수량 부족 또는 파라미터 분할 오류가
    발생할 경우 상위 오케스트레이터로 전파됩니다.
    """

    def __init__(
        self,
        message: str,
        split_mode: str = "train_test",
        forecast_horizon: int = 20,
        original_exception: Optional[Exception] = None
    ) -> None:
        """DatasetSplitExecutionError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            split_mode (str): 설정된 데이터셋 분할 모드 (기본값: 'train_test').
            forecast_horizon (int): 설정된 예측 Horizon 및 Purged Gap 기간 (기본값: 20영업일).
            original_exception (Optional[Exception]): 데이터셋 분할 중 발생한 원본 예외.
        """
        # [설계 의도] 시계열 분할 구동 시 설정된 분할 모드와 Horizon 정보를 기록하여 파티션 격리 오염 원인을 명확히 추적함
        details = {
            "split_mode": split_mode,
            "forecast_horizon": forecast_horizon
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class TargetGenerationError(FeatureError):
    """예측 타겟 변수(target_return_20d) 산출 및 시계열 shift 연산 중 발생하는 예외.
    
    1달 Horizon($T+20$) 타겟 생성 시 Horizon 경계 아웃오브바운드, 타겟 컬럼 유출(Leakage)
    또는 연속 결측으로 인한 정답 라벨 손상 상황을 포착합니다.
    """

    def __init__(
        self,
        message: str,
        target_horizon: int = 20,
        original_exception: Optional[Exception] = None
    ) -> None:
        """TargetGenerationError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            target_horizon (int): 설정된 타겟 예측 기간 (기본값: 20영업일).
            original_exception (Optional[Exception]): 타겟 생성 중 발생한 원본 예외.
        """
        # [설계 의도] 타겟 생성 시 설정된 Horizon 정보를 기록하여 타겟 변수 산출 오염 원인을 명확히 추적함
        details = {
            "target_horizon": target_horizon
        }
        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )


class FeatureServiceError(FeatureError):
    """FeatureService 오케스트레이션 및 파이프라인 제어 단계에서 발생하는 최상위 예외.
    
    하위 피처 태스크 파이프라인 순차 기동 중 발생하는 시스템 장애나
    최종 피처 행렬 사출 계약 파괴 상황을 포착하여 보존합니다.
    """

    def __init__(
        self,
        message: str,
        original_exception: Optional[Exception] = None
    ) -> None:
        """FeatureServiceError 예외 인스턴스를 초기화합니다.

        Args:
            message (str): 장애 발생 사유에 대한 상세 설명 메시지.
            original_exception (Optional[Exception]): 근본 원인이 된 하위 시스템의 원본 예외 객체.
        """
        details = {}
        if original_exception:
            details["original_exception_type"] = type(original_exception).__name__

        super().__init__(
            message=message,
            details=details,
            original_exception=original_exception,
            should_retry=False
        )