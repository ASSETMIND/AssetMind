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

    # 임계치(80%) 이상인 저정보 피처 컬럼 추출
    removed_feature_names: List[str] = zero_ratios[zero_ratios >= max_zero_ratio].index.tolist()
    filtered_X_train: pd.DataFrame = X_train.drop(columns=removed_feature_names)

    return filtered_X_train, removed_feature_names

def filter_constant_features(
    X_train: pd.DataFrame
) -> Tuple[pd.DataFrame, List[str]]:
    """고유값(nunique)이 1개 이하인 변동성 0의 상수(Constant / Zero-Variance) 컬럼을 감지하여 제거합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 데이터프레임.

    Returns:
        Tuple[pd.DataFrame, List[str]]: 정제된 X_train 및 제거된 상수 피처 컬럼 이름 리스트.
    """
    removed_feature_names: List[str] = [
        column for column in X_train.columns if X_train[column].nunique() <= 1
    ]
    filtered_X_train: pd.DataFrame = X_train.drop(columns=removed_feature_names)

    return filtered_X_train, removed_feature_names

def filter_missing_ratio(
    X_train: pd.DataFrame,
    max_missing_ratio: float = 0.2
) -> Tuple[pd.DataFrame, List[str]]:
    """피처 내 결측치(NaN)의 비율이 max_missing_ratio를 초과하는 고결측 오염 컬럼을 감지하여 제거합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 데이터프레임.
        max_missing_ratio (float): 허용 가능한 최대 결측치 비율 (기본값: 0.2 = 20%).

    Returns:
        Tuple[pd.DataFrame, List[str]]: 정제된 X_train 및 제거된 피처 컬럼 이름 리스트.
    """
    # [설계 의도] 피처별 NaN 결측치 비율 산출 (Dong & Peng 2013, Gu et al. 2020 학술 기준 적용)
    missing_ratios: pd.Series = X_train.isna().mean()

    # 임계치(20%) 초과 고결측 피처 컬럼 추출 및 제거
    removed_feature_names: List[str] = missing_ratios[missing_ratios > max_missing_ratio].index.tolist()
    filtered_X_train: pd.DataFrame = X_train.drop(columns=removed_feature_names)

    return filtered_X_train, removed_feature_names