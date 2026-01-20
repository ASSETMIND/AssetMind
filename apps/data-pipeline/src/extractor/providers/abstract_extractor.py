"""
데이터 수집 추상화 모듈 (Data Extraction Abstraction)

이 모듈은 '설정 주도(Configuration-Driven) ETL' 파이프라인의 'E(Extraction)' 단계를 정의합니다.
KISExtractor와 같은 구현체가 반드시 따라야 할 엄격한 실행 흐름(Template Method)을 제공합니다.

데이터 흐름 (Data Flow):
RequestDTO(job_id) -> Validate (Req & Policy) -> Prepare (Token & Params) -> Fetch (I/O) -> Verify Status -> Wrap(ResponseDTO)

주요 기능:
- Template Method 패턴을 통한 수집 생명주기 제어
- 설정(Policy) 및 요청 정합성 검증 단계 강제
- 인증, 파라미터 병합 등 I/O 사전 작업의 추상화
- 데이터 변환 없는 순수 원본(Raw Data) 전달 보장

Trade-off:
- Strict Template Structure:
    - 장점: 모든 구현체(KIS, KRX 등)가 동일한 품질 관리 기준(검증->수집->상태확인)을 따르게 됨.
    - 단점: 구현체의 자유도가 낮아짐.
    - 근거: 데이터 파이프라인의 신뢰성을 위해 '수집 성공'의 기준을 추상 계층에서 강력하게 통제해야 함.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..domain.interfaces import IExtractor, IHttpClient
from ..domain.dtos import RequestDTO, ResponseDTO
from ..domain.exceptions import ExtractorError, NetworkError
from ...common.log import LogManager


class AbstractExtractor(IExtractor, ABC):
    """모든 데이터 수집기(Provider)의 최상위 추상 클래스.
    
    구현체(KISExtractor 등)는 이 클래스가 정의한 3단계 프로세스(_hooks)를
    반드시 구체적인 로직으로 채워야 합니다.

    Attributes:
        http_client (IHttpClient): HTTP 요청 처리를 위한 어댑터.
        logger (logging.Logger): 추적성을 위한 로거 인스턴스.
    """

    def __init__(self, http_client: IHttpClient):
        """AbstractExtractor를 초기화합니다.

        Args:
            http_client (IHttpClient): 비동기 HTTP 클라이언트.
        """
        self.http_client = http_client
        self.logger = LogManager.get_logger(self.__class__.__name__)

    async def extract(self, request: RequestDTO) -> ResponseDTO:
        """데이터 추출(Extraction) 템플릿 메서드.

        KISExtractor의 로직과 일치하도록 3단계의 엄격한 순서를 보장합니다.

        Process:
            1. _validate_request: 요청된 job_id가 설정(Config)에 존재하는지, 필수 파라미터가 있는지 검증.
            2. _fetch_raw_data: 인증(Token), 설정 로드, 파라미터 병합을 수행 후 실제 I/O 실행.
            3. _create_response: API 응답의 비즈니스 성공 여부(Status)를 확인하고 DTO로 포장.

        Args:
            request (RequestDTO): job_id와 파라미터를 포함한 요청 객체.

        Returns:
            ResponseDTO: 원본 데이터(Raw Data)와 메타데이터가 포함된 응답 객체.

        Raises:
            ExtractorError: 검증 실패, 설정 누락, API 비즈니스 에러 등 수집 불가 상황.
        """
        self.logger.info(f"Starting extraction task. Request: {request}")

        try:
            # 1. Validation Phase (Policy & Request Check)
            self._validate_request(request)

            # 2. Execution Phase (Auth -> Merge Params -> I/O)
            raw_data = await self._fetch_raw_data(request)

            # 3. Packaging Phase (Status Check -> Wrap)
            response = self._create_response(raw_data)

            self.logger.info("Extraction completed successfully.")
            return response

        except NetworkError as e:
            # 인프라(Network) 에러를 도메인(Extractor) 에러로 치환
            self.logger.error(f"Network error during extraction: {str(e)}")
            raise ExtractorError(f"Network failure: {str(e)}") from e
        except ExtractorError as e:
            # 구현체에서 발생시킨 도메인 에러(설정 누락, 비즈니스 에러 등)는 그대로 전파
            self.logger.warning(f"Extraction logic failed: {str(e)}")
            raise e
        except Exception as e:
            # 예상치 못한 시스템 에러 캡처
            self.logger.error(f"Unexpected error during extraction: {str(e)}", exc_info=True)
            raise ExtractorError(f"Extraction failed: {str(e)}") from e

    @abstractmethod
    def _validate_request(self, request: RequestDTO) -> None:
        """요청의 정합성 및 설정(Policy) 존재 여부를 검증합니다.

        구현체는 반드시 다음을 확인해야 합니다:
        1. request.job_id의 유효성.
        2. AppConfig에 해당 job_id에 대한 정책(Policy) 존재 여부.
        3. 정책 실행을 위한 필수 파라미터 누락 여부.

        Args:
            request (RequestDTO): 요청 객체.

        Raises:
            ExtractorError: 설정이 없거나 요청이 잘못되어 수집을 시작할 수 없는 경우.
        """
        pass

    @abstractmethod
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """수집 준비(Preparation) 및 실행(Execution)을 담당합니다.

        단순한 I/O 호출뿐만 아니라 다음 과정을 포함해야 합니다:
        1. 인증 토큰 확보 (Authentication).
        2. 설정(Policy) 로드 및 파라미터 병합 (Merging).
        3. 실제 API 호출 (I/O).

        Args:
            request (RequestDTO): 요청 객체.

        Returns:
            Any: API로부터 받은 원본 응답 데이터 (Dictionary 등).
        """
        pass

    @abstractmethod
    def _create_response(self, raw_data: Any) -> ResponseDTO:
        """수집 결과 검증(Verification) 및 포장(Packaging)을 담당합니다.

        구현체는 반드시 다음을 수행해야 합니다:
        1. 응답 데이터 내의 비즈니스 에러 코드(예: rt_cd) 확인.
        2. 실패 시 ExtractorError 발생.
        3. 성공 시 원본 데이터를 변형 없이 ResponseDTO에 담아 반환.

        Args:
            raw_data (Any): _fetch_raw_data의 결과값.

        Returns:
            ResponseDTO: 최종 결과 객체.

        Raises:
            ExtractorError: API 호출은 성공했으나 비즈니스 로직상 실패인 경우.
        """
        pass