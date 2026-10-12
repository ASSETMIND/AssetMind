from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [수치 연산 안정성 및 정류 활성화 상수]
EPSILON_LOG_BOUND: float = 1e-12              # log(0) 언더플로 방지를 위한 로그 입력 하한 임계치
MAX_RISK_DISTANCE_CLIP: float = 50.0          # exp 오버플로 방지를 위한 표준화 위험 거리 상한 클리핑 임계치
SAFE_GATE_VALUE: float = 1.0                  # 정상 구역 체류 시 알파 신호 완전 보존 계수
SIGMOID_SCALE_FACTOR: float = 2.0             # z=0 시점 게이트 값 1.0 유지를 위한 정류 시그모이드 분자 계수

# [거버넌스 국면 분류 및 감쇠 판정 임계치 상수]
NORMAL_GATE_THRESHOLD: float = 0.990          # 국면 1 (정상 운용) 판정 하한 게이트 임계치
MILD_DERISKING_THRESHOLD: float = 0.800       # 국면 2 (경미 감쇠) 하한 및 국면 3 (고위험 억제) 상한 경계 임계치

# [아티팩트 결손 방어 기본 폴백 상수]
DEFAULT_INFLECTION_FALLBACK: float = 0.500    # XAI 정책표 미등재 보조 피처용 기본 변곡점 임계치
DEFAULT_STANDARD_DEVIATION: float = 1.0       # 관측치 표준편차 미제공 시 단위 정규화 표준편차


# ==============================================================================
# Public API Functions
# ==============================================================================
def build_xai_risk_governance_report(
    feature_importance_report: pd.DataFrame,
    inflection_policy_summary: Optional[pd.DataFrame] = None,
    features: Optional[pd.DataFrame] = None,
    composite_gate: Optional[pd.Series] = None,
    individual_gates: Optional[pd.DataFrame] = None,
    risk_distances: Optional[pd.DataFrame] = None,
    scale_standard_deviations: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]:
    """XAI 아티팩트와 관측치로부터 거버넌스 실행 파라미터 및 3대 감사 대시보드 테이블을 동적 사출합니다.

    Args:
        feature_importance_report (pd.DataFrame): Train 글로벌 피처 중요도 보고서 (Feature Name, Mean |SHAP|, Signal Corr).
        inflection_policy_summary (Optional[pd.DataFrame]): 피처별 SHAP 변곡점 정책표 (Inflection Threshold 포함).
        features (Optional[pd.DataFrame]): 실측 팩터 관측 시계열 데이터프레임.
        composite_gate (Optional[pd.Series]): 사전 산출된 종합 리스크 게이트 G_t 시계열 (미제공 시 자동 산출).
        individual_gates (Optional[pd.DataFrame]): 사전 산출된 개별 팩터 감쇠 계수 g_{i, t} (미제공 시 자동 산출).
        risk_distances (Optional[pd.DataFrame]): 사전 산출된 표준화 위험 침범 거리 z_{i, t} (미제공 시 자동 산출).

    Returns:
        Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]:
            - Dict[str, Any]: 리스크 게이트 연산용 정합성 설정 딕셔너리.
            - Dict[str, pd.DataFrame]: 3대 감사 대시보드 딕셔너리
                - 'gate_summary': 종합 리스크 게이트 통계 및 3대 운용 국면 요약표.
                - 'regime_attribution': 거버넌스 운용 국면별 8대 팩터 영향도 및 위험 기여도 분해표.
                - 'factor_audit_trail': 8대 팩터별 세부 게이트 감사 및 수리 상태 추적표.

    Raises:
        ValueError: 입력 데이터프레임이 비어 있거나 필수 메타데이터 동적 추출에 실패한 경우.
    """
    _validate_dataframe_integrity(feature_importance_report, "feature_importance_report")

    feature_weights: Dict[str, float] = _extract_dynamic_feature_weights(feature_importance_report)
    target_feature_names: List[str] = list(feature_weights.keys())

    inflection_thresholds: Dict[str, float] = _extract_dynamic_inflection_thresholds(
        inflection_source=inflection_policy_summary,
        feature_names=target_feature_names,
    )
    resolved_scale_deviations: Dict[str, float] = _extract_dynamic_scale_deviations(
        features=features,
        feature_names=target_feature_names,
        scale_source=inflection_policy_summary,
        explicit_scales=scale_standard_deviations,
    )
    risk_direction_signs: Dict[str, int] = _resolve_dynamic_direction_signs(
        report=feature_importance_report,
        feature_names=target_feature_names,
        inflection_source=inflection_policy_summary,
    )

    # [수정 완료] 추출/검증 완료된 resolved_scale_deviations를 설정 딕셔너리에 정확히 바인딩
    configuration: Dict[str, Any] = _assemble_governance_configuration(
        inflection_thresholds=inflection_thresholds,
        scale_standard_deviations=resolved_scale_deviations,
        feature_weights=feature_weights,
        risk_direction_signs=risk_direction_signs,
    )

    if composite_gate is None or individual_gates is None or risk_distances is None:
        if features is None:
            raise ValueError("감사 대시보드 테이블 생성을 위해 features 관측 데이터가 반드시 제공되어야 합니다.")
        composite_gate, individual_gates, risk_distances = generate_xai_risk_governance_gates(
            features=features[target_feature_names],
            risk_policy_configuration=configuration,
        )

    dashboards: Dict[str, pd.DataFrame] = _build_governance_report_bundle(
        configuration=configuration,
        composite_gate=composite_gate,
        individual_gates=individual_gates,
        risk_distances=risk_distances,
    )

    return configuration, dashboards


