from typing import List, Optional, Tuple
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import TimeSeriesSplit

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_SHADOW_COUNT: int = 20                                                  # 통계적 노이즈 바닥선 검증용 섀도우 변수 생성 기본 개수
DEFAULT_RANDOM_SEED: int = 42                                                   # 난수 생성 및 모델 학습 재현성을 보장하기 위한 시드
DEFAULT_CV_SPLITS: int = 5                                                      # 시계열 교차검증(TimeSeriesSplit) 분할 폴드 수
DEFAULT_ELASTICNET_L1_RATIOS: Tuple[float, ...] = (0.1, 0.5, 0.7, 0.9, 0.99)    # ElasticNet L1 정규화 탐색 후보군
DEFAULT_LGBM_MAX_DEPTH: int = 3                                                 # 과적합 방지를 위한 LightGBM 트리 최대 깊이 제약
DEFAULT_LGBM_NUM_LEAVES: int = 7                                                # 얕은 트리의 리프 노드 수 상한선 (2^3 - 1)
DEFAULT_MIN_FEATURES: int = 10                                                  # Kneedle 곡률 변곡점 선별 시 최소 보존 피처 수 하한선
DEFAULT_MAX_FEATURES: int = 100                                                 # 과적합 방지 및 차원 축소를 위한 최대 선별 피처 수 상한선
DEFAULT_TARGET_COVERAGE: float = 0.90                                           # 다단계 변곡점 탐색 시 목표 최소 누적 설명력 (Coverage 90%)
DEFAULT_MAX_TIERS: int = 3                                                      # 무한 루프 발산 방지를 위한 Multi-Tier 변곡점 최대 순회 캡 (내부 전용)
MIN_MARGINAL_IMPORTANCE: float = 1e-4                                           # 재정규화 시 미세 노이즈 왜곡 포착을 차단하기 위한 한계 중요도 바닥선

# ==============================================================================
# Public API Functions
# ==============================================================================

def generate_shadow_features(
    feature_matrix: pd.DataFrame,
    shadow_count: int = DEFAULT_SHADOW_COUNT,
    random_seed: int = DEFAULT_RANDOM_SEED
) -> Tuple[pd.DataFrame, List[str]]:
    """원본 피처 데이터의 행(Row)을 무작위 치환하여 통계적 바닥선 검증용 섀도우 변수를 생성합니다.

    Args:
        feature_matrix: 원본 피처 데이터프레임.
        shadow_count: 생성할 섀도우 변수 개수 (기본값: 20).
        random_seed: 난수 생성 시드 (기본값: 42).

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - augmented_feature_matrix: 섀도우 변수가 결합된 확장 데이터프레임.
            - shadow_feature_names: 생성된 섀도우 변수 컬럼명 리스트.
    """
    # 1. 입력 피처 행렬이 비어있는 경우 원본 복사본 즉시 반환
    if feature_matrix.empty or feature_matrix.shape[1] == 0:
        return feature_matrix.copy(), []

    random_generator: np.random.RandomState = np.random.RandomState(random_seed)
    actual_shadow_count: int = min(shadow_count, feature_matrix.shape[1])

    # 2. 비복원 추출로 섀도우 변수로 복제할 원본 컬럼 선정
    selected_columns = random_generator.choice(
        feature_matrix.columns,
        size=actual_shadow_count,
        replace=False
    )

    # 3. 각 컬럼의 행 데이터를 무작위 순열 치환하여 타깃과의 연관성 파괴
    shadow_features_dict = {}
    shadow_feature_names: List[str] = []

    for index, column_name in enumerate(selected_columns):
        shadow_name: str = f"shadow_feature_{index}"
        shadow_feature_names.append(shadow_name)
        shuffled_values: np.ndarray = random_generator.permutation(feature_matrix[column_name].values)
        shadow_features_dict[shadow_name] = shuffled_values

    # 4. 원본 피처 행렬과 생성된 섀도우 변수 행렬 결합
    shadow_dataframe: pd.DataFrame = pd.DataFrame(
        shadow_features_dict,
        index=feature_matrix.index
    )
    augmented_feature_matrix: pd.DataFrame = pd.concat([feature_matrix, shadow_dataframe], axis=1)

    return augmented_feature_matrix, shadow_feature_names


