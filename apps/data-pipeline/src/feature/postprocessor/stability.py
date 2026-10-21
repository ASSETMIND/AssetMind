from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple
import numpy as np
import pandas as pd

from src.dataset.walk_forward_splitter import WalkForwardSplitter
from src.model.evaluation.metrics import rank_ic
from src.statistics.correlation import pearson_correlation, spearman_correlation
from src.statistics.parametric.one_t_test import one_sample_t_test

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_MIN_SIGN_CONSISTENCY: float = 0.80                                             # 5개 Fold 중 기준 부호와 동일한 방향성을 유지해야 하는 최소 비율 (4/5 Fold)
DEFAULT_MAX_IC_PVALUE: float = 0.05                                                    # 단일표본 t-검정에서 무신호 귀무가설(mean IC == 0)을 기각하기 위한 유의수준 상한선
DEFAULT_MINIMUM_FEATURES: int = 10                                                     # 필터링 통과 피처가 부족할 때 안정성 상위순으로 보존할 최소 피처 수 하한선
SEVERE_SIGN_FLIP_IC_THRESHOLD: float = 0.08                                            # 부호 역전 시 단순 노이즈가 아닌 구조적 역전으로 판정할 절대 상관계수 임계값
ZERO_SIGNAL_EPSILON: float = 1e-6                                                      # 신호 크기가 0인지 판정하기 위한 부동소수점 오차 허용 한계값
DEFAULT_CORRELATION_METRIC: str = "rank_ic"                                            # 시계열 안정성 검증 시 사용할 기본 상관계수 산출 방식 (rank_ic, spearman, pearson)
SUPPORTED_CORRELATION_METRICS: Tuple[str, ...] = ("rank_ic", "spearman", "pearson")    # 지원 가능한 상관성 평가 지표 패밀리


@dataclass(frozen=True)
class FeatureQualityGate:
    """피처 선별 시 시계열 부호 일관성 및 유효 설명력을 검증하기 위한 품질 게이트 DTO.

    Attributes:
        min_sign_consistency: 5개 Fold 중 동일한 상관계수 부호를 유지해야 하는 최소 비율 (기본값: 0.80).
        max_ic_pvalue: 5개 Fold 1-Sample t-검정 유의확률 상한선 (기본값: 0.05).
        correlation_metric: 상관계수 평가 지표 ('rank_ic', 'spearman', 'pearson', 기본값: 'rank_ic').
    """
    min_sign_consistency: float = DEFAULT_MIN_SIGN_CONSISTENCY
    max_ic_pvalue: float = DEFAULT_MAX_IC_PVALUE
    correlation_metric: str = DEFAULT_CORRELATION_METRIC


# ==============================================================================
# Public API Functions
# ==============================================================================

def filter_walk_forward_stability(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    splitter: WalkForwardSplitter,
    gate: Optional[FeatureQualityGate] = None,
    minimum_features: int = DEFAULT_MINIMUM_FEATURES,
    metric: str = DEFAULT_CORRELATION_METRIC
) -> Tuple[pd.DataFrame, List[str]]:
    """5-Fold Expanding Window를 순회하며 시계열 부호 일관성과 통계적 유의성이 검증된 정예 피처를 필터링합니다.

    Args:
        feature_matrix: 공선성 정제가 완료된 후보 피처 데이터프레임.
        target_series: 미래 수익률 정답 타깃 시계열.
        splitter: 시계열 무유출 Expanding 교차검증 분할기 인스턴스.
        gate: 부호 일관성 및 t-검정 유의수준 임계치를 정의한 품질 게이트 객체 (기본값: None 시 기본 DTO 사용).
        minimum_features: 파이프라인 최소 생존 피처 수 (기본값: 10).
        metric: 상관성 평가 지표 유형 ('rank_ic', 'spearman', 'pearson', 기본값: 'rank_ic').

    Returns:
        Tuple[pd.DataFrame, List[str]]:
            - filtered_matrix: 부호 안정성과 통계적 유의성이 확인된 잔여 피처 데이터프레임.
            - dropped_features: 기준 미달로 인해 탈락한 피처명 리스트.

    Raises:
        ValueError: minimum_features 인자가 1 미만이거나 지원하지 않는 metric이 유입된 경우 발생.
    """
    # 1. 입력 데이터프레임 공백 검사 및 파라미터 유효성 검증
    if _is_empty_feature_matrix(feature_matrix):
        return feature_matrix.copy(), []

    _validate_stability_parameters(minimum_features=minimum_features)
    quality_gate: FeatureQualityGate = _resolve_quality_gate(gate=gate)
    resolved_metric: str = _resolve_correlation_metric(metric=metric, gate=quality_gate)
    candidate_features: List[str] = feature_matrix.columns.tolist()

    # 2. 5-Fold Walk-Forward 교차검증을 순회하며 각 Fold 검증 구간(OOF)별 상관계수 시퀀스 수집
    fold_ic_repository: Dict[str, List[float]] = _collect_oof_correlations(
        feature_matrix=feature_matrix,
        target_series=target_series,
        splitter=splitter,
        candidate_features=candidate_features,
        metric=resolved_metric
    )

    # 3. 전체 학습 데이터 기준 벤치마크 부호 산출 및 개별 피처의 안정성/유의성 가설 검정 수행
    stable_features, dropped_features, stability_metrics = _evaluate_feature_candidates(
        feature_matrix=feature_matrix,
        target_series=target_series,
        splitter=splitter,
        candidate_features=candidate_features,
        fold_ic_repository=fold_ic_repository,
        quality_gate=quality_gate,
        metric=resolved_metric
    )

    # 4. 기준 통과 피처 수가 최소 보존치 미만일 경우 부호 일치율 및 t-stat 기준 상위 피처로 보전
    if len(stable_features) < minimum_features:
        stable_features, dropped_features = _fallback_to_top_stable_features(
            candidate_features=candidate_features,
            stability_metrics=stability_metrics,
            minimum_features=minimum_features
        )

    # 5. 최종 통과 피처만 슬라이싱된 데이터프레임과 탈락 피처 목록 반환
    return feature_matrix[stable_features], dropped_features


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _is_empty_feature_matrix(feature_matrix: pd.DataFrame) -> bool:
    """피처 행렬이 비어있거나 컬럼 수가 0개인지 확인합니다."""
    return feature_matrix.empty or feature_matrix.shape[1] == 0


