from typing import Dict, Literal, Tuple, Union
import numpy as np
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
MINIMUM_OBSERVATION_COUNT: int = 3            # 상관계수 t-검정 자유도(df = n - 2) 확보를 위한 최소 표본 크기
ZERO_VARIANCE_EPSILON: float = 1e-12          # 표본 분산이 0에 수렴하여 상관계수 정의가 불가능한지 판정하기 위한 임계치
PERFECT_CORRELATION_EPSILON: float = 1e-12    # |r|이 1.0에 도달하여 t-통계량 분모(1 - r^2)가 0이 되는 현상을 방지하기 위한 수치 임계치


# ==============================================================================
# Public API Functions
# ==============================================================================

def pearson_correlation(
    x_values: Union[np.ndarray, list],
    y_values: Union[np.ndarray, list],
    alternative: Literal["two-sided", "greater", "less"] = None
) -> Dict[str, float]:
    """두 연속형 변수 간의 피어슨 선형 상관계수 및 모수 가설 검정을 수행합니다.

    Args:
        x_values: 첫 번째 수치 시퀀스.
        y_values: 두 번째 수치 시퀀스 (x_values와 길이가 동일해야 함).
        alternative: 대립가설 유형 ('two-sided', 'greater', 'less').

    Returns:
        Dict[str, float]: 
            - correlation: 피어슨 상관계수 (r, [-1.0, 1.0]).
            - statistic: t-통계량 (t-stat).
            - p_value: 유의확률 (p-value).
            - degrees_of_freedom: 자유도 (df = n - 2).
            - sample_size: 결측치를 제외한 유효 관측치 수 (n).

    Raises:
        ValueError: 두 표본의 원본 길이가 일치하지 않거나 alternative 인자가 잘못된 경우 발생.
    """
    # 1. 입력된 대립가설 파라미터가 유효한지 검증
    _validate_alternative_hypothesis(alternative=alternative)

    # 2. 두 시퀀스를 1차원 float64 배열로 규격화하고 동일 인덱스 기준 결측치(NaN/Inf) 동시 제거
    clean_x, clean_y = _clean_and_align_arrays(x_values=x_values, y_values=y_values)
    sample_size: int = len(clean_x)

    # 3. 유효 표본 크기가 최소 요구치(3개) 미만인 경우 자유도 부족으로 기본 결과 반환
    if sample_size < MINIMUM_OBSERVATION_COUNT:
        return _build_insufficient_sample_result(sample_size=sample_size)

    # 4. 각 변수의 표본 표준편차를 산출하고 분산 0 여부 확인
    std_x: float = float(np.std(clean_x, ddof=1))
    std_y: float = float(np.std(clean_y, ddof=1))

    # 5. 둘 중 하나라도 분산이 0인 경우 공분산 정의 불가로 상관계수 0.0 처리
    if std_x <= ZERO_VARIANCE_EPSILON or std_y <= ZERO_VARIANCE_EPSILON:
        return _build_zero_variance_result(sample_size=sample_size)

    # 6. 표본 공분산 및 피어슨 선형 상관계수 r 계산
    mean_x: float = float(np.mean(clean_x))
    mean_y: float = float(np.mean(clean_y))
    covariance: float = float(np.sum((clean_x - mean_x) * (clean_y - mean_y)) / (sample_size - 1))
    r_statistic: float = float(np.clip(covariance / (std_x * std_y), -1.0, 1.0))

    # 7. 유효 자유도(df = n - 2) 및 검정 통계량 t 산출: t = r * sqrt((n - 2) / (1 - r^2))
    degrees_of_freedom: int = sample_size - 2
    t_statistic: float = _calculate_correlation_t_stat(
        correlation=r_statistic,
        degrees_of_freedom=degrees_of_freedom
    )

    # 8. 대립가설 방향에 맞춰 t-분포 기반 p-value 계산
    p_value: float = _calculate_p_value(
        t_statistic=t_statistic,
        degrees_of_freedom=degrees_of_freedom,
        alternative=alternative
    )

    # 9. 최종 산출된 수리통계 결과 딕셔너리 반환
    return {
        "correlation": r_statistic,
        "statistic": t_statistic,
        "p_value": p_value,
        "degrees_of_freedom": float(degrees_of_freedom),
        "sample_size": float(sample_size)
    }


