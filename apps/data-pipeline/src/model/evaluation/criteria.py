from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

from src.model.evaluation.schema import (
    EvaluationMetric,
    METRIC_REGISTRY,
)


# ==============================================================================
# 1. 평가 게이트 및 가중치 불변 자료구조 정의 (Public Data Classes)
# ==============================================================================

@dataclass(frozen=True)
class HardGate:
    """프로덕션 배포를 위한 최소 요구조건 하드 게이트 설정 DTO (4대 지표 전수 통과 필수).

    Attributes:
        min_mda (float): 최소 허용 방향성 적중률 (기본값: 0.50).
        min_rank_ic (float): 최소 허용 순위 정보 계수 (기본값: 0.00).
        max_mdd (float): 최대 허용 낙폭 비율 (기본값: 0.30, 즉 30%).
        min_factor_tstat (float): 최소 허용 Newey-West t-통계량 (기본값: 1.96, p <= 0.05).
    """
    min_mda: float = 0.50
    min_rank_ic: float = 0.00
    max_mdd: float = 0.30
    min_factor_tstat: float = 1.96


@dataclass(frozen=True)
class SoftGate:
    """모델 일반화 품질 검증을 위한 소프트 게이트 설정 DTO (5대 지표 중 K개 이상 통과 필수).

    Attributes:
        max_rmse (float): 최대 허용 RMSE (기본값: 0.35).
        max_mae (float): 최대 허용 MAE (기본값: 0.25).
        min_icir (float): 최소 허용 팩터 정보 비율 (기본값: 0.50).
        min_sharpe (float): 최소 허용 연율화 샤프 지수 (기본값: 0.50).
        min_sortino (float): 최소 허용 연율화 소르티노 지수 (기본값: 0.70).
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
    """4대 평가 계층별 복합 스코어링 가중치 설정 DTO (기본 합계: 1.0).

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
# 2. 공개 게이트 판정 및 감사 리포트 API (Public Interfaces)
# ==============================================================================

def check_hard_gate(
    metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
    gate: HardGate,
) -> Tuple[bool, List[str]]:
    """단일 모델의 4대 하드 게이트 만족 여부 및 위반 사유 리스트(violations)를 전수 검사합니다.

    Args:
        metrics: 모델의 산출 지표 딕셔너리 (EvaluationMetric Enum 또는 문자열 키 지원).
        gate: 하드 게이트 임계치 설정 DTO.

    Returns:
        Tuple[bool, List[str]]:
            - is_passed (bool): 4대 하드 게이트 전수 통과 여부 (모두 통과 시 True).
            - violations (List[str]): 기준 미달/초과된 지표의 상세 위반 사유 문자열 리스트.
    """
    # Enum 기반 O(1) 조회를 위해 비공개 헬퍼를 거쳐 표준 키 매핑 딕셔너리로 정규화
    clean_metrics: Dict[EvaluationMetric, float] = _standardize_metrics_map(metrics)
    violations: List[str] = []

    # 하드 게이트 검사 명세를 (표준 지표 키, 실측값, 임계치) 튜플 리스트로 선언적 구성
    validation_specs: List[Tuple[EvaluationMetric, float, float]] = [
        (EvaluationMetric.MDA, clean_metrics.get(EvaluationMetric.MDA, 0.0), gate.min_mda),
        (EvaluationMetric.RANK_IC, clean_metrics.get(EvaluationMetric.RANK_IC, -1.0), gate.min_rank_ic),
        (EvaluationMetric.MDD, clean_metrics.get(EvaluationMetric.MDD, 1.0), gate.max_mdd),
        (EvaluationMetric.FACTOR_T_STAT, clean_metrics.get(EvaluationMetric.FACTOR_T_STAT, 0.0), gate.min_factor_tstat),
    ]

    for metric, actual_value, threshold in validation_specs:
        is_passed, violation_message = _validate_metric_threshold(
            metric=metric,
            actual_value=actual_value,
            threshold=threshold,
        )
        if not is_passed and violation_message is not None:
            violations.append(violation_message)

    is_all_passed: bool = len(violations) == 0
    return is_all_passed, violations


