from typing import Any, Dict, Literal, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_POPULATION_MEAN: float = 0.0                                              # 귀무가설(H0) 기준 모평균 기본값
SUPPORTED_ONE_T_METHODS: Tuple[str, ...] = ("student", "johnson")                 # 지원하는 1표본 t-검정 알고리즘 목록 (기본, 개선 순서)
SUPPORTED_ALTERNATIVES: Tuple[str, ...] = ("two-sided", "greater", "less")        # 지원하는 대립가설 방향 목록
MINIMUM_OBSERVATION_COUNT: int = 2                                                # 1·2차 적률(평균, 분산) 산출 및 자유도(df>=1) 확보를 위한 최소 표본 수
MINIMUM_SKEWNESS_OBSERVATION_COUNT: int = 3                                       # 3차 적률(비편향 왜도) 산출을 위한 수학적 최소 관측치 수
ZERO_VARIANCE_EPSILON: float = 1e-12                                              # 분모 제로 나눗셈 방지를 위한 부동소수점 임계치
PROBABILITY_LOWER_BOUND: float = 0.0                                              # 확률값 하한선
PROBABILITY_UPPER_BOUND: float = 1.0                                              # 확률값 상한선
SUPPORTED_SKEWNESS_METHODS: Tuple[str, ...] = ("moment", "median", "quantile")    # 지원하는 표본 왜도 산출 알고리즘 목록
DEFAULT_SKEWNESS_METHOD: str = "moment"                                           # 기본 왜도 산출 방식


