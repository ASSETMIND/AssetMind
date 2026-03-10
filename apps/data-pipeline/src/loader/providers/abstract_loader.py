"""
[AbstractLoader 모듈]

[모듈 목적 및 상세 설명]
ILoader 인터페이스를 구현하며, 모든 구체적인 적재기(Concrete Loader, 예: S3Loader, PostgreSQLLoader)들이 공통적으로 가져야 할 실행 흐름(Template Method Pattern)과 로깅/에러 핸들링 로직을 제공합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
ExtractedDTO -> [_validate_dto: 스키마/데이터 무결성 검증] -> [_apply_load: 실제 적재 알고리즘 적용] -> Boolean (성공 여부 반환)

주요 기능:
- [기능 1] Template Method (`load`): 검증 -> 적재 -> 로깅으로 이어지는 표준화된 파이프라인 실행 흐름 강제
- [기능 2] 예외 포착 및 래핑: 하위 클래스에서 발생하는 예측 불가능한 런타임 에러를 도메인 예외(LoaderError)로 규격화
- [기능 3] 로깅 내장: 모든 적재기의 실행 시작/종료 및 에러 발생 시점을 자동으로 추적

Trade-off: 장점 - 중복되는 로깅 및 예외 처리(Try-Catch) 보일러플레이트를 부모 클래스로 끌어올려, 하위 클래스 개발자는 순수 데이터 적재 알고리즘(`_apply_load`)과 검증(`_validate_dto`)에만 집중할 수 있습니다. 단점 - 파이썬의 동적 타이핑 특성상, 추상 클래스의 보호 속성(Protected Attributes) 접근이나 오버라이딩을 문법적으로 완벽히 강제하기는 어렵습니다. 근거 - 실제 프로덕션 파이프라인에서는 적재 단계(DB, S3 등)에서 네트워크 타임아웃이나 인증 에러가 빈번하게 발생합니다. "어떤 적재기에서 에러가 터졌는가?"를 즉시 추적하는 것이 생명이며, 모든 구체 클래스가 각자 로깅과 에러 핸들링을 구현하면 반드시 누락이 발생하므로 중앙 집중식 에러 핸들링을 제공하는 템플릿 메서드 패턴 도입이 필수적입니다.
"""

import logging
from abc import abstractmethod

from src.common.interfaces import ILoader
from src.common.dtos import ExtractedDTO
from src.common.exceptions import ETLError, LoaderError, LoaderValidationError, ConfigurationError
from src.common.log import LogManager
from src.common.config import ConfigManager
from src.common.decorators.log_decorator import log_decorator


# 하위 로더들이 공통으로 사용할 수 있는 기본 타임아웃 값 등을 상수로 정의합니다.
DEFAULT_LOADER_TIMEOUT_SEC: int = 300

