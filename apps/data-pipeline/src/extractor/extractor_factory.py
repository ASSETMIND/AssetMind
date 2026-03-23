"""
설정(ConfigManager)과 작업 ID(Job ID)를 기반으로 적절한 데이터 수집기(Extractor) 인스턴스를 동적으로 생성하고,
필요한 의존성(AuthStrategy, HttpClient)을 주입하여 조립(Assemble)하는 팩토리 모듈입니다.
Simple Factory 패턴을 적용하여 클라이언트(파이프라인 컨트롤러)가 구체적인 클래스(KISExtractor 등)의 
구현 세부사항을 알 필요 없이 추상 인터페이스(IExtractor)에만 의존하도록 설계되었습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 스케줄러 또는 파이프라인으로부터 특정 데이터 수집 작업(job_id)과 HTTP 클라이언트 인스턴스 유입.
2. Lookup Policy: ConfigManager를 통해 해당 job_id에 매핑된 수집 정책(JobPolicy) 및 Provider 식별.
3. Get or Create Auth: 인증이 필요한 Provider(KIS, UPBIT)의 경우, 캐시된 인증 객체를 가져오거나 새로 생성.
4. Instantiate Extractor: 식별된 Provider에 맞는 구체적인 수집기 인스턴스(KISExtractor 등) 생성 및 의존성 주입.
5. Output: 초기화가 완료된 IExtractor 추상화 객체 반환.

주요 기능:
- Centralized Instantiation: 파이프라인 내 모든 수집기의 생성 로직을 중앙 집중화하여 도메인 간 결합도를 낮춤.
- Auth Strategy Caching: 상태를 가지는 인증 전략(AuthStrategy) 객체를 메모리에 캐싱하여 불필요한 토큰 재발급 방지.
- Explicit Dependency Injection: 런타임에 필요한 HTTP 클라이언트와 인증 전략을 명시적으로 주입하여 테스트 용이성 확보.
- Safe Initialization: 객체 생성 중 발생하는 예외를 도메인 표준 에러(ExtractorError)로 래핑하여 파이프라인 패닉 방지.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. Auth Strategy Caching (Singleton-like):
   - 장점: KIS, UPBIT와 같이 상태 관리(Token)나 암호화 연산 비용이 있는 인증 객체를 재사용하여 불필요한 토큰 재발급 요청을 방지하고 성능을 최적화함.
   - 단점: 런타임에 외부 요인으로 Config가 변경되더라도 캐시된 인증 객체는 갱신되지 않음(App 재시작 필요).
   - 근거: 배치 파이프라인 특성상 실행 도중 API Key가 변경되는 경우는 극히 드물며, 외부 API Rate Limit 준수와 네트워크 오버헤드 감소가 압도적으로 중요함.
2. Explicit Dependency Mapping vs Dynamic Import:
   - 장점: Reflection이나 동적 임포트(Dynamic Import)를 사용하지 않고 명시적으로 분기(if-elif)하여 매핑함으로써 IDE의 코드 탐색과 정적 분석(Type Checking) 지원을 최적화함.
   - 단점: 새로운 Provider 추가 시 Factory 코드를 직접 수정해야 하므로 OCP(개방-폐쇄 원칙)를 일부 위반함.
   - 근거: 지원하는 Provider의 수가 제한적(4~5개)이고, 런타임의 유연성보다 컴파일(또는 린트) 타임에 구성 오류를 명확히 잡는 것이 운영 안정성에 훨씬 유리함.
"""

import logging
from typing import Dict, Optional, Type

from src.common.config import ConfigManager, JobPolicy
from src.common.log import LogManager
from src.common.interfaces import IExtractor, IHttpClient, IAuthStrategy
from src.common.exceptions import ExtractorError

from src.common.decorators.log_decorator import log_decorator

from src.extractor.providers.kis_extractor import KISExtractor
from src.extractor.providers.fred_extractor import FREDExtractor
from src.extractor.providers.ecos_extractor import ECOSExtractor
from src.extractor.providers.upbit_extractor import UPBITExtractor

from src.extractor.adapters.auth import KISAuthStrategy, UPBITAuthStrategy


