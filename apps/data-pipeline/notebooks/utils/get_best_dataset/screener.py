import os
import time
import warnings
from typing import Any, Dict, List, Tuple
import joblib
import pandas as pd

from src.model.core.elasticnet_regressor import ElasticNetRegressor
from src.model.core.xgboost_regressor import XGBoostRegressor
from src.model.core.random_forest_regressor import RandomForestRegressor


def screen_champion_dataset(
    dataset_partitions: Dict[str, pd.DataFrame],
    eval_partition: str = "X_test"
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """단일 데이터셋 파티션에 대해 3대 베이스라인 모델을 독립 학습하고 검증 지표를 산출합니다.

    Args:
        dataset_partitions (Dict[str, pd.DataFrame]): X_train, y_train, X_test, y_test 등을 포함하는 데이터 딕셔너리.
        eval_partition (str): 평가 대상 피처 파티션 키 (기본값: "X_test").

    Returns:
        Tuple[Dict[str, Any], List[Dict[str, Any]]]:
            - summary_record: 데이터셋 평균 및 최고 모델 성능 요약 레코드.
            - detailed_metrics: 3개 개별 모델의 세부 평가 결과 리스트.
    """
    X_train: pd.DataFrame = dataset_partitions["X_train"]
    y_train: pd.Series = dataset_partitions["y_train"]
    
    # 평가 대상 타겟 파티션 키 결정
    target_eval_key: str = "y_val" if eval_partition == "X_val" and "y_val" in dataset_partitions else "y_test"
    target_feature_key: str = eval_partition if eval_partition in dataset_partitions else "X_test"
    
    X_eval: pd.DataFrame = dataset_partitions[target_feature_key]
    y_eval: pd.Series = dataset_partitions[target_eval_key]

    # 상태 격리된 3대 베이스라인 모델 인스턴스화
    candidate_models = [
        ElasticNetRegressor(alpha=1.0, l1_ratio=0.5, random_state=42),
        XGBoostRegressor(n_estimators=100, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, random_state=42),
        RandomForestRegressor(n_estimators=100, max_depth=3, min_samples_split=4, random_state=42)
    ]

    detailed_metrics: List[Dict[str, Any]] = []

    for model_instance in candidate_models:
        model_instance.fit(X_train=X_train, y_train=y_train)
        metrics = model_instance.evaluate(X_test=X_eval, y_test=y_eval)
        detailed_metrics.append({
            "model_name": model_instance.model_name,
            "RMSE": metrics["RMSE"],
            "MAE": metrics["MAE"],
            "MDA": metrics["MDA"]
        })

    average_mda: float = sum(m["MDA"] for m in detailed_metrics) / len(detailed_metrics)
    average_rmse: float = sum(m["RMSE"] for m in detailed_metrics) / len(detailed_metrics)
    average_mae: float = sum(m["MAE"] for m in detailed_metrics) / len(detailed_metrics)
    best_model_metric = max(detailed_metrics, key=lambda x: x["MDA"])

    summary_record = {
        "Selected Features": X_train.shape[1],
        "Avg MDA": average_mda,
        "Avg RMSE": average_rmse,
        "Avg MAE": average_mae,
        "Best Model": best_model_metric["model_name"],
        "Best Model MDA": best_model_metric["MDA"],
        "Best Model RMSE": best_model_metric["RMSE"]
    }

    return summary_record, detailed_metrics


def run_batch_screening(
    model_ready_repository: Dict[str, Dict[str, pd.DataFrame]]
) -> Tuple[pd.DataFrame, str, Dict[str, Any], pd.DataFrame]:
    """18종 데이터셋 전체에 대해 3대 모델 일괄 스크리닝을 수행하고 종합 랭킹을 도출합니다.

    Args:
        model_ready_repository (Dict[str, Dict[str, pd.DataFrame]]): 모델 투입 준비 완료 데이터셋 저장소.

    Returns:
        Tuple[pd.DataFrame, str, Dict[str, Any], pd.DataFrame]:
            - raw_ranking_df: 수치형 정렬 완료 랭킹 데이터프레임.
            - champion_id: 1위 챔피언 데이터셋 버킷 ID.
            - champion_meta: 1위 챔피언 주요 성능 메타데이터 딕셔너리.
            - display_ranking_df: 보고서 출력용 포맷팅 데이터프레임.
    """
    from tqdm.auto import tqdm

    total_count: int = len(model_ready_repository)
    print("=" * 115)
    print(f" 🚀 [Batch Dataset Screening Launch] Target Datasets: {total_count} Sets × 3 Models (54 Evaluations)")
    print("=" * 115)

    batch_records: List[Dict[str, Any]] = []
    start_time: float = time.time()

    progress_bar = tqdm(
        model_ready_repository.items(),
        total=total_count,
        desc="🔍 [Dataset Screening]",
        unit="set"
    )

    for bucket_job_id, dataset_partitions in progress_bar:
        step_start = time.time()
        summary_record, _ = screen_champion_dataset(dataset_partitions=dataset_partitions)
        elapsed: float = time.time() - step_start

        summary_record["Dataset Bucket ID"] = bucket_job_id
        summary_record["Elapsed Time"] = f"{elapsed:.2f}s"
        batch_records.append(summary_record)

    total_elapsed: float = time.time() - start_time
    print(f" ✅ [Screening Completed] Total Elapsed Time: {total_elapsed:.2f}s")

    raw_ranking_df = pd.DataFrame(batch_records)

    # 1순위: Avg MDA(내림차순) ➔ 2순위: Avg RMSE(오름차순) 정렬
    raw_ranking_df.sort_values(
        by=["Avg MDA", "Avg RMSE"],
        ascending=[False, True],
        inplace=True
    )
    raw_ranking_df.reset_index(drop=True, inplace=True)
    raw_ranking_df.index += 1
    raw_ranking_df.index.name = "Rank"

    # 1위 챔피언 확정
    champion_id: str = raw_ranking_df.iloc[0]["Dataset Bucket ID"]
    champion_meta = {
        "id": champion_id,
        "avg_mda": raw_ranking_df.iloc[0]["Avg MDA"],
        "avg_rmse": raw_ranking_df.iloc[0]["Avg RMSE"],
        "avg_mae": raw_ranking_df.iloc[0]["Avg MAE"],
        "features": int(raw_ranking_df.iloc[0]["Selected Features"]),
        "best_model": raw_ranking_df.iloc[0]["Best Model"],
        "total_elapsed": total_elapsed
    }

    # 표시용 포맷팅 데이터프레임 생성
    display_ranking_df = raw_ranking_df.copy()
    display_ranking_df["Avg MDA"] = display_ranking_df["Avg MDA"].map(lambda x: f"{x * 100:.2f}%")
    display_ranking_df["Avg RMSE"] = display_ranking_df["Avg RMSE"].map(lambda x: f"{x:.6f}")
    display_ranking_df["Avg MAE"] = display_ranking_df["Avg MAE"].map(lambda x: f"{x:.6f}")
    display_ranking_df["Best Model MDA"] = display_ranking_df["Best Model MDA"].map(lambda x: f"{x * 100:.2f}%")
    display_ranking_df["Best Model RMSE"] = display_ranking_df["Best Model RMSE"].map(lambda x: f"{x:.6f}")

    return raw_ranking_df, champion_id, champion_meta, display_ranking_df


def save_champion_dataset(
    model_ready_repository: Dict[str, Dict[str, pd.DataFrame]],
    champion_dataset_id: str,
    output_artifact_path: str = "champion_dataset.pkl"
) -> Dict[str, Any]:
    """1위 챔피언 데이터셋 파티션을 로컬 파일로 직렬화 저장하고 무결성을 검증합니다.

    Args:
        model_ready_repository (Dict[str, Dict[str, pd.DataFrame]]): 모델 투입 준비 완료 데이터셋 저장소.
        champion_dataset_id (str): 최종 1위 챔피언 데이터셋 ID.
        output_artifact_path (str): 저장할 아티팩트 파일 경로 (기본값: "champion_dataset.pkl").

    Returns:
        Dict[str, Any]: 저장된 파일 크기 및 파티션별 Shape 메타데이터 딕셔너리.
    """
    champion_partitions: Dict[str, pd.DataFrame] = model_ready_repository[champion_dataset_id]

    joblib.dump(champion_partitions, output_artifact_path)
    file_size_kb: float = os.path.getsize(output_artifact_path) / 1024.0

    restored_partitions = joblib.load(output_artifact_path)
    assert "X_train" in restored_partitions and "X_test" in restored_partitions, "파티션 무결성 검증 실패: X_train 또는 X_test 누락"

    return {
        "artifact_path": output_artifact_path,
        "file_size_kb": file_size_kb,
        "train_shape": champion_partitions["X_train"].shape,
        "test_shape": champion_partitions["X_test"].shape
    }