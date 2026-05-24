"""
[ReaderService]

[데이터 읽기 파이프라인의 단일 진입점(Facade) 역할을 수행하는 서비스 계층]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 분석가(Jupyter EDA 환경) 또는 파이프라인 제어기에서 타겟 스토리지 식별자 및 논리적/물리적 경로(source_path) 유입.
2. Initialization: `read_stream()` 호출 시 내부 레지스트리(인메모리 캐시)를 확인하고, Miss 발생 시 `_get_or_create_reader()`를 통해 대상 리더(예: S3ZstdStreamingReader) 지연 로딩(Lazy Loading).
3. Execution: 캐싱된 구체 리더(AbstractReader)의 `read_stream()` 템플릿 메서드에 S3 Object Key와 Batch Size를 전달하여 스트리밍 위임.
4. Output: Worker Node의 OOM(Out-Of-Memory)을 방지하며, 설정된 배치(청크) 단위로 데이터를 순차 반환(Yield)하는 제너레이터(Iterator) 파이프라인 반환.

주요 기능:
- Lazy Initialization & Registry Pattern: 시스템 기동 시 불필요한 네트워크 커넥션(Boto3 세션 등)을 맺지 않고, 인스턴스 캐싱을 통해 런타임 재사용성 및 파이프라인 기동 속도 극대화.
- Facade Interface: KIS, FRED, ECOS 등 다양한 프로바이더의 파티셔닝된 브론즈 데이터(Raw)를 하나의 `read_stream` 인터페이스로 통합 제공하여 다형성(Polymorphism) 달성.
- Pre-condition Validation (Fail-Fast): 물리 스토리지 I/O 레이어로 진입하기 전, `assert` 문을 활용하여 데이터 경로(source_path)의 타입 및 무결성을 조기에 검증.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 인메모리 싱글톤 레지스트리(캐싱) vs 호출 시점 인스턴스 매번 생성:
  - 장점: EDA 과정에서 일별 분할된 수백 개의 S3 JSONL 파티션 파일(예: `kis_kospi_...`, `fred_us_treasury_...`)을 연속적으로 순회할 때, 반복되는 클라우드 인증(STS) 및 Handshake 커넥션 비용을 완벽히 제거하여 I/O 처리량(Throughput)이 극대화됨.
  - 단점: 서비스 생명주기 동안 AbstractReader 인스턴스와 네트워크 소켓 상태가 메모리에 지속적으로 상주함.
  - 근거: 금융 시계열 데이터 분석 및 ML 특성 분리(Feature Engineering) 과정에서 가장 큰 병목은 컴퓨팅이 아닌 네트워크 대기(I/O Bound) 시간임. 약간의 메모리 점유(수십 MB)를 허용하더라도, 연결(Connection)을 재사용하는 Fast-Path 구조가 모델 학습 대기 시간과 클라우드 API 호출 비용을 줄이는 데 압도적으로 유리함.
"""

from typing import Any, Dict, Iterator

from src.common.config import ConfigManager
from src.common.log import LogManager
from src.common.decorators.log_decorator import log_decorator
from src.common.exceptions import ConfigurationError, ReaderInitializationError, ReaderServiceError
from src.reader.providers.abstract_reader import AbstractReader

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [설계 의도] 파이프라인 호출 시 타겟 스토리지 식별자가 누락될 경우를 대비한 대체값.
# 금융 원천 데이터의 1차 적재소인 S3 데이터 레이크를 기본값으로 강제하여 분석가의 사용 편의성 증대.
DEFAULT_READER_TARGET: str = "s3"

# [설계 의도] 1차 EDA 및 Pandas DataFrame 변환 효율을 극대화하는 청크(배치) 사이즈 스윗스팟.
# 대용량 JSONL 압축 해제 시 메모리 스파이크를 방지하기 위해 매직 넘버를 배제하고 상수로 통제함.
DEFAULT_BATCH_SIZE: int = 10000


