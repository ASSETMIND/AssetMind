from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.model.evaluation.schema import (
    EvaluationMetric,
    METRIC_REGISTRY,
)


# ==============================================================================
# 1. 평가 게이트 및 가중치 불변 자료구조 정의 (Public Data Classes)
# ==============================================================================

@dataclass(frozen=True)
class MLValidityGate:
    """기계학습 기본 수렴 및 방향성 붕괴 차단을 위한 기초 유효성 게이트 DTO (Tier 1).

    Attributes:
        min_mda (float): 최소 허용 방향성 적중률 (기본값: 0.50, 무작위 동전 던지기 기준선).
        max_rmse_ratio (float): 타겟 표준편차(target_std) 대비 허용 최대 RMSE 배수 (기본값: 1.00).
    """
    min_mda: float = 0.50
    max_rmse_ratio: float = 1.00


@dataclass(frozen=True)
class FactorQualityGate:
    """예측 신호의 상대적 랭킹 단조성 및 시계열 일관성 검증 게이트 DTO (Tier 2).

    Attributes:
        min_rank_ic (float): 최소 허용 순위 정보 계수 (기본값: 0.00).
        min_icir (float): 최소 허용 팩터 정보 비율 (기본값: 0.30).
    """
    min_rank_ic: float = 0.00
    min_icir: float = 0.30


@dataclass(frozen=True)
class FinanceGate:
    """포지션 진입 시 위험조정수익성 및 극단 하방 자본 파산 차단을 위한 금융 성과 게이트 DTO (Tier 3).

    Attributes:
        min_sharpe (float): 최소 허용 연율화 샤프 지수 (기본값: 0.50).
        min_sortino (float): 최소 허용 연율화 소르티노 지수 (기본값: 0.70).
        max_mdd (float): 최대 허용 낙폭 비율 (기본값: 0.30, 즉 30%).
    """
    min_sharpe: float = 0.50
    min_sortino: float = 0.70
    max_mdd: float = 0.30


@dataclass(frozen=True)
class StatisticalGate:
    """예측 신호의 팩터 순위 정보력(Rank IC)에 대한 통계적 유의성 검증 게이트 DTO (Tier 4).

    Attributes:
        min_factor_tstat (float): 최소 허용 팩터 Rank IC t-통계량 (기본값: 1.96, 유의수준 α=0.05 기준선).
    """
    # [설계 의도] 팩터 신호 품질(Rank IC)에 대해 계량경제학 표준 기각역(t >= 1.96, p < 0.05)을 강제하여
    # 우연에 의한 가짜 알파(Spurious Alpha)를 엄격히 차단함
    min_factor_tstat: float = 1.96


@dataclass(frozen=True)
class Weights:
    """HPO 최적화 및 챔피언 선별을 위한 순수 신호 품질 중심의 2계층 가중치 DTO.

    Attributes:
        layer_1_ml (float): 기계학습 기본 방향성(MDA) 계층 가중치 (기본값: 0.30).
        layer_2_factor (float): 퀀트 팩터 신호 품질(Rank IC & ICIR) 계층 가중치 (기본값: 0.70).
    """
    layer_1_ml: float = 0.30
    layer_2_factor: float = 0.70

@dataclass(frozen=True)
class OverfitGate:
    """일반화 붕괴 및 과적합 통제를 위한 상대적 평가 게이트 DTO (Tier 3).

    Attributes:
        k_score_sigma (float): CV 표본오차 연동 점수 허용 하한 배수 (기본값: 2.132, Student-t df=4 95% 단측 임계치).
        base_gdr_mdd (float): 기준 MDD 최대 허용 악화율 (%, 기본값: 30.0).
        max_rir (float): CV 대비 Test RMSE 최대 허용 팽창 배수 (기본값: 1.25, 표본오차 5% 반영).
        min_dsr (float): HPO 다중 시도 편향 보정 최소 신뢰확률 (기본값: 0.95).
        max_gdr_score (float): OOS 자연 감쇄율(Harvey et al. 2016 30~50%) 반영 최대 허용 열화율 (%, 기본값: 38.0).
        max_gdr_mdd (float): 하위 호환용 기본 악화율 (기본값: 30.0).
        max_score_lower_bound (float): 포화 분산 왜곡 방어용 동적 신뢰 하한 최대 상한선 (기본값: 0.85).
    """
    k_score_sigma: float = 2.132
    base_gdr_mdd: float = 30.0
    max_rir: float = 1.25
    min_dsr: float = 0.95
    max_gdr_score: float = 38.0
    max_gdr_mdd: float = 30.0
    max_score_lower_bound: float = 0.85

