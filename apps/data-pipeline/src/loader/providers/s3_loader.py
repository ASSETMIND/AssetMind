"""
[S3Loader 모듈]

[모듈 목적 및 상세 설명]
금융 원천 데이터의 원형 보존 및 메모리 최적화를 위한 zstd 스트리밍 적재를 담당하는 구체(Concrete) 적재기 클래스입니다.
AbstractLoader를 상속받아 ILoader 인터페이스의 규격을 준수하며, AWS S3로의 안전하고 효율적인 데이터 전송을 보장합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
ExtractedDTO -> [_validate_dto: 필수 필드(data, meta) 검증] -> [_apply_load: S3 적재 파이프라인 시작] -> [_generate_s3_key: meta 정보를 활용한 파티셔닝 키 생성] -> [_compress_to_zstd_stream: Zstd 압축] -> [_execute_multipart_upload: S3 멀티파트 업로드] -> Boolean (성공 여부 반환).

주요 기능:
- [기능 1] Zstd 스트리밍 압축: 금융 데이터의 방대한 페이로드를 메모리 효율적으로 압축 (zstandard 라이브러리 활용).
- [기능 2] 자동 멀티파트 업로드: 대용량 데이터 업로드 시 네트워크 단절을 방지하고 전송 속도를 극대화하기 위해 Boto3의 내부 멀티파트 업로드 기능을 활용.
- [기능 3] Hive-Style 파티셔닝: DTO의 meta 정보(provider, job_id)를 활용하여 S3 Object Key를 생성, 추후 Athena/Glue 기반 쿼리 성능 최적화.

Trade-off: 
- 장점: `ExtractedDTO`의 `meta` 필드를 활용한 동적 S3 경로 생성으로 데이터 카탈로깅이 자동화됩니다. `zstd`를 활용한 스트림 압축은 gzip 대비 압축/해제 속도가 매우 빠르며 메모리 스파이크를 방지합니다. 
- 단점: zstandard C-extension 의존성이 추가되며, 멀티파트 업로드 중 치명적 실패 발생 시 S3 버킷에 Incomplete Multipart Object가 남아 스토리지 비용이 누수될 수 있습니다 (S3 Lifecycle Rule 설정으로 보완 필요).
- 근거: S3에 적재되는 금융 원천 데이터는 향후 분석 및 감사(Audit)를 위해 원본을 반드시 유지해야 하며 데이터 볼륨이 큽니다. 따라서 적재 시간 단축과 스토리지 비용 절감을 동시에 달성하기 위해 zstd 압축과 멀티파트 업로드의 조합은 불가피한 엔지니어링 선택입니다. DTO의 `meta` 필드를 강제 검증함으로써 잘못된 파티션에 데이터가 적재되는 데이터 늪(Data Swamp) 현상을 원천 차단합니다.
"""

import io
import json
import uuid
import datetime
from typing import Any

import boto3
import zstandard as zstd
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import BotoCoreError, ClientError

# Local Imports
from src.common.dtos import ExtractedDTO
from src.common.config import ConfigManager
from src.common.exceptions import (
    ConfigurationError, 
    ZstdCompressionError, 
    S3UploadError
)
from src.loader.providers.abstract_loader import AbstractLoader
from src.common.decorators.log_decorator import log_decorator

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# Boto3 멀티파트 업로드 임계값 설정 (10MB 이상 시 멀티파트 작동)
S3_MULTIPART_THRESHOLD_BYTES: int = 10 * 1024 * 1024
# 동시 업로드 스레드 수 제한 (네트워크 I/O 최적화)
S3_MAX_CONCURRENCY: int = 10
# Zstd 압축 레벨 (1~22, 3이 일반적인 Default 값으로 속도와 압축률의 최적 밸런스 제공)
ZSTD_COMPRESSION_LEVEL: int = 3


