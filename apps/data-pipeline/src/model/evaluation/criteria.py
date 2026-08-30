"""
금융 ML 6대 평가 계층 기반 모델 적격성 판정 게이트 및 가중치 명세 모듈.

[주요 구성 요소]
1. HardGate: 프로덕션 배포 최소 가드레일 (5개 지표 전수 통과 필수)
2. SoftGate: 모델 일반화 품질 기준 (5개 지표 중 K개 이상 통과 필수)
3. Weights: 4대 평가 계층(ML 오차, 팩터 품질, 금융 시뮬레이션, 알파 유의성) 가중치 DTO
4. get_score_report: 전 후보 모델의 게이트 통과 현황 및 탈락 사유 감사 리포트 생성
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


# ==============================================================================
# 1. 평가 게이트 및 가중치 불변 자료구조 정의 (Data Classes)
# ==============================================================================

@dataclass(frozen=True)
class HardGate:
    """하드 게이트 임계치 설정 (5개 전수 만족 필수).
    
    Attributes:
        min_mda (float): 최소 방향성 적중률 (기본값: 0.50).
        min_rank_ic (float): 최소 순위 정보 계수 (기본값: 0.00).
        max_mdd (float): 최대 허용 낙폭 비율 (기본값: 0.30).
        min_factor_tstat (float): 최소 Newey-West t-통계량 (기본값: 1.96, p <= 0.05).
        max_latency_ms (float): 최대 허용 추론 지연시간 (기본값: 500.0ms).
    """
    min_mda: float = 0.50
    min_rank_ic: float = 0.00
    max_mdd: float = 0.30
    min_factor_tstat: float = 1.96
    max_latency_ms: float = 500.0


@dataclass(frozen=True)
class SoftGate:
    """소프트 게이트 임계치 설정 (5개 고정 지표 중 K개 이상 만족 필수).
    
    Attributes:
        max_rmse (float): 최대 허용 RMSE (기본값: 0.35).
        max_mae (float): 최대 허용 MAE (기본값: 0.25).
        min_icir (float): 최소 팩터 정보 비율 (기본값: 0.50).
        min_sharpe (float): 최소 신호 기반 연율화 샤프 지수 (기본값: 0.50).
        min_sortino (float): 최소 신호 기반 연율화 소르티노 지수 (기본값: 0.70).
        min_passed_count (int): 최소 통과 필요 소프트 지표 개수 K (기본값: 3).
    """
    max_rmse: float = 0.35
    max_mae: float = 0.25
    min_icir: float = 0.50
    min_sharpe: float = 0.50
    min_sortino: float = 0.70
    min_passed_count: int = 3


@dataclass(frozen=True)
class Weights:
    """4대 평가 계층별 복합 스코어링 가중치 설정 (합계 1.0).
    
    Attributes:
        layer_1_ml (float): 기계학습 기본 오차 계층 가중치 (기본값: 0.15).
        layer_2_factor (float): 퀀트 팩터 신호 품질 계층 가중치 (기본값: 0.35).
        layer_3_finance (float): 금융 시뮬레이션 성과 계층 가중치 (기본값: 0.35).
        layer_4_stat (float): 단일 알파 통계적 유의성 계층 가중치 (기본값: 0.15).
    """
    layer_1_ml: float = 0.15
    layer_2_factor: float = 0.35
    layer_3_finance: float = 0.35
    layer_4_stat: float = 0.15


# ==============================================================================
# 2. 내부 게이트 검증 서브 루틴 (Private Helpers)
# ==============================================================================

def extract_metric_value(metrics: Dict[str, float], keys: List[str], default: float = 0.0) -> float:
    """대소문자 및 언더바 표기 차이에 관계없이 지표 값을 안전하게 적출합니다."""
    for key in keys:
        if key in metrics:
            return float(metrics[key])
        lower_key = key.lower()
        for m_key, m_val in metrics.items():
            if m_key.lower() == lower_key:
                return float(m_val)
    return default


def check_hard_gate(metrics: Dict[str, float], gate: HardGate) -> Tuple[bool, List[str]]:
    """단일 모델의 5대 하드 게이트 만족 여부 및 위반 사유를 검사합니다."""
    violations: List[str] = []
    
    val_mda = extract_metric_value(metrics, ["MDA", "mda"], default=0.0)
    if val_mda < gate.min_mda:
        violations.append(f"MDA 미달 ({val_mda:.4f} < {gate.min_mda:.2f})")
        
    val_rank_ic = extract_metric_value(metrics, ["Rank_IC", "rank_ic", "Rank IC"], default=-1.0)
    if val_rank_ic < gate.min_rank_ic:
        violations.append(f"Rank IC 미달 ({val_rank_ic:.4f} < {gate.min_rank_ic:.2f})")
        
    val_mdd = extract_metric_value(metrics, ["MDD", "mdd"], default=1.0)
    if val_mdd > gate.max_mdd:
        violations.append(f"MDD 초과 ({val_mdd * 100:.1f}% > {gate.max_mdd * 100:.1f}%)")
        
    val_tstat = extract_metric_value(metrics, ["Factor_t_stat", "factor_t_stat", "t_stat", "tstat"], default=0.0)
    if val_tstat < gate.min_factor_tstat:
        violations.append(f"Factor t-stat 유의성 미달 ({val_tstat:.2f} < {gate.min_factor_tstat:.2f})")
        
    val_latency = extract_metric_value(metrics, ["Latency", "latency", "latency_ms", "Latency_ms"], default=0.0)
    if val_latency > gate.max_latency_ms:
        violations.append(f"추론 Latency 초과 ({val_latency:.2f}ms > {gate.max_latency_ms:.2f}ms)")
        
    is_passed = len(violations) == 0
    return is_passed, violations


def check_soft_gate(metrics: Dict[str, float], gate: SoftGate) -> Tuple[bool, int, int, List[str]]:
    """단일 모델의 5대 소프트 게이트 전수 검사를 집행합니다."""
    passed_count = 0
    total_evaluated = 5
    unmet_reasons: List[str] = []
    
    val_rmse = extract_metric_value(metrics, ["RMSE", "rmse"], default=999.0)
    if val_rmse <= gate.max_rmse:
        passed_count += 1
    else:
        unmet_reasons.append(f"RMSE 초과 ({val_rmse:.5f} > {gate.max_rmse:.5f})")
        
    val_mae = extract_metric_value(metrics, ["MAE", "mae"], default=999.0)
    if val_mae <= gate.max_mae:
        passed_count += 1
    else:
        unmet_reasons.append(f"MAE 초과 ({val_mae:.5f} > {gate.max_mae:.5f})")
        
    val_icir = extract_metric_value(metrics, ["ICIR", "icir"], default=0.0)
    if val_icir >= gate.min_icir:
        passed_count += 1
    else:
        unmet_reasons.append(f"ICIR 미달 ({val_icir:.3f} < {gate.min_icir:.2f})")
        
    val_sharpe = extract_metric_value(metrics, ["Signal_Sharpe", "signal_sharpe", "Sharpe", "sharpe"], default=-99.0)
    if val_sharpe >= gate.min_sharpe:
        passed_count += 1
    else:
        unmet_reasons.append(f"Sharpe 미달 ({val_sharpe:.2f} < {gate.min_sharpe:.2f})")
        
    val_sortino = extract_metric_value(metrics, ["Sortino_Ratio", "sortino_ratio", "Sortino", "sortino"], default=-99.0)
    if val_sortino >= gate.min_sortino:
        passed_count += 1
    else:
        unmet_reasons.append(f"Sortino 미달 ({val_sortino:.2f} < {gate.min_sortino:.2f})")
        
    is_passed = passed_count >= gate.min_passed_count
    return is_passed, passed_count, total_evaluated, unmet_reasons


def standardize_input_candidates(
    candidates_metrics: Union[Dict[str, Dict[str, float]], pd.DataFrame]
) -> Dict[str, Dict[str, float]]:
    """입력 데이터 형식을 표준 딕셔너리 포맷으로 통일 변환합니다."""
    if isinstance(candidates_metrics, pd.DataFrame):
        return {str(idx): row.to_dict() for idx, row in candidates_metrics.iterrows()}
    elif isinstance(candidates_metrics, dict):
        return candidates_metrics
    else:
        raise TypeError(f"지원하지 않는 입력 형식입니다: {type(candidates_metrics)}")


# ==============================================================================
# 3. 공개 감사 리포트 API (Public Audit Interface)
# ==============================================================================

def get_score_report(
    candidates_metrics: Union[Dict[str, Dict[str, float]], pd.DataFrame],
    hard_gate: Optional[HardGate] = None,
    soft_gate: Optional[SoftGate] = None
) -> pd.DataFrame:
    """전체 후보 모델의 2단계 게이트 통과 현황 및 탈락 사유 감사 리포트를 생성합니다."""
    if hard_gate is None:
        hard_gate = HardGate()
    if soft_gate is None:
        soft_gate = SoftGate()
        
    candidate_dict = standardize_input_candidates(candidates_metrics)
    audit_records: List[Dict[str, Any]] = []
    
    for model_name, metrics in candidate_dict.items():
        hard_pass, hard_violations = check_hard_gate(metrics, hard_gate)
        soft_pass, soft_count, soft_total, soft_unmets = check_soft_gate(metrics, soft_gate)
        is_qualified = hard_pass and soft_pass
        
        audit_records.append({
            "model_name": model_name,
            "is_qualified": "QUALIFIED" if is_qualified else "DISQUALIFIED",
            "hard_gate_pass": hard_pass,
            "hard_violations": ", ".join(hard_violations) if hard_violations else "None",
            "soft_gate_pass": soft_pass,
            "soft_passed_ratio": f"{soft_count} / {soft_total} (K={soft_gate.min_passed_count})",
            "soft_unmet_reasons": ", ".join(soft_unmets) if soft_unmets else "None"
        })
        
    return pd.DataFrame(audit_records).set_index("model_name")