def elasticnet_importance(
    scaled_feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    l1_ratios: Optional[List[float]] = None,
    cross_validation_splits: int = DEFAULT_CV_SPLITS,
    random_seed: int = DEFAULT_RANDOM_SEED
) -> pd.Series:
    """스케일링된 피처 행렬에 대해 ElasticNetCV를 학습시켜 회귀 계수 절대값을 산출합니다.

    Args:
        scaled_feature_matrix: 스케일링된 피처 데이터프레임 (Shadow 포함).
        target_series: 정답 타깃 시계열.
        l1_ratios: 탐색할 L1 정규화 비율 리스트 (기본값: None 시 DEFAULT_ELASTICNET_L1_RATIOS 사용).
        cross_validation_splits: 시계열 교차검증 분할 수 (기본값: 5).
        random_seed: 난수 생성 시드 (기본값: 42).

    Returns:
        pd.Series: 피처별 ElasticNet 절대 회귀 계수 시리즈.
    """
    # 1. 입력 피처 행렬 공백 검사
    if scaled_feature_matrix.empty or scaled_feature_matrix.shape[1] == 0:
        return pd.Series(dtype=float)

    candidate_l1_ratios: List[float] = (
        list(DEFAULT_ELASTICNET_L1_RATIOS) if l1_ratios is None else l1_ratios
    )

    # 2. 피처와 타깃의 결측치 및 무한대를 정제하고 인덱스 동기화
    clean_features, clean_target = _clean_features_and_target(
        feature_matrix=scaled_feature_matrix,
        target_series=target_series
    )

    # 3. 시간 순서를 보존하는 TimeSeriesSplit 교차검증 기반 ElasticNetCV 모델 적합
    time_series_cv: TimeSeriesSplit = TimeSeriesSplit(n_splits=cross_validation_splits)
    elastic_net_model = ElasticNetCV(
        l1_ratio=candidate_l1_ratios,
        cv=time_series_cv,
        random_state=random_seed,
        max_iter=3000,
        selection="random"
    )
    elastic_net_model.fit(clean_features, clean_target)

    # 4. 피처별 회귀 계수 절대값을 중요도 시리즈로 변환
    absolute_coefficients: np.ndarray = np.abs(elastic_net_model.coef_)
    return pd.Series(absolute_coefficients, index=scaled_feature_matrix.columns)


def lightgbm_importance(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    maximum_depth: int = DEFAULT_LGBM_MAX_DEPTH,
    number_of_leaves: int = DEFAULT_LGBM_NUM_LEAVES,
    colsample_bytree: float = 0.7,
    subsample: float = 0.8,
    random_seed: int = DEFAULT_RANDOM_SEED
) -> pd.Series:
    """과적합이 억제된 Shallow LightGBM을 학습시켜 분할 이득(Gain) 기반 중요도를 산출합니다.

    Args:
        feature_matrix: 피처 데이터프레임 (Shadow 포함).
        target_series: 정답 타깃 시계열.
        maximum_depth: 트리 최대 깊이 (기본값: 3).
        number_of_leaves: 리프 노드 수 상한 (기본값: 7).
        colsample_bytree: 피처 서브샘플링 비율 (기본값: 0.7).
        subsample: 행 서브샘플링 비율 (기본값: 0.8).
        random_seed: 난수 생성 시드 (기본값: 42).

    Returns:
        pd.Series: 피처별 분할 이득(Gain) 중요도 시리즈.
    """
    # 1. 입력 피처 행렬 공백 검사
    if feature_matrix.empty or feature_matrix.shape[1] == 0:
        return pd.Series(dtype=float)

    # 2. 피처와 타깃의 결측치 및 무한대를 정제하고 인덱스 동기화
    clean_features, clean_target = _clean_features_and_target(
        feature_matrix=feature_matrix,
        target_series=target_series
    )

    # 3. 과적합 방지를 위해 얕은 깊이로 설정된 LightGBM 회귀 모델 학습
    lightgbm_model = lgb.LGBMRegressor(
        max_depth=maximum_depth,
        num_leaves=number_of_leaves,
        colsample_bytree=colsample_bytree,
        subsample=subsample,
        random_state=random_seed,
        importance_type="gain",
        n_estimators=100,
        verbose=-1
    )
    lightgbm_model.fit(clean_features, clean_target)

    # 4. 부스터 객체에서 피처 분할 이득(Gain) 중요도 추출
    gain_importances: np.ndarray = lightgbm_model.booster_.feature_importance(importance_type="gain")
    return pd.Series(gain_importances, index=feature_matrix.columns)


