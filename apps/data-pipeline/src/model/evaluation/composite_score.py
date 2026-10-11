from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.model.evaluation.criteria import (
    FactorQualityGate,
    FinanceGate,
    MLValidityGate,
    StatisticalGate,
    Weights,
    check_factor_quality_gate,
    check_finance_gate,
    check_ml_validity_gate,
    check_statistical_gate,
)
from src.model.evaluation.schema import (
    EvaluationLayer,
    EvaluationMetric,
    METRIC_REGISTRY,
)


# ==============================================================================
# 1. 공개 복합 스코어링 API (Public Scoring Interfaces)
# ==============================================================================

def get_score(
    candidates_metrics: Union[Dict[str, Dict[Any, float]], pd.DataFrame],
    ml_gate: Optional[MLValidityGate] = None,
    factor_gate: Optional[FactorQualityGate] = None,
    finance_gate: Optional[FinanceGate] = None,
    stat_gate: Optional[StatisticalGate] = None,
    weights: Optional[Weights] = None,
    target_std: float = 1.0,
) -> pd.DataFrame:
    """도메인 게이트를 통과한 적격 후보 모델들에 대해 비대칭 감점이 반영된 신호 복합 스코어 리더보드를 산출합니다.

    Args:
        candidates_metrics: 전체 후보 모델들의 원시 지표 맵 또는 판다스 DataFrame.
        ml_gate: ML 유효성 게이트 설정 DTO (None일 경우 기본값 적용).
        factor_gate: 팩터 품질 게이트 설정 DTO (None일 경우 기본값 적용).
        finance_gate: 금융 성과 게이트 설정 DTO (선택 사항).
        stat_gate: 통계적 유의성 게이트 설정 DTO (선택 사항).
        weights: 2대 핵심 계층(ML, Factor) 가중치 설정 DTO (None일 경우 기본값 적용).
        target_std: 타겟 시계열 표준편차 (기본값: 1.0).

    Returns:
        pd.DataFrame: 적격 모델들의 원시 지표, 계층별 부분 점수(score_l1_ml, score_l2_factor),
            최종 복합 스코어(composite_score) 및 랭킹(rank)이 정렬된 리더보드.
    """
    effective_ml_gate: MLValidityGate = ml_gate or MLValidityGate()
    effective_factor_gate: FactorQualityGate = factor_gate or FactorQualityGate()
    effective_weights: Weights = weights or Weights()

    standardized_candidates = _standardize_candidates(candidates_metrics)
    qualified_dict: Dict[str, Dict[str, float]] = {}

    for model_name, metric_map in standardized_candidates.items():
        # [설계 의도] 1단계: 기초 수렴 실패 및 부호 붕괴 모델 사전 차단
        ml_pass, _ = check_ml_validity_gate(metric_map, effective_ml_gate, target_std=target_std)
        if not ml_pass:
            continue

        # [설계 의도] 2단계: 순위 상관력 역전 모델 차단
        factor_pass, _ = check_factor_quality_gate(metric_map, effective_factor_gate)
        if not factor_pass:
            continue

        # [설계 의도] 3단계: 선택적 금융 리스크 및 통계적 유의성 검증
        if finance_gate is not None:
            fin_pass, _ = check_finance_gate(metric_map, finance_gate)
            if not fin_pass:
                continue

        if stat_gate is not None:
            stat_pass, _ = check_statistical_gate(metric_map, stat_gate)
            if not stat_pass:
                continue

        qualified_dict[model_name] = {
            metric.value: score for metric, score in metric_map.items()
        }

    if not qualified_dict:
        return pd.DataFrame(columns=["composite_score", "rank"])

    qualified_df = pd.DataFrame.from_dict(qualified_dict, orient="index")

    scored_leaderboard = _calculate_score(
        qualified_metrics_df=qualified_df,
        weights=effective_weights,
        target_std=target_std,
    )

    return scored_leaderboard


