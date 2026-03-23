"""
금융 원천 데이터의 원형 보존 및 스토리지 최적화를 위한 Zstandard(zstd) 스트리밍 압축 적재를 담당하는 구체화된(Concrete) 적재기 모듈입니다.
`AbstractLoader`의 템플릿 생명주기를 상속받아 파이프라인의 표준 규격을 준수하며, AWS S3로의 대용량 데이터 전송을 멀티파트(Multipart) 방식으로 안전하고 효율적으로 수행합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Validation: ExtractedDTO 유입 시, S3 파티셔닝에 필수적인 메타데이터(source, job_id) 및 원본 데이터 무결성 사전 검증.
2. Key Generation: 검증된 메타데이터를 활용하여 Hive-Style 파티셔닝 기반의 S3 Object Key 동적 생성.
3. Compression: 방대한 JSON/Text 페이로드를 Zstd 알고리즘으로 직렬화 및 인메모리 바이너리 스트림 압축.
4. Execution: Boto3 TransferConfig를 활용하여 임계값 초과 시 병렬 멀티파트 업로드 자동 수행.
5. Output: 최종 S3 적재 성공 여부(Boolean) 반환 및 실패 시 구체화된 도메인 예외(S3UploadError) 발생.

주요 기능:
- Zstd Streaming Compression: gzip 대비 압축/해제 속도가 월등히 빠르고 압축률이 뛰어난 zstandard 라이브러리를 활용하여 메모리 스파이크 및 네트워크 대역폭 비용 최소화.
- Automated Multipart Upload: 대용량 페이로드 업로드 시 Boto3의 고수준 API(`upload_fileobj`)를 통한 네트워크 단절 방지 및 멀티스레드 병렬 전송 극대화.
- Hive-Style Partitioning: DTO의 `meta` 정보를 파싱하여 `provider=.../job=.../year=...` 형태의 경로를 동적 생성, 향후 Athena/Glue 기반의 데이터 카탈로깅 및 쿼리 성능 최적화 보장.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
1. Zstandard Compression vs Gzip/Raw JSON:
   - 장점: 방대한 텍스트 위주의 금융 데이터 압축 시 Gzip 대비 압축 속도는 약 3~5배, 해제 속도는 2~3배 빠르며 스토리지 비용을 획기적으로 절감함.
   - 단점: 파이썬 생태계 내장 모듈이 아니므로 `zstandard` C-extension 서드파티 의존성이 추가됨.
   - 근거: S3에 적재되는 금융 원천 데이터는 추후 백테스팅 및 감사(Audit)를 위해 원본 포맷을 반드시 유지해야 하므로 데이터 볼륨이 기하급수적으로 증가함. 인프라 비용 절감과 적재 파이프라인의 I/O 병목 해소를 위해 Zstd 도입은 필수적인 엔지니어링 선택임.
2. High-level Boto3 API (`upload_fileobj`) vs Low-level Multipart API:
   - 장점: 파일 크기를 직접 계산하고 청크를 나누어 ETag를 관리하는 복잡한 보일러플레이트를 완벽히 제거하며, `TransferConfig`만으로 스레드 풀 기반의 병렬 처리가 가능함.
   - 단점: 업로드 도중 치명적 프로세스 패닉 발생 시 S3 버킷에 불완전한 파트(Incomplete Multipart Object)가 남아 스토리지 비용 누수가 발생할 수 있음.
   - 근거: 어플리케이션 계층에서 복잡한 청크 롤백을 구현하는 것보다 고수준 API의 안정성을 취하고, 인프라 계층(S3 Lifecycle Rule)에서 불완전 파트를 자동 삭제하도록 역할을 분리하는 것이 유지보수에 압도적으로 유리함.
3. Explicit Metadata Validation (`_validate_dto`):
   - 장점: 파티셔닝 키 구성에 필수적인 `source`와 `job_id` 누락을 네트워크 I/O 전 단계에서 완벽히 차단함.
   - 단점: 수집기(Extractor) 계층의 메타데이터 스키마와 묵시적인 강한 결합(Coupling)이 발생함.
   - 근거: 메타데이터가 누락된 채 임의의 경로(Unknown)에 데이터가 적재되면 데이터 레이크가 검색 불가능한 쓰레기장(Data Swamp)으로 전락하므로, 강결합을 수용하더라도 무결성 강제 검증이 운영상 더 중요함.
"""

