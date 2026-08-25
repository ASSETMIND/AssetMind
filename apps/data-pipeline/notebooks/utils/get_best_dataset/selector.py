import copy
import time
from typing import Any, Dict, List, Tuple, Union
import numpy as np
import pandas as pd

from tqdm import tqdm

from src.feature.postprocessor.filter import (
    filter_constant_features,
    filter_missing_ratio,
    filter_zero_ratio,
    pearson_collinearity,
    hierarchical_collinearity
)
from src.feature.postprocessor.scaler import robust_scale
from src.feature.postprocessor.selector import (
    generate_shadow_features,
    elasticnet_importance,
    lightgbm_importance,
    combine_importances,
    select_feature
)


def process_single_dataset_selection(
    split_datasets: Dict[str, Union[pd.DataFrame, pd.Series]],
    max_missing_ratio: float = 0.2,
    max_zero_ratio: float = 0.8,
    pearson_threshold: float = 0.85,
    distance_threshold: float = 0.40,
    cumulative_threshold: float = 0.99,
    min_features: int = 10,
    max_features: int = 100
) -> Tuple[Dict[str, pd.DataFrame], List[str], float, Dict[str, Any]]:
    """단일 데이터셋 파티션에 대해 5단계 후행 전처리 및 2-Pillar 동적 피처 선별을 집행합니다."""
    model_ready_datasets = copy.deepcopy(split_datasets)
    X_train: pd.DataFrame = model_ready_datasets["X_train"]
    # [설계 의도] y_train 시계열 내 무한대(inf) 결측 정제 및 연속성 복원
    y_train: pd.Series = (
        model_ready_datasets["y_train"]
        .replace([np.inf, -np.inf], np.nan)
        .ffill()
        .bfill()
        .fillna(0.0)
    )
    model_ready_datasets["y_train"] = y_train

    # 타겟 검증/테스트 파티션(y_val, y_test) 무한대 정제 동기화
    for target_key in ["y_val", "y_test"]:
        if target_key in model_ready_datasets and isinstance(model_ready_datasets[target_key], pd.Series):
            model_ready_datasets[target_key] = (
                model_ready_datasets[target_key]
                .replace([np.inf, -np.inf], np.nan)
                .ffill()
                .bfill()
                .fillna(0.0)
            )

    initial_feature_count: int = X_train.shape[1]

    # [설계 의도] Step 1. 저정보 노이즈 피처 필터링 (상수, 결측률, 영값 비율 기준)
    X_train, dropped_constants = filter_constant_features(X_train)
    X_train, dropped_missings = filter_missing_ratio(X_train, max_missing_ratio=max_missing_ratio)
    X_train, dropped_zeros = filter_zero_ratio(X_train, max_zero_ratio=max_zero_ratio)
    noise_removed_count: int = len(dropped_constants) + len(dropped_missings) + len(dropped_zeros)

    # [설계 의도] Step 2. 단변량 피어슨 및 계층 군집화(HFC) 다변량 공선성 압축
    X_train, dropped_pearson = pearson_collinearity(X_train, threshold=pearson_threshold)
    X_train, dropped_hierarchical = hierarchical_collinearity(
        feature_matrix=X_train,
        target_series=y_train,
        distance_threshold=distance_threshold
    )
    collinear_filtered_count: int = X_train.shape[1]

    # [설계 의도] Step 3. X_train 통계량 기반 RobustScaler 학습 및 전체 파티션 정규화 (Leakage-Free)
    numeric_feature_names: List[str] = X_train.select_dtypes(include=["number"]).columns.tolist()
    X_train = X_train[numeric_feature_names].replace([np.inf, -np.inf], np.nan)

    current_filtered_features: List[str] = X_train.columns.tolist()
    train_median = X_train.median(numeric_only=True)

    X_train = X_train.fillna(train_median).ffill().bfill()
    X_train_scaled, _, robust_scaler_instance = robust_scale(X_train=X_train)
    model_ready_datasets["X_train"] = X_train_scaled

    for partition_key in ["X_val", "X_test", "X_inference"]:
        if partition_key in model_ready_datasets and not model_ready_datasets[partition_key].empty:
            partition_data = model_ready_datasets[partition_key][current_filtered_features]
            partition_data = (
                partition_data
                .replace([np.inf, -np.inf], np.nan)
                .ffill()
                .fillna(train_median[current_filtered_features])
                .bfill()
            )
            scaled_matrix = robust_scaler_instance.transform(partition_data)
            model_ready_datasets[partition_key] = pd.DataFrame(
                scaled_matrix,
                index=partition_data.index,
                columns=partition_data.columns
            )

    # [설계 의도] Step 4. 임베디드 2-Pillar (ElasticNet + LightGBM) 중요도 산출 및 동적 피처 선별
    X_train_shadow, shadow_names = generate_shadow_features(feature_matrix=X_train_scaled)

    linear_scores = elasticnet_importance(
        scaled_feature_matrix=X_train_shadow,
        target_series=y_train
    )
    tree_scores = lightgbm_importance(
        feature_matrix=X_train_shadow,
        target_series=y_train
    )
    combined_feature_scores = combine_importances(
        linear_importance=linear_scores,
        tree_importance=tree_scores,
        shadow_feature_names=shadow_names
    )

    selected_features, achieved_cumulative_ratio = select_feature(
        feature_scores=combined_feature_scores,
        cumulative_threshold=cumulative_threshold,
        min_features=min_features,
        max_features=max_features
    )

    # [설계 의도] Step 5. 최종 선별 피처로 전체 파티션 동기화 슬라이싱
    for partition_key in ["X_train", "X_val", "X_test", "X_inference"]:
        if partition_key in model_ready_datasets and not model_ready_datasets[partition_key].empty:
            model_ready_datasets[partition_key] = model_ready_datasets[partition_key][selected_features]

    audit_meta = {
        "initial_feature_count": initial_feature_count,
        "noise_removed_count": noise_removed_count,
        "dropped_constants": dropped_constants,
        "dropped_missings": dropped_missings,
        "dropped_zeros": dropped_zeros,
        "dropped_pearson": dropped_pearson,
        "dropped_hierarchical": dropped_hierarchical,
        "collinear_filtered_count": collinear_filtered_count,
        "selected_features_count": len(selected_features)
    }

    return model_ready_datasets, selected_features, achieved_cumulative_ratio, audit_meta


