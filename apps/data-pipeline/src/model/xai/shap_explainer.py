from typing import Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import shap
from dataclasses import replace

from src.dataset.benchmark_provider import (
    detect_market_stress_events,
    fetch_kospi_benchmark_series,
)
from src.model.xai.policy_analyzer import (
    analyze_regime_cohorts,
    detect_salient_inflection_features,
    extract_multiple_inflections,
)
from src.model.xai.shap_schema import (
    InflectionPolicyResult,
    RegimeCohortResult,
    ShapResult,
    create_shap_result,
)


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 배경 데이터셋 표본화 설정
DEFAULT_MAXIMUM_BACKGROUND_SAMPLES: int = 100    # 베이스라인 기댓값 산정용 배경 데이터셋 대표 표본 크기
DEFAULT_RANDOM_STATE: int = 42                   # 표본 무작위 추출 및 결과 재현성 보장을 위한 난수 시드

# 시계열 롤링 이동평균 설정
DEFAULT_ROLLING_WINDOW_SIZE: int = 20            # 동적 시계열 XAI 롤링 평균 산출 기본 윈도우 (20영업일)

# 리스크 변곡점 정책 설정
DEFAULT_CUMULATIVE_RATIO_THRESHOLD: float = 90.0  # 파레토 법칙 기반 핵심 피처 선별 누적 기여도 임계치 (%)


