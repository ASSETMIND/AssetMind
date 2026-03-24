"""
이 모듈은 '설정 주도(Configuration-Driven) ETL' 파이프라인의 'E(Extraction)' 단계를 정의하는 핵심 추상화 계층입니다.
변경된 Pydantic 설정 객체(ConfigManager)와 상호작용하며, 모든 데이터 수집기(Extractor)가 표준화된 생명주기(Lifecycle)와 
에러 처리 정책을 일관되게 따르도록 인터페이스 규격을 강제합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. RequestDTO: 외부(스케줄러/API)로부터 특정 데이터 수집 작업(job_id) 실행 요청 유입.
2. Validation: ConfigManager를 통해 요청된 job_id가 유효한 수집 정책(JobPolicy)인지 사전 검증.
3. Preparation & Fetch: 수집기 구현체가 인증 토큰 확보 및 파라미터를 병합하여 실제 HTTP I/O 요청 수행.
4. Verification & Wrap: 수집된 원본 데이터(Raw Data)의 무결성을 검증하고, 파이프라인 표준 규격인 ExtractedDTO로 래핑하여 반환.

주요 기능:
- Template Method Pattern: 수집 생명주기 제어 로직(Validation -> Execution -> Packaging)을 상위에서 정의하고 세부 구현은 하위로 위임.
- Dependency Injection: Pydantic 기반 설정 객체(ConfigManager)와 HTTP 클라이언트(IHttpClient)의 의존성 주입을 통한 결합도 제어.
- Error Isolation: 인프라 계층(Network)의 장애와 도메인 계층(Extractor)의 비즈니스 에러를 분리하고 데코레이터를 통한 로깅 규격 표준화.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Strong Coupling with ConfigManager:
  - 장점: 모든 수집기 구현체가 Pydantic 모델이 제공하는 강력한 타입 안전성(Type Safety)과 자동완성 혜택을 누릴 수 있어 개발자의 휴먼 에러를 방지함.
  - 단점: 추상화 계층이 구체적인 설정 관리자(ConfigManager)에 직접 의존하게 되어, 설정 스키마 변경 시 모든 Extractor 구현체에 파급 효과가 발생함(강한 결합).
  - 근거: 엔터프라이즈 데이터 파이프라인 환경에서는 런타임의 '유연성'보다, 잘못된 설정으로 인한 대규모 데이터 오염을 막기 위한 '초기화 타임 에러 감지(Fail-Fast)'가 운영 안정성에 압도적으로 중요하므로 이 결합도를 수용함.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.common.interfaces import IExtractor, IHttpClient
from src.common.dtos import RequestDTO, ExtractedDTO
from src.common.exceptions import ETLError, ExtractorError, ConfigurationError
from src.common.log import LogManager
from src.common.config import ConfigManager
from src.common.decorators.log_decorator import log_decorator


# ==============================================================================
# [Abstract Class] AbstractExtractor
# ==============================================================================
class AbstractExtractor(IExtractor, ABC):
    """모든 데이터 수집기(Provider)가 상속받아야 하는 최상위 템플릿(추상) 클래스.
    
    구현체(KISExtractor, FREDExtractor 등)는 이 클래스를 상속받아 구체적인 수집 로직(Hook 메서드)을 
    구현해야 하며, 반드시 Pydantic 기반의 ConfigManager를 통해 작업 정책을 할당받아야 합니다.

    Attributes:
        http_client (IHttpClient): 비동기 HTTP 통신을 담당하는 인프라 어댑터 인스턴스.
        config (ConfigManager): 수집 정책(JobPolicy)이 포함된 애플리케이션 전역 설정 객체.
        logger (logging.Logger): 클래스별 격리된 추적성을 제공하는 로거 인스턴스.
    """

    def __init__(self, http_client: IHttpClient):
        """AbstractExtractor 인스턴스를 초기화하고 필수 의존성의 무결성을 검증합니다.

        Args:
            http_client (IHttpClient): 데이터 수집에 사용할 비동기 HTTP 클라이언트.

        Raises:
            ConfigurationError: 필수 의존성(IHttpClient 등)이 주입되지 않은 경우.
        """
        # [설계 의도] 방어적 프로그래밍. 의존성이 누락된 상태로 인스턴스가 생성되어
        # 런타임 도중 파이프라인이 붕괴되는 것을 초기화 시점에 조기 차단(Fail-Fast)함.
        if http_client is None:
            raise ConfigurationError("초기화 실패: IHttpClient 인스턴스가 필요합니다.")
             
        self.http_client = http_client
        
        # [설계 의도] 파이프라인 설정(extractor.yml)을 로드하여 자식 클래스들이 
        # 안전하게 JobPolicy에 접근할 수 있도록 싱글톤 캐시에서 인스턴스를 가져옴.
        self.config = ConfigManager.load("extractor")
        self.logger = LogManager.get_logger(self.__class__.__name__)

    @log_decorator()
    async def extract(self, request: RequestDTO) -> ExtractedDTO:
        """데이터 수집 파이프라인의 전체 생명주기를 관장하는 템플릿 메서드(Template Method).

        모든 자식 수집기는 이 메서드가 강제하는 순서(Validation -> Execution -> Packaging)를
        준수해야 하며, 개별 단계의 세부 로직(_hooks)만 오버라이딩하여 구현합니다.
        
        [설계 의도]
        수동으로 작성되었던 시작/종료 로깅, 에러 로깅 및 예외 래핑(ETLError) 역할을 `@log_decorator`로
        완벽히 위임하여 횡단 관심사를 분리(DRY 원칙 준수)하고, 이 메서드는 비즈니스 생명주기 제어에만 집중함.

        Args:
            request (RequestDTO): 실행할 작업의 고유 ID(job_id)와 런타임 파라미터를 포함한 데이터 전송 객체.

        Returns:
            ExtractedDTO: 외부 API로부터 수집된 원본 데이터(Raw Data)와 작업 메타데이터가 포함된 표준 응답 객체.
        """
        # [설계 의도] 자식 클래스의 _create_response에서 출처를 식별하기 위해
        # RequestDTO 내부에 명시된 job_id를 안전하게 추출 (Duck Typing 방어).
        job_id = request.job_id if request and hasattr(request, "job_id") else "Unknown"

        # 1. Validation Hook: 요청 및 설정 검증
        self._validate_request(request)
        
        # 2. Execution Hook: 실제 I/O 기반 데이터 수집 수행
        raw_data = await self._fetch_raw_data(request)

        # 3. Packaging Hook: 수집 데이터의 표준 규격화
        # [설계 의도] 인터페이스 계약(Contract)에 맞춰 하위 구현체에 job_id를 강제로 주입하여 
        # 어떤 스키마(JobPolicy)에서 파생된 데이터인지 런타임 추적성을 보장함.
        response = self._create_response(raw_data, job_id)

        return response

    @abstractmethod
    def _validate_request(self, request: RequestDTO) -> None:
        """수집 요청의 정합성 및 설정(JobPolicy) 존재 여부를 사전 검증하는 훅(Hook) 메서드.

        구현체는 `self.config` 내부에 해당 `request.job_id`에 매핑되는 유효한 수집 정책이 
        존재하는지 판단하고, 누락된 파라미터가 없는지 확인해야 합니다.

        Args:
            request (RequestDTO): 검증할 수집 요청 객체.

        Raises:
            ExtractorError: 설정 파일에 정책이 누락되었거나 필수 요청 파라미터가 유효하지 않은 경우.
        """
        pass # pragma: no cover

    @abstractmethod
    async def _fetch_raw_data(self, request: RequestDTO) -> Any:
        """수집 준비(Preparation) 및 비동기 네트워크 실행(Execution)을 담당하는 훅(Hook) 메서드.

        구현체는 `self.config` 객체의 속성에 접근하여 다음 작업을 반드시 수행해야 합니다:
        1. (필요 시) 인증 모듈을 통한 토큰 확보 및 헤더 구성.
        2. JobPolicy에 정의된 정적 Params와 RequestDTO의 런타임 Params 병합.
        3. `self.http_client`를 이용한 비동기 HTTP 요청 수행.

        Args:
            request (RequestDTO): 수집 파라미터가 포함된 요청 객체.

        Returns:
            Any: 외부 API로부터 반환된 파싱 전 원본 응답 데이터 (주로 Dict 구조체).
        """
        pass # pragma: no cover

    @abstractmethod
    def _create_response(self, raw_data: Any, job_id: str) -> ExtractedDTO:
        """수집된 원본 결과의 검증(Verification) 및 시스템 표준 포장(Packaging)을 담당하는 훅(Hook) 메서드.

        [설계 의도]
        단순히 HTTP Status 200이 떨어졌더라도 비즈니스 로직상 에러(예: 결과값 빈 배열, API Limit 초과 메시지)가
        포함되어 있을 수 있으므로, 이를 파싱하여 확인한 뒤 다운스트림(Loader)이 이해할 수 있는 
        ExtractedDTO 규격으로 래핑합니다.

        Args:
            raw_data (Any): `_fetch_raw_data`가 반환한 수집 원본 데이터.
            job_id (str): 현재 실행 중인 작업의 고유 ID (메타데이터 추적용).

        Returns:
            ExtractedDTO: 후속 파이프라인 단계로 전달할 최종 표준 결과 객체.

        Raises:
            ExtractorError: API 호출 자체는 성공했으나 반환된 페이로드 내부에 비즈니스 에러가 포함된 경우.
        """
        pass # pragma: no cover