# ==============================================================================
# 2. 공개 게이트 판정 및 감사 리포트 API (Public Interfaces)
# ==============================================================================

def check_ml_validity_gate(
    metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
    gate: MLValidityGate,
    target_std: float = 1.0,
) -> Tuple[bool, List[str]]:
    """머신러닝 기본 방향성 및 오차 발산 여부를 검증합니다 (Tier 1).

    Args:
        metrics: 모델의 산출 지표 딕셔너리.
        gate: ML 유효성 게이트 설정 DTO.
        target_std: 타겟 시계열 표준편차 (RMSE 상한 기준 분모).

    Returns:
        Tuple[bool, List[str]]: (전수 통과 여부, 위반 사유 목록).
    """
    clean_metrics: Dict[EvaluationMetric, float] = _standardize_metrics_map(metrics)
    violations: List[str] = []
    safe_std: float = target_std if (target_std > 0.0 and np.isfinite(target_std)) else 1.0
    max_allowable_rmse: float = safe_std * gate.max_rmse_ratio

    # [설계 의도] 1. 부호(방향성)가 50% 미만으로 무너진 모델 즉시 컷
    actual_mda = clean_metrics.get(EvaluationMetric.MDA, 0.0)
    if actual_mda < gate.min_mda:
        violations.append(f"MDA 미달 ({actual_mda:.4f} < {gate.min_mda:.4f})")

    # [설계 의도] 2. RMSE가 타겟 분산보다 커서 단순 평균 예측보다 못한 발산 모델 컷
    actual_rmse = clean_metrics.get(EvaluationMetric.RMSE, float("inf"))
    if actual_rmse > max_allowable_rmse:
        violations.append(f"RMSE 초과 ({actual_rmse:.4f} > {max_allowable_rmse:.4f})")

    return len(violations) == 0, violations


def check_factor_quality_gate(
    metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
    gate: FactorQualityGate,
) -> Tuple[bool, List[str]]:
    """팩터 신호의 순위 단조성과 시계열 안정성을 검증합니다 (Tier 2).

    Args:
        metrics: 모델의 산출 지표 딕셔너리.
        gate: 팩터 품질 게이트 설정 DTO.

    Returns:
        Tuple[bool, List[str]]: (전수 통과 여부, 위반 사유 목록).
    """
    clean_metrics: Dict[EvaluationMetric, float] = _standardize_metrics_map(metrics)
    violations: List[str] = []

    actual_rank_ic = clean_metrics.get(EvaluationMetric.RANK_IC, -1.0)
    if actual_rank_ic <= gate.min_rank_ic:
        violations.append(f"Rank IC 미달 ({actual_rank_ic:.4f} <= {gate.min_rank_ic:.4f})")

    actual_icir = clean_metrics.get(EvaluationMetric.ICIR, -999.0)
    if actual_icir < gate.min_icir:
        violations.append(f"ICIR 미달 ({actual_icir:.4f} < {gate.min_icir:.4f})")

    return len(violations) == 0, violations


def check_finance_gate(
    metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
    gate: FinanceGate,
) -> Tuple[bool, List[str]]:
    """신호 기반 단순 매매 집행 시의 금융 리스크 및 하방 위험을 검증합니다 (Tier 3).

    Args:
        metrics: 모델의 산출 지표 딕셔너리.
        gate: 금융 성과 게이트 설정 DTO.

    Returns:
        Tuple[bool, List[str]]: (전수 통과 여부, 위반 사유 목록).
    """
    clean_metrics: Dict[EvaluationMetric, float] = _standardize_metrics_map(metrics)
    violations: List[str] = []

    actual_sharpe = clean_metrics.get(EvaluationMetric.SIGNAL_SHARPE, -999.0)
    if actual_sharpe < gate.min_sharpe:
        violations.append(f"Signal Sharpe 미달 ({actual_sharpe:.4f} < {gate.min_sharpe:.4f})")

    actual_sortino = clean_metrics.get(EvaluationMetric.SORTINO_RATIO, -999.0)
    if actual_sortino < gate.min_sortino:
        violations.append(f"Sortino Ratio 미달 ({actual_sortino:.4f} < {gate.min_sortino:.4f})")

    actual_mdd = clean_metrics.get(EvaluationMetric.MDD, 1.0)
    if actual_mdd > gate.max_mdd:
        violations.append(f"MDD 한도 초과 ({actual_mdd:.4f} > {gate.max_mdd:.4f})")

    return len(violations) == 0, violations