# ==============================================================================
# Public API Functions
# ==============================================================================
class ShapExplainer:
    """챔피언 머신러닝 회귀 모델 대상 TreeSHAP/LinearSHAP 연산 및 시계열 기여도 전이 해석기.

    Attributes:
        maximum_background_samples (int): 배경 데이터셋 구축용 최대 표본 크기.
        random_state (int): 배경 데이터 표본 추출 난수 시드.
        rolling_window_size (int): 시계열 기여도 롤링 평균 기본 윈도우.
    """

    def __init__(
        self,
        maximum_background_samples: int = DEFAULT_MAXIMUM_BACKGROUND_SAMPLES,
        random_state: int = DEFAULT_RANDOM_STATE,
        rolling_window_size: int = DEFAULT_ROLLING_WINDOW_SIZE,
        max_background_samples: Optional[int] = None,
        rolling_window: Optional[int] = None,
    ) -> None:
        """ShapExplainer 인스턴스를 초기화합니다.

        Args:
            maximum_background_samples (int): 배경 데이터셋 최대 표본 크기. Defaults to 100.
            random_state (int): 재현성 난수 시드. Defaults to 42.
            rolling_window_size (int): 동적 시계열 롤링 윈도우 크기. Defaults to 20.
            max_background_samples (Optional[int]): 하위 호환용 배경 데이터 표본 크기. Defaults to None.
            rolling_window (Optional[int]): 하위 호환용 롤링 윈도우 크기. Defaults to None.
        """
        self.maximum_background_samples: int = max_background_samples or maximum_background_samples
        self.random_state: int = random_state
        self.rolling_window_size: int = rolling_window or rolling_window_size

    def explain(
        self,
        model: Any,
        training_features: Optional[pd.DataFrame] = None,
        evaluation_features: Optional[pd.DataFrame] = None,
        evaluation_targets: Optional[pd.Series] = None,
        compute_interaction: bool = False,
        model_name: Optional[str] = None,
        benchmark_series: Optional[pd.Series] = None,
        auto_detect_policy: bool = True,
        auto_detect_events: bool = True,
        auto_detect_regime: bool = True,
        cumulative_ratio_threshold: float = DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
        X_train: Optional[pd.DataFrame] = None,
        X_test: Optional[pd.DataFrame] = None,
        y_test: Optional[pd.Series] = None,
    ) -> ShapResult:
        """학습 및 평가 피처를 수령하여 SHAP 행렬, 2차 교호작용 및 롤링 기여도를 산출합니다.

        Args:
            model (Any): 학습 완료된 챔피언 회귀 추정기 인스턴스 또는 다형성 래퍼 객체.
            training_features (Optional[pd.DataFrame]): 베이스라인 산정용 학습 피처 행렬.
            evaluation_features (Optional[pd.DataFrame]): 기여도 및 설명 대상 평가 피처 행렬.
            evaluation_targets (Optional[pd.Series]): 실측 타깃 시계열 (국면 코호트 감사용). Defaults to None.
            compute_interaction (bool): 2차 교호작용(Interaction) 텐서 연산 집행 여부. Defaults to False.
            model_name (Optional[str]): 모델 식별 명칭 (None 시 클래스/래퍼 속성 추론). Defaults to None.
            benchmark_series (Optional[pd.Series]): 시장 벤치마크 지수 시계열. Defaults to None.
            auto_detect_policy (bool): 리스크 변곡점 정책 자동 분석 여부. Defaults to True.
            auto_detect_events (bool): 시장 스트레스 이벤트 자동 색출 여부. Defaults to True.
            auto_detect_regime (bool): 5대 시장 국면 코호트 감사 자동 집행 여부. Defaults to True.
            cumulative_ratio_threshold (float): 핵심 피처 누적 기여도 임계 비율 (%). Defaults to 90.0.
            X_train (Optional[pd.DataFrame]): 하위 호환용 학습 피처 행렬. Defaults to None.
            X_test (Optional[pd.DataFrame]): 하위 호환용 평가 피처 행렬. Defaults to None.
            y_test (Optional[pd.Series]): 하위 호환용 실측 타깃 시계열. Defaults to None.

        Returns:
            ShapResult: 수리통계적 가산성 공리 검정 및 시계열 메타데이터가 캡슐화된 불변 DTO.

        Raises:
            ValueError: 입력 피처 데이터프레임이 유효하지 않거나 컬럼 불일치, 결측치가 존재할 경우 발생.
        """
        resolved_training_features, resolved_evaluation_features = _resolve_feature_dataframes(
            primary_training=training_features,
            primary_evaluation=evaluation_features,
            fallback_training=X_train,
            fallback_evaluation=X_test,
        )

        _validate_feature_consistency(
            training_features=resolved_training_features,
            evaluation_features=resolved_evaluation_features,
        )

        underlying_model, resolved_model_name = _resolve_underlying_model(
            model=model,
            fallback_name=model_name,
        )

        background_feature_array = _sample_background_features(
            feature_dataframe=resolved_training_features,
            maximum_sample_count=self.maximum_background_samples,
            random_state=self.random_state,
        )

        explainer = _build_shap_explainer(
            model=underlying_model,
            background_data=background_feature_array,
        )

        shap_values, base_value, shap_explanation = _calculate_shap_values(
            explainer=explainer,
            evaluation_matrix=resolved_evaluation_features.to_numpy(dtype=np.float64),
            feature_names=resolved_evaluation_features.columns.tolist(),
        )

        raw_predictions = _predict_model_values(
            model=model,
            evaluation_features=resolved_evaluation_features,
        )

        interaction_values: Optional[np.ndarray] = None
        if compute_interaction:
            interaction_values = _calculate_interaction_values(
                explainer=explainer,
                evaluation_matrix=resolved_evaluation_features.to_numpy(dtype=np.float64),
            )

        rolling_shap_dataframe = _calculate_rolling_shap_dataframe(
            shap_values=shap_values,
            feature_names=resolved_evaluation_features.columns.tolist(),
            evaluation_index=resolved_evaluation_features.index,
            window_size=self.rolling_window_size,
        )

        resolved_targets: Optional[pd.Series] = evaluation_targets if evaluation_targets is not None else y_test

        resolved_benchmark, resolved_stress_events = _resolve_market_context(
            evaluation_index=resolved_evaluation_features.index,
            target_series=resolved_targets,
            benchmark_series=benchmark_series,
            auto_detect_events=auto_detect_events,
        )

        # 1차 완성 DTO 팩토리 호출 (가산성 공리 검정 및 글로벌 중요도 연산 수행)
        shap_result = create_shap_result(
            model_name=resolved_model_name,
            feature_names=resolved_evaluation_features.columns.tolist(),
            evaluation_index=resolved_evaluation_features.index,
            shap_values=shap_values,
            base_value=base_value,
            raw_predictions=raw_predictions,
            shap_explanation=shap_explanation,
            background_samples_count=len(background_feature_array),
            interaction_values=interaction_values,
            rolling_shap_dataframe=rolling_shap_dataframe,
            benchmark_series=resolved_benchmark,
            stress_events=resolved_stress_events,
        )

        # [설계 의도] 산출된 SHAP 수치로부터 누적 90% 기반 리스크 변곡점 정책을 내부에서 원스톱으로 자동 분석
        inflection_policy_result = _resolve_policy_context(
            shap_result=shap_result,
            evaluation_features=resolved_evaluation_features,
            auto_detect_policy=auto_detect_policy,
            cumulative_ratio_threshold=cumulative_ratio_threshold,
        )

        # [설계 의도] 실측 타깃과 모델 예측값을 결합하여 5대 시장 국면별 코호트 감사를 원스톱으로 자동 분석
        regime_cohort_result = _resolve_regime_cohort_context(
            target_series=resolved_targets,
            raw_predictions=raw_predictions,
            shap_values=shap_values,
            feature_names=resolved_evaluation_features.columns.tolist(),
            evaluation_index=resolved_evaluation_features.index,
            auto_detect_regime=auto_detect_regime,
        )

        # [설계 의도] 불필요한 DTO 재검증(중복 가산성 검정 및 중요도 연산)을 방지하고, dataclasses.replace를 통해 O(1)로 불변 갱신
        if inflection_policy_result is not None or regime_cohort_result is not None:
            return replace(
                shap_result,
                inflection_policy_result=inflection_policy_result,
                regime_cohort_result=regime_cohort_result,
            )

        return shap_result


