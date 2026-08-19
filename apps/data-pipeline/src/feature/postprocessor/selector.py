from typing import List, Optional, Tuple
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import TimeSeriesSplit


def generate_shadow_features(
    feature_matrix: pd.DataFrame,
    shadow_count: int = 3,
    random_seed: int = 42
) -> Tuple[pd.DataFrame, List[str]]:
    """원본 피처 데이터프레임의 행(Row)을 무작위 치환하여 통계적 바닥선 검증용 섀도우 변수를 생성합니다.

    Args:
        feature_matrix (pd.DataFrame): 원본 피처 데이터프레임.
        shadow_count (int): 생성할 섀도우(그림자) 변수의 개수 (기본값: 3).
        random_seed (int): 재현성을 위한 난수 생성 시드 (기본값: 42).

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - augmented_feature_matrix: 섀도우 변수가 결합된 확장 데이터프레임.
            - shadow_feature_names: 생성된 섀도우 변수 컬럼명 리스트.
    """
    if feature_matrix.empty:
        return feature_matrix.copy(), []

    random_generator: np.random.RandomState = np.random.RandomState(random_seed)
    available_column_count: int = feature_matrix.shape[1]
    actual_shadow_count: int = min(shadow_count, available_column_count)

    # 무작위 컬럼 선택 및 행 데이터 셔플링
    selected_columns = random_generator.choice(
        feature_matrix.columns, 
        size=actual_shadow_count, 
        replace=False
    )
    
    shadow_features_dictionary = {}
    shadow_feature_names: List[str] = []

    for index, column_name in enumerate(selected_columns):
        shadow_name: str = f"shadow_feature_{index}"
        shadow_feature_names.append(shadow_name)
        # 시계열 종속성 파괴를 위한 행 단위 독립 셔플링
        shuffled_values: np.ndarray = random_generator.permutation(feature_matrix[column_name].values)
        shadow_features_dictionary[shadow_name] = shuffled_values

    shadow_dataframe: pd.DataFrame = pd.DataFrame(
        shadow_features_dictionary, 
        index=feature_matrix.index
    )
    augmented_feature_matrix: pd.DataFrame = pd.concat([feature_matrix, shadow_dataframe], axis=1)

    return augmented_feature_matrix, shadow_feature_names


def elasticnet_importance(
    scaled_feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    l1_ratios: Optional[List[float]] = None,
    cross_validation_splits: int = 5,
    random_seed: int = 42
) -> pd.Series:
    """정규화된 피처 행렬에 대해 ElasticNetCV를 학습시켜 선형 회귀 계수 절대값을 산출합니다.

    Args:
        scaled_feature_matrix (pd.DataFrame): 스케일링된 피처 데이터프레임 (Shadow 포함).
        target_series (pd.Series): 정답 타깃 시계열.
        l1_ratios (Optional[List[float]]): 탐색할 L1 비율 리스트 (기본값: [0.1, 0.5, 0.7, 0.9, 0.99]).
        cross_validation_splits (int): 시계열 교차검증 분할 수 (기본값: 5).
        random_seed (int): 난수 생성 시드 (기본값: 42).

    Returns:
        pd.Series: 피처별 ElasticNet 절대 회귀 계수 시리즈.
    """
    if scaled_feature_matrix.empty:
        return pd.Series(dtype=float)

    if l1_ratios is None:
        l1_ratios = [0.1, 0.5, 0.7, 0.9, 0.99]

    # 시계열 특성을 보존하기 위한 TimeSeriesSplit 적용
    time_series_cross_validator: TimeSeriesSplit = TimeSeriesSplit(n_splits=cross_validation_splits)

    elastic_net_model: ElasticNetCV = ElasticNetCV(
        l1_ratio=l1_ratios,
        cv=time_series_cross_validator,
        random_state=random_seed,
        max_iter=3000,
        selection="random"
    )

    # 결측치 방어 및 인덱스 정렬
    aligned_features: pd.DataFrame = scaled_feature_matrix.fillna(0.0)
    aligned_target: pd.Series = target_series.loc[scaled_feature_matrix.index].fillna(0.0)

    elastic_net_model.fit(aligned_features, aligned_target)

    absolute_coefficients: np.ndarray = np.abs(elastic_net_model.coef_)
    return pd.Series(absolute_coefficients, index=scaled_feature_matrix.columns)


