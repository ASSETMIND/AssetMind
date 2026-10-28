from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 수리적 공리 검증 및 단위 변환 설정
DEFAULT_ADDITIVITY_TOLERANCE: float = 1e-4        # Shapley 가산성 공리(Additivity Axiom) 허용 수치 오차 임계치
PERCENTAGE_MULTIPLIER: float = 100.0              # 비율 수치의 백분율(%) 환산 승수

# XAI 도메인 공통 기본 설정 (SSOT)
DEFAULT_CUMULATIVE_RATIO_THRESHOLD: float = 90.0  # 파레토 법칙 기반 핵심 피처 선별 누적 중요도 임계 비율 (%)
DEFAULT_ROLLING_WINDOW_SIZE: int = 20             # 동적 시계열 XAI 롤링 이동평균 산출 기본 윈도우 (20영업일)


# ==============================================================================
# Public API Functions
# ==============================================================================
@dataclass(frozen=True)
class AdditivityAuditResult:
    """Shapley 가산성 공리(Additivity Axiom) 수치 무결성 검증 결과 DTO.

    Attributes:
        maximum_absolute_error (float): 전체 표본 중 관측된 최대 가산성 절대 오차.
        mean_absolute_error (float): 전체 표본의 평균 가산성 절대 오차.
        is_axiom_satisfied (bool): 허용 오차 이내 공리 충족 여부.
        tolerance (float): 검증에 적용된 허용 오차 임계 기준.
        sample_count (int): 가산성 감사가 집행된 유효 관측치 수.
    """

    maximum_absolute_error: float
    mean_absolute_error: float
    is_axiom_satisfied: bool
    tolerance: float
    sample_count: int

    @property
    def max_absolute_error(self) -> float:
        """하위 호환성을 위한 maximum_absolute_error 별칭 프로퍼티."""
        return self.maximum_absolute_error


@dataclass(frozen=True)
class StressScenarioConfig:
    """시장 레짐 시프트 및 극단 국면 감사 이벤트 정의 DTO.

    Attributes:
        event_date (str): 이벤트 발생 거래일 (YYYY-MM-DD).
        event_label (str): 이벤트 국면 식별 명칭.
        description (str): 이벤트 발생 배경 및 정량 맥락 설명.
    """

    event_date: str
    event_label: str
    description: str = ""


@dataclass(frozen=True)
class InflectionPointResult:
    """개별 리스크 팩터의 SHAP 변곡점 및 영향도 분석 결과 DTO.

    Attributes:
        feature_name (str): 분석 대상 리스크 피처 식별 명칭.
        inflection_threshold (float): 제로 크로싱 또는 구조적 변곡점 임계 수치.
        mean_shap_below_threshold (float): 임계치 미만 정상 구간 평균 SHAP 기여도.
        mean_shap_above_threshold (float): 임계치 이상 위험 구간 평균 SHAP 기여도.
        delta_impact (float): 임계치 전후 기여도 변화량 (하방 충격량).
    """

    feature_name: str
    inflection_threshold: float
    mean_shap_below_threshold: float
    mean_shap_above_threshold: float
    delta_impact: float

    @property
    def as_dictionary(self) -> Dict[str, float]:
        """시각화 모듈 연동을 위한 변곡점 지표 딕셔너리 표현을 반환합니다."""
        return {
            "inflection_threshold": self.inflection_threshold,
            "mean_shap_below": self.mean_shap_below_threshold,
            "mean_shap_above": self.mean_shap_above_threshold,
            "delta_impact": self.delta_impact,
        }


@dataclass(frozen=True)
class InflectionPolicyResult:
    """다중 리스크 팩터의 변곡점 정책 및 컷오프 임계치 집계 DTO.

    Attributes:
        policy_records (Dict[str, InflectionPointResult]): 피처별 변곡점 분석 결과 맵.
        policy_summary_dataframe (pd.DataFrame): 다중 팩터 리스크 컷오프 감사 요약표.
    """

    policy_records: Dict[str, InflectionPointResult]
    policy_summary_dataframe: pd.DataFrame


