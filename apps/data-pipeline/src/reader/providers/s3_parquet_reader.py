# ==============================================================================
# 1. Module Header Documentation
# ==============================================================================
"""
[S3 Parquet Streaming Reader 모듈]

[S3에 적재된 실버 레이어의 Parquet 데이터를 메모리 스파이크 없이 읽어들이고, 시스템 표준 규격인 청크(Chunk) 단위의 리스트 레코드로 순차 반환하는 리더(Reader) 구현체입니다.]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Request: AbstractReader.read_stream()을 통해 실버 S3 파티션 경로(source_path)와 배치 사이즈 유입.
2. Connection: Boto3 클라이언트를 통해 대상 S3 버킷의 특정 파티션 하위 Parquet 객체 목록 조회 및 스트림 연결 수립.
3. Loading: PyArrow 엔진을 활용하여 S3 객체의 바이너리 데이터를 메모리 버퍼로 읽어와 ParquetFile 구조로 바인딩.
4. Parsing: iter_batches()를 사용하여 Parquet의 컬럼너 구조 장점을 유지한 채 지정된 배치 크기만큼의 RecordBatch 추출.
5. Output: 추출된 데이터를 시스템 표준 포맷인 List[Dict] 형태로 역직렬화하여 제너레이터(yield) 방식으로 다운스트림에 순차 반환.

주요 기능:
- S3 Partition Directory Scanning: 하이브 스타일 파티션(year/month/day) 하위의 모든 Parquet 파일들을 Paginator로 안전하게 전수 조사.
- PyArrow Integration: Pandas의 패런츠 엔진인 PyArrow의 고성능 Parquet 파싱 능력을 극대화하여 데이터 로드 속도 최적화.
- Memory-Safe Chunking: 대용량 데이터 유입 시에도 RecordBatch 단위를 제어하여 워커 노드의 OOM(Out-Of-Memory) 위험 원천 차단.
- Batch Yielding: 상위 서비스 레이어(ReaderService)의 정산 및 요약 리포트 내역 자산과 100% 호환되는 배치 구조 반환.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. PyArrow RecordBatch 기반 `to_pylist()` 변환 구조:
   - 장점: 파사드 서비스(ReaderService)의 공통 정합성 검증 레이어 및 데이터 파이프라인 전체의 표준 데이터형(List[Dict]) 규격을 수정 없이 만족함.
   - 단점: 컬럼너(Columnar) 데이터를 파이썬 딕셔너리 객체 배열로 변환하는 과정에서 미세한 CPU 역직렬화 오버헤드가 발생함.
   - 근거: 골드 파이프라인의 유연한 다형성 설계와 공통 래퍼(_wrap_stream_with_report)의 무결성 유지가 최우선이며, 매일 실행되는 하루치 데이터 규모에서는 이 변환 비용이 전체 네트워크 I/O Bound 시간에 비해 미미함.
2. io.BytesIO 전량 로드 후 ParquetFile 파싱:
   - 장점: S3의 파르케 객체를 다룰 때 발생할 수 있는 복잡한 HTTP Range Request 탐색(Seek) 문제를 단일 파일 바이트 로드로 단순화하여 네트워크 단질 리스크를 최소화함.
   - 단점: 개별 파르케 파일 크기만큼의 임시 바이트 메모리 점유가 필요함.
   - 근거: 실버 파이프라인을 통과한 하루치 파티션 분할 파일은 단일 파일당 수십 MB 이내로 통제되므로 워커 노드의 가용 자원 안에서 안전하게 고속 처리가 가능함.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.fs as pafs
import pyarrow.parquet as pq

from src.reader.providers.abstract_reader import AbstractReader
from src.common.exceptions import ReaderInitializationError, DataReadStreamError
from src.common.config import ConfigManager

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [설계 의도] Parquet 포맷 식별을 위한 표준 파일 확장자 정의
PARQUET_FILE_EXTENSION: str = ".parquet"


# ==============================================================================
# Main Class/Functions
# ==============================================================================
class S3ParquetStreamingReader(AbstractReader):
    """S3 실버 버킷에 저장된 파티션별 Parquet 데이터를 청크 단위 스트리밍으로 읽어오는 구체화 리더.

    `AbstractReader`의 템플릿 생명주기를 엄격히 준수하며, Boto3와 PyArrow를 결합하여
    안정적이고 규격화된 정제 데이터를 레코드 스트림 형태로 반환합니다.

    Attributes:
        _bucket_name (str): 데이터를 읽어올 타겟 실버 S3 버킷 이름.
        _region (str): AWS 리전 이름.
    """

    def __init__(self, bucket_name: str, region: str) -> None:
        """S3ParquetStreamingReader 인스턴스를 초기화합니다.

        Args:
            bucket_name (str): 데이터를 추출할 대상 실버 S3 버킷 이름.
            region (str): S3 버킷이 위치한 AWS 리전 정보.

        Raises:
            ReaderInitializationError: 버킷 이름이나 리전 정보가 누락된 경우.
        """
        super().__init__(provider_name="S3_SILVER_READER")

        # [설계 의도] 인프라 식별 정보 누락 시 런타임에 커넥션 오류가 발생하기 전에 
        # Fail-Fast 원칙에 따라 초기화 시점에 조기 차단함.
        if not bucket_name or not region:
            raise ReaderInitializationError(
                message="S3ParquetStreamingReader 초기화 실패: bucket_name과 region은 필수 파라미터입니다.",
                provider_name=self.provider_name
            )

        self._bucket_name = bucket_name
        self._region = region

    def _initialize_client(self) -> Any:
        """Boto3 S3 클라이언트를 지연 초기화(Lazy Initialization)합니다.

        [설계 의도]
        실제 데이터를 읽는 시점에만 커넥션을 수립하여 메모리와 소켓 리소스를 절약하며,
        환경변수를 통한 통합 테스트용 LocalStack 엔드포인트 분기 처리를 지원함.

        Returns:
            Any: 인증이 완료된 Boto3 S3 Client 객체.

        Raises:
            ReaderInitializationError: AWS 자격 증명 오류 등으로 클라이언트 생성 실패 시.
        """
        try:
            client_kwargs = {
                "service_name": "s3",
                "region_name": self._region
            }

            import os
            local_endpoint = os.environ.get("LOCAL_S3_ENDPOINT")
            if local_endpoint:
                client_kwargs.update({
                    "endpoint_url": local_endpoint,
                    "aws_access_key_id": "test",
                    "aws_secret_access_key": "test"
                })
                self.logger.info(f"[{self.provider_name}] LocalStack S3 Endpoint로 클라이언트 초기화 완료 ({local_endpoint})")

            return boto3.client(**client_kwargs)

        except (BotoCoreError, Exception) as e:
            raise ReaderInitializationError(
                message="Boto3 S3 클라이언트 초기화 중 치명적인 오류가 발생했습니다.",
                provider_name=self.provider_name,
                original_exception=e
            ) from e

    def _validate_source(self, source_path: str) -> None:
        """읽어올 대상 S3 파티션 Prefix 경로의 무결성을 사전 검증합니다.

        Args:
            source_path (str): 읽어올 대상 S3 파티션 디렉터리 경로.

        Raises:
            ReaderInitializationError: 파일 경로 정보가 유효하지 않거나 누락된 경우.
        """
        if not source_path or not source_path.strip():
            raise ReaderInitializationError(
                message="source_path(S3 Prefix) 정보가 누락되었거나 유효하지 않습니다.",
                provider_name=self.provider_name
            )
        
        # [설계 의도] 단일 파일이 아닌 일별 파티션 디렉터리(Prefix) 전체를 스캔하므로 
        # 하이브 스타일 파티션 경로 컨벤션을 투영하는 디버깅용 정보 로그만 남김.
        self.logger.debug(f"[{self.provider_name}] 실버 파티션 디렉터리 경로 검증 완료: {source_path}")

    def _generate_chunks(self, source_path: str, batch_size: int) -> Iterator[List[Dict[str, Any]]]:
        """S3 실버 파티션 내의 Parquet 파일들을 스캔하고 청크 단위로 파싱하여 리스트 레코드로 순차 반환합니다.

        Args:
            source_path (str): 대상 실버 S3 객체 Prefix 경로.
            batch_size (int): 한 번에 반환(yield)할 최대 레코드 수.

        Returns:
            Iterator[List[Dict[str, Any]]]: 파싱이 완료된 파이썬 딕셔너리 리스트 (배치 단위).

        Raises:
            DataReadStreamError: S3 오토메이션 에러, Parquet 파일 파싱 실패, 네트워크 단절 발생 시.
        """
        try:
            # 1. [설계 의도] S3 Paginator를 사용하여 하나의 파티션 디렉터리 내에 분할 적재된 모든 파일 목록을 전수 조사함.
            paginator = self._client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self._bucket_name, Prefix=source_path)

            total_records = 0
            file_count = 0
            batch_buffer: List[Dict[str, Any]] = []

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']
                    
                    # 2. [설계 의도] 가비지 파일이나 스파크 메타데이터(_SUCCESS 등)를 철저히 배제하고 순수 Parquet 포맷만 필터링함.
                    if not key.endswith(PARQUET_FILE_EXTENSION):
                        continue

                    file_count += 1
                    self.logger.debug(f"[{self.provider_name}] 실버 Parquet 파일 파일 처리 시작: {key}")

                    # 3. 개별 Parquet 파일 내 바이트 스트리밍 및 파일 버퍼 파싱
                    response = self._client.get_object(Bucket=self._bucket_name, Key=key)
                    streaming_body = response['Body']

                    # [설계 의도] PyArrow의 ParquetFile 버퍼 바인딩을 통해 컬럼너 파일 포맷의 고성능 로드 메커니즘을 확보함.
                    parquet_bytes = streaming_body.read()
                    parquet_file = pq.ParquetFile(io.BytesIO(parquet_bytes))

                    # 4. 설정된 배치 사이즈 단위로 RecordBatch를 순회하며 데이터 추출 및 포맷팅
                    for record_batch in parquet_file.iter_batches(batch_size=batch_size):
                        # [설계 의도] RecordBatch 단위로 데이터를 쪼개어 파이썬 기본 데이터형인 List[Dict] 배열로 변환함으로써 
                        # ReaderService의 기존 정산 및 공통 래퍼 시스템 리포트와 완벽한 정합성을 유지함.
                        records: List[Dict[str, Any]] = record_batch.to_pylist()
                        
                        for record in records:
                            batch_buffer.append(record)
                            total_records += 1

                            # 버퍼가 오케스트레이터 설정 배치 사이즈에 도달하면 즉시 다운스트림으로 Yield
                            if len(batch_buffer) >= batch_size:
                                yield batch_buffer
                                batch_buffer = []

                    # 리소스 누수(Leak) 방지를 위한 명시적 스트림 종료
                    streaming_body.close()

            # 5. 전체 파티션 파일 순회를 마친 후 잔여 버퍼 데이터 최종 반환
            if batch_buffer:
                yield batch_buffer

            if file_count == 0:
                self.logger.warning(f"[{self.provider_name}] 지정된 실버 파티션 경로({source_path}) 내부에 처리할 Parquet 파일이 존재하지 않습니다.")

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            raise DataReadStreamError(
                message=f"S3 실버 파티션 인프라 접근 실패 (오류 코드: {error_code})",
                source_path=source_path,
                original_exception=e
            ) from e

        except Exception as e:
            raise DataReadStreamError(
                message="S3 실버 Parquet 스트리밍 제너레이터 구동 중 예기치 않은 구조적 오류가 발생했습니다.",
                source_path=source_path,
                original_exception=e
            ) from e
        
    def _download_single_parquet_table(self, s3_key_str: str) -> Optional[pa.Table]:
        """S3 단일 Parquet 객체를 바이너리로 병렬 다운로드하여 PyArrow Table로 Zero-Copy 변환합니다.

        [설계 의도]
        CPython dict 객체 변환(to_pylist) 오버헤드를 0으로 차단하고,
        Boto3 SDK의 Automatic Retry(Exponential Backoff)를 사용하여 네트워크 안정성을 확보합니다.
        S3 Key 경로(year=YYYY/month=MM/day=DD)에서 Hive 파티션 날짜를 파싱하여 PyArrow Table 컬럼으로 동적 결합합니다.

        Args:
            s3_key_str (str): S3 Parquet 객체 Key.

        Returns:
            Optional[pa.Table]: PyArrow 메모리 테이블 (실패 시 None).
        """
        try:
            s3_response = self._client.get_object(
                Bucket=self._bucket_name,
                Key=s3_key_str
            )
            binary_content: bytes = s3_response["Body"].read()

            # [설계 의도] C++ 레벨 PyArrow 메모리 버퍼로 변환하여 Zero-Copy 수집
            parquet_table: pa.Table = pq.read_table(io.BytesIO(binary_content))

            # [설계 의도] S3 Key 경로에서 Hive 파티션(year/month/day)을 추출하여 컬럼 벡터로 바인딩
            date_match = re.search(r"year=(\d{4})/month=(\d{2})/day=(\d{2})", s3_key_str)
            if date_match:
                year_val = int(date_match.group(1))
                month_val = int(date_match.group(2))
                day_val = int(date_match.group(3))
                num_rows = parquet_table.num_rows

                parquet_table = parquet_table.append_column("year", pa.array([year_val] * num_rows, type=pa.int64()))
                parquet_table = parquet_table.append_column("month", pa.array([month_val] * num_rows, type=pa.int64()))
                parquet_table = parquet_table.append_column("day", pa.array([day_val] * num_rows, type=pa.int64()))

            return parquet_table

        except Exception as error_context:
            self.logger.warning(
                f"[{self.provider_name}] 단일 Parquet 다운로드 중 지연 감지 - Key: {s3_key_str} | 원인: {str(error_context)}"
            )
            return None

    def _get_pyarrow_s3_filesystem(self) -> pafs.S3FileSystem:
        """LocalStack(로컬) 및 AWS S3 프로덕션 환경에 동적으로 바인딩되는 
        PyArrow Native C++ S3FileSystem 인스턴스를 생성합니다.
        """
        local_endpoint = os.environ.get("LOCAL_S3_ENDPOINT", "")
        if local_endpoint:
            endpoint_clean = local_endpoint.replace("http://", "").replace("https://", "")
            scheme = "http" if "http://" in local_endpoint else "https"
            return pafs.S3FileSystem(
                endpoint_override=endpoint_clean,
                access_key=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
                secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
                scheme=scheme,
                region=self._region
            )
        return pafs.S3FileSystem(region=self._region)

    def _generate_dataframe(self, source_path: str, **kwargs) -> pd.DataFrame:
        """PyArrow C++ Native S3FileSystem과 Dataset API를 활용하여 S3 Hive 파티션 데이터를
        C++ 레벨 멀티스레드로 Zero-Copy 고속 스캔 및 인메모리 병합을 수행합니다.
        """
        try:
            s3_fs = self._get_pyarrow_s3_filesystem()
            clean_source_path = source_path.strip("/")
            target_s3_uri = f"{self._bucket_name}/{clean_source_path}"

            # [설계 의도] PyArrow C++ Dataset 엔진으로 S3 Hive 파티션(year/month/day) 자동 인식 및 스캔
            dataset: ds.Dataset = ds.dataset(
                target_s3_uri,
                filesystem=s3_fs,
                format="parquet",
                partitioning="hive"
            )

            table: pa.Table = dataset.to_table()
            if table.num_rows == 0:
                return pd.DataFrame()

            # [설계 의도] PyArrow Table을 단 1회의 to_pandas() 연산으로 변환하여 메모리 복사 최소화
            combined_dataframe: pd.DataFrame = table.to_pandas()

            # [설계 의도] Hive 파티션(year, month, day)에서 trade_date 생성 및 pd.concat(axis=1)으로 PerformanceWarning 방지
            if all(col in combined_dataframe.columns for col in ["year", "month", "day"]):
                trade_date_series = pd.to_datetime(combined_dataframe[["year", "month", "day"]])
                combined_dataframe.drop(columns=["year", "month", "day"], inplace=True)
                combined_dataframe = pd.concat([trade_date_series.rename("trade_date"), combined_dataframe], axis=1)

            return combined_dataframe

        except Exception as e:
            raise DataReadStreamError(
                message=f"[{self.provider_name}] S3 Parquet Dataset C++ Native 고속 로드 중 오류가 발생했습니다.",
                source_path=source_path,
                original_exception=e
            ) from e