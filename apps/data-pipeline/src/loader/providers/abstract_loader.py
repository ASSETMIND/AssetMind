"""
`ILoader` 인터페이스를 구현하며, 모든 구체적인 데이터 적재기(Concrete Loader, 예: S3Loader, PostgreSQLLoader)가 
공통적으로 준수해야 할 파이프라인 실행 흐름(Template Method Pattern)과 중앙 집중식 로깅/에러 핸들링 로직을 제공하는 추상화 계층입니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 수집 계층(Extractor)으로부터 추출 및 정규화가 완료된 표준 데이터 객체(ExtractedDTO) 유입.
2. Validation: `_validate_dto` 훅(Hook)을 통해 타겟 스토리지에 적재하기 전 스키마 및 데이터 무결성 사전 검증.
3. Execution: `_apply_load` 훅을 통해 하위 클래스에 위임된 물리적 적재(Network I/O) 알고리즘 적용.
4. Output: 검증 및 적재 프로세스의 최종 성공 여부를 나타내는 Boolean 값 반환.

주요 기능:
- Template Method Pattern: 검증 -> 적재 -> 로깅으로 이어지는 표준화된 파이프라인 실행 흐름을 상위에서 강제하여 일관성 확보.
- Exception Wrapping: 하위 클래스의 네트워크 I/O 중 발생하는 예측 불가능한 네이티브 예외를 도메인 표준 예외(LoaderError)로 규격화.
- Observability (가시성): 모든 적재기의 실행 시작/종료 시간 및 에러 발생 시점을 데코레이터와 템플릿 로직을 통해 자동 추적.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Centralized Template Method vs Subclass Autonomy:
  - 장점: 중복되는 로깅 및 예외 처리(Try-Catch) 보일러플레이트 코드를 부모 클래스로 완벽히 끌어올려, 하위 클래스 개발자는 순수 데이터 적재 알고리즘(`_apply_load`)과 도메인 검증(`_validate_dto`)에만 집중할 수 있어 DRY 원칙이 극대화됨.
  - 단점: 파이썬의 동적 타이핑 특성상, 추상 클래스의 보호 속성(Protected Attributes) 접근이나 오버라이딩을 컴파일 타임에 문법적으로 완벽히 강제하기는 어려움.
  - 근거: 실제 프로덕션 파이프라인에서는 적재 단계(DB, S3 등)에서 네트워크 타임아웃이나 인증 에러가 가장 빈번하게 발생함. "어떤 적재기에서 에러가 터졌는가?"를 즉시 추적하는 것이 운영의 핵심이므로, 개별 하위 클래스의 자율성보다 중앙 집중식 에러 핸들링을 통한 파이프라인 안정성 확보가 압도적으로 중요함.
"""

import logging
from abc import abstractmethod

from src.common.interfaces import ILoader
from src.common.dtos import ExtractedDTO
from src.common.exceptions import ETLError, LoaderError, LoaderValidationError, ConfigurationError
from src.common.log import LogManager
from src.common.config import ConfigManager
from src.common.decorators.log_decorator import log_decorator


# ==============================================================================
# [Configuration] Constants
# ==============================================================================
# [설계 의도] 대용량 데이터 적재 시 발생할 수 있는 네트워크 지연을 고려하여, 
# 모든 하위 로더들이 공통으로 참조할 수 있는 넉넉한 기본 타임아웃 값(5분)을 상수로 정의함.
DEFAULT_LOADER_TIMEOUT_SEC: int = 300

