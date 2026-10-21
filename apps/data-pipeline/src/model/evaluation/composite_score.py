from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from src.model.evaluation.criteria import (
    HardGate,
    SoftGate,
    Weights,
    check_hard_gate,
    check_soft_gate,
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
    hard_gate: Optional[HardGate] = None,
    soft_gate: Optional[SoftGate] = None,
    weights: Optional[Weights] = None,
    target_std: float = 1.0,
) -> pd.DataFrame:
    """하드 및 소프트 게이트를 통과한 적격 후보 모델들에 대해 4대 계층 가중 복합 스코어 리더보드를 산출합니다.

    Args:
        candidates_metrics: 전체 후보 모델들의 원시 지표 맵 또는 판다스 DataFrame.
        hard_gate: 하드 게이트 임계치 설정 DTO (None일 경우 기본값 적용).
        soft_gate: 소프트 게이트 임계치 설정 DTO (None일 경우 기본값 적용).
        weights: 4대 평가 계층 가중치 설정 DTO (None일 경우 기본값 적용).
        target_std: 타겟 시계열 표준편차 (RMSE/MAE 정규화 기준 분모, 기본값: 1.0).

    Returns:
        pd.DataFrame: 적격 모델들의 원시 지표, 4대 계층별 부분 점수(score_l1~l4),
            최종 복합 스코어(composite_score) 및 랭킹(rank)이 정렬된 리더보드.
            (적격 모델이 없을 경우 빈 DataFrame 반환)
    """
    effective_hard_gate: HardGate = hard_gate or HardGate()
    effective_soft_gate: SoftGate = soft_gate or SoftGate()
    effective_weights: Weights = weights or Weights()

    # [설계 의도] 입력 데이터를 표준 Enum 맵으로 변환 후 2단계 게이트 필터링 집행
    standardized_candidates = _standardize_candidates(candidates_metrics)
    qualified_dict: Dict[str, Dict[str, float]] = {}

    for model_name, metric_map in standardized_candidates.items():
        hard_pass, _ = check_hard_gate(metric_map, effective_hard_gate)
        if not hard_pass:
            continue

        soft_pass, _, _, _ = check_soft_gate(metric_map, effective_soft_gate)
        if not soft_pass:
            continue

        # 직렬화 및 DataFrame 생성을 위해 키를 표준 문자열(Enum.value)로 평탄화
        qualified_dict[model_name] = {
            metric.value: score for metric, score in metric_map.items()
        }

    # 적격 모델이 전무한 경우 Fail-Safe 방어
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
    """단일 Optuna HPO Trial의 Fold 평균 검증 지표를 수신하여 [0.0, 1.0] 연속 복합 목적함수 스코어를 산출합니다.

    Args:
        metrics: 단일 시도에서 산출된 Fold 평균 평가 지표 딕셔너리.
        weights: 4대 계층 가중치 설정 DTO (None일 경우 기본값 적용).
        target_std: 훈련 타겟 시계열의 표준편차 (RMSE/MAE 스케일 역방향 정규화 기준값).

    Returns:
        float: [0.0, 1.0] 범위로 수렴하는 단일 목적함수 스칼라 점수 (최대화 대상).
    """
    effective_weights: Weights = weights or Weights()
    clean_metrics: Dict[EvaluationMetric, float] = _standardize_metrics_map(metrics)
    safe_std: float = target_std if (target_std > 0.0 and np.isfinite(target_std)) else 1.0

    # --------------------------------------------------------------------------
    # Layer 1. 기계학습 기본 예측 오차 (MDA: 정방향, RMSE/MAE: 타겟 분산 대비 역방향)
    # --------------------------------------------------------------------------
    val_mda = clean_metrics.get(EvaluationMetric.MDA, 0.5)
    val_rmse = clean_metrics.get(EvaluationMetric.RMSE, safe_std)
    val_mae = clean_metrics.get(EvaluationMetric.MAE, safe_std)

    norm_mda = float(np.clip(val_mda, 0.0, 1.0))
    norm_rmse = float(np.clip(1.0 - (val_rmse / safe_std), 0.0, 1.0))
    norm_mae = float(np.clip(1.0 - (val_mae / safe_std), 0.0, 1.0))
    score_l1 = float(np.mean([norm_mda, norm_rmse, norm_mae]))

    # --------------------------------------------------------------------------
    # Layer 2. 퀀트 팩터 신호 품질 (Rank IC: [-1, 1] -> [0, 1], ICIR: [0, 2.0] -> [0, 1])
    # --------------------------------------------------------------------------
    val_rank_ic = clean_metrics.get(EvaluationMetric.RANK_IC, 0.0)
    val_icir = clean_metrics.get(EvaluationMetric.ICIR, 0.0)

    norm_rank_ic = float(np.clip((val_rank_ic + 1.0) / 2.0, 0.0, 1.0))
    norm_icir = float(np.clip(val_icir / 2.0, 0.0, 1.0))
    score_l2 = float(np.mean([norm_rank_ic, norm_icir]))

    # --------------------------------------------------------------------------
    # Layer 3. 금융 시뮬레이션 성과 (Sharpe: [0, 3.0], Sortino: [0, 4.0], MDD: 역방향)
    # --------------------------------------------------------------------------
    val_sharpe = clean_metrics.get(EvaluationMetric.SIGNAL_SHARPE, 0.0)
    val_sortino = clean_metrics.get(EvaluationMetric.SORTINO_RATIO, 0.0)
    val_mdd = clean_metrics.get(EvaluationMetric.MDD, 1.0)

    norm_sharpe = float(np.clip(val_sharpe / 3.0, 0.0, 1.0))
    norm_sortino = float(np.clip(val_sortino / 4.0, 0.0, 1.0))
    norm_mdd = float(np.clip(1.0 - val_mdd, 0.0, 1.0))
    score_l3 = float(np.mean([norm_sharpe, norm_sortino, norm_mdd]))

    # --------------------------------------------------------------------------
    # Layer 4. 단일 신호 통계적 유의성 (Factor t-stat: [0, 3.0] -> [0, 1])
    # --------------------------------------------------------------------------
    val_tstat = clean_metrics.get(EvaluationMetric.FACTOR_T_STAT, 0.0)
    score_l4 = float(np.clip(val_tstat / 3.0, 0.0, 1.0))

    # --------------------------------------------------------------------------
    # 4대 계층 가중 선형 결합 (Weighted Linear Combination)
    # --------------------------------------------------------------------------
    total_weight = (
        effective_weights.layer_1_ml +
        effective_weights.layer_2_factor +
        effective_weights.layer_3_finance +
        effective_weights.layer_4_stat
    )
    divisor: float = total_weight if total_weight > 0.0 else 1.0

    trial_score: float = (
        effective_weights.layer_1_ml * score_l1 +
        effective_weights.layer_2_factor * score_l2 +
        effective_weights.layer_3_finance * score_l3 +
        effective_weights.layer_4_stat * score_l4
    ) / divisor

    return float(trial_score)


