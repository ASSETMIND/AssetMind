"""
데이터 적재 파이프라인의 단일 진입점(Facade) 역할을 수행하는 서비스 계층입니다.
설정(yml) 값에 따라 내부적으로 적절한 구체 로더(Concrete Loader, 예: S3Loader)를 동적으로 초기화하고 실행을 위임합니다.
시스템 기동 시의 부하를 줄이고 런타임 성능을 극대화하기 위해, 로더 인스턴스를 지연 초기화(Lazy Initialization)하고 
메모리에 캐싱(Caching)하는 레지스트리 패턴(Registry Pattern)으로 최적화되었습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 스케줄러 또는 파이프라인 컨트롤러로부터 수집 및 정규화가 완료된 ExtractedDTO 유입.
2. Initialization: `execute_load()` 호출 시 캐시를 확인하고, Miss 발생 시에만 `_get_or_create_loader()`를 통해 타겟 로더 지연 로딩.
3. Delegation: 캐싱된 구체 로더(ILoader 구현체)의 `load()` 템플릿 메서드로 DTO 전달 및 실행 위임.
4. Output: 타겟 스토리지 적재 파이프라인의 최종 성공 여부(Boolean) 반환.

주요 기능:
- Lazy Initialization: 애플리케이션 시작 시점에 무거운 모듈(Boto3, Psycopg2 등)의 임포트와 네트워크 커넥션을 맺지 않고, 실제 적재가 일어나는 최초 시점에만 로더를 초기화하여 메모리 점유와 기동 시간 최소화.
- Instance Caching (Registry Pattern): 한 번 초기화된 로더 인스턴스를 내부 딕셔너리에 보관하여, 수만 건의 데이터가 스트리밍되는 상황에서도 초기화 오버헤드 없이 즉시 재사용(Fast-Path) 보장.
- Exception & Logging Centralization: 시스템 전역의 `log_decorator`와 도메인 표준 예외(`LoaderError`, `ConfigurationError`)를 활용하여 노이즈 없는 일관된 에러 핸들링 및 가시성(Observability) 확보.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Lazy Initialization & Caching vs Eager Initialization:
  - 장점: 불필요한 추상화 계층을 줄이고 인스턴스를 재사용함으로써 런타임 반복 호출에 대한 객체 생성 오버헤드를 제로(0)에 가깝게 줄이고 파이프라인 시작 성능을 극대화함.
  - 단점: 파이프라인 기동 후 첫 번째 `execute_load` 호출 시 모듈 로드 및 커넥션 연결로 인한 미세한 지연(Cold Start)이 발생함.
  - 근거: 실제 ETL 운영 환경에서는 단발성 호출보다 연속적인 대량의 데이터 처리가 주를 이룸. 1회의 Cold Start 비용을 지불하더라도 수만 회의 호출 성능(I/O 병목 해소)을 극대화하는 것이 전체 시스템 처리량(Throughput) 관점에서 압도적으로 유리하므로 이 설계를 채택함.
"""

import logging
from typing import Dict, Optional

from src.common.config import ConfigManager
from src.common.dtos import ExtractedDTO
from src.common.interfaces import ILoader
from src.common.exceptions import ConfigurationError, LoaderError
from src.common.log import LogManager
from src.common.decorators.log_decorator import log_decorator

# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# [설계 의도] 파이프라인 설정(loader.yml)에 명시적 타겟이 누락되었을 경우를 대비한 
# 방어적 대체값(Fallback). 데이터 유실을 막기 위해 기본 스토리지인 S3를 강제함.
DEFAULT_LOADER_TARGET: str = "s3"