def generate_xai_risk_governance_gates(
    features: pd.DataFrame,
    risk_policy_configuration: Dict[str, Any],
) -> Tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    """동적 거버넌스 설정을 바탕으로 표준화 위험 거리, 개별 감쇠 계수, 종합 게이트를 일괄 산출합니다.

    Args:
        features (pd.DataFrame): 추론 또는 백테스트 대상 팩터 관측 시계열 데이터프레임.
        risk_policy_configuration (Dict[str, Any]): build_xai_risk_governance_report에서 사출된 실행 설정.

    Returns:
        Tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
            - pd.Series: 단일 종합 리스크 게이트 G_t 시계열 (0.0 ~ 1.0).
            - pd.DataFrame: 각 팩터별 개별 감쇠 계수 g_{i, t} 데이터프레임.
            - pd.DataFrame: 각 팩터별 표준화 위험 침범 거리 z_{i, t} 데이터프레임.

    Raises:
        ValueError: 피처 데이터가 비어 있거나 설정 매핑이 결손된 경우.
    """
    _validate_governance_inputs(features, risk_policy_configuration)

    risk_distances: pd.DataFrame = _compute_standardized_risk_distances(
        features=features,
        configuration=risk_policy_configuration,
    )
    individual_gates: pd.DataFrame = _apply_rectified_sigmoid_transformation(risk_distances)
    composite_gate: pd.Series = _compute_weighted_composite_gate(
        individual_gates=individual_gates,
        weights_dict=risk_policy_configuration["feature_weights"],
    )

    return composite_gate, individual_gates, risk_distances


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_dataframe_integrity(
    data_frame: pd.DataFrame,
    variable_name: str,
) -> None:
    """데이터프레임의 결손 및 공백 상태를 검증합니다."""
    if data_frame is None or data_frame.empty:
        raise ValueError(f"입력된 {variable_name} 데이터프레임이 비어 있거나 유효하지 않습니다.")


