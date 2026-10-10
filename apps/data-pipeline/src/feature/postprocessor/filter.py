from typing import List, Optional, Set, Tuple
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_MAX_MISSING_RATIO: float = 0.2      # 고결측치 피처를 배제하기 위한 결측치 비율 상한선 (20% 초과 시 탈락)
DEFAULT_MAX_ZERO_RATIO: float = 0.8         # 희소(Sparse) 피처를 배제하기 위한 0.0 수치 비율 상한선 (80% 이상 시 탈락)
DEFAULT_PEARSON_THRESHOLD: float = 0.85     # 피어슨 선형 공선성 판정을 위한 상관계수 절대값 임계치 (|r| >= 0.85)
DEFAULT_DISTANCE_THRESHOLD: float = 0.40    # HFC 계층 군집화 상관거리 절단 임계치 (Distance <= 0.40)


# ==============================================================================
# Public API Functions
# ==============================================================================

def filter_constant_features(
    X_train: pd.DataFrame
) -> Tuple[pd.DataFrame, List[str]]:
    """고유값 수(nunique)가 1개 이하인 변동성 0의 상수 컬럼을 감지하여 제거합니다.

    Args:
        X_train: 학습 피처 데이터프레임.

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - filtered_matrix: 상수 피처가 제거된 데이터프레임.
            - removed_feature_names: 감지되어 제거된 상수 피처명 리스트.
    """
    # 1. 입력 데이터프레임 공백 검사
    if X_train.empty or X_train.shape[1] == 0:
        return X_train.copy(), []

    # 2. 피처별 고유값 개수(nunique)가 1개 이하인 상수 컬럼 탐색
    removed_feature_names: List[str] = [
        col for col in X_train.columns if X_train[col].nunique() <= 1
    ]

    # 3. 상수 컬럼 제거 및 정제된 데이터프레임 반환
    filtered_matrix: pd.DataFrame = X_train.drop(columns=removed_feature_names)
    return filtered_matrix, removed_feature_names


def filter_missing_ratio(
    X_train: pd.DataFrame,
    max_missing_ratio: float = DEFAULT_MAX_MISSING_RATIO
) -> Tuple[pd.DataFrame, List[str]]:
    """결측치(NaN) 비율이 기준치를 초과하는 고결측 오염 피처를 감지하여 제거합니다.

    Args:
        X_train: 학습 피처 데이터프레임.
        max_missing_ratio: 허용 가능한 최대 결측치 비율 (기본값: 0.2 = 20%).

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - filtered_matrix: 고결측 피처가 제거된 데이터프레임.
            - removed_feature_names: 감지되어 제거된 고결측 피처명 리스트.
    """
    # 1. 입력 데이터프레임 공백 검사
    if X_train.empty or X_train.shape[1] == 0:
        return X_train.copy(), []

    # 2. 각 컬럼별 결측치 비율 산출
    missing_ratios: pd.Series = X_train.isna().mean()

    # 3. 임계치 초과 고결측 컬럼 필터링
    removed_feature_names: List[str] = missing_ratios[missing_ratios > max_missing_ratio].index.tolist()

    # 4. 결측 컬럼 제거 및 정제된 데이터프레임 반환
    filtered_matrix: pd.DataFrame = X_train.drop(columns=removed_feature_names)
    return filtered_matrix, removed_feature_names


def filter_zero_ratio(
    X_train: pd.DataFrame,
    max_zero_ratio: float = DEFAULT_MAX_ZERO_RATIO
) -> Tuple[pd.DataFrame, List[str]]:
    """수치 0.0의 비율이 기준치 이상인 희소(Sparse) 피처를 감지하여 제거합니다.

    Args:
        X_train: 학습 피처 데이터프레임.
        max_zero_ratio: 허용 가능한 최대 0.0 수치 비율 (기본값: 0.8 = 80%).

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - filtered_matrix: 희소 피처가 제거된 데이터프레임.
            - removed_feature_names: 감지되어 제거된 희소 피처명 리스트.
    """
    # 1. 입력 데이터프레임 공백 검사
    if X_train.empty or X_train.shape[1] == 0:
        return X_train.copy(), []

    # 2. 피처별 0.0 수치 비율 산출
    zero_ratios: pd.Series = (X_train == 0.0).sum(axis=0) / max(len(X_train), 1)

    # 3. 임계치 이상 희소 컬럼 추출
    removed_feature_names: List[str] = zero_ratios[zero_ratios >= max_zero_ratio].index.tolist()

    # 4. 희소 컬럼 제거 및 정제된 데이터프레임 반환
    filtered_matrix: pd.DataFrame = X_train.drop(columns=removed_feature_names)
    return filtered_matrix, removed_feature_names


