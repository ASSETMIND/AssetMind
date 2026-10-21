from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.model.xai.shap_schema import (
    InflectionPointResult,
    InflectionPolicyResult,
    RegimeCohortResult,
    ShapResult,
    create_inflection_point_result,
    create_inflection_policy_result,
    create_regime_cohort_result,
)


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 리스크 변곡점 탐색 설정
DEFAULT_INFLECTION_QUANTILE_CUTOFF: float = 0.05  # 변곡점 탐색 시 양극단 이상치 차단 분위수 임계치
DEFAULT_TOP_K_INFLECTION_FEATURES: int = 3        # 자동 선별 대상 상위 핵심 리스크 팩터 기본 개수
DEFAULT_CUMULATIVE_RATIO_THRESHOLD: float = 90.0  # 파레토 법칙 기반 핵심 피처 선별 누적 중요도 임계 비율 (%)

# 시장 국면 코호트 감사 설정
DEFAULT_REGIME_PERCENTILE_THRESHOLD: float = 0.20  # 시장 급등/급락 및 극단 국면 분위수 임계치
DEFAULT_NORMAL_SIGMA_BOUND: float = 0.5           # 평시 안정 국면 표준편차 경계 배수
DEFAULT_LONG_BIAS_THRESHOLD: float = 0.05         # 모델 Long 스탠스 판정 임계치
DEFAULT_SHORT_BIAS_THRESHOLD: float = -0.05       # 모델 Short 스탠스 판정 임계치
DEFAULT_ALIGNMENT_MIN_PREDICTION: float = 0.03    # 신호 정합성 판정용 최소 유의 예측 강도 임계치


