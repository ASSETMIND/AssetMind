from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.model.xai.shap_schema import (
    DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
    InflectionPointResult,
    InflectionPolicyResult,
    ShapResult,
    create_inflection_point_result,
    create_inflection_policy_result,
)


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 리스크 변곡점 탐색 및 이상치 필터링 설정
DEFAULT_INFLECTION_QUANTILE_CUTOFF: float = 0.05  # 변곡점 탐색 시 양극단 이상치 차단 분위수 임계치


# ==============================================================================
# Public API Functions
# ==============================================================================
class RiskPolicyAnalyzer:
    """SHAP 기여도 곡선 기반 리스크 임계 변곡점 탐색 및 행동 정책 경계선 사출 분석기.

    Attributes:
        quantile_cutoff (float): 양극단 이상치 차단 분위수 기준값.
    """

    def __init__(
        self,
        quantile_cutoff: float = DEFAULT_INFLECTION_QUANTILE_CUTOFF,
    ) -> None:
        """RiskPolicyAnalyzer 인스턴스를 초기화합니다.

        Args:
            quantile_cutoff (float): 양극단 이상치 제거 분위수. Defaults to DEFAULT_INFLECTION_QUANTILE_CUTOFF.
        """
        # 이상치 차단 분위수 상태 저장
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
            InflectionPointResult: 변곡점 임계치, 구간별 평균 기여도 및 충격량이 담긴 불변 DTO.

        Raises:
            ValueError: 대상 피처명이 SHAP 결과 또는 평가 피처 행렬에 존재하지 않는 경우 발생.
        """
        # 1. 분석 대상 피처가 SHAP 결과 및 평가 데이터프레임에 존재하는지 검증
        _validate_feature_presence(
            feature_name=feature_name,
            available_features=shap_result.feature_names,
            evaluation_features=evaluation_features,
        )

        # 2. 대상 피처의 원시 관측값 벡터와 1차 SHAP 기여도 벡터 추출
        feature_values, shap_feature_values = _extract_feature_and_shap_vectors(
            shap_result=shap_result,
            feature_name=feature_name,
            evaluation_features=evaluation_features,
        )

        # 3. 이상치 제거 후 제로 크로싱 변곡점 임계치 및 구간별 충격량 연산
        threshold, mean_below, mean_above, delta_impact = _calculate_inflection_metrics(
            feature_values=feature_values,
            shap_feature_values=shap_feature_values,
            quantile_cutoff=self.quantile_cutoff,
        )

        # 4. 단일 피처 변곡점 분석 결과 불변 DTO 생성 및 반환
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
            InflectionPolicyResult: 개별 변곡점 결과 맵과 감사 요약 데이터프레임이 포함된 불변 DTO.

        Raises:
            ValueError: target_features 리스트가 비어 있는 경우 발생.
        """
        # 1. 분석 대상 피처 명단 유효성 검증
        if not target_features:
            raise ValueError("[RiskPolicyAnalyzer] target_features 리스트가 비어 있습니다.")

        # 2. 유효 피처별 변곡점 분석 순차 실행 및 레코드 수집
        policy_records: Dict[str, InflectionPointResult] = {}
        for feature_name in target_features:
            if feature_name in shap_result.feature_names:
                policy_records[feature_name] = self.analyze_feature_inflection(
                    shap_result=shap_result,
                    feature_name=feature_name,
                    evaluation_features=evaluation_features,
                )

        # 3. 다중 피처 변곡점 정책 요약 DTO 조립 및 반환
        return create_inflection_policy_result(policy_records=policy_records)

    def detect_salient_features(
        self,
        shap_result: ShapResult,
        evaluation_features: pd.DataFrame,
        top_k: Optional[int] = None,
        cumulative_ratio_threshold: float = DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
    ) -> List[str]:
        """누적 중요도 임계치 이내에서 제로 크로싱이 존재하고 하방 충격량이 큰 핵심 리스크 팩터를 자동 선별합니다.

        Args:
            shap_result (ShapResult): 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
            evaluation_features (pd.DataFrame): 평가 데이터셋 원시 피처 행렬.
            top_k (Optional[int]): 선별할 상위 팩터 개수 (None 시 누적 중요도 기준 전수 선별). Defaults to None.
            cumulative_ratio_threshold (float): 후보군 한정 누적 중요도 비율 임계치 (%). Defaults to DEFAULT_CUMULATIVE_RATIO_THRESHOLD.

        Returns:
            List[str]: 하방 충격량 크기 순으로 정렬된 핵심 리스크 피처 식별 명단.
        """
        # 내장 순위 산출 알고리즘을 호출하여 핵심 변곡점 피처 명단 반환
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
        quantile_cutoff (float): 이상치 차단 분위수. Defaults to DEFAULT_INFLECTION_QUANTILE_CUTOFF.

    Returns:
        InflectionPointResult: 산출된 변곡점 결과 불변 DTO.

    Raises:
        ValueError: 대상 피처명이 결과 풀에 부재할 경우 발생.
    """
    # 분석기 인스턴스 생성 및 단일 피처 변곡점 분석 위임
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
        quantile_cutoff (float): 이상치 차단 분위수. Defaults to DEFAULT_INFLECTION_QUANTILE_CUTOFF.

    Returns:
        InflectionPolicyResult: 통합 리스크 정책 결과 불변 DTO.

    Raises:
        ValueError: target_features가 비어 있을 경우 발생.
    """
    # 분석기 인스턴스 생성 및 다중 피처 정책 경계선 분석 위임
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
    """누적 기여도 임계치 이내에서 정책 변곡점이 뚜렷한 핵심 리스크 팩터를 자동 도출하는 공개 함수형 진입점.

    Args:
        shap_result (ShapResult): 검증 완료된 SHAP 결과 DTO.
        evaluation_features (pd.DataFrame): 평가 피처 행렬.
        top_k (Optional[int]): 자동 사출할 상위 피처 개수 (None 시 누적 임계치 전체). Defaults to None.
        cumulative_ratio_threshold (float): 핵심 피처 누적 기여도 기준 (%). Defaults to DEFAULT_CUMULATIVE_RATIO_THRESHOLD.
        quantile_cutoff (float): 이상치 차단 분위수. Defaults to DEFAULT_INFLECTION_QUANTILE_CUTOFF.

    Returns:
        List[str]: 자동 선별된 핵심 리스크 팩터 명단.
    """
    # 분석기 인스턴스 생성 및 핵심 변곡점 피처 탐지 위임
    analyzer = RiskPolicyAnalyzer(quantile_cutoff=quantile_cutoff)
    return analyzer.detect_salient_features(
        shap_result=shap_result,
        evaluation_features=evaluation_features,
        top_k=top_k,
        cumulative_ratio_threshold=cumulative_ratio_threshold,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_feature_presence(
    feature_name: str,
    available_features: List[str],
    evaluation_features: pd.DataFrame,
) -> None:
    """대상 피처가 SHAP 결과 피처 풀과 평가 데이터프레임에 모두 존재하는지 검증합니다."""
    # 피처명 누락 시 명시적 예외 발생
    if feature_name not in available_features or feature_name not in evaluation_features.columns:
        raise ValueError(
            f"[_validate_feature_presence] 피처 '{feature_name}'이(가) 결과 풀 또는 평가 데이터에 존재하지 않습니다."
        )


def _extract_feature_and_shap_vectors(
    shap_result: ShapResult,
    feature_name: str,
    evaluation_features: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray]:
    """특정 피처의 원시 관측값 배열과 대응하는 1차 SHAP 기여도 배열을 추출합니다."""
    # 피처 위치 인덱스 조회 및 float64 1차원 배열 추출
    feature_index = shap_result.feature_names.index(feature_name)
    feature_values = evaluation_features[feature_name].to_numpy(dtype=np.float64)
    shap_feature_values = shap_result.shap_values[:, feature_index]
    return feature_values, shap_feature_values


def _calculate_inflection_metrics(
    feature_values: np.ndarray,
    shap_feature_values: np.ndarray,
    quantile_cutoff: float,
) -> Tuple[float, float, float, float]:
    """양극단 이상치 제거 및 정렬 후 제로 크로싱 변곡점과 구간별 충격량을 통합 연산합니다."""
    # 1. 분위수 기준 양극단 이상치 제거 및 피처값 오름차순 정렬
    filtered_features, filtered_shap = _filter_quantile_outliers(
        feature_values=feature_values,
        shap_values=shap_feature_values,
        quantile_cutoff=quantile_cutoff,
    )
    sort_indices = np.argsort(filtered_features)
    sorted_features = filtered_features[sort_indices]
    sorted_shap = filtered_shap[sort_indices]

    # 2. 최적 제로 크로싱 변곡점 임계치 탐색
    threshold = _find_inflection_threshold(
        sorted_feature_values=sorted_features,
        sorted_shap_values=sorted_shap,
    )

    # 3. 임계치 전후 구간의 평균 SHAP 기여도 및 하방 충격량 산출
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
    # 상하단 분위수 경계 산출 및 유효 마스크 슬라이싱
    lower_cutoff_bound = np.quantile(feature_values, quantile_cutoff)
    upper_cutoff_bound = np.quantile(feature_values, 1.0 - quantile_cutoff)
    valid_mask = (feature_values >= lower_cutoff_bound) & (feature_values <= upper_cutoff_bound)
    return feature_values[valid_mask], shap_values[valid_mask]


def _find_inflection_threshold(
    sorted_feature_values: np.ndarray,
    sorted_shap_values: np.ndarray,
) -> float:
    """SHAP 기여도의 제로 크로싱 중 하방 충격량이 최대화되는 최적 임계치 또는 중위수를 도출합니다."""
    # 1. 인접 표본 간 부호 변화(Zero-Crossing) 위치 인덱스 탐색
    sign_differences = np.diff(np.sign(sorted_shap_values))
    zero_crossing_indices = np.where(sign_differences)[0]

    if len(zero_crossing_indices) == 0:
        return float(np.median(sorted_feature_values))

    if len(zero_crossing_indices) == 1:
        return float(sorted_feature_values[zero_crossing_indices[0]])

    # 2. [설계 의도] 다중 제로 크로싱(노이즈 진동) 발생 시 전후 충격량(|Δ Impact|)이 최대화되는 지점을 선정
    best_threshold: float = float(sorted_feature_values[zero_crossing_indices[0]])
    maximum_delta_impact: float = -1.0

    for crossing_index in zero_crossing_indices:
        candidate_threshold = float(sorted_feature_values[crossing_index])
        below_mask = sorted_feature_values < candidate_threshold
        above_mask = sorted_feature_values >= candidate_threshold

        if np.any(below_mask) and np.any(above_mask):
            current_impact = abs(
                float(np.mean(sorted_shap_values[above_mask]))
                - float(np.mean(sorted_shap_values[below_mask]))
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
    # 임계치 미만/이상 구간 마스킹 후 각 구간 평균 기여도 및 차분(Delta) 계산
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
    # 파레토 누적 기여도 임계치에 도달하기 전까지의 상위 피처 목록 추출
    if global_importance_dataframe.empty:
        return []

    previous_cumulative = global_importance_dataframe["cumulative_ratio_pct"].shift(1, fill_value=0.0)
    retained_mask = previous_cumulative < cumulative_ratio_threshold
    retained_features = global_importance_dataframe[retained_mask].index.tolist()

    return retained_features if retained_features else global_importance_dataframe.index.tolist()[:1]


def _evaluate_single_feature_impact(
    shap_result: ShapResult,
    feature_name: str,
    evaluation_features: pd.DataFrame,
    quantile_cutoff: float,
) -> Tuple[bool, float]:
    """단일 피처의 제로 크로싱 보유 여부와 절대 하방 충격량(|Delta Impact|)을 산출합니다."""
    # 1. 피처값 및 SHAP 벡터 추출 후 이상치 제거 및 정렬
    feature_values, shap_feature_values = _extract_feature_and_shap_vectors(
        shap_result=shap_result,
        feature_name=feature_name,
        evaluation_features=evaluation_features,
    )
    filtered_features, filtered_shap = _filter_quantile_outliers(
        feature_values=feature_values,
        shap_values=shap_feature_values,
        quantile_cutoff=quantile_cutoff,
    )
    sorted_indices = np.argsort(filtered_features)
    sorted_shap = filtered_shap[sorted_indices]

    # 2. 부호 반전(Zero-Crossing) 존재 여부 판정 및 절대 충격량 계산
    sign_differences = np.diff(np.sign(sorted_shap))
    has_zero_crossing = len(np.where(sign_differences)[0]) > 0

    _, _, _, delta_impact = _calculate_inflection_metrics(
        feature_values=feature_values,
        shap_feature_values=shap_feature_values,
        quantile_cutoff=quantile_cutoff,
    )
    return has_zero_crossing, abs(delta_impact)


def _rank_features_by_impact(
    shap_result: ShapResult,
    evaluation_features: pd.DataFrame,
    quantile_cutoff: float,
    top_k: Optional[int] = None,
    cumulative_ratio_threshold: float = DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
) -> List[str]:
    """누적 중요도 피처 풀 내에서 제로 크로싱 유무 및 절대 하방 충격량을 산출하여 순위화합니다."""
    # 1. 누적 중요도 기준 1차 후보 피처 풀 필터링
    candidate_features = _filter_features_by_cumulative_importance(
        global_importance_dataframe=shap_result.global_importance_dataframe,
        cumulative_ratio_threshold=cumulative_ratio_threshold,
    )
    valid_candidates = [
        name for name in candidate_features if name in shap_result.feature_names
    ]

    # 2. [설계 의도] 제로 크로싱(부호 반전)이 실제 존재하는 피처를 1차 적격 후보로 우선 채택
    impact_scores: Dict[str, float] = {}
    fallback_scores: Dict[str, float] = {}

    for feature_name in valid_candidates:
        has_zero_crossing, abs_impact = _evaluate_single_feature_impact(
            shap_result=shap_result,
            feature_name=feature_name,
            evaluation_features=evaluation_features,
            quantile_cutoff=quantile_cutoff,
        )
        if has_zero_crossing:
            impact_scores[feature_name] = abs_impact
        else:
            fallback_scores[feature_name] = abs_impact

    # 3. 제로 크로싱 후보가 요구 개수(top_k)에 미달하거나 전무할 경우 후보 풀 충격량으로 보충
    requires_fallback = (top_k is not None and len(impact_scores) < top_k) or (len(impact_scores) == 0)
    if requires_fallback:
        impact_scores.update(fallback_scores)

    # 4. 절대 충격량 내림차순 정렬 및 상위 K개 반환
    sorted_features = sorted(
        impact_scores.keys(),
        key=lambda name: impact_scores[name],
        reverse=True,
    )
    return sorted_features[:top_k] if top_k is not None else sorted_features