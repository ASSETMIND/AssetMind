# ==============================================================================
# 1. Module Header Documentation
# ==============================================================================
"""
[S3 Zstandard Streaming Reader 모듈]

[S3에 적재된 대용량 Zstandard 압축 JSON Lines(JSONL) 데이터를 메모리 스파이크 없이 실시간으로 압축 해제하고 청크(Chunk) 단위로 순차 반환하는 리더(Reader) 구현체입니다.]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Request: AbstractReader.read_stream()을 통해 S3 Object Key(source_path)와 배치 사이즈 유입.
2. Connection: Boto3 클라이언트를 통해 대상 S3 객체의 StreamingBody 연결 수립.
3. Decompression: zstandard C-Extension을 활용하여 네트워크에서 유입되는 Byte Stream을 실시간 압축 해제.
4. Parsing: 해제된 Byte Stream을 UTF-8 Text로 디코딩하고 개행 문자(\n) 단위로 분리하여 JSON 직렬화 해제.
5. Output: 설정된 배치 사이즈(예: 10,000건)에 도달할 때마다 List[Dict] 형태의 레코드 배치를 제너레이터(yield) 방식으로 반환.

주요 기능:
- S3 Byte Streaming: 파일을 로컬 디스크나 메모리에 다운로드하지 않고 HTTP Socket 레벨에서 스트리밍 읽기 수행.
- Zstandard On-the-fly Decompression: zstd 알고리즘의 우수한 해제 속도를 활용하여 I/O 병목 최소화.
- Line-by-Line JSON Parsing: `io.TextIOWrapper`를 결합하여 OOM 발생 위험 없이 한 줄씩 안전하게 메모리 적재.
- Batch Yielding: 하류 파이프라인(Pandas DataFrame 변환 등)의 벡터 연산 효율성을 위한 리스트 형태의 배치 반환.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. `io.TextIOWrapper` 기반 라인 파싱 vs 청크 단위 수동 버퍼링(split('\n')):
   - 장점: 파이썬 내장 C 구현체를 활용하므로 수동으로 바이트 버퍼를 관리하고 자르는 보일러플레이트 코드를 제거하며 메모리 누수 위험이 적음.
   - 단점: UTF-8 디코딩 시 스트림 래퍼를 여러 겹 거치게 되어 미세한 함수 호출 오버헤드가 발생함.
   - 근거: 실무 파이프라인에서는 바이트 경계(Boundary) 오류로 인한 데이터 유실(Corrupted JSON) 방지가 최우선이므로, 검증된 표준 라이브러리 조합을 활용하는 것이 압도적으로 안전함.
2. `boto3` StreamingBody 직접 사용 vs `smart_open` 등 서드파티 라이브러리:
   - 장점: 외부 의존성을 최소화하고 AWS SDK의 기본 동작(Retries, Timeout)을 직접 제어할 수 있음.
   - 단점: 연결 유실이나 소켓 타임아웃 발생 시 복구 로직을 수동으로 예외 처리해야 함.
   - 근거: `AbstractReader`의 `DataReadStreamError`를 통한 구조화된 예외 처리 아키텍처가 이미 준비되어 있으므로, 래퍼 라이브러리 없이 네이티브 API를 사용하는 것이 시스템 투명성 관점에서 유리함.
3. 개별 Dict 반환 vs List[Dict] 배치 반환:
   - 장점: 제너레이터가 한 번에 N개의 레코드를 반환하므로, 하류의 Pandas `pd.DataFrame.from_records()` 호출 횟수를 줄여 직렬화 병목을 극복함.
   - 단점: 배치 사이즈(예: 10,000)만큼의 Python Dict 객체를 순간적으로 메모리에 유지해야 하므로 최소 수백 MB의 버퍼 메모리가 요구됨.
   - 근거: Worker Node 스펙(통상 4GB 이상) 대비 100~200MB의 배치 버퍼는 충분히 감내할 수 있는 수준이며, Pandas 변환 속도의 극적인 상승(수십 배)을 위해 필수적인 트레이드오프임.
"""

import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterator, List

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import zstandard as zstd

from src.reader.providers.abstract_reader import AbstractReader
from src.common.exceptions import ReaderInitializationError, DataReadStreamError
from src.common.config import ConfigManager

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [설계 의도] zstandard 해제기 내부의 C 레벨 버퍼 크기.
# 너무 작으면 I/O 컨텍스트 스위칭이 빈번해지고, 너무 크면 OOM이 발생할 수 있으므로
# S3 청크 사이즈 기준(8MB~16MB)에 맞춰 최적화된 16MB를 할당.
ZSTD_READ_BUFFER_BYTES: int = 16 * 1024 * 1024