@dataclass(frozen=True)
class RegimeCohortResult:
    """5대 시장 국면별 코호트 감사 및 SHAP 평균 기여도 집계 DTO.

    Attributes:
        regime_audit_dataframe (pd.DataFrame): 5대 시장 국면별 집계 감사표.
        regime_mean_shap_dataframe (pd.DataFrame): 국면별 피처 SHAP 평균 기여도 행렬.
        regime_mean_predictions (Dict[str, float]): 국면별 모델 평균 예측치 맵.
        regime_sample_counts (Dict[str, int]): 국면별 유효 관측일 표본 수 맵.
    """

    regime_audit_dataframe: pd.DataFrame
    regime_mean_shap_dataframe: pd.DataFrame
    regime_mean_predictions: Dict[str, float]
    regime_sample_counts: Dict[str, int]


@dataclass(frozen=True)
class ShapResult:
    """SHAP 분석 산출물, 수리통계적 감사 메타데이터 및 정책 메타를 캡슐화한 불변 DTO.

    Attributes:
        model_name (str): 설명 대상 챔피언 모델 식별 명칭.
        feature_names (List[str]): 설명에 투입된 정예 피처 명단.
        evaluation_index (pd.Index): 평가 데이터셋의 시계열 날짜 인덱스.
        shap_values (np.ndarray): N x P 차원의 원시 SHAP Value 행렬.
        base_value (float): 모델의 기준 기댓값 (Base Value, E[f(x)]).
        raw_predictions (np.ndarray): 모델의 실제 원시 예측값 벡터 f(x).
        global_importance_dataframe (pd.DataFrame): 피처별 Mean |SHAP| 및 상대 기여도 감사표.
        additivity_audit (AdditivityAuditResult): 가산성 공리 검증 결과 객체.
        shap_explanation (Any): shap 라이브러리 Explanation 객체 (시각화 연동용).
        interaction_values (Optional[np.ndarray]): N x P x P 2차 교호작용 텐서.
        rolling_shap_dataframe (Optional[pd.DataFrame]): 시계열 롤링 SHAP 기여도 데이터프레임.
        background_samples_count (int): Background Dataset 표본 크기.
        evaluated_samples_count (int): SHAP이 산출된 평가 데이터셋 표본 크기.
        inflection_policy_result (Optional[InflectionPolicyResult]): 변곡점 정책 분석 결과 DTO.
        regime_cohort_result (Optional[RegimeCohortResult]): 5대 시장 국면별 코호트 감사 결과 DTO.
        benchmark_series (Optional[pd.Series]): 시장 벤치마크 지수 시계열.
        stress_events (Optional[List[Tuple[str, str]]]): 시장 스트레스 이벤트 (날짜, 명칭) 목록.
    """

    model_name: str
    feature_names: List[str]
    evaluation_index: pd.Index
    shap_values: np.ndarray
    base_value: float
    raw_predictions: np.ndarray
    global_importance_dataframe: pd.DataFrame
    additivity_audit: AdditivityAuditResult
    shap_explanation: Any
    interaction_values: Optional[np.ndarray]
    rolling_shap_dataframe: Optional[pd.DataFrame]
    background_samples_count: int
    evaluated_samples_count: int
    inflection_policy_result: Optional[InflectionPolicyResult] = None
    regime_cohort_result: Optional[RegimeCohortResult] = None
    benchmark_series: Optional[pd.Series] = None
    stress_events: Optional[List[Tuple[str, str]]] = None

    @property
    def top_features(self) -> List[str]:
        """전역 평균 절대 기여도(Mean |SHAP|) 기준 내림차순 정렬된 피처 목록을 반환합니다."""
        return self.global_importance_dataframe.index.tolist()

    @property
    def eval_index(self) -> pd.Index:
        """하위 호환성을 위한 evaluation_index 별칭 프로퍼티."""
        return self.evaluation_index

    @property
    def global_importance_df(self) -> pd.DataFrame:
        """하위 호환성을 위한 global_importance_dataframe 별칭 프로퍼티."""
        return self.global_importance_dataframe

    @property
    def rolling_shap_df(self) -> Optional[pd.DataFrame]:
        """하위 호환성을 위한 rolling_shap_dataframe 별칭 프로퍼티."""
        return self.rolling_shap_dataframe

    @property
    def audit_summary_report(self) -> pd.DataFrame:
        """가산성 공리 검정 및 산출 메타데이터를 담은 요약 감사 데이터프레임을 생성합니다."""
        return _build_audit_summary_dataframe(shap_result=self)