def _validate_stability_parameters(minimum_features: int) -> None:
    """안정성 필터 파라미터가 유효한 수치 범위를 만족하는지 검증합니다."""
    if minimum_features < 1:
        raise ValueError(f"minimum_features는 최소 1 이상이어야 합니다. (유입: {minimum_features})")


def _validate_correlation_metric(metric: str) -> None:
    """선택된 상관성 평가 지표가 지원 목록에 존재하는지 확인합니다."""
    if metric not in SUPPORTED_CORRELATION_METRICS:
        raise ValueError(
            f"지원하지 않는 상관성 지표입니다: '{metric}'. "
            f"지원 목록: {SUPPORTED_CORRELATION_METRICS}"
        )


def _resolve_quality_gate(gate: Optional[FeatureQualityGate]) -> FeatureQualityGate:
    """입력된 품질 게이트 DTO를 확인하고 미제공 시 기본 설정 DTO를 반환합니다."""
    return gate if gate is not None else FeatureQualityGate()


def _resolve_correlation_metric(metric: str, gate: FeatureQualityGate) -> str:
    """인자로 전달된 지표와 Gate DTO 내부의 지표 중 우선순위를 결정하고 유효성을 검증합니다."""
    chosen_metric: str = metric if metric != DEFAULT_CORRELATION_METRIC else gate.correlation_metric
    _validate_correlation_metric(metric=chosen_metric)
    return chosen_metric


def _calculate_single_correlation(
    feature_vector: np.ndarray,
    target_vector: np.ndarray,
    metric: str,
    holding_period: int
) -> float:
    """설정된 지표 유형에 따라 타깃과 피처 간의 상관계수를 산출합니다."""
    if metric == "rank_ic":
        # 20일 중첩 시계열 위상 평균 Rank IC 산출
        return float(rank_ic(
            y_true=target_vector,
            y_pred=feature_vector,
            holding_period=holding_period
        ))
    elif metric == "spearman":
        result = spearman_correlation(x_values=feature_vector, y_values=target_vector)
        return float(result["correlation"])
    elif metric == "pearson":
        result = pearson_correlation(x_values=feature_vector, y_values=target_vector)
        return float(result["correlation"])
    else:
        return 0.0


def _collect_oof_correlations(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    splitter: WalkForwardSplitter,
    candidate_features: List[str],
    metric: str
) -> Dict[str, List[float]]:
    """Walk-Forward 분할기를 순회하며 각 Fold의 Validation 구간에서 피처별 상관계수를 수집합니다."""
    fold_ic_repository: Dict[str, List[float]] = {feat: [] for feat in candidate_features}

    # 각 Fold의 검증 구간(val_feature_fold, val_target_fold) 데이터 추출 및 지정 지표 연산
    for _, _, val_feature_fold, val_target_fold in splitter.split_walk_forward(X=feature_matrix, y=target_series):
        target_array: np.ndarray = val_target_fold.to_numpy(dtype=np.float64)

        for feature_name in candidate_features:
            feature_array: np.ndarray = val_feature_fold[feature_name].to_numpy(dtype=np.float64)
            current_fold_metric: float = _calculate_single_correlation(
                feature_vector=feature_array,
                target_vector=target_array,
                metric=metric,
                holding_period=splitter.forecast_horizon
            )
            fold_ic_repository[feature_name].append(current_fold_metric)

    return fold_ic_repository


