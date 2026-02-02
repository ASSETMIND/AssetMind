"""
데이터 수집 추상화 모듈 (Data Extraction Abstraction)

이 모듈은 '설정 주도(Configuration-Driven) ETL' 파이프라인의 'E(Extraction)' 단계를 정의합니다.
변경된 Pydantic 설정 객체(AppConfig)와 상호작용하며, 모든 수집기가 표준화된 생명주기(Lifecycle)를
따르도록 강제합니다.

데이터 흐름 (Data Flow):
RequestDTO(job_id) -> Validate(Config.policy -> JobPolicy) -> Prepare(Token & Params) -> Fetch(I/O) -> Verify -> Wrap(ResponseDTO)

주요 기능:
- Template Method 패턴을 통한 수집 생명주기 제어 (Validation -> Execution -> Packaging)
- Pydantic 기반 설정 객체(AppConfig) 의존성 주입 및 타입 보장
- 인프라 계층(Network)과 도메인 계층(Extractor)의 에러 격리 및 로깅 표준화

Trade-off:
- Strong Coupling with AppConfig:
    - 장점: 모든 수집기가 Pydantic 모델의 타입 안전성(Type Safety)과 자동완성 혜택을 누림.
    - 단점: AppConfig 구조 변경 시 모든 Extractor 구현체에 영향을 줌.
    - 근거: 엔터프라이즈 환경에서 '컴파일 타임 에러 감지'가 '유연성'보다 운영 안정성에 더 중요함.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..domain.interfaces import IExtractor, IHttpClient
from ..domain.dtos import RequestDTO, ResponseDTO
from ..domain.exceptions import ExtractorError, NetworkError
from ...common.log import LogManager
from ...common.config import AppConfig


class AbstractExtractor(IExtractor, ABC):
    """모든 데이터 수집기(Provider)의 최상위 추상 클래스.
    
    구현체(KISExtractor 등)는 이 클래스를 상속받아 구체적인 수집 로직을 구현해야 하며,
    반드시 Pydantic 기반의 AppConfig를 주입받아야 합니다.

    Attributes:
        http_client (IHttpClient): HTTP 요청 처리를 위한 어댑터.
        config (AppConfig): 애플리케이션 전역 설정 객체. (JobPolicy 포함)
        logger (logging.Logger): 추적성을 위한 로거 인스턴스.
    """

    def __init__(self, http_client: IHttpClient, config: AppConfig):
        """AbstractExtractor를 초기화하고 필수 의존성을 검증합니다.

        Args:
            http_client (IHttpClient): 비동기 HTTP 클라이언트.
            config (AppConfig): 데이터 수집 정책이 포함된 앱 설정 객체.

        Raises:
            ExtractorError: 필수 의존성(Config 등)이 누락된 경우.
        """
        # Rationale: 의존성 주입 시점에 None 체크를 수행하여 런타임 NullReference 에러 방지.
        if not config:
             raise ExtractorError("Initialization Failed: 'AppConfig' cannot be None.")
             
        self.http_client = http_client
        self.config = config
        self.logger = LogManager.get_logger(self.__class__.__name__)

    async def extract(self, request: RequestDTO) -> ResponseDTO:
        """데이터 추출(Extraction) 템플릿 메서드.

        모든 수집기는 이 메서드가 정의한 순서(Validation -> Execution -> Packaging)를
        따라야 하며, 개별 단계(_hooks)만 오버라이딩하여 구현합니다.

        Process:
            1. _validate_request: JobPolicy(Pydantic) 존재 여부 및 필수 필드 검증.
            2. _fetch_raw_data: 인증, 파라미터 병합 후 실제 I/O 실행.
            3. _create_response: 응답 상태 확인 및 DTO 포장.

        Args:
            request (RequestDTO): job_id와 파라미터를 포함한 요청 객체.

        Returns:
            ResponseDTO: 원본 데이터(Raw Data)와 메타데이터가 포함된 응답 객체.

        Raises:
            ExtractorError: 검증 실패, 설정 누락, API 비즈니스 에러 등 수집 불가 상황.
        """
        try:
            # 0. Logging Entry Point (Null Safety Protected)
            job_id = request.job_id if request else "Unknown"
            self.logger.info(f"Starting extraction task. Job: {job_id}")

            # 1. Validation Phase (Policy & Request Check)
            # Fail-Fast 원칙: I/O 비용 발생 전 요청과 설정의 유효성을 먼저 확인.
            self._validate_request(request)

            # 2. Execution Phase (Auth -> Merge Params -> I/O)
            # 복잡한 준비 과정(토큰 등)과 실행을 하나의 추상 메서드로 캡슐화.
            raw_data = await self._fetch_raw_data(request)

            # 3. Packaging Phase (Status Check -> Wrap)
            # 데이터의 가공 없이 순수 '수집 성공 여부'만 판단하여 전달.
            response = self._create_response(raw_data)

            self.logger.info(f"Extraction completed successfully. Job: {request.job_id}")
            return response

        except NetworkError as e:
            # Rationale: 인프라(Network) 에러를 도메인(Extractor) 에러로 치환하여 상위 레이어의 에러 처리를 단순화.
            self.logger.error(f"Network error during extraction: {str(e)}")
            raise ExtractorError(f"Network failure: {str(e)}") from e
        except ExtractorError as e:
            # 구현체에서 의도적으로 발생시킨 도메인 에러는 그대로 전파 (로그 레벨은 경고로 처리).
            self.logger.warning(f"Extraction logic failed: {str(e)}")
            raise e
        except Exception as e:
            # Rationale: 예상치 못한 버그(Uncaught Exception)는 Stack Trace를 남겨 디버깅을 지원.
            self.logger.error(f"Unexpected error during extraction: {str(e)}", exc_info=True)
            raise ExtractorError(f"Extraction failed: {str(e)}") from e

    @abstractmethod
    def _validate_request(self, request: RequestDTO) -> None:
        """요청의 정합성 및 설정(JobPolicy) 존재 여부를 검증합니다.

        구현체는 `self.config.extraction_policy` (Dict[str, JobPolicy])를 확인하여
        요청된 작업이 유효한지 판단해야 합니다.

        Args:
            request (RequestDTO): 요청 객체.

        Raises:
            ExtractorError: 설정이 없거나 요청이 유효하지 않은 경우.
        """
        pass

    @abstractmethod
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """수집 준비(Preparation) 및 실행(Execution)을 담당합니다.

        구현체는 `self.config` 객체의 속성(Attribute)에 접근하여 다음을 수행합니다:
        1. (필요 시) 인증 토큰 확보.
        2. JobPolicy의 Params와 Request Params 병합.
        3. HTTP 요청 수행.

        Args:
            request (RequestDTO): 요청 객체.

        Returns:
            Any: API로부터 받은 원본 응답 데이터.
        """
        pass

    @abstractmethod
    def _create_response(self, raw_data: Any) -> ResponseDTO:
        """수집 결과 검증(Verification) 및 포장(Packaging)을 담당합니다.

        Args:
            raw_data (Any): _fetch_raw_data의 결과값.

        Returns:
            ResponseDTO: 최종 결과 객체.

        Raises:
            ExtractorError: API 호출은 성공했으나 비즈니스 로직상 실패인 경우.
        """
        pass