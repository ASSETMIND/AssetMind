import copy
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from tqdm import tqdm

from src.dataset.walk_forward_splitter import WalkForwardSplitter
from src.feature.postprocessor.filter import (
    filter_constant_features,
    filter_missing_ratio,
    filter_zero_ratio,
    hierarchical_collinearity,
    pearson_collinearity
)
from src.feature.postprocessor.forward_selection import (
    combine_importances,
    elasticnet_importance,
    generate_shadow_features,
    lightgbm_importance,
    select_feature
)
from src.feature.postprocessor.scaler import rolling_scale
from src.feature.postprocessor.stability import FeatureQualityGate, filter_walk_forward_stability

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_MAX_MISSING_RATIO: float = 0.2      # 고결측치 피처를 배제하기 위한 최대 결측 비율 상한선 (20% 초과)
DEFAULT_MAX_ZERO_RATIO: float = 0.8         # 희소(Sparse) 피처를 배제하기 위한 최대 0.0 수치 비율 상한선 (80% 이상)
DEFAULT_PEARSON_THRESHOLD: float = 0.85     # 피어슨 선형 공선성 판정을 위한 상관계수 절대값 임계치 (|r| >= 0.85)
DEFAULT_DISTANCE_THRESHOLD: float = 0.40    # HFC 계층 군집화 상관거리 절단 임계치 (Distance <= 0.40)
DEFAULT_MIN_FEATURES: int = 10              # 2-Pillar 변곡점 선별 시 최소 확보 피처 수 하한선
DEFAULT_MAX_FEATURES: int = 50              # 과적합 방지를 위한 2-Pillar 선별 피처 수 상한선
DEFAULT_ROLLING_WINDOW: int = 60            # 적응형 스케일링 롤링 윈도우 크기 (60영업일)
DEFAULT_ROLLING_MIN_PERIODS: int = 20       # 롤링 통계량 계산을 위한 최소 관측치 일수 (20영업일)
DEFAULT_CLIP_BOUND: float = 3.0             # 극단치 억제를 위한 윈저화 표준편차 유계화 배수 (±3-sigma)


# ==============================================================================
# Public API Functions
# ==============================================================================