class ExtractorFactory:
    """수집기(Extractor) 인스턴스 생성을 전담하는 팩토리 클래스.

    모든 수집기 객체는 이 클래스를 통해서만 생성되어야 하며, 이를 통해
    의존성 주입의 일관성을 유지하고 객체 생성 로직의 복잡성을 외부로부터 캡슐화합니다.
    """

    # [설계 의도] Provider별 인증 객체 재사용을 위한 메모리 저장소.
    # 토큰 발급 횟수를 최소화하기 위해 애플리케이션 수명주기 동안 인스턴스를 유지(Flyweight 패턴 응용).
    _auth_cache: Dict[str, IAuthStrategy] = {}

    @classmethod
    def _get_or_create_auth(cls, provider: str, config: ConfigManager) -> IAuthStrategy:
        """지정된 Provider의 인증 전략 인스턴스를 반환하거나, 없을 경우 새로 생성하여 캐싱합니다.

        Args:
            provider (str): 인증 전략을 식별하기 위한 제공자 이름 (예: "KIS", "UPBIT").
            config (ConfigManager): 인증 전략 초기화에 필요한 애플리케이션 전역 설정 객체.

        Returns:
            IAuthStrategy: 캐싱되었거나 새로 생성된 인증 전략 인스턴스.

        Raises:
            ExtractorError: 시스템에서 지원하지 않는 인증 제공자가 입력된 경우.
        """
        # [설계 의도] Cache Hit: 이미 생성된 전략이 있다면 즉시 재사용하여 
        # 불필요한 객체 생성 비용 및 외부 통신(Token 발급)을 원천 차단.
        if provider in cls._auth_cache:
            return cls._auth_cache[provider]

        # [설계 의도] Cache Miss: 전략 객체 신규 생성 분기.
        if provider == "KIS":
            strategy = KISAuthStrategy(config)
        elif provider == "UPBIT":
            strategy = UPBITAuthStrategy(config)
        else:
            raise ExtractorError(f"지원하지 않는 인증 제공자입니다: {provider}")

        # [설계 의도] 향후 요청 시 재사용을 위해 생성된 객체를 메모리 딕셔너리에 보관.
        cls._auth_cache[provider] = strategy
        
        return strategy

    @classmethod
    @log_decorator()
    def create_extractor(
        cls, 
        job_id: str, 
        http_client: IHttpClient, 
    ) -> IExtractor:
        """주어진 Job ID에 매핑된 수집 정책을 확인하여 적절한 Extractor 인스턴스를 조립 및 반환합니다.

        Args:
            job_id (str): 실행할 수집 작업의 고유 식별자 (extractor.yml에 정의된 키).
            http_client (IHttpClient): 모든 수집기가 통신에 공유할 비동기 HTTP 클라이언트 인스턴스.

        Returns:
            IExtractor: 의존성 주입 및 초기화가 완벽히 끝난 구체화된 수집기 인터페이스 객체.

        Raises:
            ExtractorError: 
                - Job ID에 해당하는 정책을 설정에서 찾을 수 없는 경우.
                - 식별된 Provider가 시스템에 구현되지 않은 경우.
                - Extractor 초기화 과정(인증 객체 생성 등)에서 에러가 발생한 경우.
        """
        # [설계 의도] 팩토리 내부에서 ConfigManager를 로드하여 파라미터 개수를 줄이고 캡슐화를 강화함.
        # ConfigManager는 자체적으로 캐싱 로직이 있어 중복 파일 I/O가 발생하지 않음.
        config = ConfigManager.load("extractor")
        policy = config.get_extractor(job_id)

        # [설계 의도] 대소문자 입력 실수로 인한 분기 누락을 방지하기 위해 강제로 대문자 정규화.
        provider = policy.provider.upper()

        try:
            # [설계 의도] Reflection/Dynamic Import 대신 명시적 분기를 사용하여 
            # 타입 추론(Type Inference)을 보장하고 IDE 환경에서의 리팩토링 안정성을 극대화함.
            if provider == "KIS":
                auth_strategy = cls._get_or_create_auth("KIS", config)
                return KISExtractor(http_client=http_client, auth_strategy=auth_strategy)

            elif provider == "UPBIT":
                auth_strategy = cls._get_or_create_auth("UPBIT", config)
                return UPBITExtractor(http_client=http_client, auth_strategy=auth_strategy)

            elif provider == "FRED":
                return FREDExtractor(http_client=http_client)

            elif provider == "ECOS":
                return ECOSExtractor(http_client=http_client)
                
            else:
                raise ExtractorError(f"지원하지 않는 제공자입니다: '{provider}'")

        except Exception as e:
            # [설계 의도] 구체적인 객체 생성 도중 발생하는 모든 에러(Config 속성 누락, 인증 실패 등)를 
            # 도메인 표준 에러인 ExtractorError로 래핑하여 상위 스케줄러의 에러 핸들링 일관성을 보장함.
            raise ExtractorError(f"'{provider}' 수집기 초기화에 실패했습니다: {str(e)}") from e