# ==============================================================================
# Public API Functions
# ==============================================================================
class RiskPolicyAnalyzer:
    """SHAP 기여도 곡선 기반 리스크 임계 변곡점 탐색 및 행동 정책 경계선 사출 분석기.

    Attributes:
        quantile_cutoff (float): 이상치 차단 분위수 기준값.
    """

    def __init__(
        self,
        quantile_cutoff: float = DEFAULT_INFLECTION_QUANTILE_CUTOFF,
    ) -> None:
        """RiskPolicyAnalyzer 인스턴스를 초기화합니다.

        Args:
            quantile_cutoff (float): 양극단 이상치 제거 분위수. Defaults to 0.05.
        """
        self.quantile_cutoff: float = quantile_cutoff

    def analyze_feature_inflection(
        self,
        shap_result: ShapResult,
        feature_name: str,
        evaluation_features: pd.DataFrame,
    ) -> InflectionPointResult:
        """특정 리스크 팩터의 SHAP 기여도가 음수로 전환되는 변곡점 및 하방 충격량을 사출합니다.

        Args:
            shap_result (ShapResult): 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
            feature_name (str): 변곡점 분석 대상 리스크 피처 명칭.
            evaluation_features (pd.DataFrame): 평가 데이터셋 원시 피처 행렬.

        Returns:
            InflectionPointResult: 변곡점 임계치, 구간별 평균 기여도 및 충격량이 담긴 DTO.

        Raises:
            ValueError: 대상 피처명이 SHAP 결과 피처 풀에 부재하거나 입력이 비어 있는 경우 발생.
        """
        _validate_feature_presence(
            feature_name=feature_name,
            available_features=shap_result.feature_names,
        )

        feature_index = shap_result.feature_names.index(feature_name)
        feature_values = evaluation_features[feature_name].to_numpy(dtype=np.float64)
        shap_feature_values = shap_result.shap_values[:, feature_index]

        threshold, mean_below, mean_above, delta_impact = _calculate_inflection_metrics(
            feature_values=feature_values,
            shap_feature_values=shap_feature_values,
            quantile_cutoff=self.quantile_cutoff,
        )

        return create_inflection_point_result(
            feature_name=feature_name,
            inflection_threshold=threshold,
            mean_shap_below_threshold=mean_below,
            mean_shap_above_threshold=mean_above,
            delta_impact=delta_impact,
        )

    def analyze_policy_boundary(
        self,
        shap_result: ShapResult,
        target_features: List[str],
        evaluation_features: pd.DataFrame,
    ) -> InflectionPolicyResult:
        """다중 핵심 리스크 팩터군에 대한 SHAP 변곡점 및 정책 임계치를 일괄 집계합니다.

        Args:
            shap_result (ShapResult): 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
            target_features (List[str]): 분석 대상 다중 피처 명단.
            evaluation_features (pd.DataFrame): 평가 데이터셋 원시 피처 행렬.

        Returns:
            InflectionPolicyResult: 개별 변곡점 결과 맵과 감사 요약 데이터프레임이 포함된 DTO.

        Raises:
            ValueError: target_features가 비어 있는 경우 발생.
        """
        if not target_features:
            raise ValueError("[RiskPolicyAnalyzer] target_features 리스트가 비어 있습니다.")

        policy_records: Dict[str, InflectionPointResult] = {}
        for feature_name in target_features:
            if feature_name in shap_result.feature_names:
                result = self.analyze_feature_inflection(
                    shap_result=shap_result,
                    feature_name=feature_name,
                    evaluation_features=evaluation_features,
                )
                policy_records[feature_name] = result

        return create_inflection_policy_result(policy_records=policy_records)

    def detect_salient_features(
        self,
        shap_result: ShapResult,
        evaluation_features: pd.DataFrame,
        top_k: Optional[int] = None,
        cumulative_ratio_threshold: float = DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
    ) -> List[str]:
        """누적 중요도 90% 이내에서 제로 크로싱이 존재하고 하방 충격량이 극명한 핵심 리스크 팩터를 자동 선별합니다.

        Args:
            shap_result (ShapResult): 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
            evaluation_features (pd.DataFrame): 평가 데이터셋 원시 피처 행렬.
            top_k (Optional[int]): 선별할 상위 팩터 개수 (None 시 누적 중요도 기준 전수 선별). Defaults to None.
            cumulative_ratio_threshold (float): 선별 후보군 한정 누적 중요도 비율 임계치 (%). Defaults to 90.0.

        Returns:
            List[str]: 하방 충격량 순위 기준 핵심 피처 식별 명단.
        """
        return _rank_features_by_impact(
            shap_result=shap_result,
            evaluation_features=evaluation_features,
            quantile_cutoff=self.quantile_cutoff,
            top_k=top_k,
            cumulative_ratio_threshold=cumulative_ratio_threshold,
        )


def extract_feature_inflection(
    shap_result: ShapResult,
    feature_name: str,
    evaluation_features: pd.DataFrame,
    quantile_cutoff: float = DEFAULT_INFLECTION_QUANTILE_CUTOFF,
) -> InflectionPointResult:
    """단일 피처에 대한 변곡점 분석을 수행하는 공개 함수형 진입점.

    Args:
        shap_result (ShapResult): 검증 완료된 SHAP 결과 DTO.
        feature_name (str): 분석 대상 피처 명칭.
        evaluation_features (pd.DataFrame): 평가 피처 행렬.
        quantile_cutoff (float): 이상치 차단 분위수. Defaults to 0.05.

    Returns:
        InflectionPointResult: 산출된 변곡점 결과 DTO.
    """
    analyzer = RiskPolicyAnalyzer(quantile_cutoff=quantile_cutoff)
    return analyzer.analyze_feature_inflection(
        shap_result=shap_result,
        feature_name=feature_name,
        evaluation_features=evaluation_features,
    )