def create_shap_result(
    model_name: str,
    feature_names: List[str],
    evaluation_index: Optional[pd.Index] = None,
    shap_values: Optional[np.ndarray] = None,
    base_value: float = 0.0,
    raw_predictions: Optional[np.ndarray] = None,
    shap_explanation: Any = None,
    background_samples_count: int = 0,
    interaction_values: Optional[np.ndarray] = None,
    rolling_shap_dataframe: Optional[pd.DataFrame] = None,
    inflection_policy_result: Optional[InflectionPolicyResult] = None,
    regime_cohort_result: Optional[RegimeCohortResult] = None,
    benchmark_series: Optional[pd.Series] = None,
    stress_events: Optional[List[Tuple[str, str]]] = None,
    tolerance: float = DEFAULT_ADDITIVITY_TOLERANCE,
    additivity_audit: Optional[AdditivityAuditResult] = None,
    global_importance_dataframe: Optional[pd.DataFrame] = None,
    eval_index: Optional[pd.Index] = None,
    rolling_shap_df: Optional[pd.DataFrame] = None,
) -> ShapResult:
    """SHAP 산출물에 대한 차원 및 수리적 무결성을 검증하고 불변 ShapResult DTO를 생성합니다.

    Args:
        model_name (str): 설명 대상 모델 식별자.
        feature_names (List[str]): 설명 피처 컬럼 명단.
        evaluation_index (Optional[pd.Index]): 평가 데이터 행 인덱스. Defaults to None.
        shap_values (Optional[np.ndarray]): 산출된 N x P SHAP 행렬. Defaults to None.
        base_value (float): 모델의 기준 기댓값. Defaults to 0.0.
        raw_predictions (Optional[np.ndarray]): 모델의 실제 예측값 벡터. Defaults to None.
        shap_explanation (Any): shap 라이브러리 원천 Explanation 객체. Defaults to None.
        background_samples_count (int): 배경 데이터 표본 수. Defaults to 0.
        interaction_values (Optional[np.ndarray]): N x P x P 2차 교호작용 행렬. Defaults to None.
        rolling_shap_dataframe (Optional[pd.DataFrame]): 롤링 SHAP 데이터프레임. Defaults to None.
        inflection_policy_result (Optional[InflectionPolicyResult]): 변곡점 정책 결과 DTO. Defaults to None.
        regime_cohort_result (Optional[RegimeCohortResult]): 5대 시장 국면 감사 결과 DTO. Defaults to None.
        benchmark_series (Optional[pd.Series]): 시장 벤치마크 시계열. Defaults to None.
        stress_events (Optional[List[Tuple[str, str]]]): 시장 스트레스 이벤트 목록. Defaults to None.
        tolerance (float): 가산성 공리 검정 허용 오차. Defaults to DEFAULT_ADDITIVITY_TOLERANCE.
        additivity_audit (Optional[AdditivityAuditResult]): 사전 연산된 가산성 감사 결과 DTO. Defaults to None.
        global_importance_dataframe (Optional[pd.DataFrame]): 사전 연산된 전역 중요도 데이터프레임. Defaults to None.
        eval_index (Optional[pd.Index]): 하위 호환용 평가 데이터 행 인덱스. Defaults to None.
        rolling_shap_df (Optional[pd.DataFrame]): 하위 호환용 롤링 SHAP 데이터프레임. Defaults to None.

    Returns:
        ShapResult: 수리통계적 감사가 완료된 불변 DTO 인스턴스.

    Raises:
        ValueError: 입력 배열의 결손, 차원 불일치 또는 데이터 무결성 훼손 시 발생.
    """
    # 1. 하위 호환 매개변수 병합 및 유효 인덱스/데이터프레임 확정
    effective_evaluation_index = _resolve_evaluation_index(
        primary_index=evaluation_index,
        fallback_index=eval_index,
    )
    effective_rolling_dataframe = _resolve_rolling_dataframe(
        primary_dataframe=rolling_shap_dataframe,
        fallback_dataframe=rolling_shap_df,
    )

    # 2. 필수 입력 배열 존재 여부 및 텐서 차원 정합성 검증
    _validate_input_integrity(
        shap_values=shap_values,
        raw_predictions=raw_predictions,
    )
    _validate_shap_dimensions(
        shap_values=shap_values,
        raw_predictions=raw_predictions,
        feature_names=feature_names,
        evaluation_index=effective_evaluation_index,
    )

    # 3. 외부 주입 여부에 따른 가산성 공리 감사 및 전역 중요도 테이블 확보
    resolved_additivity_audit = (
        additivity_audit
        if additivity_audit is not None
        else _audit_additivity_axiom(
            shap_values=shap_values,
            base_value=base_value,
            raw_predictions=raw_predictions,
            tolerance=tolerance,
        )
    )
    resolved_global_importance = (
        global_importance_dataframe
        if global_importance_dataframe is not None
        else _calculate_global_importance(
            shap_values=shap_values,
            feature_names=feature_names,
        )
    )

    # 4. 최종 불변 ShapResult DTO 조립 및 반환
    return ShapResult(
        model_name=model_name,
        feature_names=feature_names,
        evaluation_index=effective_evaluation_index,
        shap_values=shap_values,
        base_value=base_value,
        raw_predictions=raw_predictions,
        global_importance_dataframe=resolved_global_importance,
        additivity_audit=resolved_additivity_audit,
        shap_explanation=shap_explanation,
        interaction_values=interaction_values,
        rolling_shap_dataframe=effective_rolling_dataframe,
        background_samples_count=background_samples_count,
        evaluated_samples_count=len(effective_evaluation_index),
        inflection_policy_result=inflection_policy_result,
        regime_cohort_result=regime_cohort_result,
        benchmark_series=benchmark_series,
        stress_events=stress_events,
    )


