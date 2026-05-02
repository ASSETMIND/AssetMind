"""
[abstract_reader.py]

[내부 저장소(S3, PostgreSQL 등)로부터 데이터를 읽어오기 위한 최상위 추상화 계층(Template Method)]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Request: 다운스트림(Transformer/Loader)에서 특정 데이터 소스(source_path)에 대한 스트리밍 읽기 요청 유입.
2. Validation: 입력된 경로 및 리더 상태(초기화 여부) 사전 검증.
3. Execution: 하위 구현체(Concrete Reader)에 정의된 `_generate_chunks` 호출.
4. Output: 메모리 OOM 방지를 위해 청크(Batch) 단위로 데이터를 순차 반환(Yield)하는 제너레이터(Iterator) 반환.

주요 기능:
- 템플릿 메서드 패턴(Template Method Pattern) 기반의 표준화된 데이터 읽기 파이프라인(Lifecycle) 강제.
- OOM 방지를 위한 제너레이터(Generator/Iterator) 반환 규격 강제.
- @log_decorator를 활용한 스트림 수립 생명주기 및 파라미터 자동 추적.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. Generator(Iterator) 반환 규격 강제:
   - 장점: 수십 GB의 대용량 데이터를 메모리에 한 번에 올리지 않고 청크 단위로 처리할 수 있어 Worker Node의 OOM을 완벽히 방어함.
   - 단점: 하류(Downstream) 로직에서 전체 데이터를 한 번에 조작(예: Global Sort, 전역 Aggregation)하기 까다로워짐.
   - 근거: 데이터 레이크하우스(Medallion) 환경에서 내부 I/O의 안정성이 최우선이므로, 메모리 제약을 통제할 수 있는 스트리밍 방식을 표준으로 삼는 것이 타당함. 전역 연산은 분산 처리 프레임워크나 DB 내부 연산으로 위임해야 함.
2. 템플릿 내 `yield from` 방어 로직 적용:
   - 장점: 제너레이터 실행 도중(`next()` 호출 시점) 발생하는 런타임 예외를 `DataReadStreamError` 하나로 규격화하여 파이프라인의 에러 파싱을 단순화함.
   - 단점: `yield from` 래핑으로 인해 제너레이터 호출 스택이 한 단계 깊어져 마이크로초(us) 단위의 미세한 오버헤드가 발생함.
   - 근거: 대용량 데이터 스트리밍 시 발생할 수 있는 네트워크 단절, 포맷 에러 등의 원본 예외를 놓치지 않고 구조화된 로그로 남기는 가시성(Observability)이 성능 오버헤드보다 압도적으로 중요함.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, Optional

from src.common.config import ConfigManager
from src.common.log import LogManager
from src.common.decorators.log_decorator import log_decorator
from src.common.exceptions import ReaderInitializationError, DataReadStreamError

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [설계 의도] 다운스트림(Pandas 등)으로 데이터를 넘길 때 기본적으로 한 번에 반환할 레코드 수.
# OOM을 방어하고 DataFrame 변환 효율을 극대화하는 스윗스팟(10,000)으로 설정하여 매직 넘버 사용을 배제함.
DEFAULT_BATCH_SIZE: int = 10000

# ==============================================================================
# Main Class/Functions
# ==============================================================================
class AbstractReader(ABC):
    """내부 데이터 저장소(S3, DB 등) I/O를 전담하는 최상위 리더(Reader) 추상 클래스.
    
    구현체(S3ZstdStreamingReader, PostgresReader 등)는 이 클래스를 상속받아 구체적인 
    스트리밍 로직(_generate_chunks)을 구현해야 하며, 모든 리더는 Iterator를 반환해야 합니다.

    Attributes:
        provider_name (str): 리더의 고유 식별자 (예: 'S3_BRONZE', 'POSTGRES_SILVER').
        logger (logging.Logger): 클래스별 격리된 추적성을 제공하는 로거 인스턴스.
        config (ConfigManager): 스토리지 정책이 포함된 전역 설정 객체.
    """

    def __init__(self, provider_name: str) -> None:
        """AbstractReader 인스턴스를 초기화하고 필수 설정을 준비합니다.

        Args:
            provider_name (str): 구체화된 리더의 이름. 예외 발생 시 디버깅 컨텍스트로 활용됨.

        Raises:
            ReaderInitializationError: provider_name이 누락된 상태로 초기화 시도 시.
        """
        # [설계 의도] 방어적 프로그래밍 (Fail-Fast). 
        # 로깅 및 예외 추적에 필수적인 식별자가 없으면 인스턴스화 자체를 차단함.
        if not provider_name:
            raise ReaderInitializationError(
                message="Reader 초기화 실패: provider_name은 필수 파라미터입니다.", 
                provider_name="Unknown"
            )
        
        self.provider_name = provider_name
        self.logger = LogManager.get_logger(self.__class__.__name__)
        
        # [설계 의도] 환경 설정의 결합도를 낮추기 위해 ConfigManager를 지연 로딩 방식으로 연결함.
        self.config = ConfigManager.load("reader") 

        # 클라이언트(Boto3, DB Session 등) 지연 초기화 (Lazy Initialization)를 위한 내부 변수
        self._client: Any = None

    @log_decorator()
    def read_stream(
        self, 
        source_path: str, 
        batch_size: int = DEFAULT_BATCH_SIZE, 
        **kwargs: Any
    ) -> Iterator[Any]:
        """데이터 리더 파이프라인의 생명주기를 제어하는 템플릿 메서드(Template Method).

        [설계 의도] 
        @log_decorator를 통해 '스트림 생성 요청'의 시작과 끝 파라미터를 로깅합니다.
        제너레이터의 특성상 이 함수 자체는 즉시 종료되며, 실제 데이터 I/O 도중 발생하는 에러는 
        내부의 try-except 블록(yield from)을 통해 구조화된 에러로 래핑하여 방어합니다.

        Args:
            source_path (str): 읽어올 데이터의 논리적/물리적 경로 (예: S3 Key, Table 명).
            batch_size (int, optional): 한 번에 반환할 레코드 수. Defaults to DEFAULT_BATCH_SIZE.
            **kwargs (Any): 기타 하위 구현체 쿼리 수행에 필요한 동적 파라미터.

        Returns:
            Iterator[Any]: 메모리 제한에 맞춰 청크 단위로 분할된 데이터 스트림(제너레이터).

        Raises:
            DataReadStreamError: 스트림 읽기 도중 네트워크 단절이나 포맷 에러 발생 시.
        """
        # 1. Lazy Initialization (네트워크 커넥션 최적화)
        # [설계 의도] 객체 생성 시점이 아닌, 실제 데이터 읽기가 요청되는 시점에 
        # 무거운 커넥션을 수립하여 메모리와 소켓 리소스를 절약함.
        if self._client is None:
            self._client = self._initialize_client()
            
        # 2. Validation Hook 호출
        self._validate_source(source_path)
        
        # 3. Execution (Generator 래핑 및 런타임 에러 방어)
        try:
            # [설계 의도] 하위 구현체의 제너레이터를 직접 반환하지 않고 yield from으로 감싸서
            # 하류(Downstream)가 next()를 호출할 때 발생하는 스트리밍 중단의 예외를 안전하게 포착함.
            yield from self._generate_chunks(source_path, batch_size, **kwargs)
            
        except Exception as e:
            # [설계 의도] 제너레이터 내부 런타임 에러는 데코레이터가 종료된 이후 발생하므로 명시적 로깅 수행
            error_msg = f"[{self.provider_name}] 데이터 스트림 런타임 오류 발생: {source_path}"
            self.logger.error(error_msg, exc_info=True)
            
            # 파이프라인 표준 에러(ETLError 체인)로 규격화하여 전파
            if not isinstance(e, DataReadStreamError):
                raise DataReadStreamError(
                    message=error_msg,
                    source_path=source_path,
                    original_exception=e
                ) from e
            raise

    @abstractmethod
    def _initialize_client(self) -> Any:
        """스토리지 접근을 위한 물리적 클라이언트(Boto3, psycopg2 등)를 초기화하는 훅(Hook).
        
        Returns:
            Any: 인증 및 연결이 수립된 클라이언트 인스턴스.
            
        Raises:
            ReaderInitializationError: 클라이언트 생성에 실패했을 경우.
        """
        pass

    @abstractmethod
    def _validate_source(self, source_path: str) -> None:
        """읽기 대상 경로(source_path)나 쿼리 규격의 유효성을 사전 검증하는 훅(Hook).
        
        Args:
            source_path (str): 대상 S3 경로 또는 DB 타겟 정보.
            
        Raises:
            ReaderInitializationError: 경로 형식이 잘못되었거나 누락된 경우.
        """
        pass

    @abstractmethod
    def _generate_chunks(self, source_path: str, batch_size: int, **kwargs: Any) -> Iterator[Any]:
        """실제 데이터를 물리 계층에서 청크(Batch) 단위로 읽어와 반환하는 제너레이터 훅(Hook).
        
        Args:
            source_path (str): 타겟 데이터 경로.
            batch_size (int): yield 할 최대 레코드/바이트 크기.
            **kwargs (Any): 기타 하위 구현 특화 파라미터.
            
        Returns:
            Iterator[Any]: List[Dict] 형태의 레코드 묶음 혹은 DataFrame 등.
        """
        pass