def pearson_collinearity(
    feature_matrix: pd.DataFrame,
    target_series: Optional[pd.Series] = None,
    threshold: float = DEFAULT_PEARSON_THRESHOLD
) -> Tuple[pd.DataFrame, List[str]]:
    """피어슨 선형 상관계수 기반으로 다중공선성(|r| >= threshold) 피처를 감지하고 타깃 설명력 우선 원칙으로 정리합니다.

    Args:
        feature_matrix: 전처리 대상 피처 데이터프레임.
        target_series: 피처 우선 보존 판정을 위한 타깃 시계열 (기본값: None).
        threshold: 공선성 판정 상관계수 절대값 임계치 (기본값: 0.85).

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - filtered_matrix: 공선성 중복 피처가 제거된 데이터프레임.
            - dropped_feature_names: 제거된 피처명 리스트.
    """
    # 1. 입력 피처 행렬 공백 또는 단일 컬럼 검사
    if feature_matrix.empty or feature_matrix.shape[1] <= 1:
        return feature_matrix.copy(), []

    # 2. 피처 간 피어슨 선형 상관계수 절대값 행렬 및 상삼각 행렬 마스킹 생성
    correlation_matrix: pd.DataFrame = feature_matrix.corr(method="pearson").abs()
    upper_triangle_mask: np.ndarray = np.triu(np.ones(correlation_matrix.shape, dtype=bool), k=1)
    upper_triangle_matrix: pd.DataFrame = correlation_matrix.where(upper_triangle_mask)

    # 3. 타깃 설명력 우선 또는 컬럼 순서 기반 공선성 탈락 대상 피처 목록 선별
    dropped_feature_names: List[str] = _resolve_pearson_collinear_drops(
        upper_triangle_matrix=upper_triangle_matrix,
        feature_matrix=feature_matrix,
        target_series=target_series,
        threshold=threshold
    )

    # 4. 공선성 중복 피처 제거 및 정제된 데이터프레임 반환
    filtered_matrix: pd.DataFrame = feature_matrix.drop(columns=dropped_feature_names, errors="ignore")
    return filtered_matrix, dropped_feature_names


def hierarchical_collinearity(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD
) -> Tuple[pd.DataFrame, List[str]]:
    """상관거리 기반 계층적 군집화(HFC)를 수행하여 다변량 공선성을 군집화하고 각 군집 내 타깃 설명력 1위 피처만 보존합니다.

    Args:
        feature_matrix: 다변량 공선성 압축 대상 피처 데이터프레임.
        target_series: 군집 내 설명력 순위 판정을 위한 정답 타깃 시계열.
        distance_threshold: 군집 절단 상관거리 임계치 (기본값: 0.40).

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - pruned_matrix: 군집별 대표 피처만 남긴 데이터프레임.
            - dropped_feature_names: 군집 내 경쟁에서 탈락한 피처명 리스트.
    """
    # 1. 입력 피처 행렬 공백 또는 단일 컬럼 검사
    if feature_matrix.empty or feature_matrix.shape[1] <= 1:
        return feature_matrix.copy(), []

    # 2. 피어슨 상관계수를 상관거리 행렬 D = sqrt(0.5 * (1 - r))로 변환
    distance_matrix_values: np.ndarray = _compute_correlation_distance_matrix(feature_matrix=feature_matrix)

    # 3. Complete Linkage 기반 계층적 군집화 및 거리 임계치 기준 클러스터 분할
    condensed_distance_vector: np.ndarray = squareform(distance_matrix_values, checks=False)
    linkage_tree: np.ndarray = linkage(condensed_distance_vector, method="complete")
    cluster_identifiers: np.ndarray = fcluster(linkage_tree, t=distance_threshold, criterion="distance")

    # 4. 군집별로 타깃과의 상관계수가 가장 높은 1위 피처를 선별하고 나머지 탈락 피처 수집
    dropped_feature_names: List[str] = _extract_hfc_cluster_drops(
        feature_matrix=feature_matrix,
        target_series=target_series,
        cluster_identifiers=cluster_identifiers
    )

    # 5. 탈락 피처 제거 및 직교성이 확보된 정예 데이터프레임 반환
    pruned_matrix: pd.DataFrame = feature_matrix.drop(columns=dropped_feature_names, errors="ignore")
    return pruned_matrix, dropped_feature_names


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _resolve_pearson_collinear_drops(
    upper_triangle_matrix: pd.DataFrame,
    feature_matrix: pd.DataFrame,
    target_series: Optional[pd.Series],
    threshold: float
) -> List[str]:
    """피어슨 상관계수 행렬을 기반으로 임계치를 초과하는 공선성 변수 쌍 중 제거할 대상을 선별합니다.

    Args:
        upper_triangle_matrix: 대각선 상단을 제외하고 마스킹된 피어슨 상관계수 상삼각 행렬.
        feature_matrix: 후보 피처 데이터프레임.
        target_series: 피처 보존 우선순위를 결정하기 위한 정답 타깃 시계열.
        threshold: 공선성 판정 상관계수 임계치.

    Returns:
        List[str]: 공선성 제거 기준에 따라 탈락된 피처 컬럼명 정렬 리스트.
    """
    # 1. 타깃 시계열 제공 여부에 따른 분기 처리 (설명력 우선 보존 vs 컬럼 순서 기준 탈락)
    if target_series is not None and not target_series.empty:
        # 2. 각 피처와 타깃 간의 절대 선형 상관계수 계산 및 결측치 0.0 대치
        target_correlation: pd.Series = feature_matrix.apply(
            lambda col: abs(col.corr(target_series))
        ).fillna(0.0)

        # 3. 임계치 이상의 상관계수를 갖는 공선성 피처 쌍을 순회하며 설명력이 낮은 피처 수집
        dropped_feature_set: Set[str] = set()
        for col_name in upper_triangle_matrix.columns:
            # 현재 컬럼과 상관계수 임계치 이상인 상대 피처 목록 추출
            correlated_peers = upper_triangle_matrix.index[
                upper_triangle_matrix[col_name].ge(threshold)
            ].tolist()

            for peer in correlated_peers:
                # 두 변수 중 타깃과의 상관계수가 더 작은 변수를 탈락 세트에 등록
                if target_correlation[col_name] < target_correlation[peer]:
                    dropped_feature_set.add(col_name)
                else:
                    dropped_feature_set.add(peer)

        # 4. 중복 제거된 탈락 피처 목록을 알파벳순으로 정렬하여 반환
        return sorted(list(dropped_feature_set))

    # 5. 타깃 시계열이 없을 경우, 상삼각 행렬에서 임계치 이상 상관을 갖는 컬럼을 순서대로 탈락
    return [
        col for col in upper_triangle_matrix.columns
        if upper_triangle_matrix[col].ge(threshold).any()
    ]


