from typing import Any, Dict, Literal, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
SUPPORTED_SIGNED_RANK_METHODS: Tuple[str, ...] = ("wilcoxon", "pratt")        # 지원하는 부호순위검정 알고리즘 목록 (기본, 개선 순서)
SUPPORTED_ALTERNATIVES: Tuple[str, ...] = ("two-sided", "greater", "less")    # 지원하는 대립가설 방향 목록
MINIMUM_OBSERVATION_COUNT: int = 2                                            # 검정 수행을 위한 최소 유효 표본 관측치 수
ZERO_DIFFERENCE_EPSILON: float = 1e-12                                        # 영(0) 차분 및 분산 제로 판정을 위한 부동소수점 임계치
CONTINUITY_CORRECTION_VALUE: float = 0.5                                      # 정규근사 연속성 보정 상수
PROBABILITY_LOWER_BOUND: float = 0.0                                          # 확률값 하한선
PROBABILITY_UPPER_BOUND: float = 1.0                                          # 확률값 상한선


# ==============================================================================
# Public API Functions
# ==============================================================================
def signed_rank_test(
    sample_a_values: Union[np.ndarray, pd.Series, list],
    sample_b_values: Union[np.ndarray, pd.Series, list],
    method: Literal["wilcoxon", "pratt"],
    alternative: Literal["two-sided", "greater", "less"],
    use_continuity_correction: bool = True
) -> Dict[str, Any]:
    """동일 관측 대상에 대한 대응 2표본 비모수 부호순위 가설 검정(Wilcoxon Signed-Rank Test)을 수행합니다.

    Args:
        sample_a_values: 첫 번째 대응 표본 수치 시퀀스 (예: 처치군 또는 비교 대상 점수).
        sample_b_values: 두 번째 대응 표본 수치 시퀀스 (예: 대조군 또는 기준선 점수).
        method: 실행할 영(0) 차분 처리 및 순위 알고리즘 ('wilcoxon': 기본 영 차분 사전 배제, 'pratt': 개선 전체 순위 보존).
        alternative: 대립가설 검정 방향 ('two-sided', 'greater', 'less').
        use_continuity_correction: 점근 정규근사 시 연속성 보정(0.5) 적용 여부 (기본값: True).

    Returns:
        Dict[str, Any]:
            - statistic: 양의 차분 순위합 통계량 (W_plus).
            - z_statistic: 동점 및 영 차분이 보정된 점근 표준정규 Z-통계량.
            - p_value: 유의확률 (p-value).
            - median_difference: 대응 차분 표본중앙값 (median(A - B)).
            - mean_difference: 대응 차분 표본평균 (mean(A - B)).
            - rank_biserial: 순위 양분 상관계수 효과 크기 (r_rb = (W_plus - W_minus) / total_rank_sum).
            - effect_size_r: 표준화 비모수 효과 크기 (r = z_statistic / sqrt(N)).
            - non_zero_count: 영(0) 차분을 제외한 유효 관측치 수.
            - zero_count: 영(0) 차분 관측치 수.
            - method: 실행된 알고리즘 명칭.
            - alternative: 검정 방향.

    Raises:
        ValueError: 지원하지 않는 method, alternative 또는 표본 크기 불일치 및 부족 시 발생.
    """
    # 1. 부호순위검정 알고리즘 매개변수 유효성 검증
    _validate_signed_rank_method(method=method)

    # 2. 대립가설 검정 방향 매개변수 유효성 검증
    _validate_alternative_hypothesis(alternative=alternative)

    # 3. 두 대응 표본의 길이를 대조하고 결측을 배제한 유효 차분 벡터(d = A - B) 추출
    differences: np.ndarray = _clean_and_extract_differences(
        sample_a_values=sample_a_values,
        sample_b_values=sample_b_values
    )

    # 4. 차분 벡터의 최소 표본 관측치 수(2개 이상) 충족 여부 검증
    _validate_sample_size(differences=differences)

    # 5. 차분 벡터의 위치 모수(중앙값, 평균) 및 영(0) 차분 관측치 개수 산출
    median_diff, mean_diff, non_zero_count, zero_count = _compute_difference_summary(
        differences=differences
    )

    # 6. 모든 차분이 0인 경우(완전 동등 상태) 검정 불능 방어 결과 반환
    if non_zero_count == 0:
        return _build_all_zero_result(
            median_difference=median_diff,
            mean_difference=mean_diff,
            zero_count=zero_count,
            method=method,
            alternative=alternative
        )

    # 7. 지정된 알고리즘('wilcoxon' 또는 'pratt')에 따라 순위합 통계량 및 Z-통계량 산출
    w_plus, w_minus, z_statistic = _calculate_signed_rank_statistics(
        differences=differences,
        method=method,
        alternative=alternative,
        use_continuity_correction=use_continuity_correction
    )

    # 8. 순위 양분 상관계수(Rank-Biserial) 및 표준화 효과 크기(r) 산출
    rank_biserial, effect_size_r = _calculate_non_parametric_effect_sizes(
        w_plus=w_plus,
        w_minus=w_minus,
        z_statistic=z_statistic,
        total_sample_size=len(differences)
    )

    # 9. 표준정규 Z-통계량을 바탕으로 대립가설 방향에 따른 유의확률(p-value) 계산
    p_value: float = _calculate_normal_pvalue(
        z_statistic=z_statistic,
        alternative=alternative
    )

    # 10. 최종 부호순위검정 통계 결과 번들 패키징 및 반환
    return _build_signed_rank_result(
        statistic=w_plus,
        z_statistic=z_statistic,
        p_value=p_value,
        median_difference=median_diff,
        mean_difference=mean_diff,
        rank_biserial=rank_biserial,
        effect_size_r=effect_size_r,
        non_zero_count=non_zero_count,
        zero_count=zero_count,
        method=method,
        alternative=alternative
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_signed_rank_method(method: str) -> None:
    """지정된 부호순위검정 알고리즘의 지원 여부를 검증합니다."""
    if method not in SUPPORTED_SIGNED_RANK_METHODS:
        raise ValueError(
            f"지원하지 않는 부호순위검정 알고리즘입니다: '{method}'. "
            f"지원 알고리즘 목록: {SUPPORTED_SIGNED_RANK_METHODS}"
        )


def _validate_alternative_hypothesis(alternative: str) -> None:
    """대립가설 파라미터가 지원 규격에 부합하는지 검증합니다."""
    if alternative not in SUPPORTED_ALTERNATIVES:
        raise ValueError(
            f"지원하지 않는 대립가설 유형입니다: '{alternative}'. "
            f"지원 목록: {SUPPORTED_ALTERNATIVES}"
        )


def _clean_and_extract_differences(
    sample_a_values: Union[np.ndarray, pd.Series, list],
    sample_b_values: Union[np.ndarray, pd.Series, list]
) -> np.ndarray:
    """두 대응 표본을 1차원 배열로 정제하고 결측을 배제한 유효 차분 벡터를 생성합니다."""
    # 1. 두 입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화
    array_a: np.ndarray = np.ascontiguousarray(sample_a_values, dtype=np.float64).flatten()
    array_b: np.ndarray = np.ascontiguousarray(sample_b_values, dtype=np.float64).flatten()

    # 2. 두 대응 집단 간 관측치 크기 일치 여부 검증
    if len(array_a) != len(array_b):
        raise ValueError(
            f"대응표본 간 표본 크기가 일치하지 않습니다: len(A)={len(array_a)} != len(B)={len(array_b)}"
        )

    # 3. 양 집단 모두 결측치 및 무한대가 없는 동일 인덱스 유효 마스크 추출
    valid_pair_mask: np.ndarray = np.isfinite(array_a) & np.isfinite(array_b)

    # 4. 짝지어진 대응 차분(d = A - B) 벡터 산출
    return array_a[valid_pair_mask] - array_b[valid_pair_mask]


def _validate_sample_size(differences: np.ndarray) -> None:
    """차분 벡터 크기가 검정 최소 요구 표본 수를 충족하는지 검증합니다."""
    if len(differences) < MINIMUM_OBSERVATION_COUNT:
        raise ValueError(
            f"유효 대응 차분 수가 최소 요구치({MINIMUM_OBSERVATION_COUNT}) 미만입니다: {len(differences)}"
        )


def _compute_difference_summary(
    differences: np.ndarray
) -> Tuple[float, float, int, int]:
    """차분 벡터의 표본중앙값, 표본평균, 비영(non-zero) 및 영(zero) 관측치 수를 산출합니다."""
    median_diff: float = float(np.median(differences))
    mean_diff: float = float(np.mean(differences))
    non_zero_mask: np.ndarray = np.abs(differences) > ZERO_DIFFERENCE_EPSILON
    non_zero_count: int = int(np.sum(non_zero_mask))
    zero_count: int = int(len(differences) - non_zero_count)
    return median_diff, mean_diff, non_zero_count, zero_count


def _calculate_signed_rank_statistics(
    differences: np.ndarray,
    method: str,
    alternative: str,
    use_continuity_correction: bool
) -> Tuple[float, float, float]:
    """지정된 알고리즘에 따라 양/음의 순위합 통계량 및 표준정규 Z-통계량을 계산합니다."""
    if method == "wilcoxon":
        return _execute_wilcoxon_signed_rank(
            differences=differences,
            alternative=alternative,
            use_continuity_correction=use_continuity_correction
        )
    elif method == "pratt":
        return _execute_pratt_signed_rank(
            differences=differences,
            alternative=alternative,
            use_continuity_correction=use_continuity_correction
        )


def _execute_wilcoxon_signed_rank(
    differences: np.ndarray,
    alternative: str,
    use_continuity_correction: bool
) -> Tuple[float, float, float]:
    """영(0) 차분을 사전 배제한 고전 Wilcoxon (1945) 부호순위 통계량 및 Z-통계량을 계산합니다."""
    # 1. 영(0) 차분 관측치 사전 제거
    non_zero_differences: np.ndarray = differences[np.abs(differences) > ZERO_DIFFERENCE_EPSILON]
    active_count: float = float(len(non_zero_differences))

    # 2. 절대값 기준 평균 순위(Average Rank) 부여
    ranks: np.ndarray = stats.rankdata(np.abs(non_zero_differences), method="average")
    w_plus: float = float(np.sum(ranks[non_zero_differences > 0.0]))
    w_minus: float = float(np.sum(ranks[non_zero_differences < 0.0]))

    # 3. 귀무가설 하의 기댓값 및 동점(Tie) 보정 분산 계산
    expected_mean: float = active_count * (active_count + 1.0) / 4.0
    tie_correction: float = _compute_tie_variance_correction(ranks=ranks)
    variance: float = (active_count * (active_count + 1.0) * (2.0 * active_count + 1.0) - tie_correction) / 24.0

    # 4. 연속성 보정을 반영한 표준정규 Z-통계량 산출
    z_statistic: float = _compute_z_from_rank_sum(
        w_plus=w_plus,
        expected_mean=expected_mean,
        variance=variance,
        alternative=alternative,
        use_continuity_correction=use_continuity_correction
    )
    return w_plus, w_minus, z_statistic


def _execute_pratt_signed_rank(
    differences: np.ndarray,
    alternative: str,
    use_continuity_correction: bool
) -> Tuple[float, float, float]:
    """영(0) 차분을 순위 산정에 포함하는 개선 Pratt (1959) 부호순위 통계량 및 Z-통계량을 계산합니다."""
    # 1. 영(0) 차분을 포함한 전체 관측치 대상 절대값 평균 순위 부여
    total_count: float = float(len(differences))
    non_zero_mask: np.ndarray = np.abs(differences) > ZERO_DIFFERENCE_EPSILON
    zero_count: float = float(np.sum(~non_zero_mask))

    all_ranks: np.ndarray = stats.rankdata(np.abs(differences), method="average")
    w_plus: float = float(np.sum(all_ranks[differences > ZERO_DIFFERENCE_EPSILON]))
    w_minus: float = float(np.sum(all_ranks[differences < -ZERO_DIFFERENCE_EPSILON]))

    # 2. Pratt (1959) 영 차분 반영 기댓값 및 비영 차분 동점 보정 분산 계산
    expected_mean: float = (total_count * (total_count + 1.0) - zero_count * (zero_count + 1.0)) / 4.0
    non_zero_ranks: np.ndarray = all_ranks[non_zero_mask]
    tie_correction: float = _compute_tie_variance_correction(ranks=non_zero_ranks)
    numerator: float = (
        total_count * (total_count + 1.0) * (2.0 * total_count + 1.0)
        - zero_count * (zero_count + 1.0) * (2.0 * zero_count + 1.0)
        - tie_correction
    )
    variance: float = numerator / 24.0

    # 3. 연속성 보정을 반영한 표준정규 Z-통계량 산출
    z_statistic: float = _compute_z_from_rank_sum(
        w_plus=w_plus,
        expected_mean=expected_mean,
        variance=variance,
        alternative=alternative,
        use_continuity_correction=use_continuity_correction
    )
    return w_plus, w_minus, z_statistic


def _compute_tie_variance_correction(ranks: np.ndarray) -> float:
    """동점 순위(Tied Ranks) 발생에 따른 분산 감쇠 보정항을 계산합니다."""
    _, tie_counts = np.unique(ranks, return_counts=True)
    tied_groups: np.ndarray = tie_counts[tie_counts > 1].astype(np.float64)
    if len(tied_groups) == 0:
        return 0.0
    return float(np.sum(tied_groups ** 3 - tied_groups) / 2.0)


def _compute_z_from_rank_sum(
    w_plus: float,
    expected_mean: float,
    variance: float,
    alternative: str,
    use_continuity_correction: bool
) -> float:
    """양의 순위합 통계량과 기댓값, 분산을 이용해 연속성 보정된 Z-통계량을 계산합니다."""
    if variance <= ZERO_DIFFERENCE_EPSILON:
        return 0.0

    deviation: float = w_plus - expected_mean
    if use_continuity_correction:
        if alternative == "two-sided":
            deviation -= float(np.sign(deviation) * CONTINUITY_CORRECTION_VALUE)
        elif alternative == "greater":
            deviation -= CONTINUITY_CORRECTION_VALUE
        elif alternative == "less":
            deviation += CONTINUITY_CORRECTION_VALUE

    standard_deviation: float = float(np.sqrt(variance))
    return float(deviation / standard_deviation)


def _calculate_non_parametric_effect_sizes(
    w_plus: float,
    w_minus: float,
    z_statistic: float,
    total_sample_size: int
) -> Tuple[float, float]:
    """순위 양분 상관계수(Rank-Biserial)와 표준화 효과 크기(r)를 계산합니다."""
    total_rank_sum: float = w_plus + w_minus
    rank_biserial: float = (
        float((w_plus - w_minus) / total_rank_sum)
        if total_rank_sum > ZERO_DIFFERENCE_EPSILON
        else 0.0
    )
    effect_size_r: float = float(z_statistic / np.sqrt(float(total_sample_size)))
    return rank_biserial, effect_size_r


def _calculate_normal_pvalue(
    z_statistic: float,
    alternative: str
) -> float:
    """표준정규 Z-통계량을 바탕으로 대립가설 방향에 따른 유의확률을 계산합니다."""
    if alternative == "two-sided":
        raw_p_value: float = float(stats.norm.sf(np.abs(z_statistic)) * 2.0)
    elif alternative == "greater":
        raw_p_value = float(stats.norm.sf(z_statistic))
    elif alternative == "less":
        raw_p_value = float(stats.norm.cdf(z_statistic))
    else:
        raw_p_value = 1.0

    return float(np.clip(raw_p_value, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))


def _build_all_zero_result(
    median_difference: float,
    mean_difference: float,
    zero_count: int,
    method: str,
    alternative: str
) -> Dict[str, Any]:
    """모든 대응 차분이 0일 때의 기본 가설 검정 결괏값을 조립합니다."""
    return {
        "statistic": 0.0,
        "z_statistic": 0.0,
        "p_value": 1.0,
        "median_difference": median_difference,
        "mean_difference": mean_difference,
        "rank_biserial": 0.0,
        "effect_size_r": 0.0,
        "non_zero_count": 0,
        "zero_count": zero_count,
        "method": method,
        "alternative": alternative
    }


def _build_signed_rank_result(
    statistic: float,
    z_statistic: float,
    p_value: float,
    median_difference: float,
    mean_difference: float,
    rank_biserial: float,
    effect_size_r: float,
    non_zero_count: int,
    zero_count: int,
    method: str,
    alternative: str
) -> Dict[str, Any]:
    """최종 부호순위검정 통계량 및 메타데이터를 정형화된 딕셔너리로 조립합니다."""
    return {
        "statistic": statistic,
        "z_statistic": z_statistic,
        "p_value": p_value,
        "median_difference": median_difference,
        "mean_difference": mean_difference,
        "rank_biserial": rank_biserial,
        "effect_size_r": effect_size_r,
        "non_zero_count": non_zero_count,
        "zero_count": zero_count,
        "method": method,
        "alternative": alternative
    }