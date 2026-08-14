"""
Feature Selection Technical Utility Module

[모듈 목적 및 상세 설명]
$P >> N$ 고차원 금융 시계열 데이터셋에서 다공선성을 제거하고,
LassoCV(선형) 및 XGBoost(비선형) 중요도를 조합하여 핵심 피처를 선별하는 원자적 함수 모듈입니다.
"""

from typing import List, Tuple, Dict, Any
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNetCV
from xgboost import XGBRegressor


def pearson_multicollinearity(
    X_train: pd.DataFrame,
    threshold: float = 0.85
) -> Tuple[pd.DataFrame, List[str]]:
    """피어슨 상관계수 기반으로 피처 간 다공선성(|r| >= threshold)을 감지하여 중복 변수를 제거합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 데이터프레임.
        threshold (float): 다공선성 판단 임계값 (기본값: 0.85).

    Returns:
        Tuple[pd.DataFrame, List[str]]: 1차 정제된 X_train 및 제거된 중복 피처 이름 리스트.
    """
    # [설계 의도] 피처 간 절대 상관계수 행렬 산출
    correlation_matrix: pd.DataFrame = X_train.corr(method="pearson").abs()

    # 상삼각 행렬(Upper Triangle) 마스킹으로 자기 자신 및 중복 쌍 제거
    upper_triangle_mask: np.ndarray = np.triu(np.ones(correlation_matrix.shape), k=1).astype(bool)
    upper_correlation_matrix: pd.DataFrame = correlation_matrix.where(upper_triangle_mask)

    # 임계치 이상인 중복 피처 식별
    removed_feature_names: List[str] = [
        column for column in upper_correlation_matrix.columns
        if any(upper_correlation_matrix[column] >= threshold)
    ]

    filtered_X_train: pd.DataFrame = X_train.drop(columns=removed_feature_names)
    return filtered_X_train, removed_feature_names


def elasticnet_importance(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    l1_ratio: float = 0.5,
    cv_folds: int = 3
) -> pd.Series:
    """ElasticNetCV를 통한 교차검증 최적 alpha 자동 탐색 후 회귀계수 절대값 기반 선형/그룹핑 스코어를 산출합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 matrix.
        y_train (pd.Series): 정답 타겟 series.
        l1_ratio (float): L1/L2 정규화 혼합 비율 (기본값: 0.5).
        cv_folds (int): 교차검증 Fold 수 (기본값: 3).

    Returns:
        pd.Series: 0~1 사이로 Min-Max 정규화된 ElasticNet 피처 스코어.
    """
    # [설계 의도] Scikit-Learn 유한성(Finite) 검증 통과 및 계수 왜곡 방지를 위해 시계열 전진 대치 후 중앙값 보간
    imputed_X_train = X_train.ffill().fillna(X_train.median())

    elasticnet_cv_model = ElasticNetCV(
        l1_ratio=l1_ratio,
        cv=cv_folds,
        random_state=42,
        max_iter=2000,
        n_jobs=-1
    )
    elasticnet_cv_model.fit(imputed_X_train, y_train)

    absolute_coefficients: np.ndarray = np.abs(elasticnet_cv_model.coef_)
    max_val: float = float(absolute_coefficients.max())

    normalized_scores: np.ndarray = (
        absolute_coefficients / max_val if max_val > 0 else absolute_coefficients
    )

    return pd.Series(normalized_scores, index=X_train.columns, name="elasticnet_score")


def xgboost_importance(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_estimators: int = 100,
    max_depth: int = 5,
    learning_rate: float = 0.05
) -> pd.Series:
    """XGBoost 트리 기반 MDI Feature Importance를 산출하여 Boosting 관점의 비선형 스코어를 반환합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 matrix.
        y_train (pd.Series): 정답 타겟 series.
        n_estimators (int): 트리 개수 (기본값: 100).
        max_depth (int): 트리 최대 깊이 (기본값: 5).
        learning_rate (float): 학습률 (기본값: 0.05).

    Returns:
        pd.Series: 0~1 사이로 Min-Max 정규화된 XGBoost 피처 스코어.
    """
    xgboost_model = XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        random_state=42,
        n_jobs=1
    )
    xgboost_model.fit(X_train, y_train)

    raw_importances: np.ndarray = xgboost_model.feature_importances_
    max_val: float = float(raw_importances.max())

    normalized_scores: np.ndarray = (
        raw_importances / max_val if max_val > 0 else raw_importances
    )

    return pd.Series(normalized_scores, index=X_train.columns, name="xgboost_score")


def random_forest_importance(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_estimators: int = 100,
    max_depth: int = 5
) -> pd.Series:
    """RandomForest 트리 기반 MDI Feature Importance를 산출하여 Bagging 관점의 비선형 스코어를 반환합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 matrix.
        y_train (pd.Series): 정답 타겟 series.
        n_estimators (int): 트리 개수 (기본값: 100).
        max_depth (int): 트리 최대 깊이 (기본값: 5).

    Returns:
        pd.Series: 0~1 사이로 Min-Max 정규화된 RandomForest 피처 스코어.
    """
    # [설계 의도] RandomForestRegressor의 NaN 입력 불가 제약을 해결하기 위해 중앙값 기반 보간 적용
    imputed_X_train = X_train.ffill().fillna(X_train.median())

    random_forest_model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42,
        n_jobs=-1
    )
    random_forest_model.fit(imputed_X_train, y_train)

    raw_importances: np.ndarray = random_forest_model.feature_importances_
    max_val: float = float(raw_importances.max())

    normalized_scores: np.ndarray = (
        raw_importances / max_val if max_val > 0 else raw_importances
    )

    return pd.Series(normalized_scores, index=X_train.columns, name="random_forest_score")


