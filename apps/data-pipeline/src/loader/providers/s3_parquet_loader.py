"""
[모듈 제목]
Data Pipeline Silver/Gold S3 Parquet Loader Module

[모듈 목적 및 상세 설명]
Silver 및 Gold 레이어의 정형 데이터(Wide DataFrame)를 S3에 Parquet 포맷으로 분산 적재합니다.
Pandas와 PyArrow 엔진의 기본 기능을 활용하여, 데이터의 타입(Schema)을 완벽히 보존하고
지정된 파티션 키(예: year, month, day)에 따라 S3에 하이브 스타일(Hive-style) 폴더 구조를 자동 생성합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: BuilderService에서 병합이 완료된 DataFrame이 담긴 DTO.
2. Validation: DTO 내부 데이터가 정상적인 Pandas DataFrame인지, 비어있지 않은지 사전 검증.
3. Execution: pyarrow 엔진을 통해 S3 대상 경로에 Zstd 압축이 적용된 Parquet 파일로 직접 I/O 수행.
4. Output: S3 적재 성공 여부 (Boolean).

주요 기능:
- Automatic Partitioning: partition_cols 옵션을 통해 물리적인 디렉토리 생성 및 파일 분할을 엔진에 위임 (Fan-out).
- Schema Preservation: 바이너리 컬럼형 포맷을 사용하여 float32, datetime64 등의 데이터 타입 무결성 보장.
- Zstd Compression: Parquet 파일 내부 압축 알고리즘으로 zstd를 사용하여 S3 스토리지 비용 최소화 및 I/O 성능 극대화.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거)
1. Boto3 대신 Pandas/PyArrow의 S3 내장 통신(s3fs) 활용:
   - 장점: 멀티파트 업로드 버퍼링, S3 Key 문자열 조합 등의 무거운 보일러플레이트 코드가 완전히 소거됨. 파티셔닝(폴더 분할) 로직을 단 한 줄의 코드로 구현 가능.
   - 단점: s3fs 라이브러리에 대한 추가 의존성이 발생하며, Boto3 Client 수준의 미세한 예외 제어(특정 HTTP 에러 코드 캐치 등)가 추상화되어 가려짐.
   - 근거: 수백/수천 개의 일자별 폴더로 데이터를 찢어서 올리는 분산 적재(Partitioning)를 직접 코딩하는 것은 바퀴를 다시 발명하는 것(Reinventing the wheel)이며, PyArrow 엔진에 위임하는 것이 유지보수성과 성능 면에서 압도적으로 유리하므로 이 방식을 채택함.
"""

import os

import pandas as pd
from typing import Any, Dict, List

from src.common.exceptions import LoaderError
from src.common.log import LogManager
from src.common.dtos import TransformedDTO 

from src.loader.providers.abstract_loader import AbstractLoader

class S3ParquetLoader(AbstractLoader):
    """Silver/Gold 정형 데이터를 S3에 Parquet 포맷으로 파티셔닝 적재하는 구체 로더 클래스."""

    def __init__(self, bucket_name: str, prefix: str, partition_cols: List[str] = None) -> None:
        """S3ParquetLoader 초기화.

        Args:
            bucket_name (str): 데이터를 적재할 타겟 S3 버킷 명.
            prefix (str): S3 버킷 내 최상위 디렉토리 (예: "silver/market_daily").
            partition_cols (List[str]): 파티셔닝에 사용할 컬럼 리스트 (기본값: ["year", "month", "day"]).
        """
        self._logger = LogManager.get_logger(self.__class__.__name__)
        self._bucket_name = bucket_name
        self._prefix = prefix.strip("/")
        self._partition_cols = partition_cols or ["year", "month", "day"]
        
        self._logger.info(
            f"S3ParquetLoader 초기화 (Bucket: {self._bucket_name}, "
            f"Prefix: {self._prefix}, Partitioning: {self._partition_cols})"
        )

    def _validate_dto(self, dto: TransformedDTO) -> bool:
        """적재 전 데이터가 정상적인 Pandas DataFrame이며 파티셔닝 조건을 만족하는지 검증합니다."""
        
        if not hasattr(dto, "data"):
            raise LoaderError(message="DTO 객체에 'data' 속성이 존재하지 않습니다.")
            
        df = dto.data
        if not isinstance(df, pd.DataFrame):
            raise LoaderError(message=f"입력 데이터가 DataFrame이 아닙니다. (현재 타입: {type(df)})")
            
        if df.empty:
            raise LoaderError(message="데이터프레임이 비어있어 적재를 중단합니다.")
            
        # 파티션 컬럼 존재 여부 엄격 검증
        missing_cols = [col for col in self._partition_cols if col not in df.columns]
        if missing_cols:
            raise LoaderError(
                message=f"데이터프레임에 파티셔닝 필수 컬럼이 누락되었습니다: {missing_cols}"
            )
            
        return True

    def _apply_load(self, dto: TransformedDTO) -> bool:
        """DataFrame을 PyArrow 엔진을 통해 S3에 분산 파티셔닝하여 적재합니다."""
        
        df: pd.DataFrame = dto.data

        # DTO 메타데이터의 bucket_name 또는 job_id를 하위 서브 디렉터리 경로로 동적 결합
        prefix = self._prefix
        if dto.meta and isinstance(dto.meta, dict):
            bucket_subpath = (
                dto.meta.get("bucket_name")
                or dto.meta.get("job_id")
                or dto.meta.get("task_name")
            )
            if bucket_subpath and not prefix.endswith(str(bucket_subpath)):
                prefix = f"{prefix}/{bucket_subpath}"
        
        # 서브 디렉터리가 결합된 최종 prefix를 반영하여 s3_path 생성
        s3_path = f"s3://{self._bucket_name}/{prefix}"

        # LocalStack 엔드포인트 분기 및 storage_options 조립
        storage_options: Dict[str, Any] = {}
        local_endpoint = os.environ.get("LOCAL_S3_ENDPOINT")
        
        if local_endpoint:
            storage_options = {
                "client_kwargs": {
                    "endpoint_url": local_endpoint,
                    "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                    "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                    "region_name": os.getenv("AWS_DEFAULT_REGION")
                }
            }
            
        try:
            # PyArrow 내부 s3fs로 스토리지 옵션 강제 주입
            df.to_parquet(
                path=s3_path,
                engine="pyarrow",
                compression="zstd",
                partition_cols=self._partition_cols,
                index=False,
                storage_options=storage_options,
                existing_data_behavior="delete_matching"
            )
            self._logger.info(f"S3ParquetLoader: S3에 Parquet 파일로 성공적으로 적재되었습니다. (Path: {s3_path})")
            return True
            
        except Exception as e:
            self._logger.error(f"[S3ParquetLoader] 물리 S3 Parquet 파일 쓰기 중 네이티브 I/O 에러 발생: {e}", exc_info=True)
            raise LoaderError(
                message=f"S3 Parquet 적재 중 시스템 I/O 오류 발생: {str(e)}",
                should_retry=False
            ) from e