def _validate_governance_inputs(
    features: pd.DataFrame,
    configuration: Dict[str, Any],
) -> None:
    """피처 관측치와 거버넌스 설정 간 키 매핑 및 수치 무결성을 전수 검증합니다."""
    _validate_dataframe_integrity(features, "features")

    required_keys: List[str] = [
        "inflection_thresholds",
        "scale_standard_deviations",
        "feature_weights",
        "risk_direction_signs",
    ]
    missing_keys: List[str] = [k for k in required_keys if k not in configuration]
    if missing_keys:
        raise ValueError(f"거버넌스 설정에 필수 항목이 누락되었습니다: {missing_keys}")

    for column_name in features.columns:
        if column_name not in configuration["inflection_thresholds"]:
            raise ValueError(f"피처 '{column_name}'의 변곡점(inflection_thresholds) 설정이 누락되었습니다.")
        if column_name not in configuration["scale_standard_deviations"]:
            raise ValueError(f"피처 '{column_name}'의 스케일 표준편차(scale_standard_deviations) 설정이 누락되었습니다.")
        if configuration["scale_standard_deviations"][column_name] <= 0:
            raise ValueError(f"피처 '{column_name}'의 표준편차는 0보다 커야 합니다.")
        if column_name not in configuration["risk_direction_signs"]:
            raise ValueError(f"피처 '{column_name}'의 위험 방향 부호(risk_direction_signs) 설정이 누락되었습니다.")


def _extract_dynamic_feature_weights(
    report: pd.DataFrame,
) -> Dict[str, float]:
    """보고서로부터 피처명과 중요도 가중치를 동적으로 추출합니다."""
    feature_column: str = (
        "Feature Name" if "Feature Name" in report.columns
        else next((col for col in report.columns if "feature" in col.lower() or "name" in col.lower()), report.columns[0])
    )
    weight_column: str = (
        "Mean |SHAP|" if "Mean |SHAP|" in report.columns
        else next((col for col in report.columns if "shap" in col.lower() or "importance" in col.lower()), report.columns[1])
    )

    feature_series: pd.Series = report[feature_column].astype(str)
    weight_series: pd.Series = report[weight_column].astype(float)
    return dict(zip(feature_series, weight_series))


def _extract_dynamic_inflection_thresholds(
    inflection_source: Optional[pd.DataFrame],
    feature_names: List[str],
) -> Dict[str, float]:
    """XAI 변곡점 정책표로부터 임계치를 추출하고 미등재 피처는 기본값으로 매핑합니다."""
    source_mapping: Dict[str, float] = {}

    if inflection_source is not None and not inflection_source.empty:
        thresh_col = next(
            (c for c in inflection_source.columns if "inflection" in c.lower() or "threshold" in c.lower() or "θ" in c),
            None,
        )
        if thresh_col:
            if "Feature Name" in inflection_source.columns:
                source_mapping = dict(zip(inflection_source["Feature Name"].astype(str), inflection_source[thresh_col].astype(float)))
            elif inflection_source.index.name and "feature" in inflection_source.index.name.lower():
                source_mapping = inflection_source[thresh_col].astype(float).to_dict()
            elif len(inflection_source.columns) >= 2:
                source_mapping = dict(zip(inflection_source.iloc[:, 0].astype(str), inflection_source[thresh_col].astype(float)))

    extracted_thresholds: Dict[str, float] = {}
    for name in feature_names:
        if name in source_mapping:
            extracted_thresholds[name] = float(source_mapping[name])
        else:
            extracted_thresholds[name] = float(DEFAULT_INFLECTION_FALLBACK)

    return extracted_thresholds