def get_trial_score(
    metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
    weights: Optional[Weights] = None,
    target_std: float = 1.0,
) -> float:
    """단일 Optuna HPO Trial의 Fold 평균 검증 지표를 수신하여 [-1.0, 1.0] 연속 복합 목적함수 스코어를 산출합니다."""
    effective_weights: Weights = weights or Weights()
    scores = compute_layer_scores(metrics=metrics, target_std=target_std)

    # [설계 의도] 백테스트 과적합을 방지하기 위해 L3(Finance), L4(Stat)을 목적함수에서 배제하고 L1, L2만 선형 결합
    total_weight = effective_weights.layer_1_ml + effective_weights.layer_2_factor
    divisor: float = total_weight if total_weight > 0.0 else 1.0

    trial_score: float = (
        effective_weights.layer_1_ml * scores["score_l1_ml"] +
        effective_weights.layer_2_factor * scores["score_l2_factor"]
    ) / divisor

    return float(trial_score)


def compute_layer_scores(
    metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
    target_std: float = 1.0,
) -> Dict[str, float]:
    """10대 원천 지표로부터 비대칭 감점 페널티가 적용된 신호 품질 부분 점수를 산출하는 단일 진실 공급원(SSOT) 함수."""
    clean_metrics: Dict[EvaluationMetric, float] = _standardize_metrics_map(metrics)

    # [설계 의도] Layer 1. 기계학습 기본 방향성 (50% 미달 시 역방향 베팅 위험에 비례하여 [-1.0, 0.0) 연속 감점 부과)
    val_mda = clean_metrics.get(EvaluationMetric.MDA, 0.50)
    score_l1 = float(np.clip((val_mda - 0.50) / 0.15, -1.0, 1.5))

    # [설계 의도] Layer 2. 퀀트 팩터 신호 품질 (천장 효과 완화를 위해 Rank IC 상한을 1.5로 확장)
    val_rank_ic = clean_metrics.get(EvaluationMetric.RANK_IC, 0.0)
    val_icir = clean_metrics.get(EvaluationMetric.ICIR, 0.0)

    norm_rank_ic = float(np.clip(val_rank_ic / 0.15, -1.0, 1.5))
    norm_icir = float(np.clip(val_icir / 1.50, 0.0, 1.0))
    # Rank IC 순위 단조성에 70%, ICIR 시계열 안정성에 30% 배분
    score_l2 = float(0.70 * norm_rank_ic + 0.30 * norm_icir)

    return {
        "score_l1_ml": score_l1,
        "score_l2_factor": score_l2,
    }


# ==============================================================================
# 2. 내부 수리 정규화 및 스코어링 서브 루틴 (Private Helpers)
# ==============================================================================

def _calculate_score(
    qualified_metrics_df: pd.DataFrame,
    weights: Weights,
    target_std: float = 1.0,
) -> pd.DataFrame:
    """적격 모델 데이터프레임에 대해 get_trial_score와 동일한 도메인 절대 기준선 스케일링을 적용합니다.

    Args:
        qualified_metrics_df: 게이트를 통과한 모델들의 원시 지표 DataFrame.
        weights: 4대 계층 가중치 DTO.
        target_std: 타겟 시계열 표준편차 (RMSE/MAE 정규화 기준 분모).

    Returns:
        pd.DataFrame: 계층별 점수 및 최종 composite_score로 정렬된 DataFrame.
    """
    df = qualified_metrics_df.copy()
    safe_std: float = target_std if (target_std > 0.0 and np.isfinite(target_std)) else 1.0

    # [설계 의도] Layer 1. 기계학습 기본 방향성 (50% 미달 시 [-1.0, 0.0) 연속 감점 부과 벡터 연산)
    norm_mda = np.clip((df.get(EvaluationMetric.MDA.value, 0.50) - 0.50) / 0.15, -1.0, 1.5)
    df["score_l1_ml"] = norm_mda

    # [설계 의도] Layer 2. 퀀트 팩터 신호 품질 (천장 효과 완화를 위해 Rank IC 상한을 1.5로 확장)
    norm_rank_ic = np.clip(df.get(EvaluationMetric.RANK_IC.value, 0.0) / 0.15, -1.0, 1.5)
    norm_icir = np.clip(df.get(EvaluationMetric.ICIR.value, 0.0) / 1.50, 0.0, 1.0)
    df["score_l2_factor"] = (0.70 * norm_rank_ic) + (0.30 * norm_icir)

    # [설계 의도] 순수 신호 품질 2계층 가중 선형 결합 (get_trial_score와 완벽히 일치)
    total_weight: float = weights.layer_1_ml + weights.layer_2_factor
    weight_divisor: float = total_weight if total_weight > 0.0 else 1.0

    df["composite_score"] = (
        weights.layer_1_ml * df["score_l1_ml"] +
        weights.layer_2_factor * df["score_l2_factor"]
    ) / weight_divisor

    df = df.sort_values(by="composite_score", ascending=False)
    df["rank"] = np.arange(1, len(df) + 1)

    return df


