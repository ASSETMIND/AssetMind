import numpy as np
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_ALPHA: float = 0.05  # 기본 제1종 오류 유의수준 (Type I Error Rate)
DEFAULT_POWER: float = 0.80  # 기본 목표 통계적 검정력 (1 - Beta)
MIN_SAMPLE_SIZE: int = 2  # t-분포 자유도 정의를 위한 최소 표본 크기
SEARCH_MARGIN_LOWER: int = 15  # 표본 크기 탐색 시 정상 근사치 기준 하한 마진
SEARCH_MARGIN_UPPER: int = 30  # 표본 크기 탐색 시 정상 근사치 기준 상한 마진
MDE_SEARCH_ITERATIONS: int = 60  # MDE 이진 탐색 수렴 반복 횟수
MDE_SEARCH_LOW: float = 0.001  # MDE 탐색 최소 경계값
MDE_SEARCH_HIGH: float = 5.0  # MDE 탐색 최대 경계값


# ==============================================================================
# Public API Functions
# ==============================================================================
def calculate_power(
    sample_size: int,
    effect_size: float,
    alpha: float = DEFAULT_ALPHA,
    one_sided: bool = True,
) -> float:
    """비중심 t-분포를 이용하여 단일 또는 대응표본 t-검정의 통계적 검정력을 산출합니다.

    Args:
        sample_size (int): 표본 크기 (N).
        effect_size (float): 표준화된 효과 크기 (Cohen's d).
        alpha (float): 유의수준 (기본값: 0.05).
        one_sided (bool): 단측 검정 여부 (기본값: True).

    Returns:
        float: 0.0 ~ 1.0 범위의 통계적 검정력 (1 - Beta).

    Raises:
        ValueError: 표본 크기, 효과 크기, 또는 유의수준이 유효 범위를 벗어난 경우.
    """
    _validate_power_inputs(sample_size, effect_size, alpha)
    return _compute_t_power(sample_size, effect_size, alpha, one_sided)


def calculate_required_sample_size(
    effect_size: float,
    target_power: float = DEFAULT_POWER,
    alpha: float = DEFAULT_ALPHA,
    one_sided: bool = True,
) -> int:
    """목표 검정력 및 최소 탐지 가능 효과 크기(MDE)를 달성하기 위해 필요한 최소 표본 크기를 산출합니다.

    Args:
        effect_size (float): 표준화된 효과 크기 (Cohen's d).
        target_power (float): 목표 검정력 (기본값: 0.80).
        alpha (float): 유의수준 (기본값: 0.05).
        one_sided (bool): 단측 검정 여부 (기본값: True).

    Returns:
        int: 목표 검정력을 충족하는 최소 표본 크기.

    Raises:
        ValueError: 효과 크기, 목표 검정력, 또는 유의수준이 유효 범위를 벗어난 경우.
    """
    _validate_target_inputs(effect_size, target_power, alpha)
    n_approx = _estimate_sample_size_normal(effect_size, target_power, alpha, one_sided)
    return _search_exact_sample_size(n_approx, effect_size, target_power, alpha, one_sided)


def calculate_mde(
    sample_size: int,
    target_power: float = DEFAULT_POWER,
    alpha: float = DEFAULT_ALPHA,
    one_sided: bool = True,
) -> float:
    """주어진 표본 크기에서 목표 검정력을 충족하는 최소 탐지 가능 효과 크기(MDE)를 산출합니다.

    Args:
        sample_size (int): 표본 크기 (N).
        target_power (float): 목표 검정력 (기본값: 0.80).
        alpha (float): 유의수준 (기본값: 0.05).
        one_sided (bool): 단측 검정 여부 (기본값: True).

    Returns:
        float: 최소 탐지 가능 효과 크기 (Cohen's d).

    Raises:
        ValueError: 표본 크기, 목표 검정력, 또는 유의수준이 유효 범위를 벗어난 경우.
    """
    _validate_sample_and_targets(sample_size, target_power, alpha)
    return _binary_search_mde(sample_size, target_power, alpha, one_sided)


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_power_inputs(sample_size: int, effect_size: float, alpha: float) -> None:
    """검정력 산출에 필요한 기본 입력 파라미터의 범위를 검증합니다."""
    if sample_size < MIN_SAMPLE_SIZE:
        raise ValueError(f"표본 크기는 최소 {MIN_SAMPLE_SIZE} 이상이어야 합니다.")
    if effect_size <= 0.0:
        raise ValueError("효과 크기(Cohen's d)는 양수여야 합니다.")
    if not (0.0 < alpha < 1.0):
        raise ValueError("유의수준(alpha)은 (0, 1) 범위 내의 값이어야 합니다.")