def spearman_correlation(
    x_values: Union[np.ndarray, list],
    y_values: Union[np.ndarray, list],
    alternative: Literal["two-sided", "greater", "less"] = None
) -> Dict[str, float]:
    """두 변수를 비모수 순위(Rank)로 변환한 후 스피어만 순위 상관계수 및 유의성을 검정합니다.

    Args:
        x_values: 첫 번째 수치 시퀀스.
        y_values: 두 번째 수치 시퀀스.
        alternative: 대립가설 유형 ('two-sided', 'greater', 'less').

    Returns:
        Dict[str, float]: pearson_correlation과 동일한 규격의 검정 결과 딕셔너리.
    """
    # 1. 입력된 대립가설 파라미터가 유효한지 검증
    _validate_alternative_hypothesis(alternative=alternative)

    # 2. 두 시퀀스를 float64 배열로 규격화하고 동일 인덱스 결측치 동시 제거
    clean_x, clean_y = _clean_and_align_arrays(x_values=x_values, y_values=y_values)
    sample_size: int = len(clean_x)

    # 3. 유효 표본 크기가 최소 요구치 미만인 경우 기본 결과 반환
    if sample_size < MINIMUM_OBSERVATION_COUNT:
        return _build_insufficient_sample_result(sample_size=sample_size)

    # 4. 두 변수의 원시 수치를 동점 처리(Average)가 반영된 비모수 순위(Rank) 벡터로 변환
    ranked_x: np.ndarray = stats.rankdata(clean_x)
    ranked_y: np.ndarray = stats.rankdata(clean_y)

    # 5. 변환된 순위 벡터에 대해 피어슨 상관계수 연산 수행 및 결과 반환
    return pearson_correlation(
        x_values=ranked_x,
        y_values=ranked_y,
        alternative=alternative
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _validate_alternative_hypothesis(alternative: str) -> None:
    """대립가설 파라미터가 지원 규격에 부합하는지 검증합니다."""
    supported_alternatives: Tuple[str, ...] = ("two-sided", "greater", "less")
    if alternative not in supported_alternatives:
        raise ValueError(
            f"지원하지 않는 대립가설 유형입니다: '{alternative}'. "
            f"지원 목록: {supported_alternatives}"
        )


def _clean_and_align_arrays(
    x_values: Union[np.ndarray, list],
    y_values: Union[np.ndarray, list]
) -> Tuple[np.ndarray, np.ndarray]:
    """두 시퀀스의 길이를 검증하고 결측(NaN/Inf)을 제외한 유효 인덱스 쌍을 추출합니다."""
    array_x: np.ndarray = np.ascontiguousarray(x_values, dtype=np.float64).flatten()
    array_y: np.ndarray = np.ascontiguousarray(y_values, dtype=np.float64).flatten()

    if len(array_x) != len(array_y):
        raise ValueError(
            f"상관분석 대상의 표본 크기가 일치하지 않습니다: "
            f"len(X)={len(array_x)}, len(Y)={len(array_y)}"
        )

    valid_mask: np.ndarray = np.isfinite(array_x) & np.isfinite(array_y)
    return array_x[valid_mask], array_y[valid_mask]


def _build_insufficient_sample_result(sample_size: int) -> Dict[str, float]:
    """표본 수가 부족하여 상관성 검정이 불가능할 때 기본 결과 딕셔너리를 구성합니다."""
    return {
        "correlation": 0.0,
        "statistic": 0.0,
        "p_value": 1.0,
        "degrees_of_freedom": 0.0,
        "sample_size": float(sample_size)
    }


def _build_zero_variance_result(sample_size: int) -> Dict[str, float]:
    """한쪽 변수의 분산이 0이어서 상관계수 정의가 불가능할 때 기본 결과 딕셔너리를 구성합니다."""
    return {
        "correlation": 0.0,
        "statistic": 0.0,
        "p_value": 1.0,
        "degrees_of_freedom": float(max(0, sample_size - 2)),
        "sample_size": float(sample_size)
    }


def _calculate_correlation_t_stat(correlation: float, degrees_of_freedom: int) -> float:
    """상관계수 r과 자유도를 바탕으로 검정 통계량 t를 계산합니다."""
    denominator_squared: float = 1.0 - (correlation ** 2)

    # 완벽한 상관관계(|r| == 1.0)로 인한 분모 0 발생 방어
    if denominator_squared <= PERFECT_CORRELATION_EPSILON:
        return float(np.sign(correlation) * 1e6)

    return float(correlation * np.sqrt(degrees_of_freedom / denominator_squared))


def _calculate_p_value(
    t_statistic: float,
    degrees_of_freedom: int,
    alternative: str
) -> float:
    """t-통계량과 자유도를 바탕으로 대립가설 방향에 따른 유의확률을 계산합니다."""
    if alternative == "two-sided":
        raw_p_value: float = float(stats.t.sf(np.abs(t_statistic), df=degrees_of_freedom) * 2.0)
    elif alternative == "greater":
        raw_p_value = float(stats.t.sf(t_statistic, df=degrees_of_freedom))
    elif alternative == "less":
        raw_p_value = float(stats.t.cdf(t_statistic, df=degrees_of_freedom))
    else:
        raw_p_value = 1.0

    return float(np.clip(raw_p_value, 0.0, 1.0))