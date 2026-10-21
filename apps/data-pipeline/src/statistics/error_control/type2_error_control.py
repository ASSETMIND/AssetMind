from typing import Any, Dict, Literal, Tuple
import numpy as np
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05                                      # 1종 오류 기준 유의수준 (alpha)
DEFAULT_TARGET_POWER: float = 0.80                                            # 통계적 검정력 표준 벤치마크 (80% Power)
MINIMUM_SAMPLE_SIZE: int = 2                                                  # 자유도(df>=1) 확보를 위한 최소 표본 관측치 수
SUPPORTED_TYPE2_ERROR_METHODS: Tuple[str, ...] = ("normal", "nct")            # 지원하는 2종 오류/검정력 산출 알고리즘 목록
SUPPORTED_ALTERNATIVES: Tuple[str, ...] = ("two-sided", "greater", "less")    # 지원하는 대립가설 방향 목록
PROBABILITY_LOWER_BOUND: float = 0.0                                          # 확률값 하한선
PROBABILITY_UPPER_BOUND: float = 1.0                                          # 확률값 상한선


# ==============================================================================
# Public API Functions
# ==============================================================================
def compute_type2_error(
    effect_size: float,
    sample_size: int,
    alternative: Literal["two-sided", "greater", "less"],
    method: Literal["normal", "nct"],
    alpha: float = DEFAULT_SIGNIFICANCE_LEVEL,
    target_power: float = DEFAULT_TARGET_POWER
) -> Dict[str, Any]:
    """주어진 효과 크기와 표본 수 조건에서 제2종 오류율(beta)과 통계적 검정력(power)을 산출합니다.

    Args:
        effect_size: 관측된 표준화 효과 크기 (Cohen's d 또는 대응표본 Cohen's dz).
        sample_size: 표본 관측치 수 (N, 자유도 = N - 1).
        alternative: 대립가설 검정 방향 ('two-sided', 'greater', 'less').
        method: 검정력 적분 계산 알고리즘 ('normal': 점근 정규근사, 'nct': 비중심 t-분포 정밀해).
        alpha: 1종 오류 유의수준 (기본값: 0.05).
        target_power: 적정 검정력 평가 기준 (기본값: 0.80).

    Returns:
        Dict[str, Any]:
            - beta: 제2종 오류 발생 확률 (위음성 위험도).
            - power: 통계적 검정력 (1 - beta).
            - effect_size: 입력된 효과 크기 (Cohen's d).
            - degrees_of_freedom: 유효 자유도 (df = N - 1).
            - is_power_adequate: 목표 검정력 충족 여부 (power >= target_power).
            - minimum_detectable_effect_size: 목표 검정력(80%) 달성에 필요한 최소 탐지 가능 효과 크기 (MDES).
            - method: 사용된 수리 계산 알고리즘 명칭.

    Raises:
        ValueError: 지원하지 않는 method, alternative 또는 유효 범위를 벗어난 수치 입력 시 발생.
    """
    # 1. 2종 오류 계산 알고리즘 매개변수의 지원 여부 검증
    _validate_type2_method(method=method)

    # 2. 대립가설 검정 방향 매개변수의 유효성 검증
    _validate_alternative_hypothesis(alternative=alternative)

    # 3. 표본 크기, 유의수준(alpha), 목표 검정력의 수치 유효 범위 검증
    _validate_numerical_parameters(
        sample_size=sample_size,
        alpha=alpha,
        target_power=target_power
    )

    # 4. 효과 크기와 표본 크기를 바탕으로 비중심 모수(delta) 및 유효 자유도(df) 산출
    delta, degrees_of_freedom = _compute_distribution_parameters(
        effect_size=effect_size,
        sample_size=sample_size
    )

    # 5. 지정된 알고리즘 엔진을 호출하여 사후 검정력(power) 산출
    power: float = _calculate_statistical_power(
        delta=delta,
        degrees_of_freedom=degrees_of_freedom,
        alpha=alpha,
        alternative=alternative,
        method=method
    )

    # 6. 산출된 검정력을 기반으로 제2종 오류율(beta = 1 - power) 도출
    beta: float = _calculate_beta_error(power=power)

    # 7. 현재 표본 수와 alpha 하에서 목표 검정력을 달성할 수 있는 최소 효과 크기(MDES) 역산
    mdes: float = _calculate_minimum_detectable_effect_size(
        sample_size=sample_size,
        alpha=alpha,
        target_power=target_power,
        alternative=alternative
    )

    # 8. 최종 산출된 통계량, 판정 지표 및 감사 메타데이터 패키징 반환
    return _build_type2_error_result(
        beta=beta,
        power=power,
        effect_size=effect_size,
        degrees_of_freedom=degrees_of_freedom,
        is_power_adequate=bool(power >= target_power),
        mdes=mdes,
        method=method
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_type2_method(method: str) -> None:
    """지정된 2종 오류 계산 알고리즘의 지원 여부를 검증합니다."""
    if method not in SUPPORTED_TYPE2_ERROR_METHODS:
        raise ValueError(
            f"지원하지 않는 2종 오류 계산 알고리즘입니다: '{method}'. "
            f"지원 알고리즘 목록: {SUPPORTED_TYPE2_ERROR_METHODS}"
        )


def _validate_alternative_hypothesis(alternative: str) -> None:
    """대립가설 파라미터가 지원 규격에 부합하는지 검증합니다."""
    if alternative not in SUPPORTED_ALTERNATIVES:
        raise ValueError(
            f"지원하지 않는 대립가설 유형입니다: '{alternative}'. "
            f"지원 목록: {SUPPORTED_ALTERNATIVES}"
        )


def _validate_numerical_parameters(
    sample_size: int,
    alpha: float,
    target_power: float
) -> None:
    """표본 크기와 확률 매개변수들의 수학적 유효 범위를 검증합니다."""
    # 1. 표본 크기의 최소 요구 관측치(2개 이상) 충족 여부 검증
    if sample_size < MINIMUM_SAMPLE_SIZE:
        raise ValueError(
            f"표본 크기가 최소 요구치({MINIMUM_SAMPLE_SIZE}) 미만입니다: {sample_size}"
        )

    # 2. 유의수준 alpha의 개구간 (0.0, 1.0) 존재 여부 검증
    if not (PROBABILITY_LOWER_BOUND < alpha < PROBABILITY_UPPER_BOUND):
        raise ValueError(f"유의수준 alpha는 0과 1 사이의 값이어야 합니다: {alpha}")

    # 3. 목표 검정력(target_power)의 개구간 (0.0, 1.0) 존재 여부 검증
    if not (PROBABILITY_LOWER_BOUND < target_power < PROBABILITY_UPPER_BOUND):
        raise ValueError(f"목표 검정력은 0과 1 사이의 값이어야 합니다: {target_power}")


def _compute_distribution_parameters(
    effect_size: float,
    sample_size: int
) -> Tuple[float, int]:
    """효과 크기와 표본 크기를 결합하여 비중심 모수(delta) 및 유효 자유도를 계산합니다."""
    # 1. 비편향 유효 자유도 계산 (df = N - 1)
    degrees_of_freedom: int = sample_size - 1

    # 2. t-분포 비중심 모수(non-centrality parameter) 계산: delta = d * sqrt(N)
    delta: float = float(effect_size * np.sqrt(sample_size))

    return delta, degrees_of_freedom


def _calculate_statistical_power(
    delta: float,
    degrees_of_freedom: int,
    alpha: float,
    alternative: str,
    method: str
) -> float:
    """지정된 알고리즘 모드에 따라 분기하여 통계적 검정력(Power)을 계산합니다."""
    if method == "normal":
        return _compute_normal_power(
            delta=delta,
            alpha=alpha,
            alternative=alternative
        )
    elif method == "nct":
        return _compute_nct_power(
            delta=delta,
            degrees_of_freedom=degrees_of_freedom,
            alpha=alpha,
            alternative=alternative
        )


def _compute_normal_power(
    delta: float,
    alpha: float,
    alternative: str
) -> float:
    """표준정규분포 분위수를 활용한 점근적 근사 검정력을 산출합니다."""
    if alternative == "two-sided":
        z_crit: float = float(stats.norm.ppf(1.0 - alpha / 2.0))
        raw_power: float = float(
            stats.norm.sf(z_crit - delta) + stats.norm.cdf(-z_crit - delta)
        )
    elif alternative == "greater":
        z_crit = float(stats.norm.ppf(1.0 - alpha))
        raw_power = float(stats.norm.sf(z_crit - delta))
    else:
        z_crit = float(stats.norm.ppf(alpha))
        raw_power = float(stats.norm.cdf(z_crit - delta))

    # 3. 확률 닫힌구간 [0.0, 1.0] 클리핑
    return float(np.clip(raw_power, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))


def _compute_nct_power(
    delta: float,
    degrees_of_freedom: int,
    alpha: float,
    alternative: str
) -> float:
    """비중심 t-분포(Non-central Student's t)를 직접 적분하여 소표본 정밀 검정력을 산출합니다."""
    # 1. 대립가설 방향별 중심 t-분포 기준 기각역 임계치(Critical value) 도출
    if alternative == "two-sided":
        t_crit: float = float(stats.t.ppf(1.0 - alpha / 2.0, df=degrees_of_freedom))
        # 2. 비중심 t-분포 하에서 양측 기각역에 위치할 누적 확률(Power) 적분
        raw_power: float = float(
            stats.nct.sf(t_crit, df=degrees_of_freedom, nc=delta)
            + stats.nct.cdf(-t_crit, df=degrees_of_freedom, nc=delta)
        )
    elif alternative == "greater":
        t_crit = float(stats.t.ppf(1.0 - alpha, df=degrees_of_freedom))
        # 2. 우측 단측 기각역에 위치할 생존 확률(Survival function) 적분
        raw_power = float(stats.nct.sf(t_crit, df=degrees_of_freedom, nc=delta))
    else:
        t_crit = float(stats.t.ppf(alpha, df=degrees_of_freedom))
        # 2. 좌측 단측 기각역에 위치할 누적 분포 확률(CDF) 적분
        raw_power = float(stats.nct.cdf(t_crit, df=degrees_of_freedom, nc=delta))

    # 3. 확률 정의 구역 [0.0, 1.0] 내로 클리핑하여 수치 안정성 확보
    return float(np.clip(raw_power, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))


def _calculate_beta_error(power: float) -> float:
    """검정력으로부터 제2종 오류 확률(beta = 1 - power)을 산출합니다."""
    return float(np.clip(1.0 - power, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))


def _calculate_minimum_detectable_effect_size(
    sample_size: int,
    alpha: float,
    target_power: float,
    alternative: str
) -> float:
    """목표 검정력을 만족하기 위해 표본 수가 감지할 수 있는 최소 효과 크기(MDES)를 역산합니다."""
    # 1. 대립가설에 따른 임계 Z-값 도출
    z_alpha: float = (
        float(stats.norm.ppf(1.0 - alpha / 2.0))
        if alternative == "two-sided"
        else float(stats.norm.ppf(1.0 - alpha))
    )

    # 2. 목표 검정력에 도달하기 위한 Z-값 도출
    z_power: float = float(stats.norm.ppf(target_power))

    # 3. 목표 검정력 비중심 모수를 표본 크기 제곱근으로 나누어 최소 효과 크기 산출
    return float((z_alpha + z_power) / np.sqrt(sample_size))


def _build_type2_error_result(
    beta: float,
    power: float,
    effect_size: float,
    degrees_of_freedom: int,
    is_power_adequate: bool,
    mdes: float,
    method: str
) -> Dict[str, Any]:
    """최종 제2종 오류 감사 결과 및 메타데이터를 정형화된 딕셔너리로 조립합니다."""
    return {
        "beta": beta,
        "power": power,
        "effect_size": effect_size,
        "degrees_of_freedom": degrees_of_freedom,
        "is_power_adequate": is_power_adequate,
        "minimum_detectable_effect_size": mdes,
        "method": method
    }