def _validate_target_inputs(effect_size: float, target_power: float, alpha: float) -> None:
    """필요 표본 크기 산출에 필요한 파라미터 범위를 검증합니다."""
    if effect_size <= 0.0:
        raise ValueError("효과 크기(Cohen's d)는 양수여야 합니다.")
    if not (0.0 < target_power < 1.0):
        raise ValueError("목표 검정력은 (0, 1) 범위 내의 값이어야 합니다.")
    if not (0.0 < alpha < 1.0):
        raise ValueError("유의수준(alpha)은 (0, 1) 범위 내의 값이어야 합니다.")


def _validate_sample_and_targets(sample_size: int, target_power: float, alpha: float) -> None:
    """MDE 산출에 필요한 파라미터 범위를 검증합니다."""
    if sample_size < MIN_SAMPLE_SIZE:
        raise ValueError(f"표본 크기는 최소 {MIN_SAMPLE_SIZE} 이상이어야 합니다.")
    if not (0.0 < target_power < 1.0):
        raise ValueError("목표 검정력은 (0, 1) 범위 내의 값이어야 합니다.")
    if not (0.0 < alpha < 1.0):
        raise ValueError("유의수준(alpha)은 (0, 1) 범위 내의 값이어야 합니다.")


def _compute_t_power(
    sample_size: int,
    effect_size: float,
    alpha: float,
    one_sided: bool,
) -> float:
    """비중심 t-분포 기반 사후 통계적 검정력을 계산합니다."""
    degrees_of_freedom = sample_size - 1
    non_centrality_parameter = effect_size * np.sqrt(sample_size)
    alpha_adjusted = alpha if one_sided else alpha / 2.0
    critical_t = stats.t.ppf(1.0 - alpha_adjusted, df=degrees_of_freedom)

    calculated_power = 1.0 - stats.nct.cdf(critical_t, df=degrees_of_freedom, nc=non_centrality_parameter)
    return float(np.clip(calculated_power, 0.0, 1.0))


def _estimate_sample_size_normal(
    effect_size: float,
    target_power: float,
    alpha: float,
    one_sided: bool,
) -> int:
    """표준정규분포 점근 공식을 활용하여 필요 표본 크기의 근사치를 추정합니다."""
    alpha_adjusted = alpha if one_sided else alpha / 2.0
    z_alpha = stats.norm.ppf(1.0 - alpha_adjusted)
    z_beta = stats.norm.ppf(target_power)
    return int(np.ceil(((z_alpha + z_beta) / effect_size) ** 2))


def _search_exact_sample_size(
    n_approx: int,
    effect_size: float,
    target_power: float,
    alpha: float,
    one_sided: bool,
) -> int:
    """근사치 인근 구간에서 비중심 t-분포 기반 정확 검정력을 충족하는 최소 표본을 탐색합니다."""
    search_start = max(MIN_SAMPLE_SIZE, n_approx - SEARCH_MARGIN_LOWER)
    search_end = n_approx + SEARCH_MARGIN_UPPER

    for candidate_n in range(search_start, search_end + 1):
        power_at_n = _compute_t_power(candidate_n, effect_size, alpha, one_sided)
        if power_at_n >= target_power:
            return candidate_n
    return max(MIN_SAMPLE_SIZE, n_approx)


def _binary_search_mde(
    sample_size: int,
    target_power: float,
    alpha: float,
    one_sided: bool,
) -> float:
    """주어진 표본 크기에서 목표 검정력에 도달하는 Cohen's d를 이진 탐색합니다."""
    lower_bound = MDE_SEARCH_LOW
    upper_bound = MDE_SEARCH_HIGH

    for _ in range(MDE_SEARCH_ITERATIONS):
        mid_point = (lower_bound + upper_bound) / 2.0
        current_power = _compute_t_power(sample_size, mid_point, alpha, one_sided)
        if current_power < target_power:
            lower_bound = mid_point
        else:
            upper_bound = mid_point

    return float(round(mid_point, 4))