def combine_importances(
    linear_importance: pd.Series,
    tree_importance: pd.Series,
    shadow_feature_names: List[str],
    linear_weight: float = 0.5,
    tree_weight: float = 0.5
) -> pd.Series:
    """선형 계수와 트리 중요도를 L1 정규화하여 가중 결합하고 섀도우 노이즈 바닥선 이하를 제거합니다.

    Args:
        linear_importance: ElasticNet 절대 회귀 계수 시리즈.
        tree_importance: LightGBM Gain 중요도 시리즈.
        shadow_feature_names: 주입된 섀도우 변수 컬럼명 리스트.
        linear_weight: 선형 모델 중요도 가중치 (기본값: 0.5).
        tree_weight: 비선형 트리 모델 중요도 가중치 (기본값: 0.5).

    Returns:
        pd.Series: 노이즈가 제거되고 합계가 1.0으로 재정규화된 원본 피처 중요도 점수.
    """
    # 1. 두 모델의 중요도 인덱스를 결합하고 누락 항목을 0.0으로 정렬
    common_indices = linear_importance.index.union(tree_importance.index)
    aligned_linear: pd.Series = linear_importance.reindex(common_indices, fill_value=0.0)
    aligned_tree: pd.Series = tree_importance.reindex(common_indices, fill_value=0.0)

    # 2. 모델별 점수 합계가 1.0이 되도록 L1 정규화 수행
    linear_sum: float = aligned_linear.sum()
    normalized_linear: pd.Series = (aligned_linear / linear_sum) if linear_sum > 0 else aligned_linear

    tree_sum: float = aligned_tree.sum()
    normalized_tree: pd.Series = (aligned_tree / tree_sum) if tree_sum > 0 else aligned_tree

    # 3. 선형 및 비선형 정규화 중요도를 설정된 가중치로 앙상블 합성
    combined_scores: pd.Series = (linear_weight * normalized_linear) + (tree_weight * normalized_tree)

    # 4. 섀도우 변수들의 최대 점수를 통계적 노이즈 바닥선(Noise Floor)으로 산출
    shadow_scores: pd.Series = combined_scores.reindex(shadow_feature_names).dropna()
    noise_floor_threshold: float = shadow_scores.max() if not shadow_scores.empty else 0.0

    # 5. 섀도우 변수를 제외한 원본 피처 중 노이즈 바닥선을 초과하는 진성 피처 필터링
    original_feature_scores: pd.Series = combined_scores.drop(index=shadow_feature_names, errors="ignore")
    filtered_scores: pd.Series = original_feature_scores[original_feature_scores > noise_floor_threshold]

    # 모든 피처가 바닥선 이하인 경우 상위 10개 피처를 방어적으로 보존
    if filtered_scores.empty:
        filtered_scores = original_feature_scores.nlargest(10)

    # 6. 생존 피처의 중요도 점수 합이 1.0이 되도록 재정규화 후 내림차순 정렬
    survived_sum: float = filtered_scores.sum()
    final_scores: pd.Series = (filtered_scores / survived_sum) if survived_sum > 0 else filtered_scores

    return final_scores.sort_values(ascending=False)


