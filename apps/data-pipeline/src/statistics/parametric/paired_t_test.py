from typing import Any, Dict, Literal, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
SUPPORTED_PAIRED_T_METHODS: Tuple[str, ...] = ("student", "nadeau_bengio")    # 지원하는 대응표본 t-검정 알고리즘 목록 (기본, 개선 순서)
SUPPORTED_ALTERNATIVES: Tuple[str, ...] = ("two-sided", "greater", "less")    # 지원하는 대립가설 방향 목록
MINIMUM_OBSERVATION_COUNT: int = 2                                            # 자유도(df>=1) 확보를 위한 최소 표본 관측치 수
ZERO_VARIANCE_EPSILON: float = 1e-12                                          # 분모 제로 나눗셈 방지를 위한 부동소수점 임계치
PROBABILITY_LOWER_BOUND: float = 0.0                                          # 확률값 하한선
PROBABILITY_UPPER_BOUND: float = 1.0                                          # 확률값 상한선


# ==============================================================================
# Public API Functions
# ==============================================================================
def paired_t_test(
    sample_a_values: Union[np.ndarray, pd.Series, list],
    sample_b_values: Union[np.ndarray, pd.Series, list],
    method: Literal["student", "nadeau_bengio"],
    alternative: Literal["two-sided", "greater", "less"],
    test_train_ratio: Optional[float] = None
) -> Dict[str, Any]:
    """동일 관측 대상에 대한 대응 2표본 차분 평균 가설 검정(Paired t-test)을 수행합니다.

    Args:
        sample_a_values: 첫 번째 대응 표본 수치 시퀀스 (예: Baseline 모델 점수).
        sample_b_values: 두 번째 대응 표본 수치 시퀀스 (예: Candidate 모델 점수).
        method: 실행할 검정 알고리즘 ('student': 기본 Paired Student's t, 'nadeau_bengio': 개선 CV 분산보정 t).
        alternative: 대립가설 검정 방향 ('two-sided', 'greater', 'less').
        test_train_ratio: Nadeau-Bengio 검정 시 검증셋/훈련셋 크기 비율 (None인 경우 표준 K-Fold인 1 / (K - 1) 자동 적용).

    Returns:
        Dict[str, Any]:
            - statistic: 산출된 t-통계량 (t-stat).
            - p_value: 유의확률 (p-value).
            - degrees_of_freedom: 유효 자유도 (df = N - 1).
            - mean_difference: 대응 차분 표본평균 (mean(A - B)).
            - standard_error: 적용된 표준오차 (SE).
            - cohen_dz: 대응표본 효과 크기 (Cohen's dz = mean_diff / std_diff).
            - variance_correction_factor: 적용된 분산 보정 승수.
            - method: 실행된 알고리즘 명칭.
            - alternative: 검정 방향.

    Raises:
        ValueError: 지원하지 않는 method, alternative 또는 표본 크기 불일치 및 부족 시 발생.
    """
    # 1. 대응표본 t-검정 알고리즘 매개변수 유효성 검증
    _validate_paired_t_method(method=method)

    # 2. 대립가설 검정 방향 매개변수 유효성 검증
    _validate_alternative_hypothesis(alternative=alternative)

    # 3. 두 대응 표본의 길이를 대조하고 결측을 배제한 유효 차분 벡터(d = A - B) 추출
    differences: np.ndarray = _clean_and_extract_differences(
        sample_a_values=sample_a_values,
        sample_b_values=sample_b_values
    )

    # 4. 차분 벡터의 최소 표본 관측치 수(2개 이상) 충족 여부 검증
    _validate_sample_size(differences=differences)

    # 5. 차분 표본평균, 비편향 표준오차(SE), 표본표준편차, 유효 자유도 산출
    mean_diff, standard_error, sample_std, degrees_of_freedom = _compute_difference_moments(
        differences=differences
    )

    # 6. 표본 분산이 0에 수렴하는 경우 분산 제로 판정 결과 반환
    if standard_error <= ZERO_VARIANCE_EPSILON:
        return _build_zero_variance_result(
            mean_diff=mean_diff,
            degrees_of_freedom=degrees_of_freedom,
            method=method,
            alternative=alternative
        )

    # 7. 제2종 오류 감사(type2_error_control)와의 연계를 위한 Cohen's dz 효과 크기 산출
    cohen_dz: float = _calculate_cohens_dz(
        mean_diff=mean_diff,
        sample_std=sample_std
    )

    # 8. 지정된 알고리즘 엔진(student 또는 nadeau_bengio)에 따른 t-통계량 및 보정 표준오차 산출
    t_statistic, effective_se, correction_factor = _calculate_t_statistic(
        mean_diff=mean_diff,
        sample_std=sample_std,
        standard_error=standard_error,
        sample_size=len(differences),
        method=method,
        test_train_ratio=test_train_ratio
    )

    # 9. t-통계량과 자유도를 바탕으로 대립가설 검정 방향에 따른 p-value 계산
    p_value: float = _calculate_t_pvalue(
        t_statistic=t_statistic,
        degrees_of_freedom=degrees_of_freedom,
        alternative=alternative
    )

    # 10. 최종 대응표본 t-검정 통계 결과 번들 패키징 및 반환
    return _build_paired_t_result(
        statistic=t_statistic,
        p_value=p_value,
        degrees_of_freedom=degrees_of_freedom,
        mean_difference=mean_diff,
        standard_error=effective_se,
        cohen_dz=cohen_dz,
        variance_correction_factor=correction_factor,
        method=method,
        alternative=alternative
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_paired_t_method(method: str) -> None:
    """지정된 대응표본 t-검정 알고리즘의 지원 여부를 검증합니다."""
    if method not in SUPPORTED_PAIRED_T_METHODS:
        raise ValueError(
            f"지원하지 않는 대응표본 t-검정 알고리즘입니다: '{method}'. "
            f"지원 알고리즘 목록: {SUPPORTED_PAIRED_T_METHODS}"
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
    """차분 벡터 크기가 t-검정 최소 요구 표본 수를 충족하는지 검증합니다."""
    if len(differences) < MINIMUM_OBSERVATION_COUNT:
        raise ValueError(
            f"유효 대응 차분 수가 최소 요구치({MINIMUM_OBSERVATION_COUNT}) 미만입니다: {len(differences)}"
        )


def _compute_difference_moments(
    differences: np.ndarray
) -> Tuple[float, float, float, int]:
    """차분 표본평균, 비편향 표준오차(SE), 표본표준편차, 유효 자유도를 산출합니다."""
    # 1. 표본 크기 및 유효 자유도(df = N - 1) 계산
    sample_size: int = len(differences)
    degrees_of_freedom: int = sample_size - 1

    # 2. 차분 벡터의 표본평균 산출
    mean_diff: float = float(np.mean(differences))

    # 3. 비편향 표본표준편차(ddof=1) 및 표준오차(SE) 계산
    sample_std: float = float(np.std(differences, ddof=1))
    standard_error: float = float(sample_std / np.sqrt(sample_size))

    return mean_diff, standard_error, sample_std, degrees_of_freedom


def _calculate_cohens_dz(mean_diff: float, sample_std: float) -> float:
    """대응표본 표준화 효과 크기인 Cohen's dz를 계산합니다."""
    denominator: float = max(sample_std, ZERO_VARIANCE_EPSILON)
    return float(mean_diff / denominator)


def _resolve_test_train_ratio(
    test_train_ratio: Optional[float],
    sample_size: int
) -> float:
    """Nadeau-Bengio 보정을 위한 검증셋/훈련셋 크기 비율을 결정합니다."""
    # 1. 명시적으로 전달된 비율이 있는 경우 양수 여부 검증 후 사용
    if test_train_ratio is not None:
        if test_train_ratio <= 0.0:
            raise ValueError(f"test_train_ratio는 0보다 커야 합니다: {test_train_ratio}")
        return float(test_train_ratio)

    # 2. 미지정 시 표준 K-Fold 비율(1 / (K - 1)) 산출: K = sample_size
    return float(1.0 / (float(sample_size) - 1.0))


def _calculate_t_statistic(
    mean_diff: float,
    sample_std: float,
    standard_error: float,
    sample_size: int,
    method: str,
    test_train_ratio: Optional[float]
) -> Tuple[float, float, float]:
    """지정된 알고리즘 모드에 따라 분기하여 t-통계량과 유효 표준오차를 계산합니다."""
    # 1. Student's t 분기: 독립 가정을 바탕으로 표준 t-통계량 산출
    if method == "student":
        return _execute_student_paired_t(
            mean_diff=mean_diff,
            standard_error=standard_error
        )

    # 2. 개선 Nadeau-Bengio t 분기: CV 데이터 중첩 분산 보정을 반영하여 산출
    elif method == "nadeau_bengio":
        ratio: float = _resolve_test_train_ratio(
            test_train_ratio=test_train_ratio,
            sample_size=sample_size
        )
        return _execute_nadeau_bengio_t(
            mean_diff=mean_diff,
            sample_std=sample_std,
            sample_size=sample_size,
            ratio=ratio
        )


def _execute_student_paired_t(
    mean_diff: float,
    standard_error: float
) -> Tuple[float, float, float]:
    """기본 Paired Student's t-통계량을 계산합니다."""
    # 표준 t-통계량 계산: 차분평균 / 표준오차 (보정 승수 = 1.0)
    t_stat: float = float(mean_diff / standard_error)
    return t_stat, standard_error, 1.0


def _execute_nadeau_bengio_t(
    mean_diff: float,
    sample_std: float,
    sample_size: int,
    ratio: float
) -> Tuple[float, float, float]:
    """Nadeau-Bengio (2003) 수식을 적용하여 CV 데이터 중첩이 보정된 t-통계량을 계산합니다."""
    # 1. Nadeau-Bengio 분산 보정 항 계산: (1 / K + n_test / n_train)
    variance_factor: float = (1.0 / float(sample_size)) + ratio

    # 2. 보정 분산 계수를 반영한 유효 표준오차(SE_corrected) 산출
    effective_se: float = float(sample_std * np.sqrt(variance_factor))
    safe_se: float = max(effective_se, ZERO_VARIANCE_EPSILON)

    # 3. 보정된 표준오차로 차분평균을 나누어 Nadeau-Bengio t-통계량 산출
    t_stat: float = float(mean_diff / safe_se)

    # 4. 표준 분산(1/K) 대비 보정 승수(variance_factor / (1/K)) 계산
    correction_multiplier: float = variance_factor * float(sample_size)

    return t_stat, safe_se, float(correction_multiplier)


def _build_zero_variance_result(
    mean_diff: float,
    degrees_of_freedom: int,
    method: str,
    alternative: str
) -> Dict[str, Any]:
    """대응 차분 벡터의 모든 값이 동일하여 분산이 0일 때의 가설 검정 결괏값을 판정합니다."""
    # 1. 차분 평균이 0과 완벽히 일치하는지 여부에 따라 유의확률 확정 처리
    is_identical_zero: bool = np.isclose(mean_diff, 0.0)

    # 2. 분산 제로 상태의 검정 결과 딕셔너리 번들 반환
    return {
        "statistic": 0.0,
        "p_value": 1.0 if is_identical_zero else 0.0,
        "degrees_of_freedom": float(degrees_of_freedom),
        "mean_difference": mean_diff,
        "standard_error": 0.0,
        "cohen_dz": 0.0,
        "variance_correction_factor": 1.0,
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


def _build_paired_t_result(
    statistic: float,
    p_value: float,
    degrees_of_freedom: int,
    mean_difference: float,
    standard_error: float,
    cohen_dz: float,
    variance_correction_factor: float,
    method: str,
    alternative: str
) -> Dict[str, Any]:
    """최종 대응표본 t-검정 통계량 및 메타데이터를 정형화된 딕셔너리로 조립합니다."""
    return {
        "statistic": statistic,
        "p_value": p_value,
        "degrees_of_freedom": float(degrees_of_freedom),
        "mean_difference": mean_difference,
        "standard_error": standard_error,
        "cohen_dz": cohen_dz,
        "variance_correction_factor": variance_correction_factor,
        "method": method,
        "alternative": alternative
    }