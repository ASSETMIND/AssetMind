from typing import Any, Dict, Literal, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_HIGHER_IS_BETTER: bool = True                                           # 성능 지표의 값이 클수록 우수한지 여부 (기본값: True)
SUPPORTED_FRIEDMAN_METHODS: Tuple[str, ...] = ("friedman", "iman_davenport")    # 지원하는 비모수 순위 검정 알고리즘 (기본, 개선 순서)
MINIMUM_BLOCK_COUNT: int = 2                                                    # 검정 자유도 확보를 위한 최소 평가 블록(Fold) 수 (N >= 2)
MINIMUM_TREATMENT_COUNT: int = 2                                                # 비교 평가를 위한 최소 처리군(후보 모델/버킷) 수 (k >= 2)
ZERO_DIVISION_EPSILON: float = 1e-12                                            # 분모 제로 나눗셈 방지를 위한 부동소수점 임계치
PROBABILITY_LOWER_BOUND: float = 0.0                                            # 확률값 하한선
PROBABILITY_UPPER_BOUND: float = 1.0                                            # 확률값 상한선


# ==============================================================================
# Public API Functions
# ==============================================================================

def friedman_test(
    observation_matrix: Union[np.ndarray, pd.DataFrame, list],
    method: Literal["friedman", "iman_davenport"],
    higher_is_better: bool = DEFAULT_HIGHER_IS_BETTER
) -> Dict[str, Any]:
    """블록 요인을 통제한 다중 처리군 평가 점수 행렬에 대해 비모수 순위 검정을 수행합니다.

    Args:
        observation_matrix: 블록(행, 예: Fold) x 처리군(열, 예: Candidate) 구조의 2차원 수치 데이터.
        method: 실행할 통계 검정 알고리즘 ('friedman': 기본 카이제곱 검정, 'iman_davenport': 개선 F-보정 검정).
        higher_is_better: 수치가 높을수록 우수한 지표인지 여부 (True인 경우 최댓값에 1위 순위 부여).

    Returns:
        Dict[str, Any]:
            - statistic: 검정 통계량 (friedman: 카이제곱 통계량, iman_davenport: F-통계량).
            - p_value: 유의확률 (p-value).
            - degrees_of_freedom: 유효 자유도 (friedman: k - 1, iman_davenport: (df1, df2)).
            - mean_ranks: 처리군별 평균 순위 배열 (Demšar 비모수 순위, 1에 가까울수록 우수).
            - kendall_w: 블록 간 순위 일치도 효과 크기 (Kendall's W, 0.0 ~ 1.0).
            - chi2_statistic: 산출된 표준 Friedman 카이제곱 통계량.
            - f_statistic: Iman-Davenport F-통계량 (friedman 방식일 경우 None).
            - number_of_blocks: 평가에 사용된 블록(Fold) 수 (N).
            - number_of_treatments: 평가 대상 처리군(Candidate) 수 (k).
            - method: 실행된 알고리즘 명칭.
            - higher_is_better: 적용된 순위 부여 방향.

    Raises:
        ValueError: 지원하지 않는 method 지정, 비정형 차원 또는 최소 요구 크기 미달 시 발생.
    """
    # 1. 비모수 순위 검정 알고리즘 매개변수 유효성 검증
    _validate_friedman_method(method=method)

    # 2. 입력 관측치 행렬을 2차원 C-연속성 float64 배열로 정제 및 결측 검증
    clean_matrix: np.ndarray = _clean_and_validate_observation_matrix(
        observation_matrix=observation_matrix
    )

    # 3. 블록 수(N) 및 처리군 수(k)의 최소 통계적 요구 조건 충족 여부 검증
    _validate_matrix_dimensions(clean_matrix=clean_matrix)

    # 4. 각 블록(행) 내부에서 처리군 평가값에 대한 비모수 순위(동순위 평균 순위) 부여
    rank_matrix: np.ndarray = _compute_block_ranks(
        clean_matrix=clean_matrix,
        higher_is_better=higher_is_better
    )

    # 5. 각 처리군(열)별 순위 합계(R_j) 및 Demšar 평균 순위(mean_ranks) 산출
    mean_ranks, sum_ranks = _compute_mean_and_sum_ranks(rank_matrix=rank_matrix)

    # 6. 블록 내 동순위(Ties) 발생 빈도를 집계하여 분산 왜곡을 보정하는 동순위 보정 계수 산출
    tie_correction_factor: float = _compute_tie_correction_factor(clean_matrix=clean_matrix)

    # 7. 동순위 보정이 적용된 표준 Friedman 카이제곱 통계량 산출
    number_of_blocks, number_of_treatments = clean_matrix.shape
    chi2_statistic: float = _calculate_friedman_chi2_statistic(
        sum_ranks=sum_ranks,
        number_of_blocks=number_of_blocks,
        number_of_treatments=number_of_treatments,
        tie_correction_factor=tie_correction_factor
    )

    # 8. 블록 간 평가 합의 강도를 나타내는 정규화 효과 크기인 Kendall's W 산출
    kendall_w: float = _calculate_kendall_w(
        chi2_statistic=chi2_statistic,
        number_of_blocks=number_of_blocks,
        number_of_treatments=number_of_treatments
    )

    # 9. 지정된 알고리즘(friedman 또는 iman_davenport)에 따른 최종 검정 통계량, 자유도, p-value 계산
    test_statistic, p_value, degrees_of_freedom, f_statistic = _calculate_test_results(
        chi2_statistic=chi2_statistic,
        number_of_blocks=number_of_blocks,
        number_of_treatments=number_of_treatments,
        method=method
    )

    # 10. 최종 비모수 옴니버스 검정 결과 및 Demšar 평균 순위 번들 패키징 반환
    return _build_friedman_result(
        statistic=test_statistic,
        p_value=p_value,
        degrees_of_freedom=degrees_of_freedom,
        mean_ranks=mean_ranks,
        kendall_w=kendall_w,
        chi2_statistic=chi2_statistic,
        f_statistic=f_statistic,
        number_of_blocks=number_of_blocks,
        number_of_treatments=number_of_treatments,
        method=method,
        higher_is_better=higher_is_better
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _validate_friedman_method(method: str) -> None:
    """지정된 비모수 순위 검정 알고리즘의 지원 여부를 검증합니다."""
    if method not in SUPPORTED_FRIEDMAN_METHODS:
        raise ValueError(
            f"지원하지 않는 비모수 순위 검정 알고리즘입니다: '{method}'. "
            f"지원 알고리즘 목록: {SUPPORTED_FRIEDMAN_METHODS}"
        )


def _clean_and_validate_observation_matrix(
    observation_matrix: Union[np.ndarray, pd.DataFrame, list]
) -> np.ndarray:
    """다양한 형태의 2차원 입력을 float64 배열로 규격화하고 결측치 및 무한대를 검증합니다."""
    # 1. DataFrame 입력인 경우 값 배열 추출
    if isinstance(observation_matrix, pd.DataFrame):
        matrix_values = observation_matrix.to_numpy()
    else:
        matrix_values = np.ascontiguousarray(observation_matrix)

    # 2. 2차원 배열 차원 정합성 검증
    if matrix_values.ndim != 2:
        raise ValueError(f"입력 데이터는 반드시 2차원 행렬이어야 합니다 (현재 차원: {matrix_values.ndim}).")

    # 3. float64 연속 메모리 배열 변환
    float_matrix: np.ndarray = np.ascontiguousarray(matrix_values, dtype=np.float64)

    # 4. 결측치(NaN) 또는 무한대(Inf) 포함 여부 검증
    if not np.all(np.isfinite(float_matrix)):
        raise ValueError("입력 관측치 행렬에 결측치(NaN) 또는 무한대(Inf)가 포함되어 있습니다.")

    return float_matrix


def _validate_matrix_dimensions(clean_matrix: np.ndarray) -> None:
    """행렬의 블록 수(행)와 처리군 수(열)가 최소 통계적 검정 요건을 만족하는지 검증합니다."""
    number_of_blocks, number_of_treatments = clean_matrix.shape

    # 1. 최소 블록(Fold) 수 충족 여부 검증
    if number_of_blocks < MINIMUM_BLOCK_COUNT:
        raise ValueError(
            f"평가 블록 수(행)가 최소 요구치({MINIMUM_BLOCK_COUNT}) 미만입니다: {number_of_blocks}"
        )

    # 2. 최소 처리군(후보 모델) 수 충족 여부 검증
    if number_of_treatments < MINIMUM_TREATMENT_COUNT:
        raise ValueError(
            f"비교 처리군 수(열)가 최소 요구치({MINIMUM_TREATMENT_COUNT}) 미만입니다: {number_of_treatments}"
        )


def _compute_block_ranks(
    clean_matrix: np.ndarray,
    higher_is_better: bool
) -> np.ndarray:
    """각 블록(행)별로 처리군 평가 점수에 대해 동순위 평균 순위(average rank)를 산출합니다."""
    number_of_blocks, number_of_treatments = clean_matrix.shape
    rank_matrix: np.ndarray = np.empty_like(clean_matrix, dtype=np.float64)

    # 1. 각 블록별 독립 순위 부여 (higher_is_better=True인 경우 최고점에 1위 순위 할당)
    for block_index in range(number_of_blocks):
        block_values: np.ndarray = clean_matrix[block_index, :]
        if higher_is_better:
            rank_matrix[block_index, :] = stats.rankdata(-block_values, method="average")
        else:
            rank_matrix[block_index, :] = stats.rankdata(block_values, method="average")

    return rank_matrix


def _compute_mean_and_sum_ranks(
    rank_matrix: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """처리군별 순위 합계(R_j)와 Demšar 평균 순위를 계산합니다."""
    # 1. 처리군(열) 방향 순위 합계 산출
    sum_ranks: np.ndarray = np.sum(rank_matrix, axis=0)

    # 2. 블록 수로 나누어 각 처리군별 평균 순위 산출
    mean_ranks: np.ndarray = np.mean(rank_matrix, axis=0)

    return mean_ranks, sum_ranks


def _compute_tie_correction_factor(clean_matrix: np.ndarray) -> float:
    """블록별 동순위 관측치 군집 크기를 집계하여 Friedman 동순위 보정 계수를 계산합니다."""
    number_of_blocks, number_of_treatments = clean_matrix.shape
    total_tie_sum: float = 0.0

    # 1. 각 블록별 동일 값(Tied group)의 크기를 집계하여 t^3 - t 합산
    for block_index in range(number_of_blocks):
        _, group_counts = np.unique(clean_matrix[block_index, :], return_counts=True)
        tied_counts = group_counts[group_counts > 1]
        if len(tied_counts) > 0:
            total_tie_sum += float(np.sum(tied_counts ** 3 - tied_counts))

    # 2. 동순위 분산 감소율(C_tie) 계산
    denominator: float = float(number_of_blocks * number_of_treatments * (number_of_treatments ** 2 - 1))
    if denominator <= ZERO_DIVISION_EPSILON:
        return 1.0

    tie_correction_factor: float = 1.0 - (total_tie_sum / denominator)
    return max(tie_correction_factor, ZERO_DIVISION_EPSILON)


def _calculate_friedman_chi2_statistic(
    sum_ranks: np.ndarray,
    number_of_blocks: int,
    number_of_treatments: int,
    tie_correction_factor: float
) -> float:
    """동순위 보정을 반영하여 표준 Friedman 카이제곱 통계량을 계산합니다."""
    # 1. 순위합 중심값(Expected sum under H0) 설정: N * (k + 1) / 2
    expected_rank_sum: float = float(number_of_blocks * (number_of_treatments + 1)) / 2.0

    # 2. 카이제곱 척도 계수 산출: 12 / (N * k * (k + 1))
    scale_multiplier: float = 12.0 / float(number_of_blocks * number_of_treatments * (number_of_treatments + 1))

    # 3. 수치적 소거 오차를 방지하기 위해 편차 제곱합 기반으로 무보정 카이제곱 통계량 계산
    squared_deviation_sum: float = float(np.sum((sum_ranks - expected_rank_sum) ** 2))
    raw_chi2: float = scale_multiplier * squared_deviation_sum

    # 4. 동순위 보정 계수를 나누어 최종 Friedman 카이제곱 통계량 도출
    corrected_chi2: float = raw_chi2 / tie_correction_factor
    return max(corrected_chi2, 0.0)


def _calculate_kendall_w(
    chi2_statistic: float,
    number_of_blocks: int,
    number_of_treatments: int
) -> float:
    """카이제곱 통계량을 기반으로 0과 1 사이의 순위 일치도 계수(Kendall's W)를 계산합니다."""
    # 1. 이론상 최대 카이제곱 값 N * (k - 1) 산출
    max_chi2: float = float(number_of_blocks * (number_of_treatments - 1))
    if max_chi2 <= ZERO_DIVISION_EPSILON:
        return 0.0

    # 2. 정규화 및 [0.0, 1.0] 구간 클리핑
    kendall_w: float = chi2_statistic / max_chi2
    return float(np.clip(kendall_w, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))


def _calculate_iman_davenport_f_statistic(
    chi2_statistic: float,
    number_of_blocks: int,
    number_of_treatments: int
) -> float:
    """Iman-Davenport (1980) 공식을 적용하여 F-변환 통계량을 계산합니다."""
    # 1. 분모 항 계산: N * (k - 1) - chi2
    max_possible_chi2: float = float(number_of_blocks * (number_of_treatments - 1))
    denominator: float = max_possible_chi2 - chi2_statistic

    # 2. 분모가 0에 수렴하는 경우(완벽한 순위 일치) 무한대 통계량 방어
    if denominator <= ZERO_DIVISION_EPSILON:
        return 1e12

    # 3. F-통계량 산출: (N - 1) * chi2 / (N * (k - 1) - chi2)
    numerator: float = float(number_of_blocks - 1) * chi2_statistic
    return max(float(numerator / denominator), 0.0)


def _calculate_test_results(
    chi2_statistic: float,
    number_of_blocks: int,
    number_of_treatments: int,
    method: str
) -> Tuple[float, float, Any, Any]:
    """지정된 알고리즘 모드에 따라 통계량, p-value 및 자유도를 산출합니다."""
    # 1. 기본 Friedman 분기: 카이제곱 분포(df = k - 1) 기반 p-value 계산
    if method == "friedman":
        degrees_of_freedom_chi2: float = float(number_of_treatments - 1)
        raw_p_value: float = float(stats.chi2.sf(chi2_statistic, df=degrees_of_freedom_chi2))
        clipped_p_value: float = float(np.clip(raw_p_value, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))
        return chi2_statistic, clipped_p_value, degrees_of_freedom_chi2, None

    # 2. Iman-Davenport 분기: F-분포(df1 = k - 1, df2 = (k - 1) * (N - 1)) 기반 p-value 계산
    elif method == "iman_davenport":
        f_stat: float = _calculate_iman_davenport_f_statistic(
            chi2_statistic=chi2_statistic,
            number_of_blocks=number_of_blocks,
            number_of_treatments=number_of_treatments
        )
        df_numerator: float = float(number_of_treatments - 1)
        df_denominator: float = float((number_of_treatments - 1) * (number_of_blocks - 1))

        raw_f_p_value: float = float(stats.f.sf(f_stat, dfn=df_numerator, dfd=df_denominator))
        clipped_f_p_value: float = float(np.clip(raw_f_p_value, PROBABILITY_LOWER_BOUND, PROBABILITY_UPPER_BOUND))
        degrees_of_freedom_f: Tuple[float, float] = (df_numerator, df_denominator)

        return f_stat, clipped_f_p_value, degrees_of_freedom_f, f_stat


def _build_friedman_result(
    statistic: float,
    p_value: float,
    degrees_of_freedom: Any,
    mean_ranks: np.ndarray,
    kendall_w: float,
    chi2_statistic: float,
    f_statistic: Any,
    number_of_blocks: int,
    number_of_treatments: int,
    method: str,
    higher_is_better: bool
) -> Dict[str, Any]:
    """최종 비모수 옴니버스 검정 통계량 및 평균 순위를 딕셔너리로 패키징합니다."""
    return {
        "statistic": statistic,
        "p_value": p_value,
        "degrees_of_freedom": degrees_of_freedom,
        "mean_ranks": mean_ranks,
        "kendall_w": kendall_w,
        "chi2_statistic": chi2_statistic,
        "f_statistic": f_statistic,
        "number_of_blocks": number_of_blocks,
        "number_of_treatments": number_of_treatments,
        "method": method,
        "higher_is_better": higher_is_better
    }