# [설계 의도] S3 병렬 다운로드 시 메모리 피크 스파이크를 방지하면서 
# 네트워크 Latency 병목을 해소하기 위한 최적 스레드 워커 수 제한값 (4~8 권장)
MAX_THREAD_WORKERS: int = 8

# ==============================================================================
# Main Class/Functions
# ==============================================================================
class S3ZstdStreamingReader(AbstractReader):
    """S3에 적재된 Zstandard 압축 JSONL 데이터를 실시간 스트리밍으로 읽어들이는 구체화 리더.

    `AbstractReader`의 템플릿 생명주기를 준수하며, Boto3와 zstandard를 결합하여
    메모리 팽창(OOM) 없이 대용량 파일을 청크(Batch) 단위로 순차 반환합니다.

    Attributes:
        _bucket_name (str): 데이터를 읽어올 타겟 S3 버킷 이름.
        _region (str): AWS 리전 이름.
    """

    def __init__(self, bucket_name: str, region: str) -> None:
        """S3ZstdStreamingReader 인스턴스를 초기화합니다.

        Args:
            bucket_name (str): 데이터를 추출할 대상 S3 버킷 이름.
            region (str): S3 버킷이 위치한 AWS 리전 (예: 'ap-northeast-2').

        Raises:
            ReaderInitializationError: 버킷 이름이나 리전 정보가 누락된 경우.
        """
        super().__init__(provider_name="S3_BRONZE_READER")

        # [설계 의도] 인프라 식별 정보 누락 시 런타임에 커넥션 타임아웃이 발생하기 전에 
        # Fail-Fast 원칙에 따라 초기화 시점에 조기 차단함.
        if not bucket_name or not region:
            raise ReaderInitializationError(
                message="S3ZstdStreamingReader 초기화 실패: bucket_name과 region은 필수입니다.",
                provider_name=self.provider_name
            )

        self._bucket_name = bucket_name
        self._region = region

    def _initialize_client(self) -> Any:
        """Boto3 S3 클라이언트를 지연 초기화(Lazy Initialization)합니다.

        [설계 의도]
        실제 데이터를 읽는 시점에만 커넥션을 수립하여 시스템 부하를 줄이며,
        ConfigManager를 통해 주입된 환경변수를 활용하여 LocalStack 모킹(Mocking)을 지원합니다.

        Returns:
            Any: 인증이 완료된 Boto3 S3 Client.

        Raises:
            ReaderInitializationError: AWS 자격 증명 오류 등으로 클라이언트 생성 실패 시.
        """
        try:
            client_kwargs = {
                "service_name": "s3",
                "region_name": self._region
            }

            # 환경변수를 통한 통합 테스트용 LocalStack 엔드포인트 분기 처리
            import os
            local_endpoint = os.environ.get("LOCAL_S3_ENDPOINT")
            if local_endpoint:
                client_kwargs.update({
                    "endpoint_url": local_endpoint,
                    "aws_access_key_id": "test",
                    "aws_secret_access_key": "test"
                })
                self.logger.info(f"[{self.provider_name}] LocalStack S3 Endpoint로 클라이언트 초기화 ({local_endpoint})")

            return boto3.client(**client_kwargs)

        except (BotoCoreError, Exception) as e:
            raise ReaderInitializationError(
                message="Boto3 S3 클라이언트 초기화 중 오류가 발생했습니다.",
                provider_name=self.provider_name,
                original_exception=e
            ) from e

    def _validate_source(self, source_path: str) -> None:
        """S3 Object Key(source_path)의 형식 및 확장자 무결성을 사전 검증합니다.

        Args:
            source_path (str): 읽어올 대상 S3 객체 경로.

        Raises:
            ReaderInitializationError: 파일 경로가 누락되었거나 지원하지 않는 확장자인 경우.
        """
        if not source_path:
            raise ReaderInitializationError(
                message="source_path(S3 Key)가 누락되었습니다.",
                provider_name=self.provider_name
            )
        
        # [설계 의도] 단일 파일이 아닌 파티션 디렉토리(Prefix)도 허용해야 하므로
        # 기존의 엄격한 파일 확장자 검사 대신 가벼운 정보성 로그만 남깁니다.
        if not source_path.endswith(".zst"):
            self.logger.debug(f"[{self.provider_name}] 파티션 Prefix 형태의 경로를 감지했습니다: {source_path}")

    def _generate_chunks(self, source_path: str, batch_size: int, **kwargs: Any) -> Iterator[List[Dict[str, Any]]]:
        """S3에서 Zstandard 스트림을 읽어 압축을 해제하고 JSONL을 파싱하여 리스트 형태로 순차 반환합니다.

        Args:
            source_path (str): 대상 S3 객체 경로.
            batch_size (int): 한 번에 반환(yield)할 JSON 레코드의 개수.
            **kwargs (Any): 추가 파라미터 (미사용).

        Yields:
            Iterator[List[Dict[str, Any]]]: 파싱이 완료된 Python 딕셔너리 리스트 (배치 단위).

        Raises:
            DataReadStreamError: S3 다운로드 실패, 압축 해제 오류, JSON 파싱 실패 시 발생.
        """
        try:
            # 1. Paginator를 사용하여 Prefix 하위의 대상 객체 Key 목록 수집
            paginator = self._client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self._bucket_name, Prefix=source_path)

            target_object_keys: List[str] = []
            for page in pages:
                if 'Contents' not in page:
                    continue

                for object_metadata in page['Contents']:
                    object_key = object_metadata['Key']
                    if object_key.endswith('.jsonl.zst') or object_key.endswith('.json.zst'):
                        target_object_keys.append(object_key)

            if not target_object_keys:
                self.logger.warning(f"[{self.provider_name}] 지정된 파티션({source_path}) 내부에 처리할 '.zst' 파일이 없습니다.")
                return

            batch_buffer: List[Dict[str, Any]] = []

            # 2. ThreadPoolExecutor를 활용한 S3 I/O 및 압축해제 파싱 병렬 처리
            with ThreadPoolExecutor(max_workers=MAX_THREAD_WORKERS) as executor:
                future_to_key = {
                    executor.submit(self._fetch_and_parse_zstd_object, object_key): object_key
                    for object_key in target_object_keys
                }

                for future in as_completed(future_to_key):
                    object_key = future_to_key[future]
                    self.logger.debug(f"[{self.provider_name}] 파티션 파일 처리 완료: {object_key}")
                    parsed_records = future.result()

                    batch_buffer.extend(parsed_records)

                    # 3. 버퍼가 설정된 배치 사이즈에 도달하면 즉시 Yield
                    while len(batch_buffer) >= batch_size:
                        yield batch_buffer[:batch_size]
                        batch_buffer = batch_buffer[batch_size:]

            # 4. 모든 파티션 파일 처리 완료 후 잔여 버퍼 반환
            if batch_buffer:
                yield batch_buffer
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            raise DataReadStreamError(
                message=f"S3 파티션 접근 실패 (Code: {error_code})",
                source_path=source_path,
                original_exception=e
            ) from e
            
        except Exception as e:
            raise DataReadStreamError(
                message="S3 파티션 스트리밍 제너레이터 실행 중 예기치 않은 오류가 발생했습니다.",
                source_path=source_path,
                original_exception=e
            ) from e
        
    def _fetch_and_parse_zstd_object(self, object_key: str) -> List[Dict[str, Any]]:
        """S3 단일 Zstandard 압축 객체를 스트리밍 읽기하여 JSONL 파싱 후 레코드 리스트를 반환합니다.

        Args:
            object_key (str): 읽어올 S3 객체의 Key.

        Returns:
            List[Dict[str, Any]]: 파싱이 완료된 JSON 레코드 리스트.
        """
        records_list: List[Dict[str, Any]] = []
        response = self._client.get_object(Bucket=self._bucket_name, Key=object_key)
        streaming_body = response['Body']

        decompressor = zstd.ZstdDecompressor()
        zstd_reader = decompressor.stream_reader(
            streaming_body,
            read_across_frames=True,
            read_size=ZSTD_READ_BUFFER_BYTES
        )
        text_stream = io.TextIOWrapper(zstd_reader, encoding='utf-8')

        try:
            for line_number, line in enumerate(text_stream, start=1):
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                try:
                    records_list.append(json.loads(stripped_line))
                except json.JSONDecodeError as exception:
                    self.logger.error(
                        f"[{self.provider_name}] JSON 파싱 스킵 (Line {line_number} in {object_key}): {exception}"
                    )
                    continue
        finally:
            text_stream.close()
            zstd_reader.close()
            streaming_body.close()

        return records_list