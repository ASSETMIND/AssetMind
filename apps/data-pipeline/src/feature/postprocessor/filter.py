from typing import List, Set, Tuple
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform


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

def pearson_collinearity(
    feature_matrix: pd.DataFrame,
    threshold: float = 0.85
) -> Tuple[pd.DataFrame, List[str]]:
    """피어슨 상관계수 기반으로 1:1 선형 다공선성(|r| >= threshold)을 감지하여 중복 피처를 제거합니다.

    Args:
        feature_matrix (pd.DataFrame): 전처리 대상 원본 피처 데이터프레임.
        threshold (float): 다공선성 판정 상관계수 절대값 임계치 (기본값: 0.85).

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - filtered_feature_matrix: 상관계수 기준 초과 변수가 제거된 데이터프레임.
            - dropped_feature_names: 중복 판정으로 제거된 피처명 리스트.
    """
    if feature_matrix.empty:
        return feature_matrix.copy(), []

    # [수리적 연산] 피처 간 절대 Pearson 상관계수 행렬 산출
    correlation_matrix: pd.DataFrame = feature_matrix.corr(method="pearson").abs()

    # 상삼각 행렬(Upper Triangle) 마스킹으로 자기 자신(대각선) 및 중복 대칭 쌍 배제
    upper_triangle_mask: np.ndarray = np.triu(
        np.ones(correlation_matrix.shape, dtype=bool), 
        k=1
    )
    upper_triangle_matrix: pd.DataFrame = correlation_matrix.where(upper_triangle_mask)

    # 임계치 이상의 상관관계를 갖는 컬럼 추출
    dropped_feature_names: List[str] = [
        column_name
        for column_name in upper_triangle_matrix.columns
        if upper_triangle_matrix[column_name].ge(threshold).any()
    ]

    filtered_feature_matrix: pd.DataFrame = feature_matrix.drop(
        columns=dropped_feature_names, 
        errors="ignore"
    )

    return filtered_feature_matrix, dropped_feature_names


def hierarchical_collinearity(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    distance_threshold: float = 0.40
) -> Tuple[pd.DataFrame, List[str]]:
    """상관거리 기반 계층적 군집화(HFC)를 수행하여 다변량 공선성을 묶고, 각 군집 내 타깃 설명력 1위 피처만 보존합니다.

    Args:
        feature_matrix (pd.DataFrame): 다공선성 압축 대상 피처 데이터프레임.
        target_series (pd.Series): 예측 타깃 시계열 (예: T+20 수익률).
        distance_threshold (float): 군집 절단 거리 임계치 (기본값: 0.40 -> |r| >= 0.68 상당).

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - pruned_feature_matrix: 다변량 공선성이 압축된 피처 데이터프레임.
            - dropped_feature_names: 군집 내 경쟁에서 탈락하여 제거된 피처명 리스트.
    """
    if feature_matrix.empty or feature_matrix.shape[1] <= 1:
        return feature_matrix.copy(), []

    # 1. Pearson 상관계수 산출 및 수치 안정성 보정 ([-1.0, 1.0] 클리핑)
    correlation_matrix: pd.DataFrame = feature_matrix.corr(method="pearson").clip(-1.0, 1.0)
    correlation_matrix = correlation_matrix.fillna(0.0)

    # 2. 상관계수를 거리 행렬로 변환: D(i, j) = sqrt(0.5 * (1 - rho_ij))
    distance_matrix_values: np.ndarray = np.sqrt(
        np.clip(0.5 * (1.0 - correlation_matrix.values), 0.0, 1.0)
    )
    np.fill_diagonal(distance_matrix_values, 0.0)

    # 3. Complete Linkage 기반 계층적 덴드로그램 형성 및 거리 기준 군집 분할
    condensed_distance_vector: np.ndarray = squareform(
        distance_matrix_values, 
        checks=False
    )
    linkage_tree: np.ndarray = linkage(
        condensed_distance_vector, 
        method="complete"
    )
    cluster_identifiers: np.ndarray = fcluster(
        linkage_tree, 
        t=distance_threshold, 
        criterion="distance"
    )

    # 4. 각 피처와 타깃 간의 절대 상관계수(|corr(X_j, y)|) 사전 산출
    target_alignment_series: pd.Series = feature_matrix.apply(
        lambda feature_column: abs(feature_column.corr(target_series))
    ).fillna(0.0)

    # 5. 군집별 최고 설명력 피처 1개 선정 및 나머지 탈락 리스트 수집
    dropped_feature_set: Set[str] = set()
    cluster_to_features_mapping = pd.Series(
        feature_matrix.columns, 
        index=cluster_identifiers
    ).groupby(level=0).apply(list)

    for cluster_feature_list in cluster_to_features_mapping:
        if len(cluster_feature_list) <= 1:
            continue

        # 군집 내부에서 타깃과의 상관계수가 가장 높은 피처 식별
        cluster_target_scores: pd.Series = target_alignment_series[cluster_feature_list]
        best_representative_feature: str = cluster_target_scores.idxmax()

        for candidate_feature in cluster_feature_list:
            if candidate_feature != best_representative_feature:
                dropped_feature_set.add(candidate_feature)

    dropped_feature_names: List[str] = sorted(list(dropped_feature_set))
    pruned_feature_matrix: pd.DataFrame = feature_matrix.drop(
        columns=dropped_feature_names, 
        errors="ignore"
    )

    return pruned_feature_matrix, dropped_feature_names