def lightgbm_importance(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    maximum_depth: int = 3,
    number_of_leaves: int = 7,
    colsample_bytree: float = 0.7,
    subsample: float = 0.8,
    random_seed: int = 42
) -> pd.Series:
    """과적합이 억제된 Shallow LightGBM을 학습시켜 총 손실 개선도(Gain) 기반 중요도를 산출합니다.

    Args:
        feature_matrix (pd.DataFrame): 피처 데이터프레임 (Shadow 포함).
        target_series (pd.Series): 정답 타깃 시계열.
        maximum_depth (int): 트리 최대 깊이 제약 (기본값: 3).
        number_of_leaves (int): 리프 노드 수 상한 (기본값: 7).
        colsample_bytree (float): 피처 서브샘플링 비율 (기본값: 0.7).
        subsample (float): 행 서브샘플링 비율 (기본값: 0.8).
        random_seed (int): 난수 생성 시드 (기본값: 42).

    Returns:
        pd.Series: 피처별 총 분할 이득(Gain) 중요도 시리즈.
    """
    if feature_matrix.empty:
        return pd.Series(dtype=float)

    lightgbm_model: lgb.LGBMRegressor = lgb.LGBMRegressor(
        max_depth=maximum_depth,
        num_leaves=number_of_leaves,
        colsample_bytree=colsample_bytree,
        subsample=subsample,
        random_state=random_seed,
        importance_type="gain",
        n_estimators=100,
        verbose=-1
    )

    aligned_target: pd.Series = target_series.loc[feature_matrix.index]
    lightgbm_model.fit(feature_matrix, aligned_target)

    gain_importances: np.ndarray = lightgbm_model.booster_.feature_importance(importance_type="gain")
    return pd.Series(gain_importances, index=feature_matrix.columns)


def combine_importances(
    linear_importance: pd.Series,
    tree_importance: pd.Series,
    shadow_feature_names: List[str],
    linear_weight: float = 0.5,
    tree_weight: float = 0.5
) -> pd.Series:
    """선형 및 비선형 중요도를 L1 정규화하여 합성하고, 섀도우 노이즈 바닥선 이하의 피처를 제거합니다.

    Args:
        linear_importance (pd.Series): ElasticNet 절대 계수 시리즈.
        tree_importance (pd.Series): LightGBM Gain 중요도 시리즈.
        shadow_feature_names (List[str]): 주입된 섀도우 변수명 리스트.
        linear_weight (float): 선형 모델 가중치 (기본값: 0.5).
        tree_weight (float): 비선형 모델 가중치 (기본값: 0.5).

    Returns:
        pd.Series: 노이즈가 제거되고 합계가 1.0으로 재정규화된 원본 피처별 중요도 점수 (내림차순).
    """
    # 1. 인덱스 결합 및 정렬
    common_indices = linear_importance.index.union(tree_importance.index)
    aligned_linear: pd.Series = linear_importance.reindex(common_indices, fill_value=0.0)
    aligned_tree: pd.Series = tree_importance.reindex(common_indices, fill_value=0.0)

    # 2. 모델별 L1 비중 정규화 (합계 = 1.0)
    linear_sum: float = aligned_linear.sum()
    normalized_linear: pd.Series = (aligned_linear / linear_sum) if linear_sum > 0 else aligned_linear

    tree_sum: float = aligned_tree.sum()
    normalized_tree: pd.Series = (aligned_tree / tree_sum) if tree_sum > 0 else aligned_tree

    # 3. 앙상블 가중 결합
    combined_scores: pd.Series = (linear_weight * normalized_linear) + (tree_weight * normalized_tree)

    # 4. 통계적 노이즈 바닥선(Noise Floor) 산출
    shadow_scores: pd.Series = combined_scores.reindex(shadow_feature_names).dropna()
    noise_floor_threshold: float = shadow_scores.max() if not shadow_scores.empty else 0.0

    # 5. 섀도우 피처 분리 및 노이즈 초과 피처 선별
    original_feature_scores: pd.Series = combined_scores.drop(index=shadow_feature_names, errors="ignore")
    filtered_feature_scores: pd.Series = original_feature_scores[original_feature_scores > noise_floor_threshold]

    # [예외 처리] 모든 피처가 노이즈 바닥선 이하일 경우 상위 10개 강제 보존 (Fallback)
    if filtered_feature_scores.empty:
        filtered_feature_scores = original_feature_scores.nlargest(10)

    # 6. 생존 피처 합계를 1.0으로 재정규화
    survived_sum: float = filtered_feature_scores.sum()
    if survived_sum > 0:
        final_feature_scores: pd.Series = filtered_feature_scores / survived_sum
    else:
        final_feature_scores = filtered_feature_scores

    return final_feature_scores.sort_values(ascending=False)