def batch_select_features(
    split_repository: Dict[str, Dict[str, Union[pd.DataFrame, pd.Series]]],
    max_missing_ratio: float = 0.2,
    max_zero_ratio: float = 0.8,
    pearson_threshold: float = 0.85,
    distance_threshold: float = 0.40,
    cumulative_threshold: float = 0.99,
    min_features: int = 10,
    max_features: int = 100
) -> Tuple[Dict[str, Dict[str, pd.DataFrame]], pd.DataFrame, pd.DataFrame]:
    """18종 분할 데이터셋 전체를 순회하며 후행 전처리 및 동적 피처 선별을 일괄 수행합니다."""
    model_ready_repository: Dict[str, Dict[str, pd.DataFrame]] = {}
    batch_selection_summary_records: List[Dict[str, Any]] = []
    representative_audit_records: List[Dict[str, str]] = []

    total_count: int = len(split_repository)
    print("=" * 115)
    print(f" 🚀 [Batch Feature Selection Launch] Target Datasets: {total_count} Sets | 2-Pillar Hybrid + Robust Scaler")
    print("=" * 115)

    start_total_time: float = time.time()

    progress_bar = tqdm(
        enumerate(split_repository.items(), start=1),
        total=total_count,
        desc="🔍 [2-Pillar Selection]",
        unit="dataset"
    )

    for index, (bucket_job_id, split_datasets) in progress_bar:
        step_start = time.time()
        progress_bar.set_postfix_str(f"Processing: {bucket_job_id[:32]}...")

        model_ready_data, selected_cols, cum_ratio, audit = process_single_dataset_selection(
            split_datasets=split_datasets,
            max_missing_ratio=max_missing_ratio,
            max_zero_ratio=max_zero_ratio,
            pearson_threshold=pearson_threshold,
            distance_threshold=distance_threshold,
            cumulative_threshold=cumulative_threshold,
            min_features=min_features,
            max_features=max_features
        )

        model_ready_repository[bucket_job_id] = model_ready_data
        elapsed: float = time.time() - step_start
        
        progress_bar.set_postfix_str(f"Done: {bucket_job_id[:25]}... ({elapsed:.1f}s, Feats: {len(selected_cols)})")

        batch_selection_summary_records.append({
            "Dataset Bucket ID": bucket_job_id,
            "Initial Features": audit["initial_feature_count"],
            "After Noise Filter": audit["initial_feature_count"] - audit["noise_removed_count"],
            "After Collinear Filter": audit["collinear_filtered_count"],
            "Selected Features": len(selected_cols),
            "Cumulative Coverage": f"{cum_ratio * 100:.1f}%",
            "Elapsed Time": f"{elapsed:.2f}s"
        })

        if index == 1:
            init_cnt = audit["initial_feature_count"]
            noise_cnt = audit["noise_removed_count"]
            p_dropped_cnt = len(audit["dropped_pearson"])
            h_filtered_cnt = audit["collinear_filtered_count"]
            h_dropped_cnt = len(audit["dropped_hierarchical"])

            representative_audit_records.extend([
                {
                    "단계 (Pipeline Step)": "1. Noise Filter (Constant & Missing & Zero)",
                    "잔여 피처 수 (Features)": f"{init_cnt - noise_cnt:,}",
                    "변동 내역 (Changes)": f"-{noise_cnt} Features (Constant: {len(audit['dropped_constants'])}, Missing: {len(audit['dropped_missings'])}, Zero: {len(audit['dropped_zeros'])})",
                    "적용 기준 (Fit Strategy)": f"상수 및 결측률(> {max_missing_ratio*100:.0f}%), 0값(≥ {max_zero_ratio*100:.0f}%)"
                },
                {
                    "단계 (Pipeline Step)": "2. Pearson Collinearity",
                    "잔여 피처 수 (Features)": f"{init_cnt - noise_cnt - p_dropped_cnt:,}",
                    "변동 내역 (Changes)": f"-{p_dropped_cnt} Features",
                    "적용 기준 (Fit Strategy)": f"피어슨 선형 상관계수(|r| ≥ {pearson_threshold})"
                },
                {
                    "단계 (Pipeline Step)": "3. Hierarchical Feature Clustering (HFC)",
                    "잔여 피처 수 (Features)": f"{h_filtered_cnt:,}",
                    "변동 내역 (Changes)": f"-{h_dropped_cnt} Features",
                    "적용 기준 (Fit Strategy)": f"상관거리 계층 군집화 (Distance ≤ {distance_threshold})"
                },
                {
                    "단계 (Pipeline Step)": "4. Robust Feature Scaling",
                    "잔여 피처 수 (Features)": f"{h_filtered_cnt:,}",
                    "변동 내역 (Changes)": "No Dimension Change (All Partitions Normalized)",
                    "적용 기준 (Fit Strategy)": "학습 데이터 중앙값 및 IQR 통계량 기준"
                },
                {
                    "단계 (Pipeline Step)": f"5. Dynamic 2-Pillar Selection (Top {len(selected_cols)})",
                    "잔여 피처 수 (Features)": f"{len(selected_cols):,}",
                    "변동 내역 (Changes)": f"Selected {len(selected_cols)} Features",
                    "적용 기준 (Fit Strategy)": f"ElasticNet + LightGBM (Target: {int(cumulative_threshold * 100)}%)"
                }
            ])

    total_elapsed: float = time.time() - start_total_time
    print(f" ✅ [Batch Feature Selection Completed] Total Elapsed Time: {total_elapsed:.2f}s")

    summary_df = pd.DataFrame(batch_selection_summary_records)
    audit_df = pd.DataFrame(representative_audit_records).set_index("단계 (Pipeline Step)")

    return model_ready_repository, summary_df, audit_df