def check_soft_gate(
    metrics: Union[Dict[EvaluationMetric, float], Dict[str, float]],
    gate: SoftGate,
) -> Tuple[bool, int, int, List[str]]:
    """단일 모델의 5대 소프트 게이트 전수 검사를 집행하고 K개 이상 충족 여부를 판정합니다.

    Args:
        metrics: 모델의 산출 지표 딕셔너리 (EvaluationMetric Enum 또는 문자열 키 지원).
        gate: 소프트 게이트 임계치 설정 DTO.

    Returns:
        Tuple[bool, int, int, List[str]]:
            - is_gate_passed (bool): K개 이상 통과 여부 (passed_count >= min_passed_count).
            - passed_count (int): 실제 통과한 소프트 지표 개수.
            - total_evaluated (int): 전체 검사 대상 소프트 지표 개수 (항상 5).
            - violations (List[str]): 기준 미달/초과된 소프트 지표의 상세 위반 사유 리스트.
    """
    clean_metrics: Dict[EvaluationMetric, float] = _standardize_metrics_map(metrics)
    passed_count: int = 0
    total_evaluated: int = 5
    violations: List[str] = []

    # 소프트 게이트 검사 명세를 선언적 튜플 구조로 바인딩하여 반복문 검증 수행
    validation_specs: List[Tuple[EvaluationMetric, float, float]] = [
        (EvaluationMetric.RMSE, clean_metrics.get(EvaluationMetric.RMSE, float("inf")), gate.max_rmse),
        (EvaluationMetric.MAE, clean_metrics.get(EvaluationMetric.MAE, float("inf")), gate.max_mae),
        (EvaluationMetric.ICIR, clean_metrics.get(EvaluationMetric.ICIR, 0.0), gate.min_icir),
        (EvaluationMetric.SIGNAL_SHARPE, clean_metrics.get(EvaluationMetric.SIGNAL_SHARPE, -999.0), gate.min_sharpe),
        (EvaluationMetric.SORTINO_RATIO, clean_metrics.get(EvaluationMetric.SORTINO_RATIO, -999.0), gate.min_sortino),
    ]

    for metric, actual_value, threshold in validation_specs:
        is_passed, violation_message = _validate_metric_threshold(
            metric=metric,
            actual_value=actual_value,
            threshold=threshold,
        )
        if is_passed:
            passed_count += 1
        elif violation_message is not None:
            violations.append(violation_message)

    is_gate_passed: bool = passed_count >= gate.min_passed_count
    return is_gate_passed, passed_count, total_evaluated, violations


def get_score_report(
    candidates_metrics: Union[Dict[str, Dict[Any, float]], pd.DataFrame],
    hard_gate: Optional[HardGate] = None,
    soft_gate: Optional[SoftGate] = None,
) -> pd.DataFrame:
    """전체 후보 모델의 2단계 게이트 통과 현황 및 탈락 사유 감사 리포트 DataFrame을 생성합니다.

    Args:
        candidates_metrics: 모델명을 키로 하는 메트릭 맵 또는 모델별 지표 행렬 DataFrame.
        hard_gate: 하드 게이트 기준 DTO (None일 경우 기본값 적용).
        soft_gate: 소프트 게이트 기준 DTO (None일 경우 기본값 적용).

    Returns:
        pd.DataFrame: 모델명을 인덱스로 가지며 자격 적격 여부(QUALIFIED/DISQUALIFIED),
            하드/소프트 게이트 통과 여부 및 위반 사유(violations)를 포함하는 감사 대시보드.
    """
    effective_hard_gate: HardGate = hard_gate or HardGate()
    effective_soft_gate: SoftGate = soft_gate or SoftGate()

    standardized_candidates = _standardize_candidates(candidates_metrics)
    audit_records: List[Dict[str, Any]] = []

    # 각 후보 모델에 대해 하드/소프트 게이트 검사를 순차 집행하고 감사용 레코드로 정형화
    for model_name, metric_map in standardized_candidates.items():
        hard_pass, hard_violations = check_hard_gate(
            metrics=metric_map,
            gate=effective_hard_gate,
        )
        soft_pass, soft_count, soft_total, soft_violations = check_soft_gate(
            metrics=metric_map,
            gate=effective_soft_gate,
        )
        is_qualified: bool = hard_pass and soft_pass

        audit_records.append({
            "model_name": model_name,
            "is_qualified": "QUALIFIED" if is_qualified else "DISQUALIFIED",
            "hard_gate_pass": hard_pass,
            "hard_violations": ", ".join(hard_violations) if hard_violations else "None",
            "soft_gate_pass": soft_pass,
            "soft_passed_ratio": f"{soft_count} / {soft_total} (K={effective_soft_gate.min_passed_count})",
            "soft_violations": ", ".join(soft_violations) if soft_violations else "None",
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