def process_single_dataset_selection(
    split_datasets: Dict[str, Union[pd.DataFrame, pd.Series]],
    max_missing_ratio: float = DEFAULT_MAX_MISSING_RATIO,
    max_zero_ratio: float = DEFAULT_MAX_ZERO_RATIO,
    pearson_threshold: float = DEFAULT_PEARSON_THRESHOLD,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
    min_features: int = DEFAULT_MIN_FEATURES,
    max_features: int = DEFAULT_MAX_FEATURES
) -> Tuple[Dict[str, Any], List[str], float, Dict[str, Any]]:
    """단일 데이터셋 파티션에 대해 6단계 후행 전처리 및 2-Pillar 동적 피처 선별을 수행합니다.

    Args:
        split_datasets: 시계열 분할된 원본 데이터셋 딕셔너리 (X_train, y_train 등).
        max_missing_ratio: 결측치 허용 비율 상한선 (기본값: 0.20).
        max_zero_ratio: 0값 비율 허용 상한선 (기본값: 0.80).
        pearson_threshold: 피어슨 상관계수 임계치 (기본값: 0.85).
        distance_threshold: HFC 군집 거리 임계치 (기본값: 0.40).
        min_features: 최소 선별 피처 수 (기본값: 10).
        max_features: 최대 선별 피처 수 (기본값: 50).

    Returns:
        Tuple[Dict[str, Any], List[str], float, Dict[str, Any]]:
            - model_ready_datasets: 최종 선별 및 스케일링이 완료된 파티션 딕셔너리.
            - selected_features: 최종 선별된 핵심 피처명 리스트.
            - achieved_cumulative_ratio: Kneedle 엘보우 선별 누적 중요도 비율.
            - audit_meta: 각 단계별 피처 수 변동 및 탈락 내역을 담은 메타데이터.
    """
    model_ready_datasets: Dict[str, Any] = copy.deepcopy(split_datasets)
    X_train: pd.DataFrame = model_ready_datasets["X_train"]

    # 1. 타깃 시계열(y_train, y_val, y_test) 내 무한대(Inf) 및 결측치 정제
    y_train: pd.Series = _clean_target_series(model_ready_datasets["y_train"])
    model_ready_datasets["y_train"] = y_train
    for target_key in ("y_val", "y_test"):
        if target_key in model_ready_datasets and isinstance(model_ready_datasets[target_key], pd.Series):
            model_ready_datasets[target_key] = _clean_target_series(model_ready_datasets[target_key])

    initial_feature_count: int = X_train.shape[1]

    # 2. [Filter 1] 분산 0 상수, 결측률 초과, 0값 비율 초과 피처 제거
    X_train, dropped_constants = filter_constant_features(X_train)
    X_train, dropped_missings = filter_missing_ratio(X_train, max_missing_ratio=max_missing_ratio)
    X_train, dropped_zeros = filter_zero_ratio(X_train, max_zero_ratio=max_zero_ratio)
    noise_removed_count: int = len(dropped_constants) + len(dropped_missings) + len(dropped_zeros)

    # 3. [Filter 2] 피어슨 선형 상관(|r| >= threshold) 압축
    X_train, dropped_pearson = pearson_collinearity(
        feature_matrix=X_train,
        target_series=y_train,
        threshold=pearson_threshold
    )

    # 4. [Filter 3] HFC 계층 군집화 기반 상관거리(Distance <= threshold) 압축
    X_train, dropped_hierarchical = hierarchical_collinearity(
        feature_matrix=X_train,
        target_series=y_train,
        distance_threshold=distance_threshold
    )
    collinear_filtered_count: int = X_train.shape[1]

    # 5. [Filter 4] 5-Fold Walk-Forward OOF 부호 일관성(>= 80%) 및 단일표본 t-검정(p < 0.05) 검증
    time_series_splitter = WalkForwardSplitter(n_splits=5, forecast_horizon=20, min_train_ratio=0.5)
    quality_gate = FeatureQualityGate()
    X_train, dropped_unstable = filter_walk_forward_stability(
        feature_matrix=X_train,
        target_series=y_train,
        splitter=time_series_splitter,
        gate=quality_gate,
        minimum_features=min_features
    )
    stability_filtered_count: int = X_train.shape[1]

    # 6. [Filter 5] 최근 60영업일 롤링 표준화, 3-시그마 윈저화 및 외삽 방지 클리핑 적용
    numeric_columns: List[str] = X_train.select_dtypes(include=["number"]).columns.tolist()
    X_train = X_train[numeric_columns].replace([np.inf, -np.inf], np.nan)
    survived_features: List[str] = X_train.columns.tolist()

    _apply_rolling_scale_and_bounding(
        datasets=model_ready_datasets,
        target_features=survived_features,
        window=DEFAULT_ROLLING_WINDOW,
        min_periods=DEFAULT_ROLLING_MIN_PERIODS,
        clip_bound=DEFAULT_CLIP_BOUND
    )

    # 7. [Filter 6] 2-Pillar(ElasticNet + LightGBM) 중요도 산출 및 Kneedle 변곡점 피처 선별
    X_train_scaled: pd.DataFrame = model_ready_datasets["X_train"]
    X_train_shadow, shadow_names = generate_shadow_features(feature_matrix=X_train_scaled)

    linear_scores = elasticnet_importance(scaled_feature_matrix=X_train_shadow, target_series=y_train)
    tree_scores = lightgbm_importance(feature_matrix=X_train_shadow, target_series=y_train)
    combined_scores = combine_importances(
        linear_importance=linear_scores,
        tree_importance=tree_scores,
        shadow_feature_names=shadow_names
    )

    selected_features, achieved_cumulative_ratio = select_feature(
        feature_scores=combined_scores,
        min_features=min_features,
        max_features=max_features
    )

    # 8. 최종 선별된 피처 목록으로 전체 파티션 슬라이싱 동기화
    for partition_key in ("X_train", "X_val", "X_test", "X_inference"):
        if partition_key in model_ready_datasets and not model_ready_datasets[partition_key].empty:
            model_ready_datasets[partition_key] = model_ready_datasets[partition_key][selected_features]

    # 9. 감사표 생성을 위한 단계별 통계 메타데이터 조립
    audit_meta = {
        "initial_feature_count": initial_feature_count,
        "noise_removed_count": noise_removed_count,
        "dropped_constants": dropped_constants,
        "dropped_missings": dropped_missings,
        "dropped_zeros": dropped_zeros,
        "after_noise_count": initial_feature_count - noise_removed_count,
        "dropped_pearson": dropped_pearson,
        "dropped_hierarchical": dropped_hierarchical,
        "collinear_filtered_count": collinear_filtered_count,
        "dropped_unstable": dropped_unstable,
        "stability_filtered_count": stability_filtered_count,
        "selected_features": selected_features,
        "selected_features_count": len(selected_features),
        "achieved_cumulative_ratio": achieved_cumulative_ratio
    }

    return model_ready_datasets, selected_features, achieved_cumulative_ratio, audit_meta