def create_inflection_point_result(
    feature_name: str,
    inflection_threshold: float,
    mean_shap_below_threshold: float,
    mean_shap_above_threshold: float,
    delta_impact: float,
) -> InflectionPointResult:
    """단일 리스크 팩터의 변곡점 분석 결과를 캡슐화한 불변 DTO를 생성합니다.

    Args:
        feature_name (str): 분석 대상 피처 명칭.
        inflection_threshold (float): 제로 크로싱 또는 구조적 변곡점 임계 수치.
        mean_shap_below_threshold (float): 임계치 미만 구간 평균 SHAP 기여도.
        mean_shap_above_threshold (float): 임계치 이상 구간 평균 SHAP 기여도.
        delta_impact (float): 임계치 전후 기여도 변화량 (하방 충격량).

    Returns:
        InflectionPointResult: 생성된 불변 DTO 인스턴스.
    """
    # 단일 피처 변곡점 분석 결과 불변 객체 생성
    return InflectionPointResult(
        feature_name=feature_name,
        inflection_threshold=inflection_threshold,
        mean_shap_below_threshold=mean_shap_below_threshold,
        mean_shap_above_threshold=mean_shap_above_threshold,
        delta_impact=delta_impact,
    )


def create_inflection_policy_result(
    policy_records: Dict[str, InflectionPointResult],
) -> InflectionPolicyResult:
    """복수 피처의 변곡점 분석 결과들을 수집하여 종합 정책 DTO를 생성합니다.

    Args:
        policy_records (Dict[str, InflectionPointResult]): 피처명을 키로 하고 변곡점 결과를 값으로 갖는 딕셔너리.

    Returns:
        InflectionPolicyResult: 요약 감사 데이터프레임이 포함된 정책 결과 DTO.
    """
    # 1. 개별 피처 변곡점 레코드 기반 요약 데이터프레임 생성
    summary_dataframe = _build_policy_summary_dataframe(policy_records=policy_records)

    # 2. 다중 피처 변곡점 정책 결과 불변 DTO 반환
    return InflectionPolicyResult(
        policy_records=policy_records,
        policy_summary_dataframe=summary_dataframe,
    )