class S3Loader(AbstractLoader):
    """금융 원천 데이터의 Zstd 압축 및 S3 스트리밍 적재를 담당하는 클래스.
    
    Attributes:
        _boto3_client (Any): Boto3 S3 클라이언트 객체.
        _bucket_name (str): 데이터를 적재할 S3 버킷 이름.
    """

    def __init__(self, config: ConfigManager) -> None:
        """S3Loader 초기화 및 S3 클라이언트 연결을 수행합니다.

        Args:
            config (ConfigManager): 시스템 설정 정보가 담긴 객체.
            
        Raises:
            ConfigurationError: 버킷 이름 등 필수 AWS 설정이 누락된 경우.
        """
        super().__init__(config)
        
        self._bucket_name = self._config.get("aws.s3.bucket_name")
        if not self._bucket_name:
            raise ConfigurationError("S3 버킷 이름이 설정 파일에 누락되었습니다.", key_name="aws.s3.bucket_name")
            
        self._boto3_client = self._init_s3_client()

    def _init_s3_client(self) -> Any:
        """Boto3 클라이언트를 초기화합니다.
        
        Design Intent: 클라이언트 생성 로직을 분리하여 향후 AWS STS(AssumeRole) 
        또는 로컬 모킹(Moto) 시 오버라이딩을 용이하게 합니다.

        Returns:
            Any: boto3 S3 client instance.
            
        Raises:
            ConfigurationError: Boto3 클라이언트 초기화 중 설정 문제가 발생할 경우.
        """
        try:
            return boto3.client(
                's3',
                region_name=self._config.get("aws.region", "ap-northeast-2")
            )
        except (BotoCoreError, ClientError) as e:
            self._logger.error("Boto3 S3 클라이언트 초기화 실패", exc_info=True)
            raise ConfigurationError(f"AWS 설정 오류: {e}") from e

    def _validate_dto(self, dto: ExtractedDTO) -> bool:
        """ExtractedDTO의 S3 적재 필수 조건을 검증합니다.

        Args:
            dto (ExtractedDTO): 검증할 데이터 객체.

        Returns:
            bool: 무결성 검증 통과 여부.
        """
        # Design Intent: 데이터 오염 및 잘못된 파티셔닝 방지
        # dtos.py 명세에 따라 data의 존재 여부와 meta 내 provider/job_id 존재 여부를 엄격히 확인합니다.
        if dto.data is None:
            self._logger.warning("검증 실패: ExtractedDTO의 'data' 속성이 비어 있습니다.")
            return False
            
        if not isinstance(dto.meta, dict):
            self._logger.warning("검증 실패: ExtractedDTO의 'meta' 속성이 딕셔너리가 아닙니다.")
            return False
            
        if "provider" not in dto.meta or "job_id" not in dto.meta:
            self._logger.warning("검증 실패: S3 파티셔닝에 필요한 'provider' 또는 'job_id'가 meta에 없습니다.")
            return False
            
        return True

    @log_decorator()
    def _apply_load(self, dto: ExtractedDTO) -> bool:
        """검증이 완료된 DTO에 대해 실제 S3 업로드 파이프라인을 가동합니다.

        Args:
            dto (ExtractedDTO): 적재할 대상 데이터 객체.

        Returns:
            bool: 적재 성공 여부.
        """
        s3_key = self._generate_s3_key(dto)
        return self._upload_stream(dto, s3_key)

    def _generate_s3_key(self, dto: ExtractedDTO) -> str:
        """S3에 저장될 객체의 고유 키(Path)를 생성합니다.
        
        Design Intent: extractor.yml에 정의된 provider(예: KIS, FRED)와 job_id(예: kis_kospi_daily)를 
        기반으로 Hive Style 파티셔닝을 동적으로 구성하여 카탈로깅 최적화를 달성합니다 .

        Args:
            dto (ExtractedDTO): 키 생성의 기반이 되는 데이터 객체.

        Returns:
            str: S3 Object Key (경로 포함).
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        date_path = now.strftime("year=%Y/month=%m/day=%d")
        
        # _validate_dto를 통과했으므로 meta 속성 존재 보장
        provider = str(dto.meta.get("provider")).lower()
        job_id = str(dto.meta.get("job_id")).lower()
        unique_id = uuid.uuid4().hex[:8]
        
        return f"raw/provider={provider}/job={job_id}/{date_path}/{now.timestamp()}_{unique_id}.json.zst"

    def _upload_stream(self, dto: ExtractedDTO, s3_key: str) -> bool:
        """데이터를 압축하고 S3에 스트림으로 적재하는 전체 과정을 조율합니다.

        Args:
            dto (ExtractedDTO): 데이터 객체.
            s3_key (str): 대상 S3 객체 키.

        Returns:
            bool: 최종 적재 성공 여부.
        """
        data_chunks = dto.data 
        compressed_bytes = self._compress_to_zstd_stream(data_chunks)
        
        return self._execute_multipart_upload(compressed_bytes, s3_key)

    def _compress_to_zstd_stream(self, data_chunks: Any) -> bytes:
        """데이터를 zstandard 알고리즘으로 압축하여 바이트 스트림을 반환합니다.

        Args:
            data_chunks (Any): 압축할 원본 데이터.
            
        Returns:
            bytes: Zstd로 압축된 바이너리 데이터.

        Raises:
            ZstdCompressionError: 메모리 부족 또는 인코딩 실패 시.
        """
        # 1. 데이터를 Bytes로 직렬화
        try:
            if isinstance(data_chunks, bytes):
                raw_bytes = data_chunks
            elif isinstance(data_chunks, str):
                raw_bytes = data_chunks.encode('utf-8')
            else:
                raw_bytes = json.dumps(data_chunks, ensure_ascii=False).encode('utf-8')
        except (TypeError, ValueError) as e:
            raise ZstdCompressionError("데이터를 Bytes로 직렬화하는 데 실패했습니다.", original_exception=e) from e

        # 2. Zstd 압축 수행
        try:
            compressor = zstd.ZstdCompressor(level=ZSTD_COMPRESSION_LEVEL)
            return compressor.compress(raw_bytes)
        except MemoryError as e:
            raise ZstdCompressionError(
                "메모리 부족으로 압축 실패 (OOM)", 
                data_size_bytes=len(raw_bytes), 
                original_exception=e
            ) from e
        except Exception as e:
            raise ZstdCompressionError(
                "Zstd 압축 처리 중 예기치 않은 오류 발생", 
                data_size_bytes=len(raw_bytes), 
                original_exception=e
            ) from e

    def _execute_multipart_upload(self, stream: bytes, s3_key: str) -> bool:
        """바이너리 스트림을 S3에 멀티파트 방식으로 안전하게 업로드합니다.
        
        Design Intent: Boto3의 고수준 API(`upload_fileobj`)를 사용하여, 
        임계값을 넘는 데이터에 대해 자동으로 멀티파트 업로드를 수행하고 동시성(Concurrency)을 제어합니다.

        Args:
            stream (bytes): S3에 업로드할 압축된 바이너리 스트림.
            s3_key (str): 대상 S3 객체 키.

        Returns:
            bool: 업로드 성공 여부.

        Raises:
            S3UploadError: 네트워크 불안정, 인증 에러 등으로 업로드 실패 시.
        """
        file_obj = io.BytesIO(stream)
        
        transfer_config = TransferConfig(
            multipart_threshold=S3_MULTIPART_THRESHOLD_BYTES,
            max_concurrency=S3_MAX_CONCURRENCY
        )

        try:
            self._logger.info(f"S3 업로드 시작 - Bucket: {self._bucket_name}, Key: {s3_key}")
            self._boto3_client.upload_fileobj(
                Fileobj=file_obj,
                Bucket=self._bucket_name,
                Key=s3_key,
                Config=transfer_config
            )
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            is_multipart = len(stream) >= S3_MULTIPART_THRESHOLD_BYTES
            
            raise S3UploadError(
                message=f"S3 업로드 중 Boto3 ClientError 발생 (Code: {error_code})",
                bucket_name=self._bucket_name,
                s3_key=s3_key,
                is_multipart=is_multipart,
                original_exception=e
            ) from e
            
        except Exception as e:
            raise S3UploadError(
                message="S3 멀티파트 업로드 중 예기치 않은 네이티브 오류 발생",
                bucket_name=self._bucket_name,
                s3_key=s3_key,
                is_multipart=(len(stream) >= S3_MULTIPART_THRESHOLD_BYTES),
                original_exception=e
            ) from e