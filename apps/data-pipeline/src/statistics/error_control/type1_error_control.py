from typing import Any, Dict, Literal, Optional, Tuple, Union
import numpy as np
import pandas as pd

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05                                                  # 귀무가설 기각 판정을 위한 기본 유의수준 (alpha)
SUPPORTED_TYPE1_ERROR_METHODS: Tuple[str, ...] = ("bonferroni", "holm", "romano_wolf")    # 지원하는 1종 오류 제어 알고리즘 목록
MINIMUM_PVALUE_COUNT: int = 1                                                             # 다중비교 보정을 위한 최소 p-value 개수
MINIMUM_BOOTSTRAP_COUNT: int = 2                                                          # 부트스트랩 다중검정을 위한 최소 복원추출 횟수 (B)
PVALUE_LOWER_BOUND: float = 0.0                                                           # 유효 p-value 하한선
PVALUE_UPPER_BOUND: float = 1.0                                                           # 유효 p-value 상한선
VARIANCE_EPSILON: float = 1e-12                                                          # 스튜던트화 표준편차 0 나눗셈 방지용 미소 상수

# ==============================================================================
# Public API Functions
# ==============================================================================

def control_type1_error(
    p_values: Union[np.ndarray, pd.Series, list],
    method: Literal["bonferroni", "holm", "romano_wolf"],
    alpha: float = DEFAULT_SIGNIFICANCE_LEVEL,
    bootstrap_matrix: Optional[np.ndarray] = None,
    weights: Optional[Union[np.ndarray, pd.Series, list]] = None,
) -> Dict[str, Any]:
    """다중 가설 검정 시 발생하는 제1종 오류 팽창을 제어하고 보정된 p-value를 산출합니다.

    Args:
        p_values: 다중 검정 대상 원시 유의확률 시퀀스 (0.0 이상 1.0 이하, 길이 M).
        method: 1종 오류 제어 알고리즘 ('bonferroni': 단일단계, 'holm': 계단식, 'romano_wolf': 가중 부트스트랩 계단식).
        alpha: 전체 가설군에 적용할 유의수준 (기본값: 0.05).
        bootstrap_matrix: 'romano_wolf' 전용 부트스트랩 통계량 행렬 (Shape: B x M, 대립가설 방향 정렬).
        weights: 가설별 중요도 가중치 시퀀스 (길이 M, 양수, None 시 균등 가중치 1.0 적용).

    Returns:
        Dict[str, Any]:
            - adjusted_p_values: 입력 원본 순서와 일치하는 보정 p-value 배열 (np.ndarray).
            - reject: 유의수준 기준 귀무가설 기각 여부 불리언 배열 (p_adj < alpha).
            - alpha: 검정에 적용된 유의수준.
            - method: 실행된 보정 알고리즘 명칭.

    Raises:
        ValueError: 지원하지 않는 method가 지정되거나 입력 배열 차원/수치가 유효 범위를 벗어날 경우 발생.
    """
    # 1. 지정된 1종 오류 제어 알고리즘의 지원 여부 검증
    _validate_type1_method(method=method)

    # 2. 유의수준 alpha의 확률 구간(0 < alpha < 1) 정합성 검증
    _validate_significance_level(alpha=alpha)

    # 3. 입력 p-value 시퀀스를 1차원 float64 배열로 정제하고 결측/범위 검증
    clean_p_values = _clean_and_validate_p_values(p_values=p_values)

    # 4. 가설 가중치 벡터 정제 및 평균 1.0 기준 정규화 수행
    normalized_weights = _clean_and_normalize_weights(
        weights=weights,
        hypothesis_count=len(clean_p_values)
    )

    # 5. 지정된 알고리즘 엔진을 호출하여 보정 p-value 산출
    adjusted_p_values = _calculate_adjusted_p_values(
        p_values=clean_p_values,
        method=method,
        bootstrap_matrix=bootstrap_matrix,
        weights=normalized_weights
    )

    # 6. 보정된 p-value와 alpha를 대조하여 각 가설별 기각 여부 판정
    reject_flags = _evaluate_hypothesis_rejection(
        adjusted_p_values=adjusted_p_values,
        alpha=alpha
    )

    # 7. 최종 1종 오류 제어 수리통계 결과 번들 패키징 및 반환
    return _build_type1_error_result(
        adjusted_p_values=adjusted_p_values,
        reject_flags=reject_flags,
        alpha=alpha,
        method=method
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _validate_type1_method(method: str) -> None:
    """지정된 1종 오류 제어 알고리즘의 지원 여부를 검증합니다."""
    if method not in SUPPORTED_TYPE1_ERROR_METHODS:
        raise ValueError(
            f"지원하지 않는 1종 오류 제어 알고리즘입니다: '{method}'. "
            f"지원 알고리즘 목록: {SUPPORTED_TYPE1_ERROR_METHODS}"
        )


def _validate_significance_level(alpha: float) -> None:
    """유의수준(alpha)이 이론적 유효 확률 범위(0 < alpha < 1) 내에 존재하는지 검증합니다."""
    if not (PVALUE_LOWER_BOUND < alpha < PVALUE_UPPER_BOUND):
        raise ValueError(f"유의수준 alpha는 0과 1 사이의 값이어야 합니다: {alpha}")


def _clean_and_validate_p_values(
    p_values: Union[np.ndarray, pd.Series, list]
) -> np.ndarray:
    """입력 p-value 시퀀스를 1차원 배열로 표준화하고 유효 범위를 검증합니다."""
    # 1. 입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화
    flat_array: np.ndarray = np.ascontiguousarray(p_values, dtype=np.float64).flatten()

    # 2. 최소 요구 관측치 수 충족 여부 검증
    if len(flat_array) < MINIMUM_PVALUE_COUNT:
        raise ValueError(f"p-value 배열의 길이가 최소 요구치({MINIMUM_PVALUE_COUNT}) 미만입니다.")

    # 3. 결측치(NaN) 또는 무한대(Inf) 존재 여부 검증
    if not np.all(np.isfinite(flat_array)):
        raise ValueError("p-value 배열에 결측치(NaN) 또는 무한대(Inf)가 포함되어 있습니다.")

    # 4. 모든 관측치가 확률 닫힌구간 [0.0, 1.0] 내에 위치하는지 검증
    if np.any(flat_array < PVALUE_LOWER_BOUND) or np.any(flat_array > PVALUE_UPPER_BOUND):
        raise ValueError("모든 p-value는 0.0 이상 1.0 이하의 확률값이어야 합니다.")

    return flat_array


def _clean_and_normalize_weights(
    weights: Optional[Union[np.ndarray, pd.Series, list]],
    hypothesis_count: int
) -> np.ndarray:
    """가설별 가중치 벡터를 검증하고 전체 유의수준 예산 보존을 위해 평균 1.0으로 정규화합니다."""
    # 1. 가중치 미지정 시 모든 가설에 균등 가중치(1.0) 부여
    if weights is None:
        return np.ones(hypothesis_count, dtype=np.float64)

    # 2. 1차원 float64 배열 변환 및 차원 일치 검증
    weight_array: np.ndarray = np.ascontiguousarray(weights, dtype=np.float64).flatten()
    if len(weight_array) != hypothesis_count:
        raise ValueError(
            f"가중치 배열 길이({len(weight_array)})가 가설 개수({hypothesis_count})와 일치하지 않습니다."
        )

    # 3. 유한성 및 양수(> 0) 조건 검증
    if not np.all(np.isfinite(weight_array)) or np.any(weight_array <= 0.0):
        raise ValueError("모든 가설 가중치는 0보다 큰 유한한 실수여야 합니다.")

    # 4. 가중치 합계가 가설 수(M)와 같아지도록 정규화 (Mean Weight = 1.0)
    return weight_array * (float(hypothesis_count) / float(np.sum(weight_array)))


def _clean_and_validate_bootstrap_matrix(
    bootstrap_matrix: Optional[np.ndarray],
    hypothesis_count: int
) -> np.ndarray:
    """Romano-Wolf 검정을 위한 2차원 부트스트랩 행렬(B x M)의 정합성을 검증합니다."""
    # 1. 행렬 존재 여부 확인
    if bootstrap_matrix is None:
        raise ValueError("'romano_wolf' 알고리즘 실행 시 bootstrap_matrix(B x M) 입력이 필수입니다.")

    # 2. 2차원 float64 배열 변환 및 형상(Shape) 검증
    matrix: np.ndarray = np.ascontiguousarray(bootstrap_matrix, dtype=np.float64)
    if matrix.ndim != 2:
        raise ValueError(f"bootstrap_matrix는 2차원 배열(B, M)이어야 합니다: 현재 차원 {matrix.ndim}D")

    n_bootstraps, n_cols = matrix.shape
    if n_bootstraps < MINIMUM_BOOTSTRAP_COUNT:
        raise ValueError(f"부트스트랩 표본 수(B={n_bootstraps})가 최소 요구치({MINIMUM_BOOTSTRAP_COUNT}) 미만입니다.")
    if n_cols != hypothesis_count:
        raise ValueError(
            f"bootstrap_matrix 열 개수({n_cols})가 가설 개수({hypothesis_count})와 일치하지 않습니다."
        )

    # 3. 결측치 및 무한대 포함 여부 검증
    if not np.all(np.isfinite(matrix)):
        raise ValueError("bootstrap_matrix 내부에 결측치(NaN) 또는 무한대(Inf)가 포함되어 있습니다.")

    return matrix


def _calculate_adjusted_p_values(
    p_values: np.ndarray,
    method: str,
    bootstrap_matrix: Optional[np.ndarray] = None,
    weights: Optional[np.ndarray] = None,
) -> np.ndarray:
    """지정된 알고리즘 모드에 따라 분기하여 보정된 p-value를 계산합니다."""
    if method == "bonferroni":
        return _execute_bonferroni(p_values=p_values, weights=weights)
    elif method == "holm":
        return _execute_holm(p_values=p_values, weights=weights)
    elif method == "romano_wolf":
        clean_matrix = _clean_and_validate_bootstrap_matrix(
            bootstrap_matrix=bootstrap_matrix,
            hypothesis_count=len(p_values)
        )
        return _execute_romano_wolf(
            p_values=p_values,
            bootstrap_matrix=clean_matrix,
            weights=weights
        )


def _execute_bonferroni(
    p_values: np.ndarray,
    weights: Optional[np.ndarray] = None
) -> np.ndarray:
    """기본 단일 단계(Single-step) 가중 Bonferroni 알고리즘으로 p-value를 보정합니다."""
    # 1. 전체 가설 수(m) 및 가중치 벡터 준비
    hypothesis_count: int = len(p_values)
    w: np.ndarray = np.ones(hypothesis_count, dtype=np.float64) if weights is None else weights

    # 2. 가중치 대비 전체 가설 수 곱셈 및 상한선 1.0 클리핑 적용
    scaled_p_values: np.ndarray = (p_values / w) * float(hypothesis_count)
    clipped_p_values: np.ndarray = np.clip(scaled_p_values, PVALUE_LOWER_BOUND, PVALUE_UPPER_BOUND)

    return clipped_p_values


def _execute_holm(
    p_values: np.ndarray,
    weights: Optional[np.ndarray] = None
) -> np.ndarray:
    """개선 계단식(Step-down) 가중 Holm 알고리즘으로 단조성을 보존하며 p-value를 보정합니다."""
    # 1. 가중 조정된 원시 p-value(p_i / w_i) 기준 오름차순 정렬 인덱스 추출
    hypothesis_count: int = len(p_values)
    w: np.ndarray = np.ones(hypothesis_count, dtype=np.float64) if weights is None else weights
    weighted_p: np.ndarray = p_values / w

    sort_indices: np.ndarray = np.argsort(weighted_p)
    sorted_weighted_p: np.ndarray = weighted_p[sort_indices]
    sorted_weights: np.ndarray = w[sort_indices]

    # 2. 잔여 가중치 합계 비율 계단식 승수 생성 및 곱셈 적용
    remaining_weight_sums: np.ndarray = np.cumsum(sorted_weights[::-1])[::-1]
    scaled_p_values: np.ndarray = sorted_weighted_p * remaining_weight_sums

    # 3. 누적 최댓값(np.maximum.accumulate)을 적용하여 단조 증가성(Monotonicity) 강제
    monotonic_p_values: np.ndarray = np.maximum.accumulate(scaled_p_values)

    # 4. 확률 상한선 1.0 클리핑 및 원본 순서 복원
    clipped_p_values: np.ndarray = np.clip(monotonic_p_values, PVALUE_LOWER_BOUND, PVALUE_UPPER_BOUND)
    original_order_p_values: np.ndarray = np.empty_like(clipped_p_values)
    original_order_p_values[sort_indices] = clipped_p_values

    return original_order_p_values


def _compute_studentized_null_quantiles(bootstrap_matrix: np.ndarray) -> np.ndarray:
    """부트스트랩 행렬을 귀무가설 중심 스튜던트화 및 경험적 분위수(Null Quantile)로 변환합니다."""
    # 1. 각 가설별 부트스트랩 평균 및 표준편차로 최근영화·스튜던트화 수행
    n_bootstraps: int = bootstrap_matrix.shape[0]
    col_means: np.ndarray = np.mean(bootstrap_matrix, axis=0, keepdims=True)
    col_stds: np.ndarray = np.maximum(np.std(bootstrap_matrix, axis=0, ddof=1, keepdims=True), VARIANCE_EPSILON)
    studentized_matrix: np.ndarray = (bootstrap_matrix - col_means) / col_stds

    # 2. 각 열 내부에서 스튜던트화 통계량의 내림차순 순위 기반 경험적 귀무 p-분위수 산출
    order_indices: np.ndarray = np.argsort(-studentized_matrix, axis=0)
    ranks: np.ndarray = np.empty_like(order_indices, dtype=np.float64)
    row_grid: np.ndarray = np.arange(1, n_bootstraps + 1, dtype=np.float64)[:, None]
    np.put_along_axis(ranks, order_indices, row_grid, axis=0)

    return ranks / float(n_bootstraps + 1)


def _execute_romano_wolf(
    p_values: np.ndarray,
    bootstrap_matrix: np.ndarray,
    weights: Optional[np.ndarray] = None
) -> np.ndarray:
    """가중 스튜던트화 Romano-Wolf Step-down 부트스트랩 알고리즘으로 다중비교 p-value를 보정합니다."""
    # 1. 가설 수(M), 부트스트랩 횟수(B) 및 가중치 벡터 초기화
    n_bootstraps, hypothesis_count = bootstrap_matrix.shape
    w: np.ndarray = np.ones(hypothesis_count, dtype=np.float64) if weights is None else weights

    # 2. 가중치 반영 원시 p-value(p_m / w_m) 기준 오름차순(가장 유의한 순서) 정렬
    weighted_raw_p: np.ndarray = p_values / w
    sort_indices: np.ndarray = np.argsort(weighted_raw_p)
    sorted_weighted_p: np.ndarray = weighted_raw_p[sort_indices]

    # 3. 부트스트랩 행렬의 공분산 구조를 보존한 채 가중 귀무 분위수 행렬 산출
    null_quantiles: np.ndarray = _compute_studentized_null_quantiles(bootstrap_matrix=bootstrap_matrix)
    weighted_null_quantiles: np.ndarray = (null_quantiles / w[None, :])[:, sort_indices]

    # 4. Step-down 루프: 단계별로 잔여 가설 집합(R_s)의 결합 최소 분위수 분포와 대조
    stepdown_p_values: np.ndarray = np.empty(hypothesis_count, dtype=np.float64)
    for step_idx in range(hypothesis_count):
        active_min_quantiles: np.ndarray = np.min(weighted_null_quantiles[:, step_idx:], axis=1)
        exceedance_count: int = int(np.sum(active_min_quantiles <= sorted_weighted_p[step_idx] + VARIANCE_EPSILON))
        stepdown_p_values[step_idx] = float(exceedance_count) / float(n_bootstraps + 1)

    # 5. Step-down 단조 증가성(Monotonicity) 강제 및 [0.0, 1.0] 클리핑
    monotonic_p_values: np.ndarray = np.maximum.accumulate(stepdown_p_values)
    clipped_p_values: np.ndarray = np.clip(monotonic_p_values, PVALUE_LOWER_BOUND, PVALUE_UPPER_BOUND)

    # 6. 정렬 이전의 원본 가설 순서로 복원하여 반환
    original_order_p_values: np.ndarray = np.empty_like(clipped_p_values)
    original_order_p_values[sort_indices] = clipped_p_values

    return original_order_p_values


def _evaluate_hypothesis_rejection(
    adjusted_p_values: np.ndarray,
    alpha: float
) -> np.ndarray:
    """보정된 p-value와 유의수준을 대조하여 각 가설의 기각 여부를 결정합니다."""
    return adjusted_p_values < alpha


def _build_type1_error_result(
    adjusted_p_values: np.ndarray,
    reject_flags: np.ndarray,
    alpha: float,
    method: str
) -> Dict[str, Any]:
    """최종 제1종 오류 제어 통계량 및 메타데이터를 정형화된 딕셔너리로 조립합니다."""
    return {
        "adjusted_p_values": adjusted_p_values,
        "reject": reject_flags,
        "alpha": alpha,
        "method": method
    }