def select_feature(
    feature_scores: pd.Series,
    min_features: int = DEFAULT_MIN_FEATURES,
    max_features: int = DEFAULT_MAX_FEATURES,
    target_coverage: float = DEFAULT_TARGET_COVERAGE
) -> Tuple[List[str], float]:
    """정규화된 중요도 점수를 바탕으로 다단계 Kneedle 엘보우 변곡점을 탐색하여 핵심 피처를 선별합니다.

    Args:
        feature_scores: 노이즈가 제거된 피처별 중요도 점수 (내림차순 정렬).
        min_features: 최소 선별 피처 수 하한선 (기본값: 10).
        max_features: 최대 선별 피처 수 상한선 (기본값: 100).
        target_coverage: 목표 누적 설명력 비율 (기본값: 0.90).

    Returns:
        Tuple[List[str], float]:
            - selected_feature_names: 변곡점 기반으로 최종 선별된 피처명 리스트.
            - achieved_cumulative_ratio: 선별된 피처셋이 달성한 누적 중요도 비율.
    """
    # 1. 입력 스코어가 비어있는 경우 빈 결과 반환
    if feature_scores.empty:
        return [], 0.0

    sorted_scores: pd.Series = feature_scores.sort_values(ascending=False)
    total_score: float = float(sorted_scores.sum())

    # 2. 총 점수가 0 이하이거나 피처 수가 최소 기준 이하인 경우 하한선 기준으로 슬라이싱
    if total_score <= 0.0 or len(sorted_scores) <= min_features:
        bounded_count: int = min(len(sorted_scores), min_features)
        selected_features = sorted_scores.head(bounded_count).index.tolist()
        achieved_ratio = float(sorted_scores.head(bounded_count).sum() / total_score) if total_score > 0.0 else 0.0
        return selected_features, achieved_ratio

    # 3. [설계 의도] Multi-Tier Kneedle 재귀 루프를 통해 목표 커버리지(90%)를 만족하는 다단계 변곡점 인덱스 산출
    elbow_index: int = _calculate_iterative_kneedle(
        sorted_scores=sorted_scores,
        total_score=total_score,
        target_coverage=target_coverage
    )

    # 4. 산출된 변곡점에 최소/최대 피처 수 가드레일 적용 후 최종 피처 추출
    bounded_count = int(np.clip(elbow_index, min_features, max_features))
    selected_features = sorted_scores.head(bounded_count).index.tolist()
    achieved_ratio = float((sorted_scores.head(bounded_count) / total_score).sum())

    return selected_features, achieved_ratio


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _clean_features_and_target(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series
) -> Tuple[pd.DataFrame, pd.Series]:
    """피처와 타깃의 인덱스를 일치시키고 결측치 및 무한대를 0.0으로 정제합니다."""
    clean_features: pd.DataFrame = (
        feature_matrix
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    clean_target: pd.Series = (
        target_series.reindex(feature_matrix.index)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    return clean_features, clean_target


def _calculate_iterative_kneedle(
    sorted_scores: pd.Series,
    total_score: float,
    target_coverage: float = DEFAULT_TARGET_COVERAGE
) -> int:
    """잔여 피처 풀을 재정규화하며 목표 누적 설명력(Coverage)에 도달할 때까지 변곡점을 반복 탐색합니다."""
    total_features: int = len(sorted_scores)
    selected_count: int = 0

    # [설계 의도] Satopaa et al.(2011) 단일 변곡점의 조기 절단을 극복하기 위해 최대 DEFAULT_MAX_TIERS회 잔차 공간 재귀 탐색
    for tier in range(1, DEFAULT_MAX_TIERS + 1):
        remaining_scores: pd.Series = sorted_scores.iloc[selected_count:]
        if remaining_scores.empty or len(remaining_scores) <= 2:
            selected_count = total_features
            break

        # [설계 의도] 머신러닝 바닥선 수준의 미세 노이즈 피처가 Min-Max 재정규화로 왜곡 포착되는 현상 방어
        if remaining_scores.iloc[0] < MIN_MARGINAL_IMPORTANCE:
            break

        remaining_sum: float = float(remaining_scores.sum())
        if remaining_sum <= 0.0:
            break

        # 잔여 구간 내 상대적 기여도 L1 재정규화 및 누적 곡선 생성
        rem_cumulative: np.ndarray = (remaining_scores / remaining_sum).cumsum().values
        tier_elbow: int = _calculate_kneedle_elbow(cumulative_ratios=rem_cumulative)
        tier_elbow = max(1, tier_elbow)

        selected_count += tier_elbow

        # [설계 의도] 원본 기준 누적 설명력이 목표치(90%)를 달성한 경우 즉시 조기 종료
        current_coverage: float = float(sorted_scores.iloc[:selected_count].sum() / total_score)
        if current_coverage >= target_coverage or selected_count >= total_features:
            break

    return min(selected_count, total_features)


def _calculate_kneedle_elbow(cumulative_ratios: np.ndarray) -> int:
    """누적 설명력 곡선에서 시작점과 종단점을 잇는 기준선 대비 수직 거리가 최대가 되는 변곡점을 산출합니다."""
    # [설계 의도] 2개 이하 극소 표본 시 기준선 분모 제로 나눗셈(Zero Division) 크래시 방어
    if len(cumulative_ratios) <= 2:
        return len(cumulative_ratios)

    feature_counts: np.ndarray = np.arange(1, len(cumulative_ratios) + 1)

    # 시작점과 끝점을 잇는 대각 기준선(Chord Line) 계산
    chord_line: np.ndarray = cumulative_ratios[0] + (cumulative_ratios[-1] - cumulative_ratios[0]) * (
        (feature_counts - feature_counts[0]) / (feature_counts[-1] - feature_counts[0])
    )

    # 기준선 대비 수직 거리(곡률)가 최대인 지점의 피처 개수 반환
    return int(feature_counts[np.argmax(cumulative_ratios - chord_line)])