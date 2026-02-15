"""
데이터 수집기 팩토리 모듈 (Data Extractor Factory)

설정(AppConfig)과 작업 ID(Job ID)를 기반으로 적절한 데이터 수집기(Extractor) 인스턴스를
생성하고, 필요한 의존성(AuthStrategy, HttpClient)을 주입하여 조립(Assemble)합니다.
Simple Factory 패턴을 사용하여 클라이언트가 구체적인 클래스(KISExtractor 등)를 알 필요 없이
인터페이스(IExtractor)에만 의존하게 합니다.

데이터 흐름 (Data Flow):
Input(Job ID, Config, HttpClient) -> Lookup Policy -> Get or Create Auth(Cache) -> Instantiate Extractor -> Return IExtractor

주요 기능:
- 작업별(Job-specific) 수집 정책 조회 및 유효성 검증
- Provider 타입(KIS, FRED, ECOS, UPBIT)에 따른 분기 처리 및 객체 생성
- 인증 전략(AuthStrategy) 캐싱(Caching)을 통한 토큰 재사용 및 API 부하 감소
- 로거 인스턴스 최적화 (Lazy Loading 제거 및 클래스 레벨 초기화)

Trade-off:
- Auth Strategy Caching (Singleton-like):
    - 장점: KIS, UPBIT와 같이 상태 관리(Token)나 연산 비용이 있는 인증 객체를 재사용하여
      불필요한 토큰 재발급 요청을 방지하고 성능을 최적화함.
    - 단점: 런타임에 Config가 변경되더라도 캐시된 인증 객체는 갱신되지 않음(App 재시작 필요).
    - 근거: 배치 파이프라인 특성상 실행 도중 API Key가 변경되는 경우는 극히 드물며,
      API Rate Limit 준수가 우선임.

- Explicit Dependency Mapping:
    - 장점: Reflection이나 Dynamic Import를 사용하지 않고 명시적으로 매핑(Map)하여
      IDE의 코드 탐색과 정적 분석(Type Checking) 지원을 최적화함.
    - 단점: 새로운 Provider 추가 시 Factory 코드를 수정해야 함(OCP 위반 소지).
    - 근거: 지원하는 Provider의 수가 제한적이고(4~5개), 컴파일 타임에 구성 오류를 잡는 것이
      런타임 유연성보다 운영 안정성에 중요함.
"""

import logging
from typing import Dict, Optional, Type

from ..common.config import AppConfig
from ..common.log import LogManager
from .domain.interfaces import IExtractor, IHttpClient, IAuthStrategy
from .domain.exceptions import ExtractorError

# [Extractor Implementations]
from .providers.kis_extractor import KISExtractor
from .providers.fred_extractor import FREDExtractor
from .providers.ecos_extractor import ECOSExtractor
from .providers.upbit_extractor import UPBITExtractor

# [Auth Strategy Implementations]
from .adapters.auth import KISAuthStrategy, UPBITAuthStrategy


class ExtractorFactory:
    """수집기(Extractor) 생성을 전담하는 팩토리 클래스.

    모든 수집기는 이 클래스를 통해서만 생성되어야 하며, 이를 통해
    의존성 주입의 일관성을 유지하고 객체 생성의 복잡성을 캡슐화합니다.
    """

    # 1. Logger Optimization: Lazy Loading을 위해 초기값은 None으로 설정
    # (Import 시점에 Config가 로드되지 않았을 경우 발생하는 RuntimeError 방지)
    _logger: Optional[logging.Logger] = None

    # 2. Auth Strategy Caching: Provider별 인증 객체 재사용을 위한 저장소
    # Key: Provider Name (e.g., "KIS"), Value: IAuthStrategy Instance
    _auth_cache: Dict[str, IAuthStrategy] = {}

    @classmethod
    def _get_logger(cls) -> logging.Logger:
        """로거 인스턴스를 반환하며, 없으면 생성합니다 (Lazy Initialization)."""
        if cls._logger is None:
            cls._logger = LogManager.get_logger("ExtractorFactory")
        return cls._logger

    @classmethod
    def _get_or_create_auth(cls, provider: str, config: AppConfig) -> IAuthStrategy:
        """인증 전략 인스턴스를 반환하거나 없으면 생성하여 캐싱합니다."""
        # 1. Cache Hit: 이미 생성된 전략이 있다면 재사용 (Token 재활용)
        if provider in cls._auth_cache:
            return cls._auth_cache[provider]

        # 2. Cache Miss: 전략 객체 신규 생성
        if provider == "KIS":
            strategy = KISAuthStrategy(config)
        elif provider == "UPBIT":
            strategy = UPBITAuthStrategy(config)
        else:
            raise ExtractorError(f"Auth Strategy not defined for provider: {provider}")

        # 3. Caching & Return
        cls._auth_cache[provider] = strategy
        cls._logger.debug(f"AuthStrategy cached for provider: {provider}")
        return strategy

    @classmethod
    def create_extractor(
        cls, 
        job_id: str, 
        http_client: IHttpClient, 
        config: AppConfig
    ) -> IExtractor:
        """주어진 Job ID에 매핑된 정책을 확인하여 적절한 Extractor를 생성합니다.

        Args:
            job_id (str): 실행할 수집 작업의 식별자. (AppConfig.policy 키)
            http_client (IHttpClient): 공유되는 HTTP 클라이언트 인스턴스.
            config (AppConfig): 애플리케이션 전역 설정 객체.

        Returns:
            IExtractor: 초기화가 완료된 수집기 인스턴스.

        Raises:
            ExtractorError: 
                - Job ID에 해당하는 정책이 없는 경우.
                - 지원하지 않는 Provider인 경우.
        """
        # 1. 로거 확보 (Lazy Load)
        logger = cls._get_logger()

        # 2. 정책 유효성 검증 (Policy Validation)
        # Rationale: Factory 단계에서 정책 존재 여부를 검증하여, 잘못된 Job ID로 인한
        # 불필요한 객체 생성 비용과 모호한 에러를 방지합니다.
        policy = config.extraction_policy.get(job_id)
        if not policy:
            cls._logger.error(f"Creation Failed: No policy found for job_id '{job_id}'")
            raise ExtractorError(f"Configuration Error: Job ID '{job_id}' is undefined.")

        provider = policy.provider.upper()

        # 3. Provider별 인스턴스 생성 및 의존성 주입 (Instantiation & DI)
        # 캐시된 인증 전략 사용을 통해 토큰 재사용 보장
        try:
            if provider == "KIS":
                auth_strategy = cls._get_or_create_auth("KIS", config)
                return KISExtractor(http_client, auth_strategy, config)

            elif provider == "UPBIT":
                auth_strategy = cls._get_or_create_auth("UPBIT", config)
                return UPBITExtractor(http_client, auth_strategy, config)

            elif provider == "FRED":
                return FREDExtractor(http_client, config)

            elif provider == "ECOS":
                return ECOSExtractor(http_client, config)
            else:
                # 정의되지 않은 Provider (Switch Case Fallback)
                raise ExtractorError(f"Unsupported Provider: '{provider}'")

        except Exception as e:
            # 객체 생성 중 발생하는 모든 에러(Config 누락, 초기화 실패 등)를 포착
            cls._logger.error(f"Factory Error: Failed to instantiate {provider} extractor. {str(e)}", exc_info=True)
            raise ExtractorError(f"Factory Initialization Failed: {str(e)}") from e