def create_regime_cohort_result(
    regime_audit_dataframe: pd.DataFrame,
    regime_mean_shap_dataframe: pd.DataFrame,
    regime_mean_predictions: Dict[str, float],
    regime_sample_counts: Dict[str, int],
) -> RegimeCohortResult:
    """5대 시장 국면별 코호트 집계 감사 및 평균 기여도 DTO를 생성합니다.

    Args:
        regime_audit_dataframe (pd.DataFrame): 5대 시장 국면별 집계 감사표.
        regime_mean_shap_dataframe (pd.DataFrame): 국면별 피처 SHAP 평균 기여도 행렬.
        regime_mean_predictions (Dict[str, float]): 국면별 모델 평균 예측치 맵.
        regime_sample_counts (Dict[str, int]): 국면별 표본 수 맵.

    Returns:
        RegimeCohortResult: 생성된 불변 DTO 인스턴스.
    """
    # 5대 시장 국면 코호트 감사 결과 불변 객체 생성
    return RegimeCohortResult(
        regime_audit_dataframe=regime_audit_dataframe,
        regime_mean_shap_dataframe=regime_mean_shap_dataframe,
        regime_mean_predictions=regime_mean_predictions,
        regime_sample_counts=regime_sample_counts,
    )


def validate_shap_result(shap_result: ShapResult) -> bool:
    """생성된 ShapResult DTO의 수리적 공리 충족 및 상태 일관성을 검증합니다.

    Args:
        shap_result (ShapResult): 검증 대상 DTO.

    Returns:
        bool: 공리 충족 및 데이터 무결성 통과 여부.
    """
    # 내장 무결성 검증 함수를 통한 가산성 공리 및 차원 일치 여부 확인
    return _check_shap_result_validity(shap_result=shap_result)


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _resolve_evaluation_index(
    primary_index: Optional[pd.Index],
    fallback_index: Optional[pd.Index],
) -> pd.Index:
    """평가 인덱스 입력의 기본값 및 하위 호환 별칭을 안전하게 병합합니다."""
    # 기본 인덱스를 우선 선택하되 부재 시 하위 호환 인덱스 적용
    resolved_index = primary_index if primary_index is not None else fallback_index
    if resolved_index is None:
        raise ValueError("[_resolve_evaluation_index] evaluation_index는 필수 입력입니다.")
    return resolved_index