def check_statistical_gate(
    metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
    gate: StatisticalGate,
) -> Tuple[bool, List[str]]:
    """Newey-West HAC t-통계량을 통한 단일 신호 알파 유의성을 검증합니다 (Tier 4).

    Args:
        metrics: 모델의 산출 지표 딕셔너리.
        gate: 통계적 유의성 게이트 설정 DTO.

    Returns:
        Tuple[bool, List[str]]: (통과 여부, 위반 사유 목록).
    """
    clean_metrics: Dict[EvaluationMetric, float] = _standardize_metrics_map(metrics)
    violations: List[str] = []

    actual_tstat = clean_metrics.get(EvaluationMetric.FACTOR_T_STAT, 0.0)
    if actual_tstat < gate.min_factor_tstat:
        violations.append(f"Factor t-stat 유의성 미달 ({actual_tstat:.4f} < {gate.min_factor_tstat:.4f})")

    return len(violations) == 0, violations


def check_overfit_gate(
    cv_metrics: Dict[EvaluationMetric, float],
    test_metrics: Dict[EvaluationMetric, float],
    cv_score: float,
    test_score: float,
    gate: OverfitGate,
    dsr: float = 1.0,
    cv_target_std: Optional[float] = None,
    test_target_std: Optional[float] = None,
    cv_score_std: Optional[float] = None,
) -> Tuple[bool, float, float, float, List[str]]:
    """CV 대비 Test의 일반화 열화 지표(GDR, RIR) 및 DSR을 검증합니다.

    Returns:
        Tuple[bool, float, float, float, List[str]]:
            (is_passed, gdr_score, gdr_mdd, rir, violations)
    """
    violations: List[str] = []

    # 1. Score: CV 표본오차 연동 동적 신뢰 하한 검증 (Fallback: 고정 gdr_score)
    gdr_score: float = 0.0
    if cv_score > 1e-8:
        gdr_score = max(0.0, float((cv_score - test_score) / cv_score * 100.0))

    if cv_score_std is not None and cv_score_std > 0.0 and np.isfinite(cv_score_std):
        # [설계 의도] Casella & Berger (2002) 단일 미래 관측치에 대한 Student-t 예측구간(df=4, SE = s * √(1 + 1/K)) 적용
        # 및 안정성 역설(σ_cv -> 0 수렴 시 하한선 폭등)을 방어하기 위해 max_score_lower_bound 상한 캡 결합
        t_crit: float = gate.k_score_sigma
        score_se: float = cv_score_std * np.sqrt(1.0 + (1.0 / 5.0))
        raw_score_lower_bound: float = cv_score - (t_crit * score_se)
        score_lower_bound: float = min(raw_score_lower_bound, gate.max_score_lower_bound)
        if test_score < score_lower_bound:
            violations.append(
                f"Score 동적 신뢰 하한 미달 ({test_score:.4f} < {score_lower_bound:.4f} "
                f"[raw: {raw_score_lower_bound:.4f}, cap: {gate.max_score_lower_bound:.2f}])"
            )
        if gdr_score > gate.max_gdr_score:
            violations.append(f"GDR(Score) 열화 초과 ({gdr_score:.2f}% > {gate.max_gdr_score:.1f}%)")
    else:
        if gdr_score > gate.max_gdr_score:
            violations.append(f"GDR(Score) 열화 초과 ({gdr_score:.2f}% > {gate.max_gdr_score:.1f}%)")

    # 2. GDR MDD: 시장 레짐 변동성(target_std) 확대 비율 보정 동적 악화 한도 검증
    cv_mdd = max(1e-8, cv_metrics.get(EvaluationMetric.MDD, 0.0))
    test_mdd = test_metrics.get(EvaluationMetric.MDD, 0.0)
    # [설계 의도] CV MDD가 10% 미만인 초저위험 구간에서 발생하는 극소 분모(Zero-Division) 기저 왜곡을 방어하기 위해 분모 바닥선(0.10) 적용
    denominator_mdd: float = max(0.10, cv_mdd)
    gdr_mdd: float = max(0.0, float((test_mdd - cv_mdd) / denominator_mdd * 100.0))

    regime_ratio: float = 1.0
    if (
        cv_target_std is not None
        and test_target_std is not None
        and cv_target_std > 0.0
        and test_target_std > 0.0
        and np.isfinite(cv_target_std)
        and np.isfinite(test_target_std)
    ):
        # [설계 의도] ADP 3과목 Two-Sample F-검정 분산비(s_test^2 / s_cv^2) 원리를 적용하여
        # 시장 레짐 전환(이분산성)에 따른 2차 적률 변동성 확대 승수 산출
        regime_ratio = max(1.0, float((test_target_std / cv_target_std) ** 2))

    effective_max_gdr_mdd: float = gate.base_gdr_mdd * regime_ratio
    # [설계 의도] 절대 저위험 안전권(Test MDD <= 15.0%) 내 감점 면제 및 절대·상대 혼합형(Hybrid) 게이트 적용
    if test_mdd > 0.15 and gdr_mdd > effective_max_gdr_mdd:
        violations.append(
            f"GDR(MDD) 악화 초과 (+{gdr_mdd:.2f}% > {effective_max_gdr_mdd:.1f}% "
            f"[레짐 보정 {regime_ratio:.2f}x])"
        )

    # 3. RIR: NRMSE_test / NRMSE_cv (타겟 표준편차 변동성 보정 잔차 팽창비)
    cv_rmse = max(1e-8, cv_metrics.get(EvaluationMetric.RMSE, 1.0))
    test_rmse = test_metrics.get(EvaluationMetric.RMSE, 1.0)

    # [설계 의도] 타겟 시계열 이분산성(레짐 전환으로 인한 타겟 분산 확대)을 보정하기 위해
    # CV와 Test의 타겟 표준편차(target_std)가 모두 유효할 경우 정규화 NRMSE 비율로 산출
    if (
        cv_target_std is not None
        and test_target_std is not None
        and cv_target_std > 0.0
        and test_target_std > 0.0
        and np.isfinite(cv_target_std)
        and np.isfinite(test_target_std)
    ):
        cv_nrmse = cv_rmse / cv_target_std
        test_nrmse = test_rmse / test_target_std
        rir: float = float(test_nrmse / max(1e-8, cv_nrmse))
    else:
        rir = float(test_rmse / cv_rmse)

    if rir > gate.max_rir:
        violations.append(f"RIR(잔차팽창) 초과 ({rir:.3f} > {gate.max_rir:.2f})")

    # 4. DSR: 다중 시도 편향 보정치
    if dsr < gate.min_dsr:
        violations.append(f"DSR 신뢰도 미달 ({dsr:.3f} < {gate.min_dsr:.2f})")

    is_passed: bool = len(violations) == 0
    return is_passed, gdr_score, gdr_mdd, rir, violations