def select_features_batch(
    split_repository: Dict[str, Dict[str, Union[pd.DataFrame, pd.Series]]],
    max_missing_ratio: float = DEFAULT_MAX_MISSING_RATIO,
    max_zero_ratio: float = DEFAULT_MAX_ZERO_RATIO,
    pearson_threshold: float = DEFAULT_PEARSON_THRESHOLD,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
    min_features: int = DEFAULT_MIN_FEATURES,
    max_features: int = DEFAULT_MAX_FEATURES
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """18종 분할 데이터셋 전체를 순회하며 피처 전처리 및 동적 선별을 일괄 실행합니다.

    Args:
        split_repository: 18종 분할 데이터셋 딕셔너리.
        max_missing_ratio: 결측치 허용 상한 비율.
        max_zero_ratio: 0값 허용 상한 비율.
        pearson_threshold: 피어슨 상관계수 임계치.
        distance_threshold: HFC 거리 임계치.
        min_features: 최소 선별 피처 수.
        max_features: 최대 선별 피처 수.

    Returns:
        Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
            - model_ready_repository: 선별 완료된 18종 데이터셋 리포지토리.
            - batch_summary_records: 정산 대시보드 출력용 요약 레코드 리스트.
            - representative_audit_meta: 첫 번째 대표 데이터셋의 6단계 감사 메타데이터.
    """
    model_ready_repository: Dict[str, Dict[str, Any]] = {}
    batch_summary_records: List[Dict[str, Any]] = []
    representative_audit_meta: Dict[str, Any] = {}

    total_count: int = len(split_repository)
    start_total_time: float = time.time()

    progress_bar = tqdm(
        enumerate(split_repository.items(), start=1),
        total=total_count,
        desc="🔍 [2-Pillar Selection]",
        unit="dataset"
    )

    # 1. 18종 데이터셋을 순회하며 개별 전처리 및 선별 수행
    for index, (bucket_job_id, split_datasets) in progress_bar:
        step_start_time: float = time.time()
        progress_bar.set_postfix_str(f"Processing: {bucket_job_id[:32]}...")

        model_ready_data, selected_cols, cum_ratio, audit = process_single_dataset_selection(
            split_datasets=split_datasets,
            max_missing_ratio=max_missing_ratio,
            max_zero_ratio=max_zero_ratio,
            pearson_threshold=pearson_threshold,
            distance_threshold=distance_threshold,
            min_features=min_features,
            max_features=max_features
        )

        model_ready_repository[bucket_job_id] = model_ready_data
        elapsed: float = time.time() - step_start_time
        progress_bar.set_postfix_str(f"Done: {bucket_job_id[:25]}... ({elapsed:.1f}s, Feats: {len(selected_cols)})")

        # 2. 대시보드 출력을 위한 개별 데이터셋 요약 정보 적재
        batch_summary_records.append({
            "bucket_job_id": bucket_job_id,
            "initial_feature_count": audit["initial_feature_count"],
            "after_noise_count": audit["after_noise_count"],
            "collinear_filtered_count": audit["collinear_filtered_count"],
            "selected_features_count": len(selected_cols),
            "achieved_cumulative_ratio": cum_ratio,
            "elapsed_seconds": elapsed
        })

        # 3. 첫 번째 데이터셋을 대표 감사 대상(Representative Audit)으로 보존
        if index == 1:
            representative_audit_meta = copy.deepcopy(audit)
            representative_audit_meta.update({
                "representative_dataset_id": bucket_job_id,
                "max_missing_ratio": max_missing_ratio,
                "max_zero_ratio": max_zero_ratio,
                "pearson_threshold": pearson_threshold,
                "distance_threshold": distance_threshold,
                "min_features": min_features,
                "max_features": max_features
            })

    total_elapsed: float = time.time() - start_total_time
    print(f" ✅ [Batch Feature Selection Completed] Total Elapsed Time: {total_elapsed:.2f}s")

    return model_ready_repository, batch_summary_records, representative_audit_meta


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _clean_target_series(target_series: pd.Series) -> pd.Series:
    """타깃 시계열의 무한대(Inf) 값을 결측으로 치환하고 전방/후방 대치하여 결측을 보정합니다."""
    return (
        target_series
        .replace([np.inf, -np.inf], np.nan)
        .ffill()
        .bfill()
        .fillna(0.0)
    )


def _apply_rolling_scale_and_bounding(
    datasets: Dict[str, Any],
    target_features: List[str],
    window: int,
    min_periods: int,
    clip_bound: float
) -> None:
    """모든 파티션을 시간순 연결하여 롤링 스케일링을 적용하고 학습 데이터 범위를 초과하지 않도록 클리핑합니다."""
    partition_order: Tuple[str, ...] = ("X_train", "purged_gap", "X_val", "purged_gap_2", "X_test", "X_inference")

    # 1. 존재하는 파티션을 시간 순서로 연결하여 결측 정제
    partitions_to_concat: List[pd.DataFrame] = []
    for key in partition_order:
        if key in datasets and isinstance(datasets[key], pd.DataFrame) and not datasets[key].empty:
            valid_cols = [c for c in target_features if c in datasets[key].columns]
            partitions_to_concat.append(datasets[key][valid_cols])

    if not partitions_to_concat:
        return

    full_matrix: pd.DataFrame = pd.concat(partitions_to_concat, axis=0)
    full_matrix = full_matrix[~full_matrix.index.duplicated(keep="first")].sort_index()
    full_matrix = full_matrix.replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(0.0)

    # 2. 최근 60영업일 기준 롤링 평균/표준편차 스케일링 및 ±3σ 유계화
    scaled_matrix: pd.DataFrame = rolling_scale(
        full_feature_matrix=full_matrix,
        window=window,
        min_periods=min_periods,
        clip_bound=clip_bound
    )

    for key in partition_order:
        if key in datasets and isinstance(datasets[key], pd.DataFrame):
            orig_idx = datasets[key].index
            valid_idx = orig_idx.intersection(scaled_matrix.index)
            datasets[key] = scaled_matrix.loc[valid_idx, target_features].copy()

    # 3. 트리 모델 외삽을 방어하기 위해 X_train의 [최솟값, 최댓값] 범위로 이후 파티션 클리핑
    X_train_ref: pd.DataFrame = datasets["X_train"]
    for key in ("purged_gap", "X_val", "purged_gap_2", "X_test", "X_inference"):
        if key in datasets and isinstance(datasets[key], pd.DataFrame) and not datasets[key].empty:
            for col in target_features:
                if col in datasets[key].columns and col in X_train_ref.columns:
                    datasets[key][col] = np.clip(
                        datasets[key][col],
                        X_train_ref[col].min(),
                        X_train_ref[col].max()
                    )

    # 4. 후속 챔피언 정예화(Step 6 Phase 2)를 위해 스케일링된 전체 후보 풀 영속화
    datasets["_scaled_candidate_pool"] = {
        key: datasets[key].copy()
        for key in ("X_train", "purged_gap", "X_val", "X_test", "X_inference")
        if key in datasets and isinstance(datasets[key], pd.DataFrame)
    }