# ==============================================================================
# Public API Functions
# ==============================================================================
def one_sample_t_test(
    sample_values: Union[np.ndarray, pd.Series, list],
    method: Literal["student", "johnson"],
    alternative: Literal["two-sided", "greater", "less"],
    population_mean: float = DEFAULT_POPULATION_MEAN
) -> Dict[str, Any]:
    """단일 표본에 대해 모평균 가설 검정(1-Sample t-test)을 수행합니다.

    Args:
        sample_values: 가설 검정 대상 1차원 수치 배열 또는 시퀀스.
        method: 실행할 검정 알고리즘 ('student': 기본 Student's t, 'johnson': 개선 왜도 보정 t).
        alternative: 대립가설 검정 방향 ('two-sided', 'greater', 'less').
        population_mean: 귀무가설(H0)의 기준 모평균 (기본값: 0.0).

    Returns:
        Dict[str, Any]:
            - statistic: t-통계량 (t-stat).
            - p_value: 유의확률 (p-value).
            - degrees_of_freedom: 유효 자유도 (df = N - 1).
            - sample_mean: 표본 평균.
            - sample_standard_error: 표본 표준오차 (SE).
            - skewness: 적용된 표본 왜도 수치 (student인 경우 0.0).
            - method: 실행된 알고리즘 명칭.
            - alternative: 검정 방향.

    Raises:
        ValueError: 지원하지 않는 method, alternative 또는 표본 크기 부족 시 발생.
    """
    # 1. 1표본 t-검정 알고리즘 매개변수 유효성 검증
    _validate_one_t_method(method=method)

    # 2. 대립가설 검정 방향 매개변수 유효성 검증
    _validate_alternative_hypothesis(alternative=alternative)

    # 3. 입력 시퀀스를 1차원 float64 배열로 정제하고 결측치 및 무한대 배제
    clean_sample: np.ndarray = _clean_and_flatten_sample(sample_values=sample_values)

    # 4. 선택된 알고리즘에 따른 최소 표본 관측치 수 충족 여부 검증
    _validate_sample_size(clean_sample=clean_sample, method=method)

    # 5. 기본 표본 적률(평균, 표준오차, 표준편차, 자유도) 산출
    sample_mean, standard_error, sample_std, degrees_of_freedom = _compute_sample_moments(
        clean_sample=clean_sample
    )

    # 6. 표본 분산이 0에 수렴하는 경우 분산 제로 판정 결과 반환
    if standard_error <= ZERO_VARIANCE_EPSILON:
        return _build_zero_variance_result(
            sample_mean=sample_mean,
            population_mean=population_mean,
            degrees_of_freedom=degrees_of_freedom,
            method=method,
            alternative=alternative
        )

    # 7. 지정된 알고리즘 엔진(student 또는 johnson)에 따른 t-통계량 및 적용 왜도 산출
    t_statistic, applied_skewness = _calculate_t_statistic(
        clean_sample=clean_sample,
        sample_mean=sample_mean,
        population_mean=population_mean,
        standard_error=standard_error,
        sample_std=sample_std,
        method=method
    )

    # 8. t-통계량과 자유도를 바탕으로 대립가설 검정 방향에 따른 p-value 계산
    p_value: float = _calculate_t_pvalue(
        t_statistic=t_statistic,
        degrees_of_freedom=degrees_of_freedom,
        alternative=alternative
    )

    # 9. 최종 1표본 t-검정 통계 결과 번들 패키징 및 반환
    return _build_one_t_result(
        statistic=t_statistic,
        p_value=p_value,
        degrees_of_freedom=degrees_of_freedom,
        sample_mean=sample_mean,
        sample_standard_error=standard_error,
        skewness=applied_skewness,
        method=method,
        alternative=alternative
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _validate_one_t_method(method: str) -> None:
    """지정된 1표본 t-검정 알고리즘의 지원 여부를 검증합니다."""
    # 1. 지원 대상 알고리즘 목록 포함 여부 대조 검증
    if method not in SUPPORTED_ONE_T_METHODS:
        raise ValueError(
            f"지원하지 않는 1표본 t-검정 알고리즘입니다: '{method}'. "
            f"지원 알고리즘 목록: {SUPPORTED_ONE_T_METHODS}"
        )


def _validate_alternative_hypothesis(alternative: str) -> None:
    """대립가설 파라미터가 지원 규격에 부합하는지 검증합니다."""
    # 1. 지원 대상 대립가설 방향 포함 여부 검증
    if alternative not in SUPPORTED_ALTERNATIVES:
        raise ValueError(
            f"지원하지 않는 대립가설 유형입니다: '{alternative}'. "
            f"지원 목록: {SUPPORTED_ALTERNATIVES}"
        )


def _clean_and_flatten_sample(sample_values: Union[np.ndarray, pd.Series, list]) -> np.ndarray:
    """입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화하고 결측치를 배제합니다."""
    # 1. 입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화
    flat_array: np.ndarray = np.ascontiguousarray(sample_values, dtype=np.float64).flatten()

    # 2. 유한한 실수(NaN/Inf 제외) 관측치만 필터링하여 반환
    return flat_array[np.isfinite(flat_array)]


def _validate_sample_size(clean_sample: np.ndarray, method: str) -> None:
    """선택된 알고리즘 모드에 맞춰 최소 유효 표본 크기를 검증합니다."""
    sample_size: int = len(clean_sample)

    # 1. 기본 Student's t-검정을 위한 최소 요구 관측치 수(2개) 검증
    if sample_size < MINIMUM_OBSERVATION_COUNT:
        raise ValueError(
            f"표본 크기가 최소 요구치({MINIMUM_OBSERVATION_COUNT}) 미만입니다: {sample_size}"
        )

    # 2. 3차 적률(왜도) 보정을 위한 수학적 최소 관측치 수(3개) 검증
    if method == "johnson" and sample_size < MINIMUM_SKEWNESS_OBSERVATION_COUNT:
        raise ValueError(
            f"Johnson 왜도 보정 t-검정을 위한 표본 크기가 최소 요구치({MINIMUM_SKEWNESS_OBSERVATION_COUNT}) 미만입니다: {sample_size}"
        )


def _compute_sample_moments(
    clean_sample: np.ndarray
) -> Tuple[float, float, float, int]:
    """기본 표본 적률인 표본평균, 비편향 표준오차(SE), 표본표준편차, 유효 자유도를 산출합니다."""
    # 1. 표본 크기 및 유효 자유도(df = N - 1) 계산
    sample_size: int = len(clean_sample)
    degrees_of_freedom: int = sample_size - 1

    # 2. 1차 적률인 표본평균 산출
    sample_mean: float = float(np.mean(clean_sample))

    # 3. 비편향 표본표준편차(ddof=1) 및 표준오차(SE) 계산
    sample_std: float = float(np.std(clean_sample, ddof=1))
    standard_error: float = float(sample_std / np.sqrt(sample_size))

    return sample_mean, standard_error, sample_std, degrees_of_freedom


def _calculate_sample_skewness(
    clean_sample: np.ndarray,
    method: str = "moment"
) -> float:
    """정제된 표본 관측치로부터 적률, 중위수, 분위수 기반 왜도(Skewness)를 산출합니다."""
    # 1. 왜도 산출 알고리즘 지원 여부 검증
    if method not in SUPPORTED_SKEWNESS_METHODS:
        raise ValueError(
            f"지원하지 않는 왜도 산출 알고리즘입니다: '{method}'. "
            f"지원 목록: {SUPPORTED_SKEWNESS_METHODS}"
        )

    # 2. 최소 표본 크기 미달 시 0.0 반환
    if len(clean_sample) < MINIMUM_SKEWNESS_OBSERVATION_COUNT:
        return 0.0

    # 3. 3차 중심 적률 기반 Fisher-Pearson 비편향 왜도 산출 (표준 모수적 왜도)
    if method == "moment":
        return float(stats.skew(clean_sample, bias=False))

    # 4. Pearson 제2 중위수 기반 왜도 산출: 3 * (Mean - Median) / Std
    if method == "median":
        sample_mean: float = float(np.mean(clean_sample))
        sample_median: float = float(np.median(clean_sample))
        sample_std: float = float(np.std(clean_sample, ddof=1))
        if sample_std <= ZERO_VARIANCE_EPSILON:
            return 0.0
        return float(3.0 * (sample_mean - sample_median) / sample_std)

    # 5. Bowley 사분위수 기반 왜도 산출: ((Q3 - Q2) - (Q2 - Q1)) / (Q3 - Q1)
    first_quartile, median_value, third_quartile = np.percentile(clean_sample, [25.0, 50.0, 75.0])
    interquartile_range: float = third_quartile - first_quartile
    if interquartile_range <= ZERO_VARIANCE_EPSILON:
        return 0.0
    return float(((third_quartile - median_value) - (median_value - first_quartile)) / interquartile_range)


def _calculate_t_statistic(
    clean_sample: np.ndarray,
    sample_mean: float,
    population_mean: float,
    standard_error: float,
    sample_std: float,
    method: str
) -> Tuple[float, float]:
    """지정된 알고리즘 모드에 따라 분기하여 t-통계량과 적용 왜도를 계산합니다."""
    # 1. Student's t 분기: 왜도 연산 오버헤드 없이 표준 t-통계량 산출
    if method == "student":
        t_stat = _execute_student_t(
            sample_mean=sample_mean,
            population_mean=population_mean,
            standard_error=standard_error
        )
        return t_stat, 0.0

    # 2. Johnson t 분기: 독립 왜도 함수를 호출하여 왜도 계산 후 보정 통계량 산출
    elif method == "johnson":
        sample_skewness = _calculate_sample_skewness(clean_sample=clean_sample, method="moment")
        t_stat = _execute_johnson_t(
            sample_mean=sample_mean,
            population_mean=population_mean,
            standard_error=standard_error,
            sample_std=sample_std,
            sample_skewness=sample_skewness,
            sample_size=len(clean_sample)
        )
        return t_stat, sample_skewness


def _execute_student_t(
    sample_mean: float,
    population_mean: float,
    standard_error: float
) -> float:
    """기본 Student's t-통계량을 계산합니다."""
    # 1. 표준 Student's t-통계량 계산: (표본평균 - 기준모평균) / 표준오차
    return float((sample_mean - population_mean) / standard_error)


def _execute_johnson_t(
    sample_mean: float,
    population_mean: float,
    standard_error: float,
    sample_std: float,
    sample_skewness: float,
    sample_size: int
) -> float:
    """Johnson (1978) 수식을 적용하여 비대칭 왜도가 보정된 t-통계량을 계산합니다."""
    # 1. 기준 모평균과의 원천 차분 계산
    difference: float = sample_mean - population_mean
    size_float: float = float(sample_size)
    standard_deviation: float = max(sample_std, ZERO_VARIANCE_EPSILON)

    # 2. 왜도 및 표본 크기를 반영한 1차 보정항 계산: (Skewness * s) / (6 * n)
    term1: float = (sample_skewness * standard_deviation) / (6.0 * size_float)

    # 3. 차분 제곱을 결합한 2차 비대칭 보정항 계산: (Skewness / (3 * s * n)) * (diff^2)
    term2: float = (sample_skewness / (3.0 * standard_deviation * size_float)) * (difference ** 2)

    # 4. 보정된 분자를 표준오차로 나누어 Johnson's 왜도 보정 t-통계량 산출
    adjusted_difference: float = difference + term1 + term2
    return float(adjusted_difference / standard_error)


def _build_zero_variance_result(
    sample_mean: float,
    population_mean: float,
    degrees_of_freedom: int,
    method: str,
    alternative: str
) -> Dict[str, Any]:
    """표본 내 모든 관측값이 동일하여 분산이 0일 때의 가설 검정 결괏값을 판정합니다."""
    # 1. 표본평균과 기준모평균 일치 여부에 따라 유의확률 확정 처리
    is_identical_to_popmean: bool = np.isclose(sample_mean, population_mean)

    # 2. 분산 제로 상태의 검정 결과 딕셔너리 번들 반환
    return {
        "statistic": 0.0,
        "p_value": 1.0 if is_identical_to_popmean else 0.0,
        "degrees_of_freedom": float(degrees_of_freedom),
        "sample_mean": sample_mean,
        "sample_standard_error": 0.0,
        "skewness": 0.0,
        "method": method,
        "alternative": alternative
    }


def _calculate_t_pvalue(
    t_statistic: float,
    degrees_of_freedom: int,
    alternative: str
) -> float:
    """t-통계량과 자유도를 바탕으로 대립가설 방향에 따른 유의확률을 계산합니다."""
    # 1. 양측 검정: t-분포 생존함수(sf)의 2배 계산
    if alternative == "two-sided":
        raw_p_value: float = float(stats.t.sf(np.abs(t_statistic), df=degrees_of_freedom) * 2.0)

    # 2. 우측 단측 검정: t-분포 생존함수(sf) 계산
    elif alternative == "greater":
        raw_p_value = float(stats.t.sf(t_statistic, df=degrees_of_freedom))

    # 3. 좌측 단측 검정: t-분포 누적분포함수(cdf) 계산
    elif alternative == "less":
        raw_p_value = float(stats.t.cdf(t_statistic, df=degrees_of_freedom))

    else:
        raw_p_value = 1.0

    # 4. 확률 유효 구간 [0.0, 1.0] 클리핑
    return float(np.clip(raw_p_value, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))


def _build_one_t_result(
    statistic: float,
    p_value: float,
    degrees_of_freedom: int,
    sample_mean: float,
    sample_standard_error: float,
    skewness: float,
    method: str,
    alternative: str
) -> Dict[str, Any]:
    """최종 1표본 t-검정 통계량 및 메타데이터를 정형화된 딕셔너리로 조립합니다."""
    # 1. 최종 검정 결과 딕셔너리 번들 조립 및 반환
    return {
        "statistic": statistic,
        "p_value": p_value,
        "degrees_of_freedom": float(degrees_of_freedom),
        "sample_mean": sample_mean,
        "sample_standard_error": sample_standard_error,
        "skewness": skewness,
        "method": method,
        "alternative": alternative
    }