def combine_feature_ranks(
    elasticnet_scores: pd.Series,
    xgboost_scores: pd.Series,
    random_forest_scores: pd.Series,
    weights: Tuple[float, float, float] = (0.5, 0.25, 0.25)
) -> pd.Series:
    """Weighted Borda Count 기반으로 3개 이종 모델의 피처 순위 점수를 가중 합산합니다.

    스케일 및 희소성(Sparsity) 차이로 인한 점수 쏠림을 원천 차단하기 위해 점수를 순위 공간으로 변환한 뒤
    선형 축 50%(ElasticNet) : 트리 축 50%(XGBoost 25% + RandomForest 25%) 비율로 최종 순위 스코어를 산출합니다.

    Args:
        elasticnet_scores (pd.Series): ElasticNetCV 피처 스코어.
        xgboost_scores (pd.Series): XGBoost 피처 스코어.
        random_forest_scores (pd.Series): RandomForest 피처 스코어.
        weights (Tuple[float, float, float]): [ElasticNet, XGBoost, RandomForest] 가중치 비율 (기본값: (0.5, 0.25, 0.25)).

    Returns:
        pd.Series: 내림차순 정렬된 최종 결합 순위 스코어.
    """
    scores_dataframe = pd.DataFrame({
        "elasticnet": elasticnet_scores,
        "xgboost": xgboost_scores,
        "random_forest": random_forest_scores
    }).fillna(0.0)

    number_of_features = len(scores_dataframe)
    if number_of_features == 0:
        return pd.Series(dtype=float)

    # [설계 의도] 점수를 내림차순 순위(1위=1.0, N위=1/N) 공간으로 변환하여 스케일 독립성 보장
    rank_elasticnet = 1.0 - (scores_dataframe["elasticnet"].rank(ascending=False, method="min") - 1.0) / number_of_features
    rank_xgboost = 1.0 - (scores_dataframe["xgboost"].rank(ascending=False, method="min") - 1.0) / number_of_features
    rank_random_forest = 1.0 - (scores_dataframe["random_forest"].rank(ascending=False, method="min") - 1.0) / number_of_features

    # [설계 의도] 2:1:1 (0.5 : 0.25 : 0.25) 수리적 대칭 가중 합산
    combined_rank_series: pd.Series = (
        weights[0] * rank_elasticnet +
        weights[1] * rank_xgboost +
        weights[2] * rank_random_forest
    )

    return combined_rank_series.sort_values(ascending=False)


def select_important_features(
    feature_scores: pd.Series,
    cumulative_threshold: float = 0.80,
    min_features: int = 20,
    max_features: int = 50
) -> List[str]:
    """누적 중요도 비율에 도달할 때까지 핵심 피처를 동적으로 선별하되, 상·하한 가드레일로 차원을 제한합니다.

    Args:
        feature_scores (pd.Series): 피처별 앙상블 중요도 스코어 (내림차순 정렬).
        cumulative_threshold (float): 목표 누적 중요도 설명력 비율 (기본값: 0.80 = 80%).
        min_features (int): 최소 확보 피처 수 하한선 (기본값: 20).
        max_features (int): 과적합 방지 피처 수 상한선 (기본값: 50, Fan & Lv 2008 기준).

    Returns:
        List[str]: 유계 동적 선별을 통과한 핵심 피처 컬럼명 리스트.
    """
    sorted_scores = feature_scores.sort_values(ascending=False)
    total_score = sorted_scores.sum()

    # 스코어 합이 0이거나 데이터가 부족할 경우 최소 개수 기준으로 단순 슬라이싱
    if total_score <= 0 or len(sorted_scores) <= min_features:
        return sorted_scores.head(min_features).index.tolist()

    # [설계 의도] 상대 중요도 정규화 및 누적합(Cumsum) 계산
    cumulative_importance_ratio = (sorted_scores / total_score).cumsum()

    # [설계 의도] 누적 중요도 80% 달성 시점의 동적 피처 개수 산출
    threshold_mask = cumulative_importance_ratio >= cumulative_threshold
    if threshold_mask.any():
        dynamic_feature_count = int(threshold_mask.values.argmax() + 1)
    else:
        dynamic_feature_count = len(sorted_scores)

    # [설계 의도] 학술 가드레일(Fan & Lv 2008) 적용: 20 <= K <= 50 클리핑
    bounded_feature_count = max(min_features, min(dynamic_feature_count, max_features))
    bounded_feature_count = min(bounded_feature_count, len(sorted_scores))

    return sorted_scores.head(bounded_feature_count).index.tolist()