def select_feature(
    feature_scores: pd.Series,
    cumulative_threshold: float = 0.95,
    min_features: int = 10,
    max_features: int = 50
) -> Tuple[List[str], float]:
    """재정규화된 중요도를 누적하여 목표 설명력에 도달할 때까지 핵심 피처를 동적으로 선별하고 달성 비율을 반환합니다.

    Args:
        feature_scores (pd.Series): 노이즈가 필터링된 피처별 중요도 점수 (내림차순 정렬).
        cumulative_threshold (float): 목표 누적 설명력 비율 (기본값: 0.95).
        min_features (int): 최소 확보 피처 수 하한선 (기본값: 10).
        max_features (int): 과적합 방지 피처 수 상한선 (기본값: 50).

    Returns:
        Tuple[List[str], float]:
            - selected_feature_names: 유계 동적 선별을 통과한 최종 핵심 피처명 리스트.
            - achieved_cumulative_ratio: 선별된 피처셋이 달성한 실제 누적 설명력 비율 (0.0 ~ 1.0).
    """
    if feature_scores.empty:
        return [], 0.0

    sorted_scores: pd.Series = feature_scores.sort_values(ascending=False)
    total_score: float = sorted_scores.sum()

    # 스코어 합이 0이거나 전체 피처 수가 최소 기준 이하인 경우 하한선 기준으로 슬라이싱
    if total_score <= 0 or len(sorted_scores) <= min_features:
        bounded_count: int = min(len(sorted_scores), min_features)
        selected_features = sorted_scores.head(bounded_count).index.tolist()
        achieved_ratio = float(sorted_scores.head(bounded_count).sum() / total_score) if total_score > 0 else 0.0
        return selected_features, achieved_ratio

    # [설계 의도] 누적합(Cumsum) 계산을 통한 동적 컷오프 지점 탐색
    cumulative_importance_ratio: pd.Series = (sorted_scores / total_score).cumsum()
    target_indices: np.ndarray = np.where(cumulative_importance_ratio >= cumulative_threshold)[0]

    if len(target_indices) > 0:
        dynamic_cutoff_count: int = int(target_indices[0] + 1)
    else:
        dynamic_cutoff_count = len(sorted_scores)

    # 상·하한 가드레일 적용 (Fan & Lv 2008 차원 축소 이론 반영)
    bounded_feature_count: int = int(np.clip(dynamic_cutoff_count, min_features, max_features))
    selected_feature_names: List[str] = sorted_scores.head(bounded_feature_count).index.tolist()
    achieved_cumulative_ratio: float = float((sorted_scores.head(bounded_feature_count) / total_score).sum())

    return selected_feature_names, achieved_cumulative_ratio
