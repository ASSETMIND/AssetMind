"""
데이터 수집 추상화 모듈 (Data Extraction Abstraction)

이 모듈은 '설정 주도(Configuration-Driven) ETL' 파이프라인의 'E(Extraction)' 단계를 정의합니다.
KISExtractor에서 검증된 설정 주입 패턴을 표준화하여, 모든 수집기가 동일한 설정 객체를
기반으로 동작하도록 강제합니다.

데이터 흐름 (Data Flow):
RequestDTO(job_id) -> Validate(Config & Req) -> Prepare(Token & Params) -> Fetch(I/O) -> Verify -> Wrap(ResponseDTO)

주요 기능:
- Template Method 패턴을 통한 수집 생명주기(Lifecycle) 제어
- AppConfig 의존성 주입(DI) 표준화 및 초기화 검증
- 인프라 계층(Network)과 도메인 계층(Extractor)의 에러 격리

Trade-off:
- Enforced Config Dependency:
    - 장점: 모든 수집기가 Global State(전역 변수) 대신 주입된 설정을 참조하므로 테스트 용이성(Testability)과 격리성(Isolation)이 향상됨.
    - 단점: 설정이 필요 없는 단순 크롤러 구현 시에도 Config 객체를 더미로라도 전달해야 함.
    - 근거: 엔터프라이즈 환경에서는 설정을 통하지 않는 'Hard-coded' 수집 로직은 관리 부채가 되므로, 구조적으로 설정을 강제하는 것이 옳음.
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
    반드시 AppConfig를 주입받아야 합니다.

    Attributes:
        http_client (IHttpClient): HTTP 요청 처리를 위한 어댑터.
        config (AppConfig): 애플리케이션 전역 설정 객체. (Extraction Policy 포함)
        logger (logging.Logger): 추적성을 위한 로거 인스턴스.
    """

    def __init__(self, http_client: IHttpClient, config: AppConfig):
        """AbstractExtractor를 초기화하고 필수 의존성을 검증합니다.

        자식 클래스(KISExtractor)에서 개별적으로 구현하던 config 저장을
        부모 클래스로 승격하여 모든 Extractor가 설정을 갖도록 보장합니다.

        Args:
            http_client (IHttpClient): 비동기 HTTP 클라이언트.
            config (AppConfig): 데이터 수집 정책이 포함된 앱 설정 객체.

        Raises:
            ExtractorError: 필수 의존성(Config 등)이 누락된 경우.
        """
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
            1. _validate_request: 주입된 self.config와 request.job_id의 정합성 검증.
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
            # Fail-Fast 원칙에 따라, I/O 비용 발생 전 요청과 설정의 유효성을 먼저 확인.
            self._validate_request(request)

            # 2. Execution Phase (Auth -> Merge Params -> I/O)
            # 복잡한 준비 과정(토큰 등)과 실행을 하나의 추상 메서드로 캡슐화.
            raw_data = await self._fetch_raw_data(request)

            # 3. Packaging Phase (Status Check -> Wrap)
            # 데이터의 포맷팅이나 변환 없이 순수 '성공 여부'만 판단하여 전달.
            response = self._create_response(raw_data)

            self.logger.info(f"Extraction completed successfully. Job: {request.job_id}")
            return response

        except NetworkError as e:
            # 인프라(Network) 에러를 도메인(Extractor) 에러로 치환하여 상위 레이어에 전달
            self.logger.error(f"Network error during extraction: {str(e)}")
            raise ExtractorError(f"Network failure: {str(e)}") from e
        except ExtractorError as e:
            # 구현체에서 의도적으로 발생시킨 도메인 에러는 그대로 전파 (로그 레벨은 경고로 낮춤)
            self.logger.warning(f"Extraction logic failed: {str(e)}")
            raise e
        except Exception as e:
            # 예상치 못한 시스템 에러(Uncaught Exception) 캡처
            self.logger.error(f"Unexpected error during extraction: {str(e)}", exc_info=True)
            raise ExtractorError(f"Extraction failed: {str(e)}") from e

    @abstractmethod
    def _validate_request(self, request: RequestDTO) -> None:
        """요청의 정합성 및 설정(Policy) 존재 여부를 검증합니다.

        구현체는 `self.config`를 사용하여 다음을 확인해야 합니다:
        1. request.job_id가 config.extraction_policy에 정의되어 있는가?
        2. 해당 정책 실행에 필요한 필수 데이터가 갖춰져 있는가?

        Args:
            request (RequestDTO): 요청 객체.

        Raises:
            ExtractorError: 설정이 없거나 요청이 유효하지 않은 경우.
        """
        pass

    @abstractmethod
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """수집 준비(Preparation) 및 실행(Execution)을 담당합니다.

        구현체는 `self.config`와 `self.http_client`를 사용하여 다음을 수행합니다:
        1. (필요 시) 인증 토큰 확보.
        2. Config의 Static Param과 Request의 Dynamic Param 병합.
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