class AbstractLoader(ILoader):
    """모든 데이터 적재기의 기반이 되는 추상 클래스.
    
    구현체(S3Loader, PostgreSQLLoader 등)는 이 클래스를 상속받아 구체적인 
    적재 로직을 구현해야 하며, 반드시 ConfigManager를 주입받아야 합니다.

    Attributes:
        _config (ConfigManager): 애플리케이션 전역 설정 객체. (DB 커넥션 정보 등)
        _logger (logging.Logger): 구조화된 로깅을 위한 커스텀 로거 인스턴스.
    """

    def __init__(self, config: ConfigManager) -> None:
        """AbstractLoader를 초기화하고 필수 의존성을 검증합니다.

        Args:
            config (ConfigManager): 데이터 적재 정책 및 접속 정보가 포함된 설정 객체.

        Raises:
            ConfigurationError: 필수 의존성(Config 등)이 누락된 경우.
        """
        if config is None:
            raise ConfigurationError("초기화 실패: ConfigManager 인스턴스가 필요합니다.")
             
        self._config = config
        self._logger = LogManager.get_logger(self.__class__.__name__)

    @log_decorator()
    def load(self, dto: ExtractedDTO) -> bool:
        """데이터 적재 파이프라인의 뼈대(Template)를 실행합니다.
        
        로깅, DTO 검증, 실제 적재, 에러 핸들링의 순서를 엄격하게 제어합니다.

        Args:
            dto (ExtractedDTO): 적재할 대상 데이터 객체.

        Returns:
            bool: 적재 성공 여부.

        Raises:
            LoaderValidationError: DTO의 필수 데이터 누락 등 검증 실패 시.
            LoaderError: 적재 중 발생한 네트워크 이슈 등 런타임 에러.
        """
        loader_name = self.__class__.__name__

        try:
            # 1. 사전 검증: 입력 DTO의 스키마 및 무결성 사전 검증
            # 유효하지 않은 데이터로 인한 무의미한 네트워크 I/O 및 비용 발생 원천 차단
            if not self._validate_dto(dto):
                raise LoaderValidationError(
                    message=f"[{loader_name}] DTO 무결성 검증을 통과하지 못했습니다.",
                    invalid_fields=["validation_failed_in_subclass"],
                    dto_name=dto.__class__.__name__
                )

            # 2. 적재 로직: 하위 클래스에서 오버라이딩한 실제 물리적 적재 로직 실행
            # 다형성(Polymorphism) 활용: S3인지 DB인지 부모 클래스는 알 필요가 없음
            is_success = self._apply_load(dto)

            # 3. 결과 검증: 반환 타입 강제
            # 파이썬의 동적 타이핑으로 인한 버그 방지 (하위 클래스가 None을 반환하는 실수 차단)
            if not isinstance(is_success, bool):
                raise LoaderError(
                    message=f"[{loader_name}] 반환 타입 오류: bool 타입이 아닙니다. (Type: {type(is_success)})",
                    should_retry=False
                )
            
            return is_success

        except ETLError as e:
            # 이미 규격화된 도메인 에러는 구조 변경 없이 상위로 전파
            raise e
            
        except Exception as e:
            # 예측 불가한 네이티브 예외(MemoryError, Boto3/psycopg2 에러)를 포착하여 
            # 파이프라인 공통 규격인 LoaderError로 래핑. 이를 통해 로깅 시스템(ELK/Datadog)에서 구조화된 검색 보장
            error_msg = f"[{loader_name}] 데이터 적재 로직 수행 중 예기치 않은 오류 발생"
            self._logger.error(f"{error_msg} | Error: {e}", exc_info=True)
            raise LoaderError(
                message=error_msg,
                details={"loader": loader_name, "raw_error": str(e)},
                original_exception=e,
                should_retry=False
            ) from e

    @abstractmethod
    def _validate_dto(self, dto: ExtractedDTO) -> bool:
        """적재 전 ExtractedDTO의 무결성을 검증합니다.
        
        하위 클래스 구현체는 대상 스토리지(DB, S3)의 성격에 맞게 필수 데이터 포함 여부를 확인해야 합니다.
        검증 실패 시 `LoaderValidationError`를 직접 발생시키거나 `False`를 반환해야 합니다.

        Args:
            dto (ExtractedDTO): 검증할 데이터 객체.
            
        Returns:
            bool: 유효성 검증 통과 여부.
            
        Raises:
            LoaderValidationError: 데이터가 적재 조건을 만족하지 않을 경우.
        """
        pass

    @abstractmethod
    def _apply_load(self, dto: ExtractedDTO) -> bool:
        """실제 데이터 적재 알고리즘을 수행합니다.
        
        모든 구체 클래스(S3Loader, PostgreSQLLoader)는 이 메서드 내부에 
        네트워크 I/O를 수반하는 구체적인 적재 로직을 구현해야 합니다.

        Args:
            dto (ExtractedDTO): 적재할 대상 데이터 객체.

        Returns:
            bool: 적재 성공 여부.
        """
        pass