def _calculate_benchmark_sign(
    feature_series: pd.Series,
    target_series: pd.Series,
    metric: str,
    forecast_horizon: int
) -> float:
    """전체 Train 시계열 구간에 대한 피처의 전역 상관계수를 산출하고 방향성 부호(+1/-1)를 결정합니다."""
    overall_metric: float = _calculate_single_correlation(
        feature_vector=feature_series.to_numpy(dtype=np.float64),
        target_vector=target_series.to_numpy(dtype=np.float64),
        metric=metric,
        holding_period=forecast_horizon
    )

    # 상관계수 절대값이 0에 근접한 경우 양수(+1.0)를 기본 부호로 설정
    if np.abs(overall_metric) >= ZERO_SIGNAL_EPSILON:
        return float(np.sign(overall_metric))
    return 1.0


def _assess_single_feature_stability(
    ic_sequence: np.ndarray,
    benchmark_sign: float,
    quality_gate: FeatureQualityGate
) -> Tuple[bool, float, float]:
    """단일 피처의 Fold별 상관계수 시퀀스에 대해 부호 일관성과 단일표본 t-검정 유의성을 판정합니다."""
    # 벤치마크 부호와 일치하는 Fold의 비율 산출
    same_sign_ratio: float = float(np.mean(np.sign(ic_sequence) == benchmark_sign))

    # 부호가 반대이면서 유의미한 크기(>= 0.08)를 갖는 심각한 역전 존재 여부 확인
    has_severe_flip: bool = bool(
        np.any((np.sign(ic_sequence) != benchmark_sign) & (np.abs(ic_sequence) >= SEVERE_SIGN_FLIP_IC_THRESHOLD))
    )

    # Fold별 신호 평균이 0인지 단일표본 t-검정 수행 (src.statistics.parametric.one_t_test 활용)
    t_test_result: Dict[str, Any] = one_sample_t_test(
        sample_values=ic_sequence,
        method="student",
        alternative="two-sided",
        population_mean=0.0
    )
    t_stat: float = float(t_test_result["statistic"])
    p_val: float = float(t_test_result["p_value"])

    # 품질 게이트 기준 충족 여부 종합 평가
    is_sign_stable: bool = (same_sign_ratio >= quality_gate.min_sign_consistency) and not has_severe_flip
    is_signal_effective: bool = bool(p_val < quality_gate.max_ic_pvalue)
    is_passed: bool = is_sign_stable and is_signal_effective

    return is_passed, same_sign_ratio, abs(t_stat)


def _evaluate_feature_candidates(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    splitter: WalkForwardSplitter,
    candidate_features: List[str],
    fold_ic_repository: Dict[str, List[float]],
    quality_gate: FeatureQualityGate,
    metric: str
) -> Tuple[List[str], List[str], List[Tuple[str, float, float]]]:
    """모든 후보 피처에 대해 부호 안정성 검정과 통계 검정을 순회 실행하여 생존/탈락 피처를 분류합니다."""
    stable_features: List[str] = []
    dropped_features: List[str] = []
    stability_metrics: List[Tuple[str, float, float]] = []

    for feature_name in candidate_features:
        ic_sequence: np.ndarray = np.array(fold_ic_repository[feature_name], dtype=np.float64)

        # 전체 Train 시계열 구간을 대상으로 기준점 역할을 할 전역 벤치마크 부호(+1.0 / -1.0) 산출
        benchmark_sign: float = _calculate_benchmark_sign(
            feature_series=feature_matrix[feature_name],
            target_series=target_series,
            metric=metric,
            forecast_horizon=splitter.forecast_horizon
        )

        # 단일 피처의 Fold별 부호 일치율(>= 80%), 역전 여부, 1-Sample t-검정 유의성(p < 0.05) 판정
        is_passed, sign_ratio, abs_t_stat = _assess_single_feature_stability(
            ic_sequence=ic_sequence,
            benchmark_sign=benchmark_sign,
            quality_gate=quality_gate
        )

        # 후속 정렬 및 Fallback 복구 처리를 위해 피처명, 부호 일치율, |t-stat| 메트릭 튜플 적재
        stability_metrics.append((feature_name, sign_ratio, abs_t_stat))

        # 품질 게이트 통과 여부에 따라 생존 목록 또는 탈락 목록으로 분류 적재
        if is_passed:
            stable_features.append(feature_name)
        else:
            dropped_features.append(feature_name)

    # 분류가 완료된 생존 피처 목록, 탈락 피처 목록, 전체 평가 지표 메트릭 반환
    return stable_features, dropped_features, stability_metrics


def _fallback_to_top_stable_features(
    candidate_features: List[str],
    stability_metrics: List[Tuple[str, float, float]],
    minimum_features: int
) -> Tuple[List[str], List[str]]:
    """생존 피처가 최소 수량 미만일 때 부호 일치율 및 t-통계량 크기 내림차순으로 상위 피처를 복구합니다."""
    # 1순위 부호 일치율, 2순위 |t-stat| 기준으로 정렬
    stability_metrics.sort(key=lambda metric_tuple: (metric_tuple[1], metric_tuple[2]), reverse=True)

    rescued_features: List[str] = [item[0] for item in stability_metrics[:minimum_features]]
    final_dropped_features: List[str] = [col for col in candidate_features if col not in rescued_features]

    return rescued_features, final_dropped_features