def explain_champion_model(
    model: Any,
    training_features: pd.DataFrame,
    evaluation_features: pd.DataFrame,
    evaluation_targets: Optional[pd.Series] = None,
    compute_interaction: bool = True,
    model_name: Optional[str] = None,
    maximum_background_samples: int = DEFAULT_MAXIMUM_BACKGROUND_SAMPLES,
    random_state: int = DEFAULT_RANDOM_STATE,
    rolling_window_size: int = DEFAULT_ROLLING_WINDOW_SIZE,
    auto_detect_regime: bool = True,
    cumulative_ratio_threshold: float = DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
) -> ShapResult:
    """함수형 패러다임 기반으로 모델 설명 및 공리 감사를 즉시 집행하는 공개 함수.

    Args:
        model (Any): 설명 대상 학습 완료 모델 객체.
        training_features (pd.DataFrame): 베이스라인 산정용 학습 피처.
        evaluation_features (pd.DataFrame): 기여도 산출 대상 평가 피처.
        evaluation_targets (Optional[pd.Series]): 실측 타깃 시계열. Defaults to None.
        compute_interaction (bool): 2차 교호작용 텐서 연산 집행 여부. Defaults to True.
        model_name (Optional[str]): 모델 식별 명칭. Defaults to None.
        maximum_background_samples (int): 배경 데이터셋 표본 수. Defaults to 100.
        random_state (int): 표본 난수 시드. Defaults to 42.
        rolling_window_size (int): 롤링 이동평균 윈도우. Defaults to 20.
        auto_detect_regime (bool): 5대 시장 국면 감사 자동 집행 여부. Defaults to True.
        cumulative_ratio_threshold (float): 핵심 피처 누적 기여도 임계 비율 (%). Defaults to 90.0.

    Returns:
        ShapResult: 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
    """
    explainer = ShapExplainer(
        maximum_background_samples=maximum_background_samples,
        random_state=random_state,
        rolling_window_size=rolling_window_size,
    )
    return explainer.explain(
        model=model,
        training_features=training_features,
        evaluation_features=evaluation_features,
        evaluation_targets=evaluation_targets,
        compute_interaction=compute_interaction,
        model_name=model_name,
        auto_detect_regime=auto_detect_regime,
        cumulative_ratio_threshold=cumulative_ratio_threshold,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _resolve_feature_dataframes(
    primary_training: Optional[pd.DataFrame],
    primary_evaluation: Optional[pd.DataFrame],
    fallback_training: Optional[pd.DataFrame],
    fallback_evaluation: Optional[pd.DataFrame],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """학습 및 평가 피처 입력의 기본값 및 하위 호환 매개변수를 안전하게 병합합니다."""
    resolved_training = primary_training if primary_training is not None else fallback_training
    resolved_evaluation = primary_evaluation if primary_evaluation is not None else fallback_evaluation

    if resolved_training is None or resolved_evaluation is None:
        raise ValueError("[_resolve_feature_dataframes] 학습 피처와 평가 피처는 필수 입력입니다.")

    return resolved_training, resolved_evaluation


def _validate_feature_consistency(
    training_features: pd.DataFrame,
    evaluation_features: pd.DataFrame,
) -> None:
    """학습 및 평가 피처 데이터셋의 컬럼 순서 일관성과 결측치 부재를 검증합니다."""
    if list(training_features.columns) != list(evaluation_features.columns):
        raise ValueError("[_validate_feature_consistency] 학습 피처와 평가 피처의 컬럼 명단 및 순서가 일치하지 않습니다.")

    if training_features.isna().any().any() or evaluation_features.isna().any().any():
        raise ValueError("[_validate_feature_consistency] 피처 행렬 내부에 결측치(NaN)가 존재합니다.")


def _resolve_underlying_model(
    model: Any,
    fallback_name: Optional[str],
) -> Tuple[Any, str]:
    """다형성 래퍼 객체로부터 핵심 추정기 인스턴스와 식별 명칭을 추출합니다."""
    underlying_model = getattr(model, "_model", getattr(model, "model", model))

    if fallback_name is not None and len(fallback_name.strip()) > 0:
        resolved_name = fallback_name
    elif hasattr(model, "model_name") and isinstance(getattr(model, "model_name"), str):
        resolved_name = getattr(model, "model_name")
    elif hasattr(model, "name") and isinstance(getattr(model, "name"), str):
        resolved_name = getattr(model, "name")
    else:
        resolved_name = underlying_model.__class__.__name__

    return underlying_model, resolved_name


def _sample_background_features(
    feature_dataframe: pd.DataFrame,
    maximum_sample_count: int,
    random_state: int,
) -> np.ndarray:
    """베이스라인 산정용 배경 데이터셋의 대표 표본을 난수 통제 기반으로 추출합니다."""
    if len(feature_dataframe) <= maximum_sample_count:
        return feature_dataframe.to_numpy(dtype=np.float64)

    sampled_dataframe = feature_dataframe.sample(
        n=maximum_sample_count,
        random_state=random_state,
        replace=False,
    )
    return sampled_dataframe.to_numpy(dtype=np.float64)


def _build_shap_explainer(
    model: Any,
    background_data: np.ndarray,
) -> shap.Explainer:
    """모델 유형(트리 앙상블, 선형 회귀, 일반 모델)에 최적화된 SHAP Explainer를 생성합니다."""
    tree_type_names = (
        "XGB",
        "RandomForest",
        "LGBM",
        "CatBoost",
        "DecisionTree",
        "GradientBoosting",
        "Booster",
    )
    model_class_name = model.__class__.__name__

    # [설계 의도] 트리 앙상블은 tree_path_dependent 모드로 생성하여 고속 연산 및 분기 정합성 확보
    if any(tree_name in model_class_name for tree_name in tree_type_names):
        explainer = shap.TreeExplainer(model=model, feature_perturbation="tree_path_dependent")
        _sanitize_tree_explainer_categorical(explainer=explainer)
        return explainer

    if any(linear_name in model_class_name for linear_name in ("ElasticNet", "Ridge", "Lasso")):
        return shap.LinearExplainer(model=model, masker=background_data)

    return shap.Explainer(model=model, masker=background_data)


def _sanitize_tree_explainer_categorical(explainer: Any) -> None:
    """수치형 데이터셋 대상 XGBoost TreeEnsemble의 잘못된 범주형 플래그를 정제합니다."""
    tree_ensemble = getattr(explainer, "model", None)
    if tree_ensemble is not None:
        if getattr(tree_ensemble, "cat_feature_indices", None) is not None:
            tree_ensemble.cat_feature_indices = None
        if getattr(tree_ensemble, "_xgb_enable_categorical", False):
            tree_ensemble._xgb_enable_categorical = False


def _calculate_shap_values(
    explainer: Any,
    evaluation_matrix: np.ndarray,
    feature_names: List[str],
) -> Tuple[np.ndarray, float, Any]:
    """SHAP Explainer를 통해 기여도 행렬과 기준 기댓값을 산출합니다."""
    explanation = explainer(evaluation_matrix)

    # 1. 원시 SHAP 기여도 행렬 추출
    if hasattr(explanation, "values"):
        shap_values = np.asarray(explanation.values, dtype=np.float64)
    else:
        shap_values = np.asarray(explainer.shap_values(evaluation_matrix), dtype=np.float64)

    # 2. 기댓값(Base Value) 스칼라 변환
    if hasattr(explanation, "base_values"):
        base_values = np.asarray(explanation.base_values, dtype=np.float64)
        base_value = float(np.mean(base_values))
    elif hasattr(explainer, "expected_value"):
        expected_value = explainer.expected_value
        base_value = float(expected_value[0]) if isinstance(expected_value, (list, np.ndarray)) else float(expected_value)
    else:
        base_value = 0.0

    # 3. Explanation 객체 메타데이터 정합성 보정
    if hasattr(explanation, "feature_names") and explanation.feature_names is None:
        explanation.feature_names = feature_names

    return shap_values, base_value, explanation


def _calculate_interaction_values(
    explainer: Any,
    evaluation_matrix: np.ndarray,
) -> Optional[np.ndarray]:
    """TreeExplainer의 2차 교호작용(Interaction) 텐서를 연산합니다."""
    if hasattr(explainer, "shap_interaction_values"):
        interaction_tensor = explainer.shap_interaction_values(evaluation_matrix)
        return np.asarray(interaction_tensor, dtype=np.float64)
    return None


def _calculate_rolling_shap_dataframe(
    shap_values: np.ndarray,
    feature_names: List[str],
    evaluation_index: pd.Index,
    window_size: int,
) -> pd.DataFrame:
    """시계열 날짜 인덱스를 기준으로 각 피처의 SHAP 기여도 롤링 이동평균을 산출합니다."""
    raw_shap_dataframe = pd.DataFrame(shap_values, index=evaluation_index, columns=feature_names)
    rolling_shap_dataframe = raw_shap_dataframe.rolling(window=window_size, min_periods=1).mean()
    return rolling_shap_dataframe


def _predict_model_values(
    model: Any,
    evaluation_features: pd.DataFrame,
) -> np.ndarray:
    """챔피언 모델 다형성 인터페이스를 일원화하여 평가 데이터의 실제 예측값 벡터를 추출합니다."""
    if hasattr(model, "predict"):
        prediction_values = model.predict(evaluation_features)
    elif hasattr(model, "predict_raw"):
        prediction_values = model.predict_raw(evaluation_features)
    else:
        raise ValueError("[_predict_model_values] 전달된 모델 객체에 predict 인터페이스가 존재하지 않습니다.")

    if isinstance(prediction_values, (pd.Series, pd.DataFrame)):
        prediction_values = prediction_values.to_numpy()

    return np.asarray(prediction_values, dtype=np.float64).flatten()


def _resolve_market_context(
    evaluation_index: pd.Index,
    target_series: Optional[pd.Series],
    benchmark_series: Optional[pd.Series],
    auto_detect_events: bool,
) -> Tuple[Optional[pd.Series], Optional[List[Tuple[str, str]]]]:
    """시장 벤치마크 지수를 안전하게 수집하고 3대 극단 국면 이벤트를 자동 색출합니다."""
    if not auto_detect_events:
        return benchmark_series, None

    resolved_benchmark: Optional[pd.Series] = benchmark_series
    if resolved_benchmark is None:
        try:
            resolved_benchmark = fetch_kospi_benchmark_series(evaluation_index=evaluation_index)
        except Exception:
            resolved_benchmark = None

    stress_events: Optional[List[Tuple[str, str]]] = None
    if resolved_benchmark is not None:
        stress_events = detect_market_stress_events(
            benchmark_series=resolved_benchmark,
            target_series=target_series,
        )

    return resolved_benchmark, stress_events


def _resolve_policy_context(
    shap_result: ShapResult,
    evaluation_features: pd.DataFrame,
    auto_detect_policy: bool,
    cumulative_ratio_threshold: float = DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
) -> Optional[InflectionPolicyResult]:
    """누적 기여도 임계치(90%) 기반 핵심 피처 자동 색출 및 변곡점 정책을 수립합니다."""
    if not auto_detect_policy:
        return None

    salient_features = detect_salient_inflection_features(
        shap_result=shap_result,
        evaluation_features=evaluation_features,
        top_k=None,
        cumulative_ratio_threshold=cumulative_ratio_threshold,
    )

    return extract_multiple_inflections(
        shap_result=shap_result,
        target_features=salient_features,
        evaluation_features=evaluation_features,
    )


def _resolve_regime_cohort_context(
    target_series: Optional[pd.Series],
    raw_predictions: np.ndarray,
    shap_values: np.ndarray,
    feature_names: List[str],
    evaluation_index: pd.Index,
    auto_detect_regime: bool,
) -> Optional[RegimeCohortResult]:
    """실측 타깃과 모델 예측값을 바탕으로 5대 시장 국면 코호트 감사를 수행합니다."""
    if not auto_detect_regime or target_series is None:
        return None

    prediction_series = pd.Series(raw_predictions, index=evaluation_index)
    shap_dataframe = pd.DataFrame(shap_values, index=evaluation_index, columns=feature_names)

    return analyze_regime_cohorts(
        y_true=target_series,
        y_pred=prediction_series,
        shap_df=shap_dataframe,
    )