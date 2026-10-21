from typing import Any, Dict, Literal, Tuple, Union
import numpy as np
import pandas as pd

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_BIN_COUNT: int = 10                                                     # 기본 분위수 분할 구간(Bin) 개수
MINIMUM_SAMPLE_SIZE: int = 10                                                   # 안정적인 분포 분할 및 분위수 생성을 위한 최소 관측치 수
DEFAULT_EPSILON: float = 1e-4                                                   # 0 빈도 발생 시 나눗셈/로그 연산 붕괴 방지를 위한 라플라스 스무딩 엡실론
PSI_STABLE_THRESHOLD: float = 0.10                                              # 모집단 안정 상태 상한선 (공변량 표류 미감지)
PSI_CRITICAL_THRESHOLD: float = 0.25                                            # 모집단 심각한 표류 상태 하한선 (재학습/피처 배제 필수)
SUPPORTED_BIN_STRATEGIES: Tuple[str, ...] = ("quantile", "uniform")             # 지원하는 히스토그램 구간 분할 전략 목록
DEFAULT_BIN_STRATEGY: str = "quantile"                                          # 기본 구간 분할 방식
ZERO_BOUNDARY_EPSILON: float = 1e-7                                             # 외삽 데이터 포함을 위한 구간 경계 미세 확장치