# ==============================================================================
# [Main Class] LoaderService
# ==============================================================================
class LoaderService:
    """데이터 적재 파이프라인의 실행을 총괄하는 고성능 Facade 서비스 클래스.
    
    내부적으로 ILoader 구현체들을 인메모리에 캐싱하여 불필요한 객체 생성 및 
    네트워크 I/O 초기화 비용을 방지합니다.

    Attributes:
        _config (ConfigManager): 글로벌 환경 설정 및 스토리지 접속 정보를 담고 있는 싱글톤 관리자 객체.
        _target_loader (str): 런타임에 주입받은 대상 적재 시스템 식별자 (예: 'aws', 'postgres').
        _logger (logging.Logger): 클래스별로 격리된 구조화 로깅을 위한 인스턴스.
        _loader_cache (Dict[str, ILoader]): 타겟명(key)에 매핑된 활성 로더 인스턴스(value)를 보관하는 인메모리 캐시.
    """

    def __init__(self, target_loader: str) -> None:
        """LoaderService 인스턴스를 초기화하고 캐시 공간을 할당합니다.

        Args:
            target_loader (str): 적재를 수행할 대상 스토리지 식별자 (예: "aws", "postgres").
        """
        # [설계 의도] 서비스 생성 시점에는 무거운 외부 라이브러리(Boto3 등) 연동을 배제하고, 
        # 오직 설정 로드와 인메모리 캐시 딕셔너리만 할당하여 기동 속도를 최적화함.
        self._config = ConfigManager.load("loader")
        self._target_loader = target_loader
        self._logger = LogManager.get_logger(self.__class__.__name__)
        self._loader_cache: Dict[str, ILoader] = {}

    def _get_or_create_loader(self) -> ILoader:
        """설정값에 지정된 타겟 시스템에 맞는 로더를 반환합니다 (지연 로딩 및 캐싱 적용).

        Returns:
            ILoader: 환경에 맞게 초기화가 완료된 구체적인 데이터 적재기 인스턴스.

        Raises:
            ConfigurationError: 설정된 타겟 시스템이 파이프라인에서 지원하지 않는 규격일 경우.
            LoaderError: 구체 클래스의 동적 임포트(Dynamic Import) 또는 인스턴스화 과정에서 에러 발생 시.
        """
        target_system = self._target_loader.strip().lower()

        # 1. [Fast-Path] 캐시에 이미 로더 인스턴스가 존재하면 즉시 반환 (속도 극대화)
        # [설계 의도] 수천~수만 번 호출되는 적재 파이프라인에서 매번 인스턴스를 생성하는 
        # 오버헤드를 완벽히 제거하는 Registry/Cache 패턴.
        if target_system in self._loader_cache:
            return self._loader_cache[target_system]

        # 2. [Cold-Start] 캐시 미스 시에만 동적 모듈 임포트 및 지연 초기화 수행
        self._logger.info(f"[{target_system.upper()}] 로더 인스턴스 지연 초기화를 시작합니다.")

        try:
            loader_policy = self._config.get_loader(target_system)

            # [설계 의도] 메인 프로세스 기동 시 불필요한 서드파티 모듈을 로드하지 않도록,
            # 분기 블록 내부에서 동적 임포트(Dynamic Import)를 수행함.
            if target_system == "aws":
                from src.loader.providers.s3_loader import S3Loader
                loader_instance = S3Loader(
                    bucket_name=loader_policy.s3.get("bucket_name"),
                    region=loader_policy.region
                )
                
            # elif target_system == "postgres":
            #     from src.loader.providers.postgresql_loader import PostgreSQLLoader
            #     loader_instance = PostgreSQLLoader(config=self._config)
                
            else:
                raise ConfigurationError(
                    message=f"지원하지 않는 로더 타겟입니다: '{target_system}'",
                    key_name="global_loader.target"
                )

            # 성공적으로 생성된 인스턴스를 향후 재사용을 위해 캐시에 등록
            self._loader_cache[target_system] = loader_instance
            return loader_instance

        except Exception as e:
            # [설계 의도] 설정 누락 등 명시적 ConfigurationError는 상위로 Bypassing 처리.
            if isinstance(e, ConfigurationError):
                raise e
                
            # [설계 의도] 예측 못한 에러(ImportError, 네트워크 타임아웃 등)는 
            # 파이프라인 공통 규격에 맞게 도메인 예외인 LoaderError로 강제 래핑하여 추적성 확보.
            raise LoaderError(
                message=f"[{target_system.upper()}] 로더 지연 초기화 중 오류 발생",
                details={"target": target_system, "error": str(e)},
                original_exception=e,
                should_retry=False
            ) from e

    @log_decorator()
    def execute_load(self, dto: ExtractedDTO) -> bool:
        """수집 계층으로부터 전달받은 DTO를 타겟 스토리지에 안전하게 적재합니다.

        이미 정의된 `log_decorator`를 활용하여 함수 진입/종료 소요 시간, 
        예외 발생 추적 등의 보일러플레이트를 완전히 제거했습니다.

        Args:
            dto (ExtractedDTO): 적재할 대상 데이터와 수집 메타데이터가 포함된 표준 전송 객체.

        Returns:
            bool: 전체 물리적 적재 프로세스의 최종 완료 및 성공 여부.
            
        Raises:
            LoaderError: 입력 DTO 타입이 유효하지 않거나, 하위 로더 실행 중 치명적 예외 발생 시.
        """
        # [설계 의도] 파이프라인 간 데이터 컨트랙트(Contract) 강제 보장.
        # Duck Typing에 의존하지 않고 명시적으로 ExtractedDTO 타입인지 런타임에 엄격히 검증하여 데이터 오염 차단.
        if not isinstance(dto, ExtractedDTO):
            raise LoaderError(
                message=f"잘못된 DTO 타입 전달. ExtractedDTO가 필요합니다. (Type: {type(dto)})",
                details={"provided_type": str(type(dto))},
                should_retry=False
            )

        # 1. 지연 로딩 및 캐시된 로더 인스턴스 획득 (첫 호출 시에만 초기화 비용 발생)
        loader = self._get_or_create_loader()
        
        # 2. 적재 위임 수행
        # [설계 의도] 서비스 계층은 구체적인 타겟(S3, DB 등)의 구현을 몰라도 
        # ILoader 인터페이스의 load 템플릿 메서드 하나만 호출하여 다형성(Polymorphism)을 달성함.
        return loader.load(dto)