def extract_multiple_inflections(
    shap_result: ShapResult,
    target_features: List[str],
    evaluation_features: pd.DataFrame,
    quantile_cutoff: float = DEFAULT_INFLECTION_QUANTILE_CUTOFF,
) -> InflectionPolicyResult:
    """다중 리스크 피처군에 대한 정책 변곡점 일괄 분석을 집행하는 공개 함수형 진입점.

    Args:
        shap_result (ShapResult): 검증 완료된 SHAP 결과 DTO.
        target_features (List[str]): 대상 피처 명단.
        evaluation_features (pd.DataFrame): 평가 피처 행렬.
        quantile_cutoff (float): 이상치 차단 분위수. Defaults to 0.05.

    Returns:
        InflectionPolicyResult: 통합 리스크 정책 결과 DTO.
    """
    analyzer = RiskPolicyAnalyzer(quantile_cutoff=quantile_cutoff)
    return analyzer.analyze_policy_boundary(
        shap_result=shap_result,
        target_features=target_features,
        evaluation_features=evaluation_features,
    )


def detect_salient_inflection_features(
    shap_result: ShapResult,
    evaluation_features: pd.DataFrame,
    top_k: Optional[int] = None,
    cumulative_ratio_threshold: float = DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
    quantile_cutoff: float = DEFAULT_INFLECTION_QUANTILE_CUTOFF,
) -> List[str]:
    """누적 기여도 90% 이내 정책 변곡점이 뚜렷한 핵심 리스크 팩터를 자동 도출하는 공개 함수형 진입점.

    Args:
        shap_result (ShapResult): 검증 완료된 SHAP 결과 DTO.
        evaluation_features (pd.DataFrame): 평가 피처 행렬.
        top_k (Optional[int]): 자동 사출할 상위 피처 개수 (None 시 누적 임계치 전체). Defaults to None.
        cumulative_ratio_threshold (float): 핵심 피처 누적 기여도 기준 (%). Defaults to 90.0.
        quantile_cutoff (float): 이상치 차단 분위수. Defaults to 0.05.

    Returns:
        List[str]: 자동 선별된 핵심 리스크 팩터 명단.
    """
    analyzer = RiskPolicyAnalyzer(quantile_cutoff=quantile_cutoff)
    return analyzer.detect_salient_features(
        shap_result=shap_result,
        evaluation_features=evaluation_features,
        top_k=top_k,
        cumulative_ratio_threshold=cumulative_ratio_threshold,
    )


class RegimeCohortAnalyzer:
    """5대 시장 국면별 코호트 마스킹, 피처 기여도 집계 및 신호 정합성 감사 분석기.

    Attributes:
        percentile_threshold (float): 시장 급등/급락 및 극단 국면 분위수 임계치.
        normal_sigma_bound (float): 평시 안정 국면 표준편차 배수.
    """

    def __init__(
        self,
        percentile_threshold: float = DEFAULT_REGIME_PERCENTILE_THRESHOLD,
        normal_sigma_bound: float = DEFAULT_NORMAL_SIGMA_BOUND,
    ) -> None:
        """RegimeCohortAnalyzer 인스턴스를 초기화합니다.

        Args:
            percentile_threshold (float): 국면 분위수 임계치. Defaults to 0.20.
            normal_sigma_bound (float): 평시 표준편차 배수. Defaults to 0.5.
        """
        self.percentile_threshold: float = percentile_threshold
        self.normal_sigma_bound: float = normal_sigma_bound

    def analyze_cohorts(
        self,
        y_true: pd.Series,
        y_pred: pd.Series,
        shap_df: pd.DataFrame,
    ) -> RegimeCohortResult:
        """5대 시장 국면별 코호트를 마스킹하고 정량 감사표 및 평균 SHAP DTO를 산출합니다.

        Args:
            y_true (pd.Series): 실측 목표 수익률 시계열.
            y_pred (pd.Series): 모델 예측값 시계열.
            shap_df (pd.DataFrame): 평가 표본에 대한 피처별 SHAP 기여도 행렬.

        Returns:
            RegimeCohortResult: 5대 시장 국면 감사표 및 평균 기여도가 담긴 DTO.

        Raises:
            ValueError: 입력 시계열 간 유효 인덱스 교집합이 없거나 비어 있는 경우 발생.
        """
        audit_dataframe, mean_shap_dataframe, mean_predictions, sample_counts = _audit_regime_cohorts(
            y_true=y_true,
            y_pred=y_pred,
            shap_df=shap_df,
            percentile_threshold=self.percentile_threshold,
            normal_sigma_bound=self.normal_sigma_bound,
        )

        return create_regime_cohort_result(
            regime_audit_dataframe=audit_dataframe,
            regime_mean_shap_dataframe=mean_shap_dataframe,
            regime_mean_predictions=mean_predictions,
            regime_sample_counts=sample_counts,
        )