def _compute_correlation_distance_matrix(feature_matrix: pd.DataFrame) -> np.ndarray:
    """피처 간 피어슨 상관계수를 계산하고 0~1 범위의 계층 군집화용 거리 행렬로 변환합니다.

    Args:
        feature_matrix: 군집화 대상 피처 데이터프레임.

    Returns:
        np.ndarray: 피처 간 비유사도를 나타내는 대칭 상관거리 행렬 (D_ij).
    """
    # 1. 피처 간 피어슨 상관계수 행렬 산출 및 [-1.0, 1.0] 범위 수치 보정
    correlation_matrix: pd.DataFrame = (
        feature_matrix.corr(method="pearson")
        .clip(-1.0, 1.0)
        .fillna(0.0)
    )

    # 2. 상관계수를 각도/거리 척도 공식(D = sqrt(0.5 * (1 - r)))을 적용하여 거리 값으로 변환
    distance_matrix_values: np.ndarray = np.sqrt(
        np.clip(0.5 * (1.0 - correlation_matrix.values), 0.0, 1.0)
    )

    # 3. 자기 자신과의 거리인 대각 원소를 정확히 0.0으로 강제 보정
    np.fill_diagonal(distance_matrix_values, 0.0)

    # 4. 연산 완료된 대칭 거리 넘파이 배열 반환
    return distance_matrix_values


def _extract_hfc_cluster_drops(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    cluster_identifiers: np.ndarray
) -> List[str]:
    """계층적 군집화 결과에 따라 각 군집 내 타깃 설명력 1위 변수 외 나머지 변수들을 탈락 목록으로 수집합니다.

    Args:
        feature_matrix: 후보 피처 데이터프레임.
        target_series: 타깃 설명력 산출용 타깃 시계열.
        cluster_identifiers: scipy fcluster에서 할당된 피처별 군집 고유 식별자 배열.

    Returns:
        List[str]: 군집 내 경쟁에서 탈락한 피처 컬럼명 정렬 리스트.
    """
    # 1. 전체 피처와 타깃 시계열 간의 절대 피어슨 상관계수 사전 산출
    target_alignment_series: pd.Series = feature_matrix.apply(
        lambda col: abs(col.corr(target_series))
    ).fillna(0.0)

    # 2. 군집 식별자별로 소속된 피처 컬럼명 목록을 그룹화
    cluster_to_features_mapping = pd.Series(
        feature_matrix.columns,
        index=cluster_identifiers
    ).groupby(level=0).apply(list)

    # 3. 2개 이상의 피처가 포함된 군집을 순회하며 설명력 1위 피처 외 나머지 수집
    dropped_feature_set: Set[str] = set()
    for cluster_feature_list in cluster_to_features_mapping:
        # 단일 변수 군집은 경쟁 대상이 없으므로 보존
        if len(cluster_feature_list) <= 1:
            continue

        # 해당 군집 내에서 타깃 절대 상관계수가 최대인 대표 피처 추출
        cluster_target_scores: pd.Series = target_alignment_series[cluster_feature_list]
        best_feature: str = cluster_target_scores.idxmax()

        # 대표 피처를 제외한 나머지 변수들을 탈락 세트에 등록
        for candidate_feature in cluster_feature_list:
            if candidate_feature != best_feature:
                dropped_feature_set.add(candidate_feature)

    # 4. 중복이 제거된 탈락 피처 목록을 알파벳순으로 정렬하여 반환
    return sorted(list(dropped_feature_set))