# ==============================================================================
# Main Class/Functions
# ==============================================================================
class ReaderService:
    """데이터 스트리밍 읽기 파이프라인의 라우팅과 생명주기를 총괄하는 서비스(Facade) 클래스.
    
    내부 레지스트리 딕셔너리를 활용하여 AbstractReader 구현체들을 싱글톤(Singleton)처럼 
    인메모리에 캐싱함으로써 불필요한 네트워크 객체 재생성 오버헤드를 원천 차단합니다.

    Attributes:
        _config (ConfigManager): 글로벌 환경 변수 및 인프라 정책을 제공하는 싱글톤 설정 관리자.
        _target_reader (str): 런타임에 동적으로 바인딩될 스토리지 식별자 (예: 's3', 'postgres').
        _logger (logging.Logger): 클래스 네임스페이스로 격리된 구조화 로거.
        _reader_cache (Dict[str, AbstractReader]): 초기화 완료된 리더 객체를 보관하는 O(1) 탐색 캐시.
    """

    def __init__(self, target_reader: str = DEFAULT_READER_TARGET) -> None:
        """ReaderService 인스턴스를 초기화하고 지연 로딩용 캐시를 할당합니다.

        Args:
            target_reader (str, optional): 데이터를 추출할 대상 스토리지 식별자. 기본값은 "s3".
        """
        # [설계 의도] 서비스 기동 시점에는 Boto3 등 무거운 서드파티 모듈과 
        # C-extension(zstandard) 연동을 피하고, 가벼운 레지스트리 할당만 수행하여 
        # 파이프라인 및 Jupyter 커널의 기동 속도를 최적화(Lazy Init)함.
        self._config = ConfigManager.load("reader")
        self._target_reader = target_reader.strip().lower()
        self._logger = LogManager.get_logger(self.__class__.__name__)
        self._reader_cache: Dict[str, AbstractReader] = {}

    def _get_or_create_reader(self) -> AbstractReader:
        """설정값에 기반하여 대상 스토리지 I/O 리더 인스턴스를 지연 초기화 및 반환합니다.

        Returns:
            AbstractReader: 대상 스토리지 I/O 준비(인증/연결)가 완료된 구체 리더 인스턴스.

        Raises:
            ConfigurationError: 환경 설정 파일(reader.yml) 내 지원하지 않는 타겟이 입력된 경우.
            ReaderInitializationError: 구체 클래스의 동적 임포트(Dynamic Import) 혹은 네트워크 연결 실패 시.
        """
        # 1. [Fast-Path] 캐시 히트(Cache Hit) 시 즉시 반환
        # [설계 의도] 단일 프로세스에서 수백 개의 S3 Object 키를 순차적으로 호출할 때 
        # O(1) 시간 복잡도로 인스턴스를 반환하여 MLOps 파이프라인의 처리 속도를 보장함.
        if self._target_reader in self._reader_cache:
            return self._reader_cache[self._target_reader]

        # 2. [Cold-Start] 캐시 미스(Cache Miss) 시 동적 모듈 로드 및 초기화 수행
        self._logger.info(f"[{self._target_reader.upper()}] 리더 인스턴스 지연 초기화 진입")

        try:
            reader_policy = self._config.get_reader(self._target_reader)

            # [설계 의도] 분기 블록 내부 동적 임포트(Dynamic Import).
            # S3 리더만 필요한 환경에서 불필요하게 psycopg2(Postgres) 엔진이 로드되어 
            # 메모리가 낭비되거나 ImportError가 발생하는 것을 방어함.
            if self._target_reader in ["s3_zstd"]:
                from src.reader.providers.s3_zstd_reader import S3ZstdStreamingReader
                
                reader_instance = S3ZstdStreamingReader(
                    bucket_name=reader_policy.bucket_name,
                    region=reader_policy.region
                )
            
            # 확장을 고려한 예약 구조 (PostgreSQL 등 추가 시 주석 해제 후 구현)
            # elif self._target_reader == "postgres":
            #     from src.reader.providers.postgres_reader import PostgresReader
            #     reader_instance = PostgresReader(...)
                
            else:
                raise ConfigurationError(
                    message=f"지원하지 않는 데이터 리더 타겟입니다: '{self._target_reader}'",
                    key_name="global_reader.target"
                )

            # 정상적으로 생성된 객체를 향후 재사용하기 위해 레지스트리에 등록
            self._reader_cache[self._target_reader] = reader_instance
            return reader_instance

        except Exception as e:
            if isinstance(e, (ConfigurationError, ReaderInitializationError)):
                raise e
            raise ReaderInitializationError(
                message=f"[{self._target_reader.upper()}] 리더 인스턴스 초기화 중 예기치 않은 오류 발생",
                provider_name=self._target_reader,
                original_exception=e
            ) from e

    @log_decorator()
    def read_stream(self, job_id: str, execution_date: str, source_layer: str, batch_size: int = DEFAULT_BATCH_SIZE) -> Iterator[Any]:
        """지정된 작업 식별자(job_id)와 배치 기준일(execution_date) 및 대상 레이어(source_layer)를 기반으로
        하부 스토리지의 데이터 스트림을 청크 단위로 읽어오는 단일 진입점 인터페이스입니다.

        Args:
            job_id (str): 설정을 판독하기 위한 고유 작업 ID (예: 'kis_kospi_daily').
            execution_date (str): 하이브 파티션 경로 조립을 위한 배치 기준일 (YYYYMMDD).
            source_layer (str): 데이터를 읽어올 원천 메달리온 레이어 명칭.
            batch_size (int, optional): 다운스트림으로 한 번에 yield할 레코드 크기. 기본값은 DEFAULT_BATCH_SIZE.

        Returns:
            Iterator[Any]: 압축 해제 및 청크 정형화가 완료된 레코드 데이터를 순차 반환하는 제너레이터.

        Raises:
            ReaderServiceError: 입력 파라미터가 유효하지 않거나 하부 리더 구동 중 예외 발생 시.
        """
        # 1. Pre-condition 규칙 검증 및 Fail-Fast 처리
        if not job_id or not job_id.strip():
            raise ReaderServiceError(
                message=f"유효하지 않은 작업 식별자(job_id)입니다. (입력값: {job_id})",
                target_reader=self._target_reader
            )
            
        if not execution_date or not execution_date.strip():
            raise ReaderServiceError(
                message=f"유효하지 않은 실행 날짜(execution_date)입니다. (입력값: {execution_date})",
                target_reader=self._target_reader
            )

        if not source_layer or not source_layer.strip():
            raise ReaderServiceError(
                message=f"유효하지 않은 소스 레이어(source_layer)입니다. (입력값: {source_layer})",
                target_reader=self._target_reader
            )

        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ReaderServiceError(
                message=f"batch_size는 1 이상의 정수여야 합니다. (입력값: {batch_size})",
                target_reader=self._target_reader
            )

        # 2. [비즈니스 규칙 반영] job_id 접두사에서 provider 추출 및 YYYYMMDD 날짜 분해
        clean_job_id = job_id.strip()
        clean_date = execution_date.strip()
        
        provider = clean_job_id.split('_')[0]
        year = clean_date[0:4]
        month = clean_date[4:6]
        day = clean_date[6:8]
        
        layer_prefix = source_layer.strip().lower()
        
        # 3. [구조적 매핑] 브론즈 레이어의 Hive-Style 파티셔닝 디렉토리 Prefix 구조 생성
        # 예: bronze/market_data/provider=ecos/job=ecos_kdb_1y_daily/year=2026/month=05/day=23/
        source_path = (
            f"{layer_prefix}/market_data/"
            f"provider={provider}/"
            f"job={clean_job_id}/"
            f"year={year}/"
            f"month={month}/"
            f"day={day}/"
        )
        
        self._logger.info(
            f"데이터 스트림 추출 요청 위임 - Target: {self._target_reader.upper()}, "
            f"Path: {source_path}, Batch: {batch_size}"
        )

        # 2. 인스턴스 획득 및 구체 리더(S3ZstdStreamingReader)로 정합성 규격에 맞게 호출 위임
        try:
            reader = self._get_or_create_reader()
            return reader.read_stream(
                source_path=source_path,
                batch_size=batch_size
            )
        except Exception as e:
            if isinstance(e, (ConfigurationError, ReaderInitializationError, ReaderServiceError)):
                raise e
            raise ReaderServiceError(
                message=f"하부 리더 스트림 구동 중 예기치 못한 치명적 오류 발생: {e}",
                target_reader=self._target_reader
            )