def compute_historical_drawdown(
    realized_returns: pd.Series,
) -> pd.Series:
    """과거 실측 수익률 기반의 고점 대비 낙폭(Drawdown) 시계열을 산출하는 공개 함수.

    Args:
        realized_returns (pd.Series): 실측 수익률 시계열.

    Returns:
        pd.Series: 고점 대비 낙폭(Historical Drawdown) 시계열.
    """
    return _calculate_historical_drawdown(realized_returns=realized_returns)


def run_robust_regime_cohort_audit(
    y_true: pd.Series,
    y_pred: pd.Series,
    shap_df: pd.DataFrame,
    percentile_threshold: float = DEFAULT_REGIME_PERCENTILE_THRESHOLD,
    normal_sigma_bound: float = DEFAULT_NORMAL_SIGMA_BOUND,
) -> pd.DataFrame:
    """표본 중복을 허용한 5대 시장 국면별 집계 감사표를 생성하는 공개 함수.

    Args:
        y_true (pd.Series): 실측 수익률 시계열.
        y_pred (pd.Series): 모델 예측치 시계열.
        shap_df (pd.DataFrame): 피처별 SHAP 기여도 행렬.
        percentile_threshold (float): 국면 분위수 임계치. Defaults to 0.20.
        normal_sigma_bound (float): 평시 표준편차 배수. Defaults to 0.5.

    Returns:
        pd.DataFrame: 5대 시장 국면별 정량 감사표.
    """
    analyzer = RegimeCohortAnalyzer(
        percentile_threshold=percentile_threshold,
        normal_sigma_bound=normal_sigma_bound,
    )
    result = analyzer.analyze_cohorts(
        y_true=y_true,
        y_pred=y_pred,
        shap_df=shap_df,
    )
    return result.regime_audit_dataframe


