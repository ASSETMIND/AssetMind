"""
[LoaderService 모듈]

[모듈 목적 및 상세 설명]
파이프라인의 단일 진입점(Facade) 역할을 수행하며, 설정(yml) 값에 따라 내부적으로 적절한 로더(S3 또는 DB)를 동적으로 초기화하고 실행을 위임합니다.
UML의 정적 초기화 방식보다 런타임 성능 및 리소스 효율을 우선시하여, 로더 인스턴스를 지연 초기화(Lazy Initialization)하고 메모리에 캐싱(Caching)하는 패턴으로 최적화되었습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
ConfigManager, ExtractedDTO -> [LoaderService.execute_load() 호출] -> [로더 인스턴스 캐시 확인 및 지연 로딩] -> [ILoader.load() 위임 실행] -> Boolean (성공 여부 반환)

주요 기능:
- [기능 1] 성능 중심의 지연 초기화(Lazy Initialization): 애플리케이션 시작 시점에 무거운 모듈(Boto3, Psycopg2 등)의 임포트와 네트워크 커넥션을 맺지 않고, 실제 적재가 일어나는 최초 시점에만 로더를 초기화하여 메모리 점유와 기동 시간을 최소화합니다.
- [기능 2] 인스턴스 캐싱(Registry Pattern): 한 번 초기화된 로더 인스턴스를 내부 딕셔너리에 캐싱하여, 수만 건의 데이터가 스트리밍되는 상황에서도 초기화 오버헤드 없이 즉시 재사용(Fast-Path)되도록 설계했습니다.
- [기능 3] 통합 데코레이터 및 예외 재사용: 신규 예외를 만들지 않고 시스템 전역의 `log_decorator`와 `ETLError` 하위 클래스(ConfigurationError, LoaderError)만을 활용하여 노이즈 없는 일관된 예외 처리를 보장합니다.

Trade-off: 
- [장점] 캐싱 및 지연 초기화를 통해 파이프라인의 시작 성능을 극대화하고 런타임 반복 호출에 대한 오버헤드를 제로(0)에 가깝게 줄였습니다. 불필요한 추상화 계층을 줄여 I/O 병목 해소에 집중했습니다.
- [단점] 파이프라인 기동 후 첫 번째 `execute_load` 호출 시 모듈 로드 및 커넥션 연결로 인한 약간의 지연(Cold Start)이 발생합니다.
- [근거] 실제 ETL 운영 환경에서는 단발성 호출보다 연속적인 대량의 데이터 처리가 주를 이루므로, 1회의 Cold Start 비용을 지불하고 수만 회의 호출 성능을 극대화하는 것이 압도적으로 유리합니다.
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
# Constants & Configuration
# ==============================================================================
# 기본 적재 타겟 명시 (loader.yml 설정에 명시적 타겟이 누락되었을 경우의 방어적 Fallback)
DEFAULT_LOADER_TARGET: str = "s3"


# ==============================================================================
# Main Class/Functions
# ==============================================================================
class LoaderService:
    """데이터 적재 파이프라인을 총괄하는 고성능 Facade 서비스 클래스.
    
    내부적으로 ILoader 구현체들을 캐싱하여 불필요한 객체 생성 및 
    네트워크 I/O를 방지합니다.

    Attributes:
        _config_manager (ConfigManager): 글로벌 환경 설정 및 접속 정보를 담고 있는 관리자 객체.
        _loader_cache (Dict[str, ILoader]): 타겟명(key)에 따른 로더 인스턴스(value)를 저장하는 인메모리 캐시.
        _logger (logging.Logger): 구조화된 로깅을 위한 서비스 레벨 로거.
    """

    def __init__(self, config: ConfigManager) -> None:
        """LoaderService를 초기화하고 캐시 공간을 할당합니다.

        기존 UML과 다르게 이 시점에서는 무거운 구체적 로더 
        클래스를 초기화하지 않고(O(1) 연산 유지) 뼈대만 준비합니다.

        Args:
            config (ConfigManager): 애플리케이션 전역 설정 객체.

        Raises:
            ConfigurationError: ConfigManager가 유효하지 않은 경우.
        """
        if config is None:
            raise ConfigurationError("LoaderService 초기화 실패: ConfigManager가 누락되었습니다.")
            
        self._config = config
        self._logger = LogManager.get_logger(self.__class__.__name__)
        
        # 성능 최적화를 위한 로더 인스턴스 레지스트리
        self._loader_cache: Dict[str, ILoader] = {}

    def _get_or_create_loader(self) -> ILoader:
        """설정값에 따른 타겟 로더를 반환합니다. (캐시 우선 참조, 캐스 미스 시 지연 로딩 수행)

        Returns:
            ILoader: 환경에 맞게 초기화된 구체적 로더 인스턴스.

        Raises:
            ConfigurationError: 지원하지 않는 타겟이 설정되었을 경우.
            LoaderError: 구체 클래스의 임포트 또는 인스턴스화 과정에서 에러가 발생한 경우.
        """
        target_system = str(self._config.get("global_loader.target", DEFAULT_LOADER_TARGET)).strip().lower()

        # [Fast-Path] 캐시에 이미 로더 인스턴스가 존재하면 즉시 반환 (속도 극대화)
        if target_system in self._loader_cache:
            return self._loader_cache[target_system]

        # [Cold-Start] 캐스 미스 시에만 지연 초기화 수행
        self._logger.info(f"[{target_system.upper()}] 로더 인스턴스 지연 초기화(Lazy Initialization)를 시작합니다.")
        try:
            if target_system == "s3":
                from src.loader.providers.s3_loader import S3Loader
                loader_instance = S3Loader(config=self._config)
                
            # elif target_system == "postgres":
            #     from src.loader.providers.postgresql_loader import PostgreSQLLoader
            #     loader_instance = PostgreSQLLoader(config=self._config)
                
            else:
                raise ConfigurationError(
                    message=f"지원하지 않는 로더 타겟입니다: '{target_system}'",
                    key_name="global_loader.target"
                )

            # 성공적으로 생성된 인스턴스를 캐시에 등록
            self._loader_cache[target_system] = loader_instance
            return loader_instance

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise e
                
            # 예측 못한 에러(ImportError 등)는 파이프라인 규격에 맞게 LoaderError로 래핑
            raise LoaderError(
                message=f"[{target_system.upper()}] 로더 지연 초기화 중 치명적 오류 발생",
                details={"target": target_system, "error": str(e)},
                original_exception=e,
                should_retry=False
            ) from e

    @log_decorator()
    def execute_load(self, dto: ExtractedDTO) -> bool:
        """클라이언트로부터 전달받은 DTO를 최종 스토리지에 적재합니다.

        이미 정의된 `log_decorator`를 활용하여 함수 진입/종료 소요 시간, 
        예외 발생 추적 등의 보일러플레이트를 완전히 제거했습니다.

        Args:
            dto (ExtractedDTO): 적재할 데이터와 메타데이터가 포함된 DTO 객체.

        Returns:
            bool: 모든 적재 프로세스 완료 및 성공 여부.
            
        Raises:
            LoaderError: 입력 DTO가 유효하지 않거나 내부 로더에서 에러가 발생한 경우.
        """
        if not isinstance(dto, ExtractedDTO):
            raise LoaderError(
                message=f"잘못된 DTO 타입 전달. ExtractedDTO가 필요합니다. (Type: {type(dto)})",
                details={"provided_type": str(type(dto))},
                should_retry=False
            )

        # 1. 지연 로딩 및 캐시된 로더 인스턴스 획득 (첫 호출 시에만 초기화 비용 발생)
        loader = self._get_or_create_loader()
        
        # 2. 적재 위임 수행
        self._logger.info(f"[{loader.__class__.__name__}] 데이터 적재 요청 (Job ID: {dto.meta.get('job_id', 'Unknown')})")
        return loader.load(dto)