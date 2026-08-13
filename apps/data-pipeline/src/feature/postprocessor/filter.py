"""
생성된 파생 피처 행렬(X_train)에서 유의미한 신호를 제공하지 못하는 저정보 피처(Low Information Features)를 
통계적으로 탐지하여 선제적으로 제거하는 피처 후행 필터링 유틸리티 모듈입니다.
0.0 수치의 비율이 과도하게 높은 피처와 분산이 0에 가까운 고유값(Constant) 피처를 격리하여
후행 피처 선택 및 모델 학습 단계의 연산 효율성을 높이고 차원의 축복을 유지합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 시계열 분할이 완료된 학습용 피처 데이터프레임(`X_train: pd.DataFrame`).
2. Low-Information Feature Detection:
   - filter_zero_ratio: 피처별 0.0 수치 존재 비율을 산출하여 설정된 임계치(기본 80%) 초과 컬럼 감지.
   - filter_constant_features: 고유값(Unique Values) 개수를 측정하여 1개 이하인 단일값/변동성 부재 컬럼 감지.
3. Feature Drop: 감지된 저정보 피처 컬럼들을 데이터프레임에서 제거.
4. Output: 정제된 피처 데이터프레임(`filtered_X_train`) 및 제거된 피처 컬럼명 리스트(`removed_feature_names`) 반환.

주요 기능:
- [Zero Ratio Filtering] 0.0 수치 비중이 과도한 희소(Sparse) 피처를 식별 및 제거.
- [Constant Feature Filtering] 단일 고유값으로 이루어져 예측 분산(Variance)에 기여하지 못하는 피처 감지 및 축출.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 통계적 무정보 피처 사전 필터링 vs 모델 학습 단계에서 자동 처리 맡김:
  - 장점: 다중공선성 측정 및 가중치 중요도(Lasso/XGBoost) 산출 전 차원을 선제적으로 축소하여 후행 피처 선택 연산 속도를 대폭 개선함.
  - 단점: 0의 비율이 높은 특이 파생 변수가 극단적 레짐 전환 시점에 유효 신호로 작용할 가능성을 완전히 차단함.
  - 근거: 고차원 시계열 피처 환경에서 80% 이상이 0인 피처나 단일값 피처는 노이즈 유입 및 연산 지연의 주원인이므로 사전 필터링이 필연적임.
"""

from typing import List, Tuple
import pandas as pd


def filter_zero_ratio(
    X_train: pd.DataFrame,
    max_zero_ratio: float = 0.8
) -> Tuple[pd.DataFrame, List[str]]:
    """피처 내 0.0 수치의 비율이 max_zero_ratio를 초과하는 저정보 컬럼을 감지하여 제거합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 데이터프레임.
        max_zero_ratio (float): 허용 가능한 최대 0.0 비율 (기본값: 0.8 = 80%).

    Returns:
        Tuple[pd.DataFrame, List[str]]: 정제된 X_train 및 제거된 피처 컬럼 이름 리스트.
    """
    # [설계 의도] 피처별 0.0 수치 개수 및 전체 대비 비율 산출
    zero_counts: pd.Series = (X_train == 0.0).sum(axis=0)
    zero_ratios: pd.Series = zero_counts / len(X_train)

    # [설계 의도] 임계치(80%) 이상인 저정보 피처 컬럼 추출
    removed_feature_names: List[str] = zero_ratios[zero_ratios >= max_zero_ratio].index.tolist()
    filtered_X_train: pd.DataFrame = X_train.drop(columns=removed_feature_names)

    return filtered_X_train, removed_feature_names


def filter_constant_features(
    X_train: pd.DataFrame
) -> Tuple[pd.DataFrame, List[str]]:
    """고유값(Unique value)이 1개 이하인 변동성 없는 저정보 피처를 감지하여 제거합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 데이터프레임.

    Returns:
        Tuple[pd.DataFrame, List[str]]: 정제된 X_train 및 제거된 피처 컬럼 이름 리스트.
    """
    # [설계 의도] 피처별 unique value 개수 측정 (결측치 포함)
    unique_counts: pd.Series = X_train.nunique(dropna=False)
    constant_feature_names: List[str] = unique_counts[unique_counts <= 1].index.tolist()
    filtered_X_train: pd.DataFrame = X_train.drop(columns=constant_feature_names)

    return filtered_X_train, constant_feature_names