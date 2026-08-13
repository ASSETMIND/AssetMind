"""
고차원 금융 시계열 데이터셋에서 피처 간 선형 다중공선성(Multicollinearity)을 제거하고,
선형(ElasticNet/Lasso) 및 비선형(XGBoost, Random Forest) 모델의 피처 중요도를 복합 가중 스코어링하여
예측력과 일반화 성능이 뛰어난 핵심 피처 세트를 선별하는 후행 피처 선택 유틸리티 모듈입니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 시계열 분할 및 저정보 필터링이 완료된 학습 피처 데이터프레임(`X_train: pd.DataFrame`) 및 타겟 라벨(`y_train: pd.Series`).
2. Pearson Multicollinearity Filtering: 피처 간 피어슨 상관계수 행렬을 계산하여 상관계수 임계치(기본 0.85) 이상인 중복 변수 제거.
3. Multi-Model Importance Rank Selection: ElasticNetCV, XGBoost, Random Forest 모델을 독립 학습시켜 개별 피처 중요도/계수 산출 후 랭크 정규화 및 가중 합산(0.5 : 0.25 : 0.25).
4. Output: 1차 다중공선성이 정제된 데이터프레임(`pd.DataFrame`) 및 제거된 중복 피처 리스트, 또는 내림차순 정렬된 피처 순위 스코어 시리즈(`pd.Series`) 반환.

주요 기능:
- [Pearson Multicollinearity Reduction] 상관계수 상삼각 마스킹을 활용하여 정보 중복 피처 선제적 감지 및 축출.
- [Multi-Model Ensemble Rank Selection] 선형/비선형 알고리즘의 중요도를 스케일 독립적 랭크 공간으로 변환 및 가중 합산하여 다각적 피처 중요도 수치화.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 피어슨 다중공선성 선제 제거 + 앙상블 랭크 스코어링 vs 단순 단일 모델 중요도 추출:
  - 장점: 특정 모델 알고리즘 편향을 방지하고, 피처 간 심각한 다공선성에 의한 회귀 계수 불안정성을 사전에 통제함.
  - 단점: 3개 모델(ElasticNet, XGBoost, RF)을 순차 학습해야 하므로 피처 선택 단계의 연산 시간이 다소 증가함.
  - 근거: 고차원 이종 자산 시계열 학습 시 피처 안정성 수호와 오버피팅 차단이 학습 속도보다 우위에 있으므로 복합 랭크 스코어링을 채택함.
"""

from typing import List, Tuple
import numpy as np
import pandas as pd


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

    # [설계 의도] 상삼각 행렬(Upper Triangle) 마스킹으로 자기 자신 및 중복 쌍 제거
    upper_triangle_mask: np.ndarray = np.triu(np.ones(correlation_matrix.shape), k=1).astype(bool)
    upper_correlation_matrix: pd.DataFrame = correlation_matrix.where(upper_triangle_mask)

    # [설계 의도] 임계값 이상인 상관관계를 가진 피처 컬럼 식별 및 축출
    removed_feature_names: List[str] = [
        column for column in upper_correlation_matrix.columns
        if any(upper_correlation_matrix[column] >= threshold)
    ]

    filtered_X_train: pd.DataFrame = X_train.drop(columns=removed_feature_names)

    return filtered_X_train, removed_feature_names


def rank_selection(
    elasticnet_scores: pd.Series,
    xgboost_scores: pd.Series,
    random_forest_scores: pd.Series,
    weights: Tuple[float, float, float] = (0.5, 0.25, 0.25)
) -> pd.Series:
    """선형(ElasticNet) 및 비선형(XGBoost, RF) 중요도를 랭크 공간으로 변환 후 가중 합산 스코어를 산출합니다.

    Args:
        elasticnet_scores (pd.Series): ElasticNetCV 모델의 피처 절대 계수 스코어.
        xgboost_scores (pd.Series): XGBoost 모델의 피처 중요도 스코어.
        random_forest_scores (pd.Series): Random Forest 모델의 피처 중요도 스코어.
        weights (Tuple[float, float, float]): [ElasticNet, XGBoost, RandomForest] 가중치 비율 (기본값: (0.5, 0.25, 0.25)).

    Returns:
        pd.Series: 내림차순 정렬된 최종 결합 순위 스코어.
    """
    scores_dataframe: pd.DataFrame = pd.DataFrame({
        "elasticnet": elasticnet_scores,
        "xgboost": xgboost_scores,
        "random_forest": random_forest_scores
    }).fillna(0.0)

    number_of_features: int = len(scores_dataframe)
    if number_of_features == 0:
        return pd.Series(dtype=float)

    # [설계 의도] 점수를 내림차순 순위(1위=1.0, N위=1/N) 공간으로 변환하여 스케일 독립성 보장
    rank_elasticnet: pd.Series = 1.0 - (scores_dataframe["elasticnet"].rank(ascending=False, method="min") - 1.0) / number_of_features
    rank_xgboost: pd.Series = 1.0 - (scores_dataframe["xgboost"].rank(ascending=False, method="min") - 1.0) / number_of_features
    rank_random_forest: pd.Series = 1.0 - (scores_dataframe["random_forest"].rank(ascending=False, method="min") - 1.0) / number_of_features

    # [설계 의도] 지정된 가중치(0.5 : 0.25 : 0.25) 기반 수리적 대칭 가중 합산
    combined_rank_series: pd.Series = (
        weights[0] * rank_elasticnet +
        weights[1] * rank_xgboost +
        weights[2] * rank_random_forest
    )

    return combined_rank_series.sort_values(ascending=False)