# ==============================================================================
# Public API Functions
# ==============================================================================
def calculate_psi(
    reference_values: Union[np.ndarray, pd.Series, list],
    target_values: Union[np.ndarray, pd.Series, list],
    num_bins: int = DEFAULT_BIN_COUNT,
    bin_strategy: Literal["quantile", "uniform"] = DEFAULT_BIN_STRATEGY,
    epsilon: float = DEFAULT_EPSILON
) -> Dict[str, Any]:
    """기준 집단(Reference)과 비교 집단(Target) 간의 모집단 안정성 지수(PSI)를 산출합니다.

    시계열 국면 전환 또는 학습/테스트 구간 간 단변량 확률분포의 공변량 표류(Covariate Drift)를 측정합니다.

    Args:
        reference_values: 기준 집단 관측치 시퀀스 (예: 학습 데이터 전반부).
        target_values: 비교 집단 관측치 시퀀스 (예: 학습 데이터 후반부 또는 테스트 데이터).
        num_bins: 분포 분할 구간(Bin) 개수 (기본값: 10).
        bin_strategy: 구간 경계 산출 전략 ('quantile': 동빈도 분위수, 'uniform': 등간격 분할).
        epsilon: 빈도 0 발생 시 0 나눗셈 및 log(0) 방지용 스무딩 상수 (기본값: 1e-4).

    Returns:
        Dict[str, Any]:
            - statistic: 총합 PSI 수치 (표준 인터페이스 호환).
            - psi_value: 총합 PSI(Population Stability Index) 수치.
            - is_stable: PSI < 0.10 충족 여부 (불린).
            - drift_status: 표류 위험 등급 ('STABLE', 'WARNING', 'CRITICAL').
            - bin_edges: 적용된 구간 경계값 배열 (크기: B + 1).
            - reference_proportions: 기준 집단의 구간별 상대도수 비율 배열.
            - target_proportions: 비교 집단의 구간별 상대도수 비율 배열.
            - bin_contributions: 구간별 개별 PSI 기여도 배열.
            - bin_strategy: 적용된 분할 방식.
            - num_bins: 유효 구간 개수.

    Raises:
        ValueError: 지원하지 않는 bin_strategy, num_bins <= 1, epsilon <= 0 또는 표본 크기 부족 시 발생.
    """
    # 1. 분할 전략 및 수치 매개변수 유효성 검증
    _validate_psi_inputs(num_bins=num_bins, bin_strategy=bin_strategy, epsilon=epsilon)

    # 2. 입력 시퀀스를 1차원 float64 배열로 규격화하고 결측치 및 무한대 배제
    clean_reference: np.ndarray = _clean_and_flatten_sample(sample_values=reference_values)
    clean_target: np.ndarray = _clean_and_flatten_sample(sample_values=target_values)

    # 3. 양 표본의 최소 관측치 수 충족 여부 검증
    _validate_sample_sizes(clean_reference=clean_reference, clean_target=clean_target)

    # 4. 기준 집단(Reference) 기반 유효 구간 경계선(Bin Edges) 산출
    bin_edges: np.ndarray = _compute_bin_edges(
        clean_sample=clean_reference,
        num_bins=num_bins,
        bin_strategy=bin_strategy
    )

    # 5. 각 구간별 관측치 상대도수(Proportions) 산출 및 라플라스 스무딩 적용
    ref_proportions, target_proportions = _calculate_proportions(
        clean_reference=clean_reference,
        clean_target=clean_target,
        bin_edges=bin_edges,
        epsilon=epsilon
    )

    # 6. 구간별 PSI 기여도 및 최종 합산 PSI 통계량 산출
    bin_contributions, total_psi = _compute_psi_contributions(
        ref_proportions=ref_proportions,
        target_proportions=target_proportions
    )

    # 7. PSI 임계치(0.10, 0.25) 기준 표류 위험 등급 및 안정성 판정
    drift_status, is_stable = _evaluate_drift_status(psi_value=total_psi)

    # 8. 최종 PSI 분석 결과 번들 조립 및 반환
    return _build_psi_result(
        psi_value=total_psi,
        is_stable=is_stable,
        drift_status=drift_status,
        bin_edges=bin_edges,
        reference_proportions=ref_proportions,
        target_proportions=target_proportions,
        bin_contributions=bin_contributions,
        bin_strategy=bin_strategy,
        num_bins=len(bin_edges) - 1
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_psi_inputs(num_bins: int, bin_strategy: str, epsilon: float) -> None:
    """PSI 산출에 필요한 하이퍼파라미터 규격을 검증합니다."""
    # 1. 구간 분할 전략 지원 여부 검증
    if bin_strategy not in SUPPORTED_BIN_STRATEGIES:
        raise ValueError(
            f"지원하지 않는 구간 분할 전략입니다: '{bin_strategy}'. "
            f"지원 목록: {SUPPORTED_BIN_STRATEGIES}"
        )

    # 2. 최소 구간 개수 유효성 검증
    if num_bins < 2:
        raise ValueError(f"num_bins는 최소 2 이상이어야 합니다: {num_bins}")

    # 3. 라플라스 스무딩 엡실론 양수 조건 검증
    if epsilon <= 0.0:
        raise ValueError(f"epsilon은 0보다 큰 양수여야 합니다: {epsilon}")


def _clean_and_flatten_sample(sample_values: Union[np.ndarray, pd.Series, list]) -> np.ndarray:
    """입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화하고 결측치 및 무한대를 배제합니다."""
    # 1. 입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화
    flat_array: np.ndarray = np.ascontiguousarray(sample_values, dtype=np.float64).flatten()

    # 2. 유한한 실수(NaN/Inf 제외) 관측치만 필터링하여 반환
    return flat_array[np.isfinite(flat_array)]


def _validate_sample_sizes(clean_reference: np.ndarray, clean_target: np.ndarray) -> None:
    """양 표본이 신뢰할 수 있는 분포 추정을 위한 최소 관측치 수를 충족하는지 검증합니다."""
    ref_size: int = len(clean_reference)
    target_size: int = len(clean_target)

    # 1. Reference 표본 크기 검증
    if ref_size < MINIMUM_SAMPLE_SIZE:
        raise ValueError(
            f"Reference 표본 크기가 최소 요구치({MINIMUM_SAMPLE_SIZE}) 미만입니다: {ref_size}"
        )

    # 2. Target 표본 크기 검증
    if target_size < MINIMUM_SAMPLE_SIZE:
        raise ValueError(
            f"Target 표본 크기가 최소 요구치({MINIMUM_SAMPLE_SIZE}) 미만입니다: {target_size}"
        )


def _compute_bin_edges(
    clean_sample: np.ndarray,
    num_bins: int,
    bin_strategy: str
) -> np.ndarray:
    """기준 표본의 분포에 따라 지정된 전략으로 구간 경계선(Bin Edges)을 산출합니다."""
    # 1. Quantile(분위수) 분기: 동빈도 기반 경계선 산출
    if bin_strategy == "quantile":
        return _execute_quantile_bins(clean_sample=clean_sample, num_bins=num_bins)

    # 2. Uniform(등간격) 분기: Min-Max 기반 등간격 경계선 산출
    elif bin_strategy == "uniform":
        return _execute_uniform_bins(clean_sample=clean_sample, num_bins=num_bins)

    raise ValueError(f"지원하지 않는 분할 전략입니다: {bin_strategy}")


def _execute_quantile_bins(clean_sample: np.ndarray, num_bins: int) -> np.ndarray:
    """기준 표본의 동빈도 분위수를 기반으로 고유한 구간 경계선을 생성합니다."""
    # 1. 균등 분위수 생성 (0% ~ 100%)
    quantiles: np.ndarray = np.linspace(0.0, 100.0, num_bins + 1)
    raw_edges: np.ndarray = np.percentile(clean_sample, quantiles)

    # 2. 동일값 집중으로 인한 중복 경계선 병합
    unique_edges: np.ndarray = np.unique(raw_edges)

    # 3. 고유값이 1개인 상수 데이터에 대한 예외 방어 구간 생성
    if len(unique_edges) < 2:
        base_value: float = float(unique_edges[0])
        return np.array([base_value - 1.0, base_value + 1.0], dtype=np.float64)

    return unique_edges


def _execute_uniform_bins(clean_sample: np.ndarray, num_bins: int) -> np.ndarray:
    """기준 표본의 최솟값과 최댓값을 기준으로 등간격 구간 경계선을 생성합니다."""
    min_val: float = float(np.min(clean_sample))
    max_val: float = float(np.max(clean_sample))

    # 1. 표본 분산이 0에 수렴하는 경우 방어 구간 생성
    if np.isclose(min_val, max_val):
        return np.array([min_val - 1.0, max_val + 1.0], dtype=np.float64)

    # 2. 선형 등간격 구간 배열 생성
    return np.linspace(min_val, max_val, num_bins + 1)


def _calculate_proportions(
    clean_reference: np.ndarray,
    clean_target: np.ndarray,
    bin_edges: np.ndarray,
    epsilon: float
) -> Tuple[np.ndarray, np.ndarray]:
    """구간 경계선을 바탕으로 양 표본의 상대도수를 집계하고 라플라스 스무딩을 적용합니다."""
    # 1. Target 집단의 외삽 이상치(Extrapolation)를 포괄하도록 양 끝단 경계선 미세 확장
    extended_edges: np.ndarray = bin_edges.copy()
    extended_edges[0] = min(extended_edges[0], float(np.min(clean_target))) - ZERO_BOUNDARY_EPSILON
    extended_edges[-1] = max(extended_edges[-1], float(np.max(clean_target))) + ZERO_BOUNDARY_EPSILON

    # 2. 각 구간별 표본 빈도수 집계
    ref_counts, _ = np.histogram(clean_reference, bins=extended_edges)
    target_counts, _ = np.histogram(clean_target, bins=extended_edges)

    # 3. 표본 크기로 정규화하여 경험적 확률질량 산출
    ref_freq: np.ndarray = ref_counts / len(clean_reference)
    target_freq: np.ndarray = target_counts / len(clean_target)

    # 4. 빈도 0 구간에 대한 라플라스 스무딩 적용 (0 나눗셈 및 log(0) 방어)
    ref_proportions: np.ndarray = np.where(ref_freq <= 0.0, epsilon, ref_freq)
    target_proportions: np.ndarray = np.where(target_freq <= 0.0, epsilon, target_freq)

    # 5. 스무딩 후 총합이 1.0이 되도록 재정규화
    ref_proportions = ref_proportions / np.sum(ref_proportions)
    target_proportions = target_proportions / np.sum(target_proportions)

    return ref_proportions, target_proportions


def _compute_psi_contributions(
    ref_proportions: np.ndarray,
    target_proportions: np.ndarray
) -> Tuple[np.ndarray, float]:
    """구간별 대칭형 쿨백-라이블러(KLD) 적률 기여도를 계산하고 총합 PSI를 산출합니다."""
    # 1. 구간별 PSI 기여도 계산: (Target - Reference) * ln(Target / Reference)
    bin_contributions: np.ndarray = (target_proportions - ref_proportions) * np.log(
        target_proportions / ref_proportions
    )

    # 2. 전체 구간 기여도 합산 및 음수 부동소수점 오차 방어
    total_psi: float = float(np.sum(bin_contributions))
    safe_psi: float = max(total_psi, 0.0)

    return bin_contributions, safe_psi


def _evaluate_drift_status(psi_value: float) -> Tuple[str, bool]:
    """PSI 수치에 따라 학술/실무 표준 표류 위험 등급과 안정성 여부를 판정합니다."""
    # 1. 안정 구간: PSI < 0.10 (표류 미감지)
    if psi_value < PSI_STABLE_THRESHOLD:
        return "STABLE", True

    # 2. 경고 구간: 0.10 <= PSI < 0.25 (보통 수준 표류)
    elif psi_value < PSI_CRITICAL_THRESHOLD:
        return "WARNING", False

    # 3. 심각 구간: PSI >= 0.25 (치명적 모집단 표류)
    return "CRITICAL", False


def _build_psi_result(
    psi_value: float,
    is_stable: bool,
    drift_status: str,
    bin_edges: np.ndarray,
    reference_proportions: np.ndarray,
    target_proportions: np.ndarray,
    bin_contributions: np.ndarray,
    bin_strategy: str,
    num_bins: int
) -> Dict[str, Any]:
    """최종 PSI 분석 통계량 및 메타데이터를 정형화된 딕셔너리로 패키징합니다."""
    # 1. 결과 딕셔너리 번들 조립 및 반환
    return {
        "statistic": psi_value,
        "psi_value": psi_value,
        "is_stable": is_stable,
        "drift_status": drift_status,
        "bin_edges": bin_edges,
        "reference_proportions": reference_proportions,
        "target_proportions": target_proportions,
        "bin_contributions": bin_contributions,
        "bin_strategy": bin_strategy,
        "num_bins": num_bins
    }