# ==============================================================================
# [Abstract Class] AbstractLoader
# ==============================================================================
class AbstractLoader(ILoader):
    """모든 데이터 적재기(Loader)의 기반이 되는 최상위 템플릿(추상) 클래스.
    
    구현체(S3Loader, PostgreSQLLoader 등)는 이 클래스를 상속받아 구체적인 
    적재 로직(Hook 메서드)을 구현해야 하며, 설정(Config)은 자동으로 주입됩니다.

    Attributes:
        config (ConfigManager): 데이터 적재 정책 및 스토리지 접속 정보가 포함된 앱 전역 설정 객체.
        _logger (logging.Logger): 클래스별 격리된 구조화 로깅을 제공하는 커스텀 로거 인스턴스.
    """

    def __init__(self) -> None:
        """AbstractLoader 인스턴스를 초기화하고 시스템 필수 의존성을 로드합니다.

        Raises:
            ConfigurationError: `loader.yml` 설정 파일 로드에 실패하거나 문법 오류가 있는 경우.
        """
        # [설계 의도] 파이프라인 설정(loader.yml)을 싱글톤 캐시에서 로드하여 
        # 자식 클래스들이 안전하게 DB/S3 접속 정책에 접근할 수 있도록 일관된 환경 제공.
        self.config = ConfigManager.load("loader")
        self._logger = LogManager.get_logger(self.__class__.__name__)

    @log_decorator()
    def load(self, dto: ExtractedDTO) -> bool:
        """데이터 적재 파이프라인의 핵심 생명주기(Template Method)를 실행합니다.
        
        사전 검증(Validation), 실제 적재(Execution), 반환 타입 검증 및 에러 래핑의 
        실행 순서를 엄격하게 제어하여 하위 구현체의 예외를 중앙에서 통제합니다.

        Args:
            dto (ExtractedDTO): 적재할 대상 데이터와 메타데이터가 포함된 전송 객체.

        Returns:
            bool: 전체 적재 프로세스의 성공 여부.

        Raises:
            LoaderValidationError: DTO의 필수 데이터 누락 등 무결성 사전 검증 실패 시.
            LoaderError: 적재 중 발생한 네트워크 이슈 등 런타임 에러 또는 비정상적인 반환값 발생 시.
        """
        loader_name = self.__class__.__name__

        try:
            # 1. 사전 검증 훅(Hook): 입력 DTO의 스키마 및 무결성 사전 검증
            # [설계 의도] 유효하지 않은(비어있거나 손상된) 데이터로 인해 발생하는 
            # 무의미한 스토리지 네트워크 I/O 및 클라우드 비용 발생을 원천 차단(Fail-Fast).
            if not self._validate_dto(dto):
                raise LoaderValidationError(
                    message=f"[{loader_name}] DTO 무결성 검증을 통과하지 못했습니다.",
                    invalid_fields=["validation_failed_in_subclass"],
                    dto_name=dto.__class__.__name__
                )

            # 2. 적재 로직 훅(Hook): 하위 클래스에서 오버라이딩한 물리적 적재 로직 실행
            # [설계 의도] 다형성(Polymorphism) 활용. 부모 클래스는 대상 스토리지가 S3인지 DB인지 
            # 알 필요 없이 인터페이스에만 의존하여 결합도를 최소화함.
            is_success = self._apply_load(dto)

            # 3. 결과 검증: 반환 타입 강제
            # [설계 의도] 파이썬의 동적 타이핑으로 인한 휴먼 에러 방지. 하위 클래스 개발자가 
            # return 문을 잊어 None이 반환되는 치명적인 실수를 런타임에 방어함.
            if not isinstance(is_success, bool):
                raise LoaderError(
                    message=f"[{loader_name}] 반환 타입 오류: bool 타입이 아닙니다. (Type: {type(is_success)})",
                    should_retry=False
                )
            
            return is_success

        except ETLError as e:
            # [설계 의도] 하위 계층에서 이미 도메인 표준 에러(ETLError)로 규격화하여 던진 예외는 
            # 로깅 정보 보존을 위해 구조 변경 없이 상위 파이프라인으로 그대로 전파(Bypass).
            raise e
            
        except Exception as e:
            # [설계 의도] 예측 불가한 서드파티 라이브러리 예외(MemoryError, Boto3 에러, psycopg2 에러 등)를 
            # 포착하여 파이프라인 공통 규격인 LoaderError로 래핑함. 이를 통해 중앙 로깅 시스템(ELK/Datadog)에서 
            # 구조화된 검색 및 얼럿(Alert) 파싱을 완벽하게 보장함.
            raise LoaderError(
                message=f"[{loader_name}] 데이터 적재 중 예기치 않은 오류가 발생했습니다.",
                details={"loader": loader_name, "raw_error": str(e)},
                original_exception=e,
                should_retry=False
            ) from e

    @abstractmethod
    def _validate_dto(self, dto: ExtractedDTO) -> bool:
        """적재 전 `ExtractedDTO`의 데이터 스키마 및 무결성을 사전 검증하는 훅(Hook) 메서드.
        
        하위 클래스 구현체는 대상 스토리지(DB, S3 등)의 성격에 맞추어 
        필수 데이터(Data, Meta) 포함 여부 및 데이터 형식을 확인해야 합니다.

        Args:
            dto (ExtractedDTO): 검증할 데이터 객체.
            
        Returns:
            bool: 유효성 검증 통과 여부. 실패 시 `False`를 반환하거나 `LoaderValidationError`를 직접 발생시킵니다.
        """
        pass

    @abstractmethod
    def _apply_load(self, dto: ExtractedDTO) -> bool:
        """대상 스토리지에 실제 데이터를 적재하는 물리적 알고리즘을 수행하는 훅(Hook) 메서드.
        
        모든 구체 클래스(S3Loader, PostgreSQLLoader 등)는 이 메서드를 반드시 오버라이딩하여, 
        네트워크 I/O를 수반하는 구체적인 적재 로직 및 트랜잭션 관리를 구현해야 합니다.

        Args:
            dto (ExtractedDTO): 사전 검증을 통과한 적재 대상 데이터 객체.

        Returns:
            bool: 물리적 적재 프로세스의 최종 성공 여부.
        """
        pass