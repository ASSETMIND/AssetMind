from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_WASSERSTEIN_THRESHOLD: float = 0.15                                     # 분포 표류 감지를 위한 바서슈타인 거리 학술/실무 기본 임계치
MINIMUM_OBSERVATION_COUNT: int = 2                                              # 1차원 연속형 분포 거리 산출을 위한 최소 표본 관측치 수


# ==============================================================================
# Public API Functions
# ==============================================================================
def calculate_wasserstein_distance(
    reference_values: Union[np.ndarray, pd.Series, list],
    target_values: Union[np.ndarray, pd.Series, list],
    threshold: float = DEFAULT_WASSERSTEIN_THRESHOLD
) -> Dict[str, Any]:
    """기준 집단(Reference)과 비교 집단(Target) 간의 1차 바서슈타인 거리(Wasserstein Distance)를 산출합니다.

    두 확률분포를 동일하게 변환하는 데 필요한 최소 물리적 운송 비용(Earth Mover's Distance)을 측정하여
    시계열 국면 전환 및 학습/테스트 구간 간의 구조적 공변량 표류(Covariate Shift)를 감지합니다.

    Args:
        reference_values: 기준 집단 관측치 시퀀스 (예: 학습 데이터 전반부).
        target_values: 비교 대상 집단 관측치 시퀀스 (예: 학습 데이터 후반부 또는 테스트 데이터).
        threshold: 공변량 표류 판정 바서슈타인 거리 임계치 (기본값: 0.15).

    Returns:
        Dict[str, Any]:
            - statistic: 산출된 바서슈타인 거리 통계량.
            - wasserstein_distance: 바서슈타인 거리(Wasserstein Distance) 수치.
            - is_stable: distance <= threshold 충족 여부 (불린).
            - sample_1_size: 첫 번째 표본의 유효 관측치 수.
            - sample_2_size: 두 번째 표본의 유효 관측치 수.
            - threshold: 적용된 표류 판정 임계치.

    Raises:
        ValueError: threshold <= 0 또는 유효 표본 크기 부족 시 발생.
    """
    # 1. 임계치 매개변수 유효성 검증
    _validate_threshold(threshold=threshold)

    # 2. 입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화하고 결측치 및 무한대 배제
    clean_reference: np.ndarray = _clean_and_flatten_sample(sample_values=reference_values)
    clean_target: np.ndarray = _clean_and_flatten_sample(sample_values=target_values)

    # 3. 양 표본의 최소 관측치 수(각 2개 이상) 충족 여부 검증
    _validate_sample_sizes(clean_sample_1=clean_reference, clean_sample_2=clean_target)

    # 4. SciPy 엔진 기반 1차원 바서슈타인 거리 산출
    distance_value: float = float(stats.wasserstein_distance(clean_reference, clean_target))

    # 5. 임계치 기준 분포 안정성(is_stable) 판정
    is_stable: bool = bool(distance_value <= threshold)

    # 6. 최종 바서슈타인 분석 통계 번들 조립 및 반환
    return _build_wasserstein_result(
        distance_value=distance_value,
        is_stable=is_stable,
        sample_1_size=len(clean_reference),
        sample_2_size=len(clean_target),
        threshold=threshold
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_threshold(threshold: float) -> None:
    """바서슈타인 거리 판정 임계치의 유효성을 검증합니다."""
    # 음수 거리는 물리적으로 존재할 수 없으므로 0보다 큰 양수 임계치만 수용
    if threshold <= 0.0:
        raise ValueError(f"threshold는 0보다 큰 양수여야 합니다: {threshold}")


def _clean_and_flatten_sample(sample_values: Union[np.ndarray, pd.Series, list]) -> np.ndarray:
    """입력 시퀀스를 1차원 C-연속성 float64 배열로 규격화하고 결측치 및 무한대를 배제합니다."""
    # 메모리 연속성 확보 및 NaN/Inf 제거로 SciPy 연산 크래시 원천 방어
    flat_array: np.ndarray = np.ascontiguousarray(sample_values, dtype=np.float64).flatten()
    return flat_array[np.isfinite(flat_array)]


def _validate_sample_sizes(clean_sample_1: np.ndarray, clean_sample_2: np.ndarray) -> None:
    """두 표본이 누적분포 추정을 위한 최소 관측치 수를 충족하는지 검증합니다."""
    if len(clean_sample_1) < MINIMUM_OBSERVATION_COUNT:
        raise ValueError(f"Reference 표본 크기가 최소 요구치({MINIMUM_OBSERVATION_COUNT}) 미만입니다: {len(clean_sample_1)}")
    if len(clean_sample_2) < MINIMUM_OBSERVATION_COUNT:
        raise ValueError(f"Target 표본 크기가 최소 요구치({MINIMUM_OBSERVATION_COUNT}) 미만입니다: {len(clean_sample_2)}")


def _build_wasserstein_result(
    distance_value: float,
    is_stable: bool,
    sample_1_size: int,
    sample_2_size: int,
    threshold: float
) -> Dict[str, Any]:
    """최종 바서슈타인 거리 통계량 및 메타데이터를 정형화된 딕셔너리로 패키징합니다."""
    return {
        "statistic": distance_value,
        "wasserstein_distance": distance_value,
        "is_stable": is_stable,
        "sample_1_size": sample_1_size,
        "sample_2_size": sample_2_size,
        "threshold": threshold
    }