def get_score_report(
    candidates_metrics: Union[Dict[str, Dict[Any, float]], pd.DataFrame],
    ml_gate: Optional[MLValidityGate] = None,
    factor_gate: Optional[FactorQualityGate] = None,
    finance_gate: Optional[FinanceGate] = None,
    stat_gate: Optional[StatisticalGate] = None,
    overfit_gate: Optional[OverfitGate] = None,
    cv_context: Optional[Dict[str, Dict[str, Any]]] = None,
    target_std: float = 1.0,
) -> pd.DataFrame:
    """5대 도메인 게이트(ML, Factor, Finance, Statistical, Overfit) 단계별 감사 리포트를 생성합니다.

    Args:
        candidates_metrics: 모델명을 키로 하는 메트릭 맵 또는 모델별 지표 행렬 DataFrame.
        ml_gate: ML 유효성 게이트 DTO (None일 경우 기본값 적용).
        factor_gate: 팩터 품질 게이트 DTO (None일 경우 기본값 적용).
        finance_gate: 금융 성과 게이트 DTO (None일 경우 기본값 적용).
        stat_gate: 통계적 유의성 게이트 DTO (None일 경우 기본값 적용).
        overfit_gate: 과적합 게이트 DTO (None일 경우 기본값 적용).
        cv_context: CV 대비 Test 일반화 검증 컨텍스트.
        target_std: 타겟 시계열 표준편차.

    Returns:
        pd.DataFrame: 모델명을 인덱스로 가지며 최종 판정 및 도메인별 통과 현황을 명시한 감사 리포트.
    """
    effective_ml_gate = ml_gate or MLValidityGate()
    effective_factor_gate = factor_gate or FactorQualityGate()
    effective_finance_gate = finance_gate or FinanceGate()
    effective_stat_gate = stat_gate or StatisticalGate()
    effective_overfit_gate = overfit_gate or OverfitGate()

    standardized_candidates = _standardize_candidates(candidates_metrics)
    audit_records: List[Dict[str, Any]] = []

    for model_name, metric_map in standardized_candidates.items():
        ml_pass, ml_v = check_ml_validity_gate(metric_map, effective_ml_gate, target_std=target_std)
        factor_pass, factor_v = check_factor_quality_gate(metric_map, effective_factor_gate)
        fin_pass, fin_v = check_finance_gate(metric_map, effective_finance_gate)
        stat_pass, stat_v = check_statistical_gate(metric_map, effective_stat_gate)

        overfit_pass: bool = True
        overfit_v: List[str] = []
        if cv_context and model_name in cv_context:
            ctx = cv_context[model_name]
            overfit_pass, _, _, _, overfit_v = check_overfit_gate(
                cv_metrics=ctx["cv_metrics"],
                test_metrics=metric_map,
                cv_score=ctx["cv_score"],
                test_score=ctx["test_score"],
                gate=effective_overfit_gate,
                dsr=ctx.get("dsr", 1.0),
                cv_target_std=ctx.get("cv_target_std"),
                test_target_std=target_std,
                cv_score_std=ctx.get("cv_score_std"),
            )

        is_qualified = ml_pass and factor_pass and fin_pass and stat_pass and overfit_pass
        all_violations = ml_v + factor_v + fin_v + stat_v + overfit_v

        audit_records.append({
            "model_name": model_name,
            "final_verdict": "QUALIFIED" if is_qualified else "DISQUALIFIED",
            "ml_gate_pass": ml_pass,
            "factor_gate_pass": factor_pass,
            "finance_gate_pass": fin_pass,
            "stat_gate_pass": stat_pass,
            "overfit_gate_pass": overfit_pass,
            "key_violations": " | ".join(all_violations) if all_violations else "None",
        })

    return pd.DataFrame(audit_records).set_index("model_name")


