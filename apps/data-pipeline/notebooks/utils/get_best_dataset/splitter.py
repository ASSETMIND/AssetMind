import time
from typing import Any, Dict, List, Union
import pandas as pd

from src.model.dataset.splitter import DatasetSplitter


def batch_split_datasets(
    datasets: Dict[str, pd.DataFrame],
    splitter: DatasetSplitter
) -> Dict[str, Dict[str, Union[pd.DataFrame, pd.Series]]]:
    """
    18종 데이터셋 전체에 대해 DatasetSplitter를 순차 적용하여 시계열 분할 저장소를 구축합니다.

    Args:
        datasets: 18종 피처 엔지니어링 완료 데이터셋 딕셔너리
        splitter: DatasetSplitter 인스턴스

    Returns:
        Dict: 데이터셋 버킷 ID별 분할 결과 패키지 (Key: bucket_id, Value: split_dict)
    """
    split_repository: Dict[str, Dict[str, Union[pd.DataFrame, pd.Series]]] = {}

    total_count: int = len(datasets)
    split_mode_name: str = "Train/Val/Test" if len(splitter.split_ratios) == 3 else "Train/Test"
    ratios_display: str = ":".join([f"{ratio * 100:.0f}" for ratio in splitter.split_ratios])
    print("=" * 122)
    print(f" 🚀 [Batch Time-Series Splitting Launch] Mode: {split_mode_name} ({ratios_display}) | Gap: {splitter.forecast_horizon}d | Target: {total_count} Sets")
    print("=" * 122)

    for dataset_id, engineered_dataframe in datasets.items():
        split_result = splitter.split(df=engineered_dataframe)
        split_repository[dataset_id] = split_result

    return split_repository


def report_feature_leakage(
    split_repository: Dict[str, Dict[str, Union[pd.DataFrame, pd.Series]]],
    raw_columns: List[str]
) -> pd.DataFrame:
    """
    분할된 데이터셋의 X 행렬 내 원시 컬럼 잔존 여부를 전수 검증하고 정산 리포트를 사출합니다.

    Args:
        split_repository: batch_split_datasets 반환 저장소
        raw_columns: 격리 대상 원시 컬럼 리스트

    Returns:
        pd.DataFrame: 데이터셋별 격리 상태 및 세트별 Shape 정산 리포트 데이터프레임
    """
    report_records: List[Dict[str, Any]] = []

    for dataset_id, split_result in split_repository.items():
        # X 행렬 내 원시 컬럼 잔존 여부 전수 검증
        leaked_columns = [
            col for col in raw_columns
            if any(col in split_df.columns for key, split_df in split_result.items() if key.startswith("X_"))
        ]

        record: Dict[str, Any] = {
            "Dataset Bucket ID": dataset_id,
            "Target Exclusion": "ALL RAW DROPPED" if not leaked_columns else f"WARNING: Leaked {len(leaked_columns)} Cols"
        }

        # 파티션별 Shape 기록
        for split_name, data_object in split_result.items():
            if hasattr(data_object, "shape"):
                record[f"{split_name} Shape"] = f"{data_object.shape}"

        report_records.append(record)

    return pd.DataFrame(report_records)