from typing import Any, Dict, Literal, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
SUPPORTED_KS_METHODS: Tuple[str, ...] = ("asymptotic", "permutation")         # 지원하는 2-Sample KS 검정 알고리즘 목록
SUPPORTED_ALTERNATIVES: Tuple[str, ...] = ("two-sided", "greater", "less")    # 지원하는 대립가설 검정 방향 목록
MINIMUM_OBSERVATION_COUNT: int = 2                                            # eCDF 형성을 위한 최소 표본 관측치 수
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05                                      # 귀무가설 채택/기각 판정 기준 유의수준 (alpha)
DEFAULT_N_PERMUTATIONS: int = 1000                                            # 순열 검정(Permutation) 기본 무작위 셔플 반복 횟수
PROBABILITY_LOWER_BOUND: float = 0.0                                          # 확률값 하한선
PROBABILITY_UPPER_BOUND: float = 1.0                                          # 확률값 상한선


# ==============================================================================
# Public API Functions
# ==============================================================================
def two_sample_ks_test(
    sample_1_values: Union[np.ndarray, pd.Series, list],
    sample_2_values: Union[np.ndarray, pd.Series, list],
    method: Literal["asymptotic", "permutation"],
    alternative: Literal["two-sided", "greater", "less"],
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
    random_state: Optional[Union[int, np.random.RandomState, np.random.Generator]] = 42
) -> Dict[str, Any]:
    """두 연속형 독립 표본 간의 분포 동일성을 검정하는 2-Sample Kolmogorov-Smirnov 검정을 수행합니다.

    시계열 인덱스 기준 분할 구간(Reference vs Target) 간 누적분포함수(eCDF)의 최대 절대 거리를 측정합니다.

    Args:
        sample_1_values: 첫 번째 집단 관측치 시퀀스 (예: 기준 구간 Reference).
        sample_2_values: 두 번째 집단 관측치 시퀀스 (예: 비교 대상 구간 Target).
        method: 실행할 검정 알고리즘 ('asymptotic': 점근적 극한분포, 'permutation': 몬테카를로 순열 검정).
        alternative: 대립가설 검정 방향 ('two-sided', 'greater', 'less').
        n_permutations: 순열 검정 시 셔플링 반복 횟수 (기본값: 1000).
        random_state: 순열 검정 난수 생성을 위한 시드 또는 난수 생성기.

    Returns:
        Dict[str, Any]:
            - statistic: KS 검정 통계량 (Supremum eCDF 차이 거리 D).
            - p_value: 산출된 유의확률 (p-value).
            - is_identical_distribution: p >= 0.05 충족 여부 (동일 분포 귀무가설 채택 여부).
            - sample_1_size: 첫 번째 표본의 유효 관측치 수.
            - sample_2_size: 두 번째 표본의 유효 관측치 수.
            - method: 실행된 알고리즘 명칭.
            - alternative: 검정 방향.
            - significance_level: 적용된 유의수준 임계치 (0.05).

    Raises:
        ValueError: 지원하지 않는 method, alternative 또는 표본 크기 부족 시 발생.
    """
    # 1. KS 검정 알고리즘 매개변수 유효성 검증
    _validate_ks_method(method=method)

    # 2. 대립가설 검정 방향 매개변수 유효성 검증
    _validate_alternative(alternative=alternative)

    # 3. 입력 시퀀스를 1차원 float64 배열로 규격화하고 결측치 및 무한대 배제
    clean_sample_1: np.ndarray = _clean_and_flatten_sample(sample_values=sample_1_values)
    clean_sample_2: np.ndarray = _clean_and_flatten_sample(sample_values=sample_2_values)

    # 4. 양 표본의 최소 관측치 수(각 2개 이상) 충족 여부 검증
    _validate_sample_sizes(clean_sample_1=clean_sample_1, clean_sample_2=clean_sample_2)

    # 5. 지정된 알고리즘(asymptotic 또는 permutation)에 따른 D 통계량 및 p-value 산출
    d_statistic, p_value = _calculate_ks_test(
        sample_1=clean_sample_1,
        sample_2=clean_sample_2,
        method=method,
        alternative=alternative,
        n_permutations=n_permutations,
        random_state=random_state
    )

    # 6. 유의수준(alpha = 0.05) 기준 동일 분포 귀무가설 채택(p >= 0.05) 여부 판정
    is_identical: bool = bool(p_value >= DEFAULT_SIGNIFICANCE_LEVEL)

    # 7. 최종 KS 검정 통계 결과 번들 패키징 및 반환
    return _build_ks_result(
        statistic=d_statistic,
        p_value=p_value,
        is_identical_distribution=is_identical,
        sample_1_size=len(clean_sample_1),
        sample_2_size=len(clean_sample_2),
        method=method,
        alternative=alternative
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_ks_method(method: str) -> None:
    """지정된 2표본 KS 검정 알고리즘의 지원 여부를 검증합니다."""
    # 1. 지원 대상 알고리즘 목록 포함 여부 대조 검증
    if method not in SUPPORTED_KS_METHODS:
        raise ValueError(
            f"지원하지 않는 KS 검정 알고리즘입니다: '{method}'. "
            f"지원 목록: {SUPPORTED_KS_METHODS}"
        )


def _validate_alternative(alternative: str) -> None:
    """대립가설 파라미터가 지원 규격에 부합하는지 검증합니다."""
    # 1. 지원 대상 대립가설 방향 포함 여부 검증
    if alternative not in SUPPORTED_ALTERNATIVES:
        raise ValueError(
            f"지원하지 않는 대립가설 유형입니다: '{alternative}'. "
            f"지원 목록: {SUPPORTED_ALTERNATIVES}"
        )


def _clean_and_flatten_sample(sample_values: Union[np.ndarray, pd.Series, list]) -> np.ndarray:
    """입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화하고 결측치 및 무한대를 배제합니다."""
    # 1. 입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화
    flat_array: np.ndarray = np.ascontiguousarray(sample_values, dtype=np.float64).flatten()

    # 2. 유한한 실수(NaN/Inf 제외) 관측치만 필터링하여 반환
    return flat_array[np.isfinite(flat_array)]


def _validate_sample_sizes(clean_sample_1: np.ndarray, clean_sample_2: np.ndarray) -> None:
    """두 표본이 누적분포함수 추정을 위한 최소 관측치 수를 충족하는지 검증합니다."""
    # 1. 첫 번째 표본 크기 검증
    if len(clean_sample_1) < MINIMUM_OBSERVATION_COUNT:
        raise ValueError(
            f"표본 1의 크기가 최소 요구치({MINIMUM_OBSERVATION_COUNT}) 미만입니다: {len(clean_sample_1)}"
        )

    # 2. 두 번째 표본 크기 검증
    if len(clean_sample_2) < MINIMUM_OBSERVATION_COUNT:
        raise ValueError(
            f"표본 2의 크기가 최소 요구치({MINIMUM_OBSERVATION_COUNT}) 미만입니다: {len(clean_sample_2)}"
        )


def _calculate_ks_test(
    sample_1: np.ndarray,
    sample_2: np.ndarray,
    method: str,
    alternative: str,
    n_permutations: int,
    random_state: Optional[Union[int, np.random.RandomState, np.random.Generator]]
) -> Tuple[float, float]:
    """지정된 알고리즘 모드에 따라 분기하여 KS D-통계량과 p-value를 계산합니다."""
    # 1. 점근적(Asymptotic) 분포 분기: 극한 분포 근사를 통한 고속 산출
    if method == "asymptotic":
        return _execute_asymptotic_ks(
            sample_1=sample_1,
            sample_2=sample_2,
            alternative=alternative
        )

    # 2. 순열(Permutation) 분기: 몬테카를로 셔플링을 통한 비모수 정밀 p-value 산출
    elif method == "permutation":
        return _execute_permutation_ks(
            sample_1=sample_1,
            sample_2=sample_2,
            alternative=alternative,
            n_permutations=n_permutations,
            random_state=random_state
        )

    raise ValueError(f"지원하지 않는 KS 검정 알고리즘입니다: {method}")


def _execute_asymptotic_ks(
    sample_1: np.ndarray,
    sample_2: np.ndarray,
    alternative: str
) -> Tuple[float, float]:
    """SciPy 라이브러리 엔진을 호출하여 점근적(Asymptotic) 2-Sample KS 검정을 집행합니다."""
    # 1. SciPy ks_2samp 점근 근사(method='asymp') 실행
    result = stats.ks_2samp(
        data1=sample_1,
        data2=sample_2,
        alternative=alternative,
        method="asymp"
    )

    # 2. 통계량 및 확률 유효 구간 [0.0, 1.0] 클리핑
    safe_p_value: float = float(np.clip(result.pvalue, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))
    return float(result.statistic), safe_p_value


def _execute_permutation_ks(
    sample_1: np.ndarray,
    sample_2: np.ndarray,
    alternative: str,
    n_permutations: int,
    random_state: Optional[Union[int, np.random.RandomState, np.random.Generator]]
) -> Tuple[float, float]:
    """관측치 풀을 무작위 셔플링하여 귀무가설 하의 경험적 귀무분포로부터 순열 p-value를 계산합니다."""
    # 1. 관측된 표본의 실측 KS D-통계량 산출
    observed_result = stats.ks_2samp(
        data1=sample_1,
        data2=sample_2,
        alternative=alternative,
        method="asymp"
    )
    observed_d: float = float(observed_result.statistic)

    # 2. 난수 생성기 초기화 및 두 표본 병합 풀 생성
    rng: np.random.Generator = np.random.default_rng(random_state)
    pooled_samples: np.ndarray = np.concatenate([sample_1, sample_2])
    sample_1_size: int = len(sample_1)

    # 3. 몬테카를로 순열 반복 수행 및 귀무분포 통계량 집계
    permuted_statistics: np.ndarray = np.empty(n_permutations, dtype=np.float64)
    for index in range(n_permutations):
        shuffled_pool: np.ndarray = rng.permutation(pooled_samples)
        perm_sample_1: np.ndarray = shuffled_pool[:sample_1_size]
        perm_sample_2: np.ndarray = shuffled_pool[sample_1_size:]

        perm_result = stats.ks_2samp(
            data1=perm_sample_1,
            data2=perm_sample_2,
            alternative=alternative,
            method="asymp"
        )
        permuted_statistics[index] = perm_result.statistic

    # 4. 실측 통계량 이상의 극단치 발생 비율(비편향 순열 p-value) 계산: (극단치 수 + 1) / (N + 1)
    extreme_count: int = int(np.sum(permuted_statistics >= observed_d))
    permutation_p_value: float = float((extreme_count + 1.0) / (float(n_permutations) + 1.0))
    safe_p_value: float = float(np.clip(permutation_p_value, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))

    return observed_d, safe_p_value


def _build_ks_result(
    statistic: float,
    p_value: float,
    is_identical_distribution: bool,
    sample_1_size: int,
    sample_2_size: int,
    method: str,
    alternative: str
) -> Dict[str, Any]:
    """최종 2-Sample KS 검정 통계량 및 메타데이터를 정형화된 딕셔너리로 조립합니다."""
    # 1. 최종 검정 결과 딕셔너리 번들 조립 및 반환
    return {
        "statistic": statistic,
        "p_value": p_value,
        "is_identical_distribution": is_identical_distribution,
        "sample_1_size": sample_1_size,
        "sample_2_size": sample_2_size,
        "method": method,
        "alternative": alternative,
        "significance_level": DEFAULT_SIGNIFICANCE_LEVEL
    }