def _normalize_series(
    series: pd.Series,
    is_greater_better: bool = True,
) -> pd.Series:
    """단일 수치 시리즈를 [0.0, 1.0] 범위로 Min-Max 스케일링합니다 (분모 0 및 분산 0 방어).

    Args:
        series: 스케일링 대상 판다스 Series.
        is_greater_better: 최대화 대상 지표 여부 (False일 경우 역방향 스케일링).

    Returns:
        pd.Series: [0.0, 1.0] 범위로 정규화된 Series.
    """
    min_val: float = float(series.min())
    max_val: float = float(series.max())

    # [설계 의도] 모든 후보 모델의 지표가 동일하여 변별력이 없을 경우 1.0 만점 부여
    if np.isclose(max_val, min_val):
        return pd.Series(1.0, index=series.index)

    if is_greater_better:
        return (series - min_val) / (max_val - min_val)
    else:
        return (max_val - series) / (max_val - min_val)


def _standardize_metrics_map(
    raw_metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
) -> Dict[EvaluationMetric, float]:
    """임의의 키 형식을 갖는 단일 지표 맵을 표준 EvaluationMetric Enum 딕셔너리로 정규화합니다.

    Args:
        raw_metrics: 평가 지표 딕셔너리.

    Returns:
        Dict[EvaluationMetric, float]: EvaluationMetric Enum을 키로 갖는 정제된 지표 딕셔너리.
    """
    standardized: Dict[EvaluationMetric, float] = {}
    for key, value in raw_metrics.items():
        if isinstance(key, EvaluationMetric):
            standardized[key] = float(value)
        elif isinstance(key, str):
            try:
                standardized[EvaluationMetric(key.lower())] = float(value)
            except ValueError:
                continue
    return standardized


def _standardize_candidates(
    candidates_metrics: Union[Dict[str, Dict[Any, float]], pd.DataFrame],
) -> Dict[str, Dict[EvaluationMetric, float]]:
    """입력 다중 모델 데이터를 표준 Dict[str, Dict[EvaluationMetric, float]] 구조로 변환합니다.

    Args:
        candidates_metrics: 모델명을 키로 하는 메트릭 딕셔너리 또는 판다스 DataFrame.

    Returns:
        Dict[str, Dict[EvaluationMetric, float]]: 모델명을 키로 하고 정규화된 지표 맵을 값으로 갖는 딕셔너리.

    Raises:
        TypeError: 지원하지 않는 입력 데이터 타입일 경우 발생.
    """
    if isinstance(candidates_metrics, pd.DataFrame):
        return {
            str(model_name): _standardize_metrics_map(row.to_dict())
            for model_name, row in candidates_metrics.iterrows()
        }
    elif isinstance(candidates_metrics, dict):
        return {
            str(model_name): _standardize_metrics_map(metric_dict)
            for model_name, metric_dict in candidates_metrics.items()
        }
    else:
        raise TypeError(f"지원하지 않는 입력 형식입니다: {type(candidates_metrics)}")