# ==============================================================================
# 3. 내부 데이터 정규화 및 수리 검증 헬퍼 (Private Helpers)
# ==============================================================================

def _validate_metric_threshold(
    metric: EvaluationMetric,
    actual_value: float,
    threshold: float,
) -> Tuple[bool, Optional[str]]:
    """schema.py의 메타데이터(is_greater_better)를 참조하여 임계치 충족 여부 및 위반 문구를 산출합니다.

    Args:
        metric: 검증 대상 표준 평가 지표 Enum.
        actual_value: 모델이 실제로 기록한 지표 수치.
        threshold: 충족해야 하는 임계치 기준값.

    Returns:
        Tuple[bool, Optional[str]]:
            - is_passed (bool): 기준 통과 여부.
            - violation_message (Optional[str]): 탈락 시 위반 사유 설명 문구 (통과 시 None).
    """
    # schema.py의 METRIC_REGISTRY(SSOT)에 등록된 is_greater_better 메타데이터를 기반으로
    # 하드코딩된 부등호 분기 없이 단일 로직으로 최대화/최소화 방향성을 일반화하여 판정
    metadata = METRIC_REGISTRY[metric]
    display_name: str = metadata.display_name

    if metadata.is_greater_better:
        is_passed = actual_value >= threshold
        violation_message = (
            f"{display_name} 미달 ({actual_value:.4f} < {threshold:.4f})"
            if not is_passed
            else None
        )
    else:
        is_passed = actual_value <= threshold
        violation_message = (
            f"{display_name} 초과 ({actual_value:.4f} > {threshold:.4f})"
            if not is_passed
            else None
        )

    return is_passed, violation_message


def _standardize_metrics_map(
    raw_metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
) -> Dict[EvaluationMetric, float]:
    """임의의 키 형식(str 또는 EvaluationMetric)을 갖는 메트릭 맵을 표준 Enum 키 딕셔너리로 정규화합니다.

    Args:
        raw_metrics: 평가 지표 딕셔너리.

    Returns:
        Dict[EvaluationMetric, float]: EvaluationMetric Enum을 키로 갖는 정제된 지표 딕셔너리.
    """
    # 문자열 소문자 변환 후 Enum 생성자를 호출하여, 대소문자 차이로 인한 키 누락 방어
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
    """입력 데이터 형식을 표준 Dict[str, Dict[EvaluationMetric, float]] 다중 모델 맵으로 변환합니다.

    Args:
        candidates_metrics: 모델명을 키로 하는 메트릭 딕셔너리 또는 판다스 DataFrame.

    Returns:
        Dict[str, Dict[EvaluationMetric, float]]: 모델명을 키로 하고 정규화된 지표 맵을 값으로 갖는 딕셔너리.

    Raises:
        TypeError: 지원하지 않는 입력 데이터 타입(DataFrame, Dict 외)이 인입된 경우 발생.
    """
    # 외부 입력 형식의 다양성을 수용하되, 내부 감사 루프 진입 전 통일된 스키마로 방어적 변환
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