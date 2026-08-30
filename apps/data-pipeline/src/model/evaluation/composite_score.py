from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.model.evaluation.criteria import (
    HardGate,
    SoftGate,
    Weights,
    check_hard_gate,
    check_soft_gate,
    extract_metric_value,
    standardize_input_candidates,
)


# ==============================================================================
# 1. 내부 수리 정규화 및 스코어링 서브 루틴 (Private Helpers)
# ==============================================================================

def _normalize_series(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """단일 지표 시리즈를 [0.0, 1.0] 범위로 정규화합니다 (분모 0 방어)."""
    min_val = series.min()
    max_val = series.max()
    
    if np.isclose(max_val, min_val):
        return pd.Series(1.0, index=series.index)
        
    if higher_is_better:
        return (series - min_val) / (max_val - min_val)
    else:
        return (max_val - series) / (max_val - min_val)


def _calculate_score(
    qualified_metrics_df: pd.DataFrame, 
    weights: Weights
) -> pd.DataFrame:
    """적격 모델 데이터프레임에 대해 Min-Max 스케일링 후 가중 복합 스코어를 산출합니다."""
    df = qualified_metrics_df.copy()
    norm_df = pd.DataFrame(index=df.index)
    
    # [설계 의도] 지표별 정규화 집행 (수익/신호형: 정방향, 오차/손실형: 역방향)
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in ["rmse", "mae", "mdd"]:
            norm_df[col] = _normalize_series(df[col], higher_is_better=False)
        else:
            norm_df[col] = _normalize_series(df[col], higher_is_better=True)
            
    # Layer 1 점수 (ML 기본 오차: MDA, RMSE, MAE)
    l1_cols = [c for c in norm_df.columns if c.lower() in ["mda", "rmse", "mae"]]
    norm_df["score_layer_1"] = norm_df[l1_cols].mean(axis=1) if l1_cols else 0.0
    
    # Layer 2 점수 (팩터 신호 품질: Rank IC, ICIR)
    l2_cols = [c for c in norm_df.columns if c.lower() in ["rank_ic", "rank ic", "icir"]]
    norm_df["score_layer_2"] = norm_df[l2_cols].mean(axis=1) if l2_cols else 0.0
    
    # Layer 3 점수 (금융 시뮬레이션: Sharpe, Sortino, MDD)
    l3_cols = [c for c in norm_df.columns if c.lower() in ["signal_sharpe", "sharpe", "sortino_ratio", "sortino", "mdd"]]
    norm_df["score_layer_3"] = norm_df[l3_cols].mean(axis=1) if l3_cols else 0.0
    
    # Layer 4 점수 (단일 알파 유의성: Factor t-stat)
    l4_cols = [c for c in norm_df.columns if c.lower() in ["factor_t_stat", "factor t-stat", "t_stat", "tstat"]]
    norm_df["score_layer_4"] = norm_df[l4_cols].mean(axis=1) if l4_cols else 0.0
    
    # [설계 의도] 4대 계층 가중 합산 복합 스코어 계산
    df["score_l1_ml"] = norm_df["score_layer_1"]
    df["score_l2_factor"] = norm_df["score_layer_2"]
    df["score_l3_finance"] = norm_df["score_layer_3"]
    df["score_l4_stat"] = norm_df["score_layer_4"]
    
    total_weight = (
        weights.layer_1_ml + 
        weights.layer_2_factor + 
        weights.layer_3_finance + 
        weights.layer_4_stat
    )
    weight_divisor = total_weight if total_weight > 0.0 else 1.0

    df["composite_score"] = (
        weights.layer_1_ml * df["score_l1_ml"] +
        weights.layer_2_factor * df["score_l2_factor"] +
        weights.layer_3_finance * df["score_l3_finance"] +
        weights.layer_4_stat * df["score_l4_stat"]
    ) / weight_divisor
    
    df = df.sort_values(by="composite_score", ascending=False)
    df["rank"] = np.arange(1, len(df) + 1)
    
    return df


# ==============================================================================
# 2. 공개 스코어링 API (Public Scoring Interfaces)
# ==============================================================================

def get_score(
    candidates_metrics: Union[Dict[str, Dict[str, float]], pd.DataFrame],
    hard_gate: Optional[HardGate] = None,
    soft_gate: Optional[SoftGate] = None,
    weights: Optional[Weights] = None
) -> pd.DataFrame:
    """하드 및 소프트 게이트를 통과한 적격 모델에 대해 가중 복합 스코어를 산출하고 리더보드를 반환합니다."""
    if hard_gate is None:
        hard_gate = HardGate()
    if soft_gate is None:
        soft_gate = SoftGate()
    if weights is None:
        weights = Weights()
        
    candidate_dict = standardize_input_candidates(candidates_metrics)
    qualified_dict: Dict[str, Dict[str, float]] = {}
    
    # [설계 의도] criteria.py 모듈의 2단계 게이트 판정 규칙으로 필터링 집행
    for model_name, metrics in candidate_dict.items():
        hard_pass, _ = check_hard_gate(metrics, hard_gate)
        if not hard_pass:
            continue
            
        soft_pass, _, _, _ = check_soft_gate(metrics, soft_gate)
        if not soft_pass:
            continue
            
        qualified_dict[model_name] = metrics
        
    if not qualified_dict:
        return pd.DataFrame(columns=["composite_score", "rank"])
        
    qualified_df = pd.DataFrame.from_dict(qualified_dict, orient="index")
    scored_leaderboard = _calculate_score(qualified_df, weights)
    
    return scored_leaderboard


def get_trial_score(
    metrics: Dict[str, float],
    weights: Optional[Weights] = None,
    target_std: float = 1.0
) -> float:
    """단일 Optuna Trial의 CV 평균 메트릭을 받아 4대 계층 가중 연속 복합 스코어를 산출합니다.

    Args:
        metrics: Fold 평균 메트릭 딕셔너리 (MDA, Rank_IC, RMSE, Sharpe 등).
        weights: 4대 계층 가중치 설정 (None일 경우 기본값 사용).
        target_std: 타겟 시계열 표준편차 (RMSE/MAE 스케일 정규화용).

    Returns:
        float: [0.0, 1.0] 범위로 수렴하는 단일 목적함수 스칼라 점수.
    """
    if weights is None:
        weights = Weights()

    safe_std = target_std if (target_std > 0.0 and not np.isnan(target_std)) else 1.0

    # Layer 1. ML 기본 오차 (MDA: 정방향, RMSE/MAE: 역방향 정규화)
    val_mda = extract_metric_value(metrics, ["mean_mda", "MDA", "mda"], default=0.5)
    val_rmse = extract_metric_value(metrics, ["mean_rmse", "RMSE", "rmse"], default=safe_std)
    val_mae = extract_metric_value(metrics, ["mean_mae", "MAE", "mae"], default=safe_std)

    norm_mda = np.clip(val_mda, 0.0, 1.0)
    norm_rmse = np.clip(1.0 - (val_rmse / safe_std), 0.0, 1.0)
    norm_mae = np.clip(1.0 - (val_mae / safe_std), 0.0, 1.0)
    score_l1 = float(np.mean([norm_mda, norm_rmse, norm_mae]))

    # Layer 2. 팩터 신호 품질 (Rank IC: [-1, 1] -> [0, 1], ICIR: [0, 2.0] -> [0, 1])
    val_rank_ic = extract_metric_value(metrics, ["mean_rank_ic", "Rank_IC", "rank_ic"], default=0.0)
    val_icir = extract_metric_value(metrics, ["mean_icir", "ICIR", "icir"], default=0.0)

    norm_rank_ic = np.clip((val_rank_ic + 1.0) / 2.0, 0.0, 1.0)
    norm_icir = np.clip(val_icir / 2.0, 0.0, 1.0)
    score_l2 = float(np.mean([norm_rank_ic, norm_icir]))

    # Layer 3. 금융 시뮬레이션 (Sharpe: [0, 3.0] -> [0, 1], Sortino: [0, 4.0] -> [0, 1], MDD: 역방향)
    val_sharpe = extract_metric_value(metrics, ["mean_sharpe", "Signal_Sharpe", "sharpe"], default=0.0)
    val_sortino = extract_metric_value(metrics, ["mean_sortino", "Sortino_Ratio", "sortino"], default=0.0)
    val_mdd = extract_metric_value(metrics, ["mean_mdd", "MDD", "mdd"], default=1.0)

    norm_sharpe = np.clip(val_sharpe / 3.0, 0.0, 1.0)
    norm_sortino = np.clip(val_sortino / 4.0, 0.0, 1.0)
    norm_mdd = np.clip(1.0 - val_mdd, 0.0, 1.0)
    score_l3 = float(np.mean([norm_sharpe, norm_sortino, norm_mdd]))

    # Layer 4. 알파 유의성 (Factor t-stat: [0, 3.0] -> [0, 1])
    val_tstat = extract_metric_value(metrics, ["mean_tstat", "Factor_t_stat", "tstat"], default=0.0)
    norm_tstat = np.clip(val_tstat / 3.0, 0.0, 1.0)
    score_l4 = float(norm_tstat)

    # 4대 계층 가중 합산
    total_weight = (
        weights.layer_1_ml +
        weights.layer_2_factor +
        weights.layer_3_finance +
        weights.layer_4_stat
    )
    divisor = total_weight if total_weight > 0.0 else 1.0

    trial_score = (
        weights.layer_1_ml * score_l1 +
        weights.layer_2_factor * score_l2 +
        weights.layer_3_finance * score_l3 +
        weights.layer_4_stat * score_l4
    ) / divisor

    return float(trial_score)