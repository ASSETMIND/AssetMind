import os
import time
from typing import Any, Dict, List, Tuple
import boto3
import pandas as pd
from tqdm import tqdm
from src.reader.reader_service import ReaderService


class GoldDatasetLoader:
    """골드 레이어 18종 파생 데이터셋 S3 배치 스트리밍 수집 및 정제 전담 로더."""

    def __init__(
        self,
        bucket_name: str = "data-pipeline-gold",
        scan_prefix: str = "gold/market_data/gold_daily_asia/",
        target_reader: str = "s3_parquet_gold"
    ) -> None:
        self.bucket_name: str = bucket_name
        self.scan_prefix: str = scan_prefix
        self.target_reader: str = target_reader

        self.s3_endpoint_url: str = os.getenv("LOCAL_S3_ENDPOINT")
        self.aws_region_name: str = os.getenv("AWS_DEFAULT_REGION")

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.s3_endpoint_url,
            region_name=self.aws_region_name,
        )
        self.reader_service = ReaderService(target_reader=self.target_reader)

    def scan_bucket_job_ids(self) -> List[str]:
        """골드 레이어 버킷에서 유효한 18종 파생 실험 버킷 ID 목록을 스캔 및 정렬합니다."""
        response_scan = self.s3_client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=self.scan_prefix,
            Delimiter="/"
        )
        bucket_job_ids: List[str] = []
        if "CommonPrefixes" in response_scan:
            for prefix_info in response_scan["CommonPrefixes"]:
                folder_name: str = prefix_info["Prefix"].replace(self.scan_prefix, "").strip("/")
                if folder_name.startswith("bucket_"):
                    bucket_job_ids.append(folder_name)
        bucket_job_ids.sort()
        return bucket_job_ids

    def load_all_datasets(self) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
        """18종 골드 데이터셋을 일괄 수집하고 결측 보간 및 DatetimeIndex를 바인딩합니다."""
        bucket_job_ids: List[str] = self.scan_bucket_job_ids()
        gold_dataset_repository: Dict[str, pd.DataFrame] = {}
        summary_records: List[Dict[str, Any]] = []

        start_total_time: float = time.time()
        progress_bar = tqdm(bucket_job_ids, desc="Collecting Datasets", unit="dataset")

        for bucket_job_id in progress_bar:
            bucket_start_time: float = time.time()
            progress_bar.set_postfix_str(f"Processing: {bucket_job_id[:35]}...")

            # 1. Asia / Global 마켓 데이터 스트리밍 Read
            asia_dataframe: pd.DataFrame = self.reader_service.read_dataframe(
                source_path=f"gold/market_data/gold_daily_asia/{bucket_job_id}",
                job_id=f"job_asia_{bucket_job_id}",
                source_layer="gold"
            )
            global_dataframe: pd.DataFrame = self.reader_service.read_dataframe(
                source_path=f"gold/market_data/gold_daily_global/{bucket_job_id}",
                job_id=f"job_global_{bucket_job_id}",
                source_layer="gold"
            )

            # 2. Outer Join 및 중복 컬럼(_dup) 제거
            if not asia_dataframe.empty and not global_dataframe.empty:
                combined_dataframe: pd.DataFrame = pd.merge(
                    asia_dataframe,
                    global_dataframe,
                    on="trade_date",
                    how="outer",
                    suffixes=("", "_dup")
                )
                duplicate_columns = [col for col in combined_dataframe.columns if col.endswith("_dup")]
                if duplicate_columns:
                    combined_dataframe.drop(columns=duplicate_columns, inplace=True)
            elif not asia_dataframe.empty:
                combined_dataframe = asia_dataframe
            else:
                combined_dataframe = global_dataframe

            # 3. DatetimeIndex 정렬 및 바인딩
            if "trade_date" in combined_dataframe.columns:
                combined_dataframe["trade_date"] = pd.to_datetime(combined_dataframe["trade_date"])
                combined_dataframe.sort_values(by="trade_date", ascending=True, inplace=True)
                combined_dataframe.set_index("trade_date", inplace=True)

            # 4. 수치형 변환 및 시계열 결측 보간
            combined_dataframe = combined_dataframe.apply(pd.to_numeric, errors="coerce")
            combined_dataframe = combined_dataframe.ffill().bfill()

            gold_dataset_repository[bucket_job_id] = combined_dataframe
            elapsed_seconds: float = time.time() - bucket_start_time

            summary_records.append({
                "Dataset Bucket ID": bucket_job_id,
                "Total Rows": combined_dataframe.shape[0],
                "Total Features": combined_dataframe.shape[1],
                "Start Date": combined_dataframe.index.min().strftime("%Y-%m-%d") if not combined_dataframe.empty else "N/A",
                "End Date": combined_dataframe.index.max().strftime("%Y-%m-%d") if not combined_dataframe.empty else "N/A",
                "Load Time": f"{elapsed_seconds:.2f}s"
            })

        total_elapsed: float = time.time() - start_total_time
        summary_dataframe: pd.DataFrame = pd.DataFrame(summary_records)

        print("\n" + "=" * 122)
        print(f" 📊 [Total Dataset Ingestion Summary Dashboard] Executed in {total_elapsed:.2f}s")
        print("=" * 122)

        self.reader_service.log_batch_summary()
        return gold_dataset_repository, summary_dataframe