def _resolve_rolling_dataframe(
    primary_dataframe: Optional[pd.DataFrame],
    fallback_dataframe: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """롤링 기여도 데이터프레임 기본값 및 하위 호환 별칭을 안전하게 병합합니다."""
    # 기본 데이터프레임을 우선 선택하되 부재 시 하위 호환 데이터프레임 반환
    return primary_dataframe if primary_dataframe is not None else fallback_dataframe


def _validate_input_integrity(
    shap_values: Optional[np.ndarray],
    raw_predictions: Optional[np.ndarray],
) -> None:
    """입력 배열 객체의 유효성 및 None 여부를 검증합니다."""
    # 핵심 수치 배열의 결손 여부 확인
    if shap_values is None or raw_predictions is None:
        raise ValueError("[_validate_input_integrity] shap_values와 raw_predictions는 필수 배열입니다.")


def _validate_shap_dimensions(
    shap_values: np.ndarray,
    raw_predictions: np.ndarray,
    feature_names: List[str],
    evaluation_index: pd.Index,
) -> None:
    """SHAP 행렬, 예측값 벡터, 피처명, 인덱스 간의 차원 정합성을 검증합니다."""
    sample_count: int = len(evaluation_index)
    feature_count: int = len(feature_names)

    # 1. SHAP 배열의 2차원 행렬 형태 검증
    if shap_values.ndim != 2:
        raise ValueError(
            f"[_validate_shap_dimensions] shap_values는 2차원 행렬이어야 합니다. 입력 차원: {shap_values.ndim}"
        )

    # 2. 행(표본 수) 및 열(피처 수) 길이 일치 검증
    if shap_values.shape[0] != sample_count:
        raise ValueError(
            f"[_validate_shap_dimensions] 행 표본 수 불일치: "
            f"shap_values({shap_values.shape[0]}) != evaluation_index({sample_count})"
        )

    if shap_values.shape[1] != feature_count:
        raise ValueError(
            f"[_validate_shap_dimensions] 열 피처 수 불일치: "
            f"shap_values({shap_values.shape[1]}) != feature_names({feature_count})"
        )

    # 3. 원시 예측값 벡터와 평가 인덱스 간의 표본 수 일치 검증
    if len(raw_predictions) != sample_count:
        raise ValueError(
            f"[_validate_shap_dimensions] 예측값 벡터 길이 불일치: "
            f"raw_predictions({len(raw_predictions)}) != evaluation_index({sample_count})"
        )


def _audit_additivity_axiom(
    shap_values: np.ndarray,
    base_value: float,
    raw_predictions: np.ndarray,
    tolerance: float,
) -> AdditivityAuditResult:
    """Shapley 가산성 공리 오차를 계산하고 감사를 수행합니다."""
    # 1. 기댓값과 개별 피처 기여도 총합을 더하여 재구성 예측값 산출
    reconstructed_predictions: np.ndarray = base_value + np.sum(shap_values, axis=1)
    absolute_errors: np.ndarray = np.abs(raw_predictions - reconstructed_predictions)

    # 2. 최대/평균 절대 오차 산출 및 허용 오차 이내 충족 여부 판정
    maximum_error: float = float(np.max(absolute_errors))
    mean_error: float = float(np.mean(absolute_errors))
    is_satisfied: bool = bool(maximum_error <= tolerance)

    return AdditivityAuditResult(
        maximum_absolute_error=maximum_error,
        mean_absolute_error=mean_error,
        is_axiom_satisfied=is_satisfied,
        tolerance=tolerance,
        sample_count=len(raw_predictions),
    )


def _calculate_global_importance(
    shap_values: np.ndarray,
    feature_names: List[str],
) -> pd.DataFrame:
    """피처별 평균 절대 기여도, 상대 비중 및 순위 테이블을 산출합니다."""
    # 1. 피처별 평균 절대 SHAP 기여도 및 전체 대비 상대 비중(%) 연산
    mean_absolute_shap: np.ndarray = np.mean(np.abs(shap_values), axis=0)
    total_importance: float = float(np.sum(mean_absolute_shap))

    if total_importance > 0.0:
        importance_ratio: np.ndarray = (mean_absolute_shap / total_importance) * PERCENTAGE_MULTIPLIER
    else:
        importance_ratio = np.zeros_like(mean_absolute_shap)

    # 2. 중요도 기준 내림차순 정렬 및 누적 비중, 순위 컬럼 부여
    importance_dataframe = pd.DataFrame(
        {
            "mean_abs_shap": mean_absolute_shap,
            "importance_ratio_pct": importance_ratio,
        },
        index=feature_names,
    ).sort_values(by="mean_abs_shap", ascending=False)

    importance_dataframe["cumulative_ratio_pct"] = importance_dataframe["importance_ratio_pct"].cumsum()
    importance_dataframe["rank"] = np.arange(1, len(importance_dataframe) + 1)

    return importance_dataframe


def _build_policy_summary_dataframe(
    policy_records: Dict[str, InflectionPointResult],
) -> pd.DataFrame:
    """개별 변곡점 분석 결과들을 수집하여 데이터프레임 형식으로 요약합니다."""
    # 피처별 변곡점 임계치 및 정상/위험 구간 평균 기여도 레코드 구성
    summary_records = []
    for feature_name, result in policy_records.items():
        summary_records.append(
            {
                "Feature Name": feature_name,
                "Inflection Threshold": result.inflection_threshold,
                "Normal Zone Mean SHAP": result.mean_shap_below_threshold,
                "Risk Zone Mean SHAP": result.mean_shap_above_threshold,
                "Delta Impact": result.delta_impact,
            }
        )
    return pd.DataFrame(summary_records).set_index("Feature Name")


def _build_audit_summary_dataframe(shap_result: ShapResult) -> pd.DataFrame:
    """가산성 공리 검정 결과 및 주요 수치 메타데이터를 구조화 표로 사출합니다."""
    # 가산성 감사 객체 및 주요 산출물 상태 기반 요약 레코드 조립
    audit = shap_result.additivity_audit
    records = [
        {"항목": "선정 모델 식별 명칭", "수치 / 결과": shap_result.model_name, "판정 및 기준": "Holdout Test 1위 챔피언"},
        {"항목": "배경 데이터 표본수 (Background N)", "수치 / 결과": f"{shap_result.background_samples_count:,} 건", "판정 및 기준": "Train 데이터셋 기준 요약"},
        {"항목": "평가 데이터 표본수 (Evaluation N)", "수치 / 결과": f"{shap_result.evaluated_samples_count:,} 건", "판정 및 기준": "Holdout Test (OOS) 전수"},
        {"항목": "모델 기준 기댓값 (Base E[f(x)])", "수치 / 결과": f"{shap_result.base_value:.6f}", "판정 및 기준": "사전 무정보 예측 기준점"},
        {"항목": "가산성 최대 절대오차 (Max |Residual|)", "수치 / 결과": f"{audit.maximum_absolute_error:.8f}", "판정 및 기준": f"기준: ≤ {audit.tolerance:.0e}"},
        {"항목": "가산성 평균 절대오차 (Mean |Residual|)", "수치 / 결과": f"{audit.mean_absolute_error:.8f}", "판정 및 기준": "전 표본 부동소수점 평균"},
        {"항목": "Shapley 가산성 공리 검정", "수치 / 결과": "PASSED" if audit.is_axiom_satisfied else "FAILED", "판정 및 기준": "Efficiency Axiom 충족"},
        {"항목": "2차 상호작용 텐서 계산 여부", "수치 / 결과": "포함됨" if shap_result.interaction_values is not None else "미포함", "판정 및 기준": "TreeSHAP / Pairwise Interaction"},
        {"항목": "시계열 롤링 기여도 계산 여부", "수치 / 결과": "포함됨" if shap_result.rolling_shap_dataframe is not None else "미포함", "판정 및 기준": f"{DEFAULT_ROLLING_WINDOW_SIZE}일 이동평균 전이 추적"},
        {"항목": "5대 시장 국면 감사 계산 여부", "수치 / 결과": "포함됨" if shap_result.regime_cohort_result is not None else "미포함", "판정 및 기준": "5-Regime Robust Cohort Audit"},
    ]
    return pd.DataFrame(records).set_index("항목")


def _check_shap_result_validity(shap_result: ShapResult) -> bool:
    """가산성 공리 충족 여부 및 텐서 차원 일관성을 검증합니다."""
    # 가산성 공리 통과 여부와 행/열 길이 정합성 논리곱 반환
    return (
        shap_result.additivity_audit.is_axiom_satisfied
        and len(shap_result.feature_names) == shap_result.shap_values.shape[1]
        and len(shap_result.evaluation_index) == shap_result.shap_values.shape[0]
    )