# ==============================================================================
# 2. 내부 수리 정규화 및 스코어링 서브 루틴 (Private Helpers)
# ==============================================================================

def _calculate_score(
    qualified_metrics_df: pd.DataFrame,
    weights: Weights,
    target_std: float = 1.0,
) -> pd.DataFrame:
    """적격 모델 데이터프레임에 대해 get_trial_score와 동일한 도메인 절대 기준선 스케일링을 적용합니다[cite: 6].

    Args:
        qualified_metrics_df: 게이트를 통과한 모델들의 원시 지표 DataFrame.
        weights: 4대 계층 가중치 DTO.
        target_std: 타겟 시계열 표준편차 (RMSE/MAE 정규화 기준 분모).

    Returns:
        pd.DataFrame: 계층별 점수 및 최종 composite_score로 정렬된 DataFrame.
    """
    df = qualified_metrics_df.copy()
    safe_std: float = target_std if (target_std > 0.0 and np.isfinite(target_std)) else 1.0

    # [설계 의도] Layer 1. 기계학습 기본 예측 오차 (절대 도메인 기준선 벡터 연산)
    norm_mda = np.clip(df.get(EvaluationMetric.MDA.value, 0.5), 0.0, 1.0)
    norm_rmse = np.clip(1.0 - (df.get(EvaluationMetric.RMSE.value, safe_std) / safe_std), 0.0, 1.0)
    norm_mae = np.clip(1.0 - (df.get(EvaluationMetric.MAE.value, safe_std) / safe_std), 0.0, 1.0)
    df["score_l1_ml"] = (norm_mda + norm_rmse + norm_mae) / 3.0

    # [설계 의도] Layer 2. 퀀트 팩터 신호 품질 (절대 도메인 기준선 벡터 연산)
    norm_rank_ic = np.clip((df.get(EvaluationMetric.RANK_IC.value, 0.0) + 1.0) / 2.0, 0.0, 1.0)
    norm_icir = np.clip(df.get(EvaluationMetric.ICIR.value, 0.0) / 2.0, 0.0, 1.0)
    df["score_l2_factor"] = (norm_rank_ic + norm_icir) / 2.0

    # [설계 의도] Layer 3. 금융 시뮬레이션 성과 (절대 도메인 기준선 벡터 연산)
    norm_sharpe = np.clip(df.get(EvaluationMetric.SIGNAL_SHARPE.value, 0.0) / 3.0, 0.0, 1.0)
    norm_sortino = np.clip(df.get(EvaluationMetric.SORTINO_RATIO.value, 0.0) / 4.0, 0.0, 1.0)
    norm_mdd = np.clip(1.0 - df.get(EvaluationMetric.MDD.value, 1.0), 0.0, 1.0)
    df["score_l3_finance"] = (norm_sharpe + norm_sortino + norm_mdd) / 3.0

    # [설계 의도] Layer 4. 단일 신호 통계적 유의성 (절대 도메인 기준선 벡터 연산)
    df["score_l4_stat"] = np.clip(df.get(EvaluationMetric.FACTOR_T_STAT.value, 0.0) / 3.0, 0.0, 1.0)

    # [설계 의도] 4대 계층 가중 선형 결합 (Optimization 목적함수와 100% 동일 수식 적용)
    total_weight: float = (
        weights.layer_1_ml +
        weights.layer_2_factor +
        weights.layer_3_finance +
        weights.layer_4_stat
    )
    weight_divisor: float = total_weight if total_weight > 0.0 else 1.0

    df["composite_score"] = (
        weights.layer_1_ml * df["score_l1_ml"] +
        weights.layer_2_factor * df["score_l2_factor"] +
        weights.layer_3_finance * df["score_l3_finance"] +
        weights.layer_4_stat * df["score_l4_stat"]
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