def analyze_regime_cohorts(
    y_true: pd.Series,
    y_pred: pd.Series,
    shap_df: pd.DataFrame,
    percentile_threshold: float = DEFAULT_REGIME_PERCENTILE_THRESHOLD,
    normal_sigma_bound: float = DEFAULT_NORMAL_SIGMA_BOUND,
) -> RegimeCohortResult:
    """5대 시장 국면 코호트 감사를 집행하고 종합 DTO를 사출하는 공개 함수.

    Args:
        y_true (pd.Series): 실측 수익률 시계열.
        y_pred (pd.Series): 모델 예측치 시계열.
        shap_df (pd.DataFrame): 피처별 SHAP 기여도 행렬.
        percentile_threshold (float): 국면 분위수 임계치. Defaults to 0.20.
        normal_sigma_bound (float): 평시 표준편차 배수. Defaults to 0.5.

    Returns:
        RegimeCohortResult: 국면 감사표 및 평균 SHAP 행렬이 포함된 DTO.
    """
    analyzer = RegimeCohortAnalyzer(
        percentile_threshold=percentile_threshold,
        normal_sigma_bound=normal_sigma_bound,
    )
    return analyzer.analyze_cohorts(
        y_true=y_true,
        y_pred=y_pred,
        shap_df=shap_df,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_feature_presence(
    feature_name: str,
    available_features: List[str],
) -> None:
    """대상 피처가 결과 피처 풀에 존재하는지 검증합니다."""
    if feature_name not in available_features:
        raise ValueError(f"[_validate_feature_presence] 피처 '{feature_name}'이(가) 결과 풀에 존재하지 않습니다.")


def _calculate_inflection_metrics(
    feature_values: np.ndarray,
    shap_feature_values: np.ndarray,
    quantile_cutoff: float,
) -> Tuple[float, float, float, float]:
    """양극단 이상치 제거 및 정렬 후 제로 크로싱 변곡점과 구간별 충격량을 통합 연산합니다."""
    filtered_features, filtered_shap = _filter_quantile_outliers(
        feature_values=feature_values,
        shap_values=shap_feature_values,
        quantile_cutoff=quantile_cutoff,
    )

    sort_indices = np.argsort(filtered_features)
    sorted_features = filtered_features[sort_indices]
    sorted_shap = filtered_shap[sort_indices]

    threshold = _find_inflection_threshold(
        sorted_feature_values=sorted_features,
        sorted_shap_values=sorted_shap,
    )

    mean_below, mean_above, delta_impact = _compute_zone_impacts(
        sorted_feature_values=sorted_features,
        sorted_shap_values=sorted_shap,
        threshold=threshold,
    )

    return threshold, mean_below, mean_above, delta_impact


def _filter_quantile_outliers(
    feature_values: np.ndarray,
    shap_values: np.ndarray,
    quantile_cutoff: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """양극단 이상치를 필터링하여 정상 표본 구간을 추출합니다."""
    lower_cutoff_bound = np.quantile(feature_values, quantile_cutoff)
    upper_cutoff_bound = np.quantile(feature_values, 1.0 - quantile_cutoff)
    valid_mask = (feature_values >= lower_cutoff_bound) & (feature_values <= upper_cutoff_bound)
    return feature_values[valid_mask], shap_values[valid_mask]


def _find_inflection_threshold(
    sorted_feature_values: np.ndarray,
    sorted_shap_values: np.ndarray,
) -> float:
    """SHAP 기여도의 제로 크로싱 중 하방 충격량이 최대화되는 최적 임계치 또는 중위수를 도출합니다."""
    sign_differences = np.diff(np.sign(sorted_shap_values))
    zero_crossing_indices = np.where(sign_differences)[0]

    if len(zero_crossing_indices) == 0:
        return float(np.median(sorted_feature_values))

    if len(zero_crossing_indices) == 1:
        return float(sorted_feature_values[zero_crossing_indices[0]])

    # [설계 의도] 다중 제로 크로싱(노이즈 진동) 발생 시, 분할 전후의 하방 충격량(|Δ Impact|)이 최대화되는 지점을 최적 변곡점으로 선정
    best_threshold: float = float(sorted_feature_values[zero_crossing_indices[0]])
    maximum_delta_impact: float = -1.0

    for crossing_index in zero_crossing_indices:
        candidate_threshold = float(sorted_feature_values[crossing_index])
        below_mask = sorted_feature_values < candidate_threshold
        above_mask = sorted_feature_values >= candidate_threshold

        if np.any(below_mask) and np.any(above_mask):
            current_impact = abs(
                float(np.mean(sorted_shap_values[above_mask])) - float(np.mean(sorted_shap_values[below_mask]))
            )
            if current_impact > maximum_delta_impact:
                maximum_delta_impact = current_impact
                best_threshold = candidate_threshold

    return best_threshold


def _compute_zone_impacts(
    sorted_feature_values: np.ndarray,
    sorted_shap_values: np.ndarray,
    threshold: float,
) -> Tuple[float, float, float]:
    """임계치 기준 정상 영역과 위험 영역의 평균 기여도 및 하방 충격량을 연산합니다."""
    below_threshold_mask = sorted_feature_values < threshold
    above_threshold_mask = sorted_feature_values >= threshold

    mean_shap_below = (
        float(np.mean(sorted_shap_values[below_threshold_mask]))
        if np.any(below_threshold_mask)
        else 0.0
    )
    mean_shap_above = (
        float(np.mean(sorted_shap_values[above_threshold_mask]))
        if np.any(above_threshold_mask)
        else 0.0
    )
    delta_impact = mean_shap_above - mean_shap_below

    return mean_shap_below, mean_shap_above, delta_impact


def _filter_features_by_cumulative_importance(
    global_importance_dataframe: pd.DataFrame,
    cumulative_ratio_threshold: float,
) -> List[str]:
    """누적 중요도 비율 기준 핵심 정보 보존 피처 목록을 선별합니다."""
    if global_importance_dataframe.empty:
        return []

    previous_cumulative = global_importance_dataframe["cumulative_ratio_pct"].shift(1, fill_value=0.0)
    retained_mask = previous_cumulative < cumulative_ratio_threshold
    retained_features = global_importance_dataframe[retained_mask].index.tolist()

    return retained_features if retained_features else global_importance_dataframe.index.tolist()[:1]


def _rank_features_by_impact(
    shap_result: ShapResult,
    evaluation_features: pd.DataFrame,
    quantile_cutoff: float,
    top_k: Optional[int] = None,
    cumulative_ratio_threshold: float = DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
) -> List[str]:
    """누적 중요도 90% 피처 풀 내에서 제로 크로싱 유무 및 절대 하방 충격량을 산출하여 순위화합니다."""
    candidate_features = _filter_features_by_cumulative_importance(
        global_importance_dataframe=shap_result.global_importance_dataframe,
        cumulative_ratio_threshold=cumulative_ratio_threshold,
    )

    impact_scores: Dict[str, float] = {}

    for feature_name in candidate_features:
        if feature_name not in shap_result.feature_names:
            continue
        feature_index = shap_result.feature_names.index(feature_name)
        feature_values = evaluation_features[feature_name].to_numpy(dtype=np.float64)
        shap_feature_values = shap_result.shap_values[:, feature_index]

        filtered_features, filtered_shap = _filter_quantile_outliers(
            feature_values=feature_values,
            shap_values=shap_feature_values,
            quantile_cutoff=quantile_cutoff,
        )

        sorted_indices = np.argsort(filtered_features)
        sorted_shap = filtered_shap[sorted_indices]

        # [설계 의도] 제로 크로싱(부호 반전)이 실제 존재하는 피처만 1차 적격 후보로 판정
        sign_differences = np.diff(np.sign(sorted_shap))
        has_zero_crossing = len(np.where(sign_differences)[0]) > 0

        if has_zero_crossing:
            threshold, mean_below, mean_above, delta_impact = _calculate_inflection_metrics(
                feature_values=feature_values,
                shap_feature_values=shap_feature_values,
                quantile_cutoff=quantile_cutoff,
            )
            impact_scores[feature_name] = abs(delta_impact)

    # 제로 크로싱 후보가 부족하거나 없는 경우 후보 피처 풀 전체의 충격량 산출로 보충
    if top_k is not None and len(impact_scores) < top_k:
        for feature_name in candidate_features:
            if feature_name not in impact_scores and feature_name in shap_result.feature_names:
                feature_index = shap_result.feature_names.index(feature_name)
                feature_values = evaluation_features[feature_name].to_numpy(dtype=np.float64)
                shap_feature_values = shap_result.shap_values[:, feature_index]
                _, _, _, delta_impact = _calculate_inflection_metrics(
                    feature_values=feature_values,
                    shap_feature_values=shap_feature_values,
                    quantile_cutoff=quantile_cutoff,
                )
                impact_scores[feature_name] = abs(delta_impact)
    elif len(impact_scores) == 0:
        for feature_name in candidate_features:
            if feature_name in shap_result.feature_names:
                feature_index = shap_result.feature_names.index(feature_name)
                feature_values = evaluation_features[feature_name].to_numpy(dtype=np.float64)
                shap_feature_values = shap_result.shap_values[:, feature_index]
                _, _, _, delta_impact = _calculate_inflection_metrics(
                    feature_values=feature_values,
                    shap_feature_values=shap_feature_values,
                    quantile_cutoff=quantile_cutoff,
                )
                impact_scores[feature_name] = abs(delta_impact)

    sorted_features = sorted(impact_scores.keys(), key=lambda name: impact_scores[name], reverse=True)
    return sorted_features[:top_k] if top_k is not None else sorted_features


def _calculate_historical_drawdown(
    realized_returns: pd.Series,
) -> pd.Series:
    """단순 합산 기준 롤링 누적 수익률 기반 역사적 고점 대비 낙폭 시계열을 연산합니다."""
    rolling_cumulative = realized_returns.cumsum()
    rolling_peak = rolling_cumulative.cummax()
    return rolling_cumulative - rolling_peak


def _identify_regime_cohort_indices(
    y_true: pd.Series,
    y_pred: pd.Series,
    historical_dd: pd.Series,
    percentile_threshold: float,
    normal_sigma_bound: float,
) -> List[Tuple[str, pd.Index]]:
    """실측 수익률, 모델 예측 및 역사적 낙폭으로부터 5대 시장 국면 인덱스를 분할합니다."""
    model_realized_pnl = np.sign(y_pred) * y_true
    return_std = float(y_true.std())
    return_mean = float(y_true.mean())

    idx_normal = y_true[
        (y_true >= return_mean - normal_sigma_bound * return_std)
        & (y_true <= return_mean + normal_sigma_bound * return_std)
    ].index

    idx_market_bull = y_true[
        y_true >= y_true.quantile(1.0 - percentile_threshold)
    ].index

    idx_peak_alpha = model_realized_pnl[
        model_realized_pnl >= model_realized_pnl.quantile(1.0 - percentile_threshold)
    ].index

    idx_market_bear = y_true[
        y_true <= y_true.quantile(percentile_threshold)
    ].index

    idx_mdd_stress = historical_dd[
        historical_dd <= historical_dd.quantile(percentile_threshold)
    ].index

    return [
        ("Normal", idx_normal),
        ("Market Bull", idx_market_bull),
        ("Peak Model Alpha", idx_peak_alpha),
        ("Market Bear", idx_market_bear),
        ("Historical MDD Stress", idx_mdd_stress),
    ]


def _calculate_cohort_factor_rankings(
    cohort_shap: pd.DataFrame,
) -> Tuple[str, float, float, str, float, float]:
    """부호 상쇄 왜곡을 방어한 평균 절대 기여도 기준 상위 1위 및 2위 팩터를 도출합니다."""
    factor_mean_shaps = cohort_shap.mean(axis=0)
    factor_std_shaps = cohort_shap.std(axis=0)
    sorted_factors = cohort_shap.abs().mean(axis=0).sort_values(ascending=False)

    top1_factor = str(sorted_factors.index[0])
    top1_impact = float(factor_mean_shaps[top1_factor])
    top1_std = float(factor_std_shaps[top1_factor]) if not np.isnan(factor_std_shaps[top1_factor]) else 0.0

    if len(sorted_factors) > 1:
        top2_factor = str(sorted_factors.index[1])
        top2_impact = float(factor_mean_shaps[top2_factor])
        top2_std = float(factor_std_shaps[top2_factor]) if not np.isnan(factor_std_shaps[top2_factor]) else 0.0
    else:
        top2_factor = "-"
        top2_impact = 0.0
        top2_std = 0.0

    return top1_factor, top1_impact, top1_std, top2_factor, top2_impact, top2_std


def _calculate_effective_code_synchrony(
    cohort_shap: pd.DataFrame,
) -> float:
    """국면 표본에 대한 팩터 기여도의 정량적 신호 일치도(ECS) 평균을 연산합니다."""
    abs_shap_sum = cohort_shap.abs().sum(axis=1)
    net_shap_sum = cohort_shap.sum(axis=1).abs()
    ecs_series = np.where(abs_shap_sum > 0, net_shap_sum / abs_shap_sum, 1.0)
    return float(np.mean(ecs_series))


def _determine_model_stance(
    mean_prediction: float,
) -> str:
    """모델 평균 예측 강도에 따른 국면별 포지션 스탠스를 판정합니다."""
    if mean_prediction > DEFAULT_LONG_BIAS_THRESHOLD:
        return f"Long 편향 (+{mean_prediction:.3f})"
    if mean_prediction < DEFAULT_SHORT_BIAS_THRESHOLD:
        return f"Short 편향 ({mean_prediction:.3f})"
    return f"Neutral ({mean_prediction:.3f})"


def _evaluate_signal_alignment(
    mean_target: float,
    mean_prediction: float,
) -> str:
    """모델 예측 방향과 실측 시장 방향 간의 유의미한 정합성을 진단합니다."""
    is_aligned = (np.sign(mean_target) == np.sign(mean_prediction)) and (
        abs(mean_prediction) > DEFAULT_ALIGNMENT_MIN_PREDICTION
    )
    return "정합 (Hit)" if is_aligned else "괴리 (Divergence)"


def _audit_regime_cohorts(
    y_true: pd.Series,
    y_pred: pd.Series,
    shap_df: pd.DataFrame,
    percentile_threshold: float,
    normal_sigma_bound: float,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float], Dict[str, int]]:
    """5대 시장 국면별 집계 감사표, 평균 SHAP 행렬 및 상태 통계량을 전수 산출합니다."""
    common_index = shap_df.index.intersection(y_true.index).intersection(y_pred.index)
    if len(common_index) == 0:
        raise ValueError("[_audit_regime_cohorts] 유효한 공통 인덱스가 존재하지 않습니다.")

    aligned_y_true = y_true.loc[common_index]
    aligned_y_pred = y_pred.loc[common_index]
    aligned_shap = shap_df.loc[common_index]

    historical_dd = _calculate_historical_drawdown(realized_returns=aligned_y_true)
    regimes = _identify_regime_cohort_indices(
        y_true=aligned_y_true,
        y_pred=aligned_y_pred,
        historical_dd=historical_dd,
        percentile_threshold=percentile_threshold,
        normal_sigma_bound=normal_sigma_bound,
    )

    audit_records = []
    mean_shap_records: Dict[str, pd.Series] = {}
    mean_predictions: Dict[str, float] = {}
    sample_counts: Dict[str, int] = {}

    total_samples = len(aligned_shap)

    for name, cohort_idx in regimes:
        valid_idx = aligned_shap.index.intersection(cohort_idx)
        if len(valid_idx) == 0:
            continue

        cohort_shap = aligned_shap.loc[valid_idx]
        cohort_y_true = aligned_y_true.loc[valid_idx]
        cohort_y_pred = aligned_y_pred.loc[valid_idx]

        top1_factor, top1_impact, top1_std, top2_factor, top2_impact, top2_std = _calculate_cohort_factor_rankings(
            cohort_shap=cohort_shap
        )
        mean_ecs = _calculate_effective_code_synchrony(cohort_shap=cohort_shap)

        mean_pred = float(cohort_y_pred.mean())
        mean_true = float(cohort_y_true.mean())
        model_stance = _determine_model_stance(mean_prediction=mean_pred)
        alignment_status = _evaluate_signal_alignment(mean_target=mean_true, mean_prediction=mean_pred)

        mean_shap_records[name] = cohort_shap.mean(axis=0)
        mean_predictions[name] = mean_pred
        sample_counts[name] = len(valid_idx)

        audit_records.append({
            "시장 국면 (Regime)": name,
            "표본 수 (N)": f"{len(valid_idx)}일",
            "비율 (%)": f"{len(valid_idx) / total_samples * 100:.1f}%",
            "실측 수익률 (Mean y)": f"{mean_true:+.4f}",
            "모델 예측치 (Mean f(x))": f"{mean_pred:+.4f}",
            "모델 스탠스": model_stance,
            "신호 정합성": alignment_status,
            "주도 팩터 1위": top1_factor,
            "1위 기여도": f"{top1_impact:+.4f} (±{top1_std:.4f})",
            "주도 팩터 2위": top2_factor,
            "2위 기여도": f"{top2_impact:+.4f} (±{top2_std:.4f})",
            "신호 일치도 (ECS)": f"{mean_ecs:.3f}",
        })

    audit_dataframe = pd.DataFrame(audit_records).set_index("시장 국면 (Regime)")
    mean_shap_dataframe = pd.DataFrame(mean_shap_records).T

    return audit_dataframe, mean_shap_dataframe, mean_predictions, sample_counts