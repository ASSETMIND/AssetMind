from typing import Any, Dict, Literal, Tuple, Union
import numpy as np
import pandas as pd

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05                                   # 귀무가설 기각 판정을 위한 기본 유의수준 (alpha)
SUPPORTED_TYPE1_ERROR_METHODS: Tuple[str, ...] = ("bonferroni", "holm")    # 지원하는 1종 오류 제어 알고리즘 목록 (기본, 개선 순서)
MINIMUM_PVALUE_COUNT: int = 1                                              # 다중비교 보정을 위한 최소 p-value 개수
PVALUE_LOWER_BOUND: float = 0.0                                            # 유효 p-value 하한선
PVALUE_UPPER_BOUND: float = 1.0                                            # 유효 p-value 상한선


# ==============================================================================
# Public API Functions
# ==============================================================================

def control_type1_error(
    p_values: Union[np.ndarray, pd.Series, list],
    method: Literal["bonferroni", "holm"],
    alpha: float = DEFAULT_SIGNIFICANCE_LEVEL
) -> Dict[str, Any]:
    """다중 가설 검정 시 발생하는 제1종 오류 팽창을 제어하고 보정된 p-value를 산출합니다.

    Args:
        p_values: 다중 검정 대상 유의확률 시퀀스 (0.0 이상 1.0 이하).
        method: 1종 오류 제어 알고리즘 ('bonferroni': 기본 단일단계, 'holm': 개선 계단식).
        alpha: 전체 가설군에 적용할 유의수준 (기본값: 0.05).

    Returns:
        Dict[str, Any]:
            - adjusted_p_values: 입력 원본 순서와 일치하는 보정 p-value 배열 (np.ndarray).
            - reject: 유의수준 기준 귀무가설 기각 여부 불리언 배열 (p_adj < alpha).
            - alpha: 검정에 적용된 유의수준.
            - method: 실행된 보정 알고리즘 명칭.

    Raises:
        ValueError: 지원하지 않는 method가 지정되거나 p-value 수치가 유효 범위를 벗어날 경우 발생.
    """
    # 1. 지정된 1종 오류 제어 알고리즘의 지원 여부 검증
    _validate_type1_method(method=method)

    # 2. 유의수준 alpha의 확률 구간(0 < alpha < 1) 정합성 검증
    _validate_significance_level(alpha=alpha)

    # 3. 입력 p-value 시퀀스를 1차원 float64 배열로 정제하고 결측/범위 검증
    clean_p_values = _clean_and_validate_p_values(p_values=p_values)

    # 4. 지정된 알고리즘 엔진을 호출하여 보정 p-value 산출
    adjusted_p_values = _calculate_adjusted_p_values(
        p_values=clean_p_values,
        method=method
    )

    # 5. 보정된 p-value와 alpha를 대조하여 각 가설별 기각 여부 판정
    reject_flags = _evaluate_hypothesis_rejection(
        adjusted_p_values=adjusted_p_values,
        alpha=alpha
    )

    # 6. 최종 1종 오류 제어 수리통계 결과 번들 패키징 및 반환
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


def _calculate_adjusted_p_values(
    p_values: np.ndarray,
    method: str
) -> np.ndarray:
    """지정된 알고리즘 모드에 따라 분기하여 보정된 p-value를 계산합니다."""
    if method == "bonferroni":
        return _execute_bonferroni(p_values=p_values)
    elif method == "holm":
        return _execute_holm(p_values=p_values)


def _execute_bonferroni(p_values: np.ndarray) -> np.ndarray:
    """기본 단일 단계(Single-step) Bonferroni 알고리즘으로 p-value를 보정합니다."""
    # 1. 전체 가설 수(m) 산출
    hypothesis_count: int = len(p_values)

    # 2. 전체 가설 수 일괄 곱셈 및 상한선 1.0 클리핑 적용
    scaled_p_values: np.ndarray = p_values * float(hypothesis_count)
    clipped_p_values: np.ndarray = np.clip(scaled_p_values, PVALUE_LOWER_BOUND, PVALUE_UPPER_BOUND)

    return clipped_p_values


def _execute_holm(p_values: np.ndarray) -> np.ndarray:
    """개선 계단식(Step-down) Holm 알고리즘으로 단조성을 보존하며 p-value를 보정합니다."""
    # 1. 전체 가설 수(m) 및 오름차순 정렬 인덱스 추출
    hypothesis_count: int = len(p_values)
    sort_indices: np.ndarray = np.argsort(p_values)
    sorted_p_values: np.ndarray = p_values[sort_indices]

    # 2. 계단식 가중 계수 (m - i) 벡터 생성: [m, m-1, m-2, ..., 1]
    step_multipliers: np.ndarray = np.arange(hypothesis_count, 0, -1, dtype=np.float64)

    # 3. 단계별 가중치 곱셈 적용: P_(i) * (m - i + 1)
    scaled_p_values: np.ndarray = sorted_p_values * step_multipliers

    # 4. 누적 최댓값(np.maximum.accumulate)을 적용하여 단조 증가성(Monotonicity) 강제
    monotonic_p_values: np.ndarray = np.maximum.accumulate(scaled_p_values)

    # 5. 확률 상한선 1.0 클리핑 적용
    clipped_p_values: np.ndarray = np.clip(monotonic_p_values, PVALUE_LOWER_BOUND, PVALUE_UPPER_BOUND)

    # 6. 정렬 이전의 원본 입력 순서로 복원하여 반환
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