def _extract_dynamic_scale_deviations(
    features: Optional[pd.DataFrame],
    feature_names: List[str],
    scale_source: Optional[pd.DataFrame] = None,
    explicit_scales: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Train 세트 사전 추출 표준편차(Frozen Synapse)를 우선 바인딩하며 결손 시 관측치 표준편차로 안전 폴백합니다."""
    extracted_scales: Dict[str, float] = {}

    # 1. 명시적으로 주입된 Train 세트 표준편차 딕셔너리 우선 바인딩
    if explicit_scales is not None and isinstance(explicit_scales, dict):
        for name in feature_names:
            if name in explicit_scales and explicit_scales[name] > 0.0:
                extracted_scales[name] = float(explicit_scales[name])

    # 2. XAI 변곡점 정책표(scale_source) 메타데이터 내 표준편차 컬럼 검사
    if len(extracted_scales) < len(feature_names) and scale_source is not None and not scale_source.empty:
        feat_col: str = (
            "Feature Name" if "Feature Name" in scale_source.columns
            else next((c for c in scale_source.columns if "feature" in c.lower() or "name" in c.lower()), scale_source.columns[0])
        )
        std_col = next(
            (c for c in scale_source.columns if any(k in c.lower() for k in ["std", "sigma", "scale", "표준편차", "σ"])),
            None,
        )
        if std_col:
            for _, row in scale_source.iterrows():
                fname: str = str(row[feat_col])
                if fname in feature_names and fname not in extracted_scales:
                    val: float = float(row[std_col])
                    if val > 1e-6:
                        extracted_scales[fname] = val

    # 3. 관측치(features) 표본 표준편차 동적 계산 폴백
    for name in feature_names:
        if name not in extracted_scales:
            if features is not None and name in features.columns:
                sample_std = float(features[name].std(ddof=1))
                extracted_scales[name] = sample_std if sample_std > 1e-6 else DEFAULT_STANDARD_DEVIATION
            else:
                extracted_scales[name] = DEFAULT_STANDARD_DEVIATION

    return extracted_scales


def _resolve_dynamic_direction_signs(
    report: pd.DataFrame,
    feature_names: List[str],
    inflection_source: Optional[pd.DataFrame] = None,
) -> Dict[str, int]:
    """XAI 정책 메타데이터와 도메인 팩터 특성으로부터 위험 방향 부호(+1/-1)를 동적으로 완전 자동 판정합니다.

    Args:
        report (pd.DataFrame): 글로벌 피처 중요도 보고서 (Signal Corr 또는 Direction 포함).
        feature_names (List[str]): 대상 피처명 목록.
        inflection_source (Optional[pd.DataFrame]): XAI 변곡점 정책표 (Normal Zone, De-risking Zone 등 포함 가능).

    Returns:
        Dict[str, int]: 각 피처별 위험 침범 방향 부호 (+1: 초과 시 위험, -1: 하회 시 위험).
    """
    resolved_signs: Dict[str, int] = {}

    # --------------------------------------------------------------------------
    # 1. [우선순위 1] XAI 변곡점 정책표(inflection_source) 메타데이터 검사
    # --------------------------------------------------------------------------
    if inflection_source is not None and not inflection_source.empty:
        feat_col: str = (
            "Feature Name" if "Feature Name" in inflection_source.columns
            else next((c for c in inflection_source.columns if "feature" in c.lower() or "name" in c.lower()), inflection_source.columns[0])
        )

        explicit_direction_col = next(
            (c for c in inflection_source.columns if c.lower() in ["direction (s)", "direction", "sign", "s", "risk direction", "risk_direction"]),
            None,
        )
        if explicit_direction_col:
            for _, row in inflection_source.iterrows():
                fname: str = str(row[feat_col])
                if fname in feature_names:
                    val_str = str(row[explicit_direction_col]).strip()
                    try:
                        resolved_signs[fname] = 1 if float(val_str) > 0 else -1
                    except ValueError:
                        resolved_signs[fname] = 1 if any(w in val_str.lower() for w in ["초과", "right", "upper", "above", ">", "high"]) else -1

        normal_zone_col = next(
            (c for c in inflection_source.columns if "normal" in c.lower() and "zone" in c.lower()),
            None,
        )
        if normal_zone_col:
            for _, row in inflection_source.iterrows():
                fname: str = str(row[feat_col])
                if fname in feature_names and fname not in resolved_signs:
                    val_str = str(row[normal_zone_col]).lower().strip()
                    resolved_signs[fname] = -1 if any(w in val_str for w in ["right", "upper", "high", "above", ">", "초과"]) else 1

        derisk_zone_col = next(
            (c for c in inflection_source.columns if "derisk" in c.lower() or ("risk" in c.lower() and "zone" in c.lower())),
            None,
        )
        if derisk_zone_col:
            for _, row in inflection_source.iterrows():
                fname: str = str(row[feat_col])
                if fname in feature_names and fname not in resolved_signs:
                    val_str = str(row[derisk_zone_col]).lower().strip()
                    resolved_signs[fname] = 1 if any(w in val_str for w in ["right", "upper", "high", "above", ">", "초과"]) else -1

    # --------------------------------------------------------------------------
    # 2. [우선순위 2] 피처 중요도 보고서(report)의 명시적 방향 컬럼 확인
    # --------------------------------------------------------------------------
    report_feat_col: str = (
        "Feature Name" if "Feature Name" in report.columns
        else next((col for col in report.columns if "feature" in col.lower() or "name" in col.lower()), report.columns[0])
    )
    report_sign_col = next(
        (col for col in report.columns if col.lower() in ["direction (s)", "direction", "sign", "s", "risk direction", "risk_direction"]),
        None,
    )
    if report_sign_col:
        for _, row in report.iterrows():
            fname: str = str(row[report_feat_col])
            if fname in feature_names and fname not in resolved_signs:
                val_str = str(row[report_sign_col]).strip()
                try:
                    resolved_signs[fname] = 1 if float(val_str) > 0 else -1
                except ValueError:
                    resolved_signs[fname] = 1 if any(w in val_str.lower() for w in ["초과", "right", "upper", "above", ">"]) else -1

    # --------------------------------------------------------------------------
    # 3. [우선순위 3] 금융 도메인 팩터 특성(Semantic Taxonomy) 및 신호 상관관계 기반 동적 판정
    # --------------------------------------------------------------------------
    corr_col = next(
        (col for col in report.columns if "corr" in col.lower() or "ic" in col.lower()),
        None,
    )
    report_corr: Dict[str, float] = (
        dict(zip(report[report_feat_col].astype(str), report[corr_col].astype(float)))
        if corr_col else {}
    )

    for name in feature_names:
        if name in resolved_signs:
            continue

        lower_name: str = name.lower()

        # 3-A. 변동성 및 진폭 계열 (ATR, Volatility 등: 시장 충격 폭발 시 위험)
        if any(term in lower_name for term in ["atr", "volatility", "vol", "vix", "drawdown", "dispersion", "std"]):
            resolved_signs[name] = 1

        # 3-B. 수익률 및 거시 모멘텀 계열 (Return, Momentum 등: 지수 급락 시 위험)
        elif any(term in lower_name for term in ["return", "ret", "mom", "momentum", "growth", "roc", "pnl"]):
            resolved_signs[name] = -1

        # 3-C. 첨도 및 비선형 꼬리위험 계열 (Kurtosis, Skewness 등)
        elif any(term in lower_name for term in ["kurt", "kurtosis", "tail", "skew"]):
            corr_val: float = float(report_corr.get(name, 0.0))
            resolved_signs[name] = -1 if corr_val < 0 else 1

        # 3-D. 도메인 분류 불가 일반 팩터 폴백
        else:
            corr_val: float = float(report_corr.get(name, 0.0))
            resolved_signs[name] = -1 if corr_val < 0 else 1

    return resolved_signs


def _assemble_governance_configuration(
    inflection_thresholds: Dict[str, float],
    scale_standard_deviations: Dict[str, float],
    feature_weights: Dict[str, float],
    risk_direction_signs: Dict[str, int],
) -> Dict[str, Any]:
    """동적으로 검증된 파라미터들을 단일 실행 설정 딕셔너리로 패키징합니다."""
    return {
        "inflection_thresholds": inflection_thresholds,
        "scale_standard_deviations": scale_standard_deviations,
        "feature_weights": feature_weights,
        "risk_direction_signs": risk_direction_signs,
    }


def _compute_standardized_risk_distances(
    features: pd.DataFrame,
    configuration: Dict[str, Any],
) -> pd.DataFrame:
    """전체 피처 행렬에 대해 표준화 위험 침범 거리(z_{i, t})를 벡터화 연산합니다."""
    target_columns: List[str] = list(features.columns)

    threshold_series: pd.Series = pd.Series(
        [configuration["inflection_thresholds"][col] for col in target_columns], index=target_columns
    )
    scale_series: pd.Series = pd.Series(
        [configuration["scale_standard_deviations"][col] for col in target_columns], index=target_columns
    )
    sign_series: pd.Series = pd.Series(
        [configuration["risk_direction_signs"][col] for col in target_columns], index=target_columns
    )

    standardized_distances: pd.DataFrame = (
        features[target_columns]
        .sub(threshold_series, axis=1)
        .div(scale_series, axis=1)
        .mul(sign_series, axis=1)
    )

    return standardized_distances.clip(upper=MAX_RISK_DISTANCE_CLIP)


def _apply_rectified_sigmoid_transformation(
    risk_distances: pd.DataFrame,
) -> pd.DataFrame:
    """비선형 정류 시그모이드 감쇠 커널을 벡터 연산으로 적용합니다."""
    distance_array: np.ndarray = risk_distances.to_numpy()
    rectified_distance: np.ndarray = np.maximum(0.0, distance_array)
    sigmoid_multiplier: np.ndarray = SIGMOID_SCALE_FACTOR / (1.0 + np.exp(rectified_distance))

    return pd.DataFrame(
        sigmoid_multiplier,
        index=risk_distances.index,
        columns=risk_distances.columns,
    )


def _compute_weighted_composite_gate(
    individual_gates: pd.DataFrame,
    weights_dict: Dict[str, float],
) -> pd.Series:
    """개별 감쇠 계수를 글로벌 SHAP 가중치 비율로 기하 결합하여 단일 복합 리스크 게이트를 산출합니다."""
    target_columns: List[str] = list(individual_gates.columns)
    raw_weights: np.ndarray = np.array([weights_dict[col] for col in target_columns], dtype=float)

    total_weight: float = float(raw_weights.sum())
    if total_weight <= 0:
        raise ValueError("피처 가중치의 합이 0 이하이므로 복합 게이트를 연산할 수 없습니다.")
    normalized_weights: np.ndarray = raw_weights / total_weight

    clamped_gate_array: np.ndarray = np.clip(
        individual_gates[target_columns].to_numpy(), EPSILON_LOG_BOUND, SAFE_GATE_VALUE
    )
    log_gates_matrix: np.ndarray = np.log(clamped_gate_array)
    weighted_log_sum: np.ndarray = np.dot(log_gates_matrix, normalized_weights)
    composite_gate_array: np.ndarray = np.exp(weighted_log_sum)

    return pd.Series(
        composite_gate_array,
        index=individual_gates.index,
        name="composite_risk_gate",
    )


def _compute_composite_gate_summary(
    composite_gate: pd.Series,
) -> pd.DataFrame:
    """종합 리스크 게이트(G_t) 통계 및 3대 운용 국면 요약표를 사출합니다."""
    total_count: int = len(composite_gate)
    regime_1_ratio: float = (composite_gate >= NORMAL_GATE_THRESHOLD).sum() / total_count * 100.0
    regime_2_ratio: float = (
        ((composite_gate >= MILD_DERISKING_THRESHOLD) & (composite_gate < NORMAL_GATE_THRESHOLD)).sum() / total_count * 100.0
    )
    regime_3_ratio: float = (composite_gate < MILD_DERISKING_THRESHOLD).sum() / total_count * 100.0

    summary_records = [
        {
            "지표 구분": "기준 범위",
            "평균 생존율(Mean)": "-",
            "표준편차(Std)": "-",
            "최소 생존율(Min)": "-",
            "[국면 1] 정상 운용": f"(G >= {NORMAL_GATE_THRESHOLD:.2f})",
            "[국면 2] 경미 감쇠": f"({MILD_DERISKING_THRESHOLD:.2f} <= G < {NORMAL_GATE_THRESHOLD:.2f})",
            "[국면 3] 고위험 억제": f"(G < {MILD_DERISKING_THRESHOLD:.2f})",
        },
        {
            "지표 구분": "G_t 시계열 통계",
            "평균 생존율(Mean)": f"{composite_gate.mean():.4f}",
            "표준편차(Std)": f"{composite_gate.std():.4f}",
            "최소 생존율(Min)": f"{composite_gate.min():.4f}",
            "[국면 1] 정상 운용": f"{regime_1_ratio:.2f}%",
            "[국면 2] 경미 감쇠": f"{regime_2_ratio:.2f}%",
            "[국면 3] 고위험 억제": f"{regime_3_ratio:.2f}%",
        },
    ]
    return pd.DataFrame(summary_records).set_index("지표 구분")


def _compute_regime_factor_attribution(
    composite_gate: pd.Series,
    individual_gates: pd.DataFrame,
    feature_weights: Dict[str, float],
) -> pd.DataFrame:
    """거버넌스 운용 국면별 8대 팩터 영향도 및 위험 기여도 분해표를 사출합니다."""
    feature_names: List[str] = list(individual_gates.columns)
    total_shap: float = sum(feature_weights.values())

    mask_r1: pd.Series = composite_gate >= NORMAL_GATE_THRESHOLD
    mask_r2: pd.Series = (composite_gate >= MILD_DERISKING_THRESHOLD) & (composite_gate < NORMAL_GATE_THRESHOLD)
    mask_r3: pd.Series = composite_gate < MILD_DERISKING_THRESHOLD
    mask_derisk: pd.Series = composite_gate < NORMAL_GATE_THRESHOLD

    penalty_values: Dict[str, float] = {}
    for col in feature_names:
        w_i = feature_weights[col] / total_shap
        if mask_derisk.any():
            g_derisk = np.clip(individual_gates.loc[mask_derisk, col].to_numpy(), EPSILON_LOG_BOUND, SAFE_GATE_VALUE)
            penalty_values[col] = float(-w_i * np.log(g_derisk).sum())
        else:
            penalty_values[col] = 0.0

    total_penalty: float = sum(penalty_values.values())
    attribution_records: List[Dict[str, Any]] = []

    sum_w: float = 0.0
    sum_r1_weighted: float = 0.0
    sum_r2_weighted: float = 0.0
    sum_r3_weighted: float = 0.0

    for col in feature_names:
        w_i = (feature_weights[col] / total_shap) * 100.0
        g_r1 = float(individual_gates.loc[mask_r1, col].mean()) if mask_r1.any() else SAFE_GATE_VALUE
        g_r2 = float(individual_gates.loc[mask_r2, col].mean()) if mask_r2.any() else SAFE_GATE_VALUE
        g_r3 = float(individual_gates.loc[mask_r3, col].mean()) if mask_r3.any() else SAFE_GATE_VALUE

        attr_pct = (penalty_values[col] / total_penalty * 100.0) if total_penalty > 0 else w_i

        sum_w += w_i
        sum_r1_weighted += (w_i / 100.0) * g_r1
        sum_r2_weighted += (w_i / 100.0) * g_r2
        sum_r3_weighted += (w_i / 100.0) * g_r3

        attribution_records.append({
            "팩터 명칭 (Feature Name)": col,
            "글로벌 XAI 중요도 비중(w)": f"{w_i:.1f}%",
            "[국면 1] 정상 운용 평균 생존율(g)": f"{g_r1:.4f}",
            "[국면 2] 경미 감쇠 평균 생존율(g)": f"{g_r2:.4f}",
            "[국면 3] 고위험 억제 평균 생존율(g)": f"{g_r3:.4f}",
            "전체 디리스킹 위험 기여율(%)": f"{attr_pct:.1f}%",
        })

    attribution_records.append({
        "팩터 명칭 (Feature Name)": "합계 (Total / Weighted Attribution)",
        "글로벌 XAI 중요도 비중(w)": f"{sum_w:.1f}%",
        "[국면 1] 정상 운용 평균 생존율(g)": f"{sum_r1_weighted:.4f}",
        "[국면 2] 경미 감쇠 평균 생존율(g)": f"{sum_r2_weighted:.4f}",
        "[국면 3] 고위험 억제 평균 생존율(g)": f"{sum_r3_weighted:.4f}",
        "전체 디리스킹 위험 기여율(%)": "100.0%",
    })

    return pd.DataFrame(attribution_records).set_index("팩터 명칭 (Feature Name)")


def _compute_factor_audit_trail(
    configuration: Dict[str, Any],
    risk_distances: pd.DataFrame,
    individual_gates: pd.DataFrame,
) -> pd.DataFrame:
    """8대 팩터별 세부 게이트 감사 및 수리 상태 추적표를 사출합니다."""
    feature_names: List[str] = list(individual_gates.columns)
    total_shap: float = sum(configuration["feature_weights"].values())
    audit_records: List[Dict[str, Any]] = []

    for feature_name in feature_names:
        direction_sign: int = configuration["risk_direction_signs"][feature_name]
        sign_label: str = "하회(-1)" if direction_sign == -1 else "초과(+1)"
        shap_weight_pct: float = (configuration["feature_weights"][feature_name] / total_shap) * 100.0

        mean_distance: float = float(risk_distances[feature_name].mean())
        max_distance: float = float(risk_distances[feature_name].max())
        breach_ratio: float = float((risk_distances[feature_name] > 0.0).mean() * 100.0)

        mean_gate: float = float(individual_gates[feature_name].mean())
        min_gate: float = float(individual_gates[feature_name].min())
        derisk_trigger_ratio: float = float((individual_gates[feature_name] < NORMAL_GATE_THRESHOLD).mean() * 100.0)

        audit_records.append({
            "팩터 명칭 (Feature Name)": feature_name,
            "기준치(θ)": f"{configuration['inflection_thresholds'][feature_name]:.4f}",
            "학습표준편차(σ)": f"{configuration['scale_standard_deviations'][feature_name]:.4f}",
            "방향(s)": sign_label,
            "가중치(w)": f"{shap_weight_pct:.1f}%",
            "평균거리": f"{mean_distance:.4f}",
            "최대침범": f"{max_distance:.4f}",
            "위험진입률": f"{breach_ratio:.1f}%",
            "평균생존율": f"{mean_gate:.4f}",
            "최저생존율": f"{min_gate:.4f}",
            "감쇠발동률": f"{derisk_trigger_ratio:.1f}%",
        })

    return pd.DataFrame(audit_records).set_index("팩터 명칭 (Feature Name)")


def _build_governance_report_bundle(
    configuration: Dict[str, Any],
    composite_gate: pd.Series,
    individual_gates: pd.DataFrame,
    risk_distances: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """3대 감사 대시보드 데이터프레임을 단일 번들 딕셔너리로 패키징합니다."""
    return {
        "gate_summary": _compute_composite_gate_summary(composite_gate),
        "regime_attribution": _compute_regime_factor_attribution(composite_gate, individual_gates, configuration["feature_weights"]),
        "factor_audit_trail": _compute_factor_audit_trail(configuration, risk_distances, individual_gates),
    }