import io
import json
import os
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
# [Configuration] Constants
# ==============================================================================
# [설계 의도] Boto3 멀티파트 업로드 임계값. 
# 10MB 이상의 페이로드는 메모리에 모두 올리지 않고 청크 단위로 병렬 스트리밍 전송하여 OOM을 방지함.
S3_MULTIPART_THRESHOLD_BYTES: int = 10 * 1024 * 1024

# [설계 의도] 멀티파트 전송 시 동시 활성화할 스레드 수. 
# EC2/컨테이너의 네트워크 대역폭과 CPU 컨텍스트 스위칭 비용의 최적 밸런스 지점(10)으로 강제함.
S3_MAX_CONCURRENCY: int = 10

# [설계 의도] Zstd 압축 레벨 (1~22). 
# 레벨 3은 Zstd의 기본값으로, CPU 연산 비용 대비 가장 가성비 높은 압축률과 압축 속도를 제공함.
ZSTD_COMPRESSION_LEVEL: int = 3


class S3Loader(AbstractLoader):
    """금융 원천 데이터의 Zstd 스트리밍 압축 및 AWS S3 적재를 전담하는 구체화 클래스.
    
    `AbstractLoader`의 템플릿 생명주기를 준수하며, Boto3 클라이언트를 
    안전하게 캡슐화하여 클라우드 스토리지 I/O를 수행합니다.
    
    Attributes:
        _bucket_name (str): 데이터를 적재할 타겟 S3 버킷의 식별 이름.
        _region (str): S3 버킷이 프로비저닝된 AWS 리전명 (예: 'ap-northeast-2').
        _boto3_client (Any): 연결이 수립된 Boto3 S3 Session/Client 인스턴스.
    """

    def __init__(self, bucket_name: str, region: str) -> None:
        """S3Loader 인스턴스를 초기화하고 AWS 자격 증명 기반의 S3 클라이언트를 구성합니다.

        Args:
            bucket_name (str): 대상 S3 버킷 이름.
            region (str): AWS 리전 (예: 'ap-northeast-2').
            
        Raises:
            ConfigurationError: 필수 AWS 설정(bucket_name, region)이 누락되었거나 Boto3 세션 생성 실패 시.
        """
        # [설계 의도] 부모 클래스(AbstractLoader)의 초기화 메서드를 호출하여 
        # ConfigManager 로드 및 Logger 초기화를 일관성 있게 상속받음.
        super().__init__()
        
        self._bucket_name = bucket_name
        self._region = region
        
        # [설계 의도] 클라우드 인프라 연동 시 필수 파라미터 누락은 파이프라인 런타임에 
        # 치명적 에러를 유발하므로 객체 초기화 시점에 조기 검증(Fail-Fast)함.
        if not self._bucket_name:
            raise ConfigurationError("S3 버킷 이름이 누락되었습니다.", key_name="aws.s3.bucket_name")
        if not self._region:
            raise ConfigurationError("AWS 리전이 누락되었습니다.", key_name="aws.region")
            
        self._boto3_client = self._init_s3_client()

    def _init_s3_client(self) -> Any:
        """런타임 환경에 최적화된 Boto3 S3 클라이언트를 동적으로 초기화합니다.
        
        [설계 의도] 
        비즈니스 로직과 클라이언트 생성 로직을 분리하여 OCP(개방-폐쇄 원칙)를 준수합니다.
        이를 통해 향후 AWS STS(AssumeRole) 연동이나, 환경 변수를 활용한 로컬 모킹(LocalStack) 
        오버라이딩 시 메인 적재 로직의 수정 없이 유연하게 인프라 계층을 교체할 수 있습니다.

        Returns:
            Any: 사용할 준비가 완료된 boto3 S3 client 인스턴스.
            
        Raises:
            ConfigurationError: 자격 증명 오류 등 Boto3 클라이언트 초기화 중 예외 발생 시.
        """
        try:
            # 1. 공통 파라미터 세팅 (loader.yml의 운영 설정 기반)
            client_kwargs = {
                "service_name": 's3',
                "region_name": self._region
            }

            # 2. 환경 변수를 통한 자동 분기 처리 (휴먼 에러 방지 로직)
            local_endpoint = os.environ.get("LOCAL_S3_ENDPOINT")
            
            if local_endpoint:
                # [설계 의도] 통합 테스트 환경(Docker Compose)에서 외부망(Real AWS)을 타지 않고 
                # LocalStack 컨테이너로 안전하게 트래픽을 라우팅하기 위한 오버라이드 훅.
                client_kwargs.update({
                    "endpoint_url": local_endpoint,
                    "aws_access_key_id": "test",      # LocalStack Dummy Key
                    "aws_secret_access_key": "test"   # LocalStack Dummy Key
                })
                self._logger.info(f"[개발 환경 감지] LocalStack S3 클라이언트로 초기화합니다. (Endpoint: {local_endpoint})")
            else:
                self._logger.info("[운영 환경 감지] 실제 AWS S3 클라이언트로 초기화합니다.")

            # 3. 클라이언트 생성
            return boto3.client(**client_kwargs)

        except (BotoCoreError, ClientError) as e:
            raise ConfigurationError(f"AWS 설정 오류: {e}") from e

    def _validate_dto(self, dto: ExtractedDTO) -> bool:
        """적재 대상인 `ExtractedDTO`의 페이로드 및 파티셔닝 메타데이터 무결성을 사전에 검증합니다.

        [설계 의도] 
        데이터 오염 및 잘못된 파티셔닝(Data Swamp) 방지. `dtos.py` 명세에 따라 
        `data` 필드의 존재 여부와 `meta` 내 S3 키 생성 필수값(`source`, `job_id`)을 엄격히 확인하여 
        무결성이 깨진 데이터의 S3 업로드 비용을 원천 차단합니다.

        Args:
            dto (ExtractedDTO): 검증할 데이터 전송 객체.

        Returns:
            bool: 무결성 검증 통과 여부.
        """
        if dto.data is None:
            self._logger.warning("검증 실패: ExtractedDTO의 'data' 속성이 비어 있습니다.")
            return False
            
        if not isinstance(dto.meta, dict):
            self._logger.warning("검증 실패: ExtractedDTO의 'meta' 속성이 딕셔너리가 아닙니다.")
            return False
            
        if "source" not in dto.meta or "job_id" not in dto.meta:
            self._logger.warning("검증 실패: S3 파티셔닝에 필요한 'source' 또는 'job_id'가 meta에 없습니다.")
            return False
            
        return True

    def _apply_load(self, dto: ExtractedDTO) -> bool:
        """사전 검증이 완료된 DTO에 대해 실제 S3 업로드 물리 파이프라인을 가동하는 훅(Hook) 메서드.

        Args:
            dto (ExtractedDTO): 검증을 통과한 적재 대상 데이터 객체.

        Returns:
            bool: 적재 성공 여부.
        """
        s3_key = self._generate_s3_key(dto)
        return self._upload_stream(dto, s3_key)

    def _generate_s3_key(self, dto: ExtractedDTO) -> str:
        """S3 객체가 적재될 논리적 디렉토리 경로 및 파일 이름(Object Key)을 동적으로 생성합니다.
        
        [설계 의도] 
        수집 메타데이터의 `source`(예: KIS)와 `job_id`(예: kis_kospi_daily)를 기반으로 
        Hive-Style 파티셔닝(`key=value/`) 경로를 구성합니다. 이는 AWS Athena, AWS Glue 등 
        분석 서비스에서 파티션 프로젝션(Partition Projection)을 통해 쿼리 스캔 비용을 
        획기적으로 줄이는 데이터 카탈로깅 최적화 기법입니다.

        Args:
            dto (ExtractedDTO): 키 생성의 기반 메타데이터가 포함된 데이터 객체.

        Returns:
            str: 계층적 파티션과 고유 파일명이 결합된 S3 Object Key.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        date_path = now.strftime("year=%Y/month=%m/day=%d")
        
        # `_validate_dto`를 통과했으므로 meta 내부의 source, job_id 속성 존재가 완벽히 보장됨.
        provider = str(dto.meta.get("source")).lower()
        job_id = str(dto.meta.get("job_id")).lower()
        
        # 밀리초 수준의 동시 수집 충돌을 피하기 위해 난수 기반 UUID 짧은 식별자 추가
        unique_id = uuid.uuid4().hex[:8]
        
        return f"raw/provider={provider}/job={job_id}/{date_path}/{now.timestamp()}_{unique_id}.json.zst"

    def _upload_stream(self, dto: ExtractedDTO, s3_key: str) -> bool:
        """데이터 객체의 원본을 압축 스트림으로 변환하고 S3 네트워크 I/O를 수행하도록 조율합니다.

        Args:
            dto (ExtractedDTO): 원본 데이터 객체.
            s3_key (str): 대상 S3 객체 경로(Key).

        Returns:
            bool: 최종 압축 및 적재 파이프라인 성공 여부.
        """
        data_chunks = dto.data 
        compressed_bytes = self._compress_to_zstd_stream(data_chunks)
        
        return self._execute_multipart_upload(compressed_bytes, s3_key)

    def _compress_to_zstd_stream(self, data_chunks: Any) -> bytes:
        """메모리 상의 Python 객체/문자열을 Zstandard(zstd) 알고리즘으로 안전하게 직렬화 및 압축합니다.

        Args:
            data_chunks (Any): 압축할 원본 데이터 (bytes, str, 또는 json 직렬화 가능한 객체).
            
        Returns:
            bytes: Zstd로 압축 완료된 바이너리 스트림 데이터.

        Raises:
            ZstdCompressionError: JSON 직렬화 불가 객체 유입, 메모리 부족(OOM), 또는 인코딩 실패 시.
        """
        # 1. 데이터를 Bytes로 직렬화
        # [설계 의도] 파이프라인에서 전달받은 원본 데이터의 타입 불확실성을 방어하기 위해 
        # 분기 처리하여 일관된 UTF-8 바이트 스트림으로 변환함.
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
        # [설계 의도] 대용량 데이터 압축 시 C-레벨에서 할당하는 메모리가 시스템 한계를 
        # 초과할 수 있으므로, `MemoryError`를 명시적으로 포착하여 컨테이너 패닉을 방지함.
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
        """압축된 바이너리 스트림을 Boto3 TransferManager를 통해 S3에 멀티파트 방식으로 안전하게 업로드합니다.
        
        [설계 의도] 
        저수준(Low-level) API인 `create_multipart_upload`를 수동으로 제어하지 않고, 
        고수준 API인 `upload_fileobj`와 `TransferConfig`를 결합하여 사용함. 이를 통해
        임계값(10MB) 미만의 데이터는 단일 Put 요청으로 최적화하고, 임계값을 초과하는 대용량 데이터만 
        자동으로 스레드 풀을 가동하여 분할/병렬 업로드함으로써 네트워크 활용도와 안정성을 극대화함.

        Args:
            stream (bytes): S3에 업로드할 인메모리 압축 바이너리 스트림.
            s3_key (str): 타겟 S3 객체 고유 경로.

        Returns:
            bool: 성공적으로 업로드되었을 경우 True.

        Raises:
            S3UploadError: 권한 오류(403), 라우팅 오류(404), 서드파티 네트워크 단절 등으로 업로드 실패 시.
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
            # [설계 의도] AWS SDK 특화 에러를 파싱하여 도메인 예외인 S3UploadError 내부에 메타데이터화.
            # 운영팀이 CloudWatch/Datadog에서 에러 코드를 즉각적으로 식별할 수 있도록 지원.
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
            # 예상치 못한 네이티브 소켓 에러나 스트림 I/O 예외 방어
            raise S3UploadError(
                message="S3 멀티파트 업로드 중 예기치 않은 네이티브 오류 발생",
                bucket_name=self._bucket_name,
                s3_key=s3_key,
                is_multipart=(len(stream) >= S3_MULTIPART_THRESHOLD_BYTES),
                original_exception=e
            ) from e