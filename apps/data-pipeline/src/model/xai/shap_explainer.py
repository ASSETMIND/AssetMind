from dataclasses import replace
from typing import Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.dataset.benchmark_provider import (
    detect_market_stress_events,
    fetch_kospi_benchmark_series,
)
from src.model.xai.model_adapter import (
    DEFAULT_RANDOM_STATE,
    predict_model_values,
    prepare_polymorphic_explainer_context,
    resolve_underlying_model,
)
from src.model.xai.policy_analyzer import (
    detect_salient_inflection_features,
    extract_multiple_inflections,
)
from src.model.xai.regime_analyzer import analyze_regime_cohorts
from src.model.xai.shap_calculator import (
    audit_additivity_axiom,
    calculate_global_importance,
    calculate_interaction_values,
    calculate_rolling_shap_dataframe,
    calculate_shap_values,
)
from src.model.xai.shap_schema import (
    DEFAULT_CUMULATIVE_RATIO_THRESHOLD,
    DEFAULT_ROLLING_WINDOW_SIZE,
    InflectionPolicyResult,
    RegimeCohortResult,
    ShapResult,
    create_shap_result,
)


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 배경 데이터셋 표본화 설정
DEFAULT_MAXIMUM_BACKGROUND_SAMPLES: int = 100  # 베이스라인 기댓값 산정용 배경 데이터셋 대표 표본 크기


# ==============================================================================
# Public API Functions
# ==============================================================================
class ShapExplainer:
    """챔피언 회귀 모델 대상 다형성 SHAP 연산, 변곡점 정책 및 시장 국면 감사를 총괄하는 오케스트레이터.

    Attributes:
        maximum_background_samples (int): 배경 데이터셋 구축용 최대 표본 크기.
        random_state (int): 배경 데이터 표본 추출 및 마스커 난수 시드.
        rolling_window_size (int): 시계열 기여도 롤링 이동평균 기본 윈도우 크기.
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
            maximum_background_samples (int): 배경 데이터셋 최대 표본 크기. Defaults to DEFAULT_MAXIMUM_BACKGROUND_SAMPLES.
            random_state (int): 재현성 난수 시드. Defaults to DEFAULT_RANDOM_STATE.
            rolling_window_size (int): 동적 시계열 롤링 윈도우 크기. Defaults to DEFAULT_ROLLING_WINDOW_SIZE.
            max_background_samples (Optional[int]): 하위 호환용 배경 데이터 표본 크기. Defaults to None.
            rolling_window (Optional[int]): 하위 호환용 롤링 윈도우 크기. Defaults to None.
        """
        # 하위 호환 인자 병합 및 오케스트레이터 설정 상태 저장
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
        """학습 및 평가 피처를 수령하여 SHAP 행렬, 2차 교호작용, 변곡점 정책 및 국면 감사 결과를 산출합니다.

        Args:
            model (Any): 학습 완료된 챔피언 회귀 추정기 인스턴스 또는 다형성 래퍼 객체.
            training_features (Optional[pd.DataFrame]): 베이스라인 산정용 학습 피처 행렬. Defaults to None.
            evaluation_features (Optional[pd.DataFrame]): 기여도 및 설명 대상 평가 피처 행렬. Defaults to None.
            evaluation_targets (Optional[pd.Series]): 실측 타깃 시계열 (국면 코호트 감사용). Defaults to None.
            compute_interaction (bool): 2차 교호작용(Interaction) 텐서 연산 집행 여부. Defaults to False.
            model_name (Optional[str]): 모델 식별 명칭 (None 시 클래스/래퍼 속성 추론). Defaults to None.
            benchmark_series (Optional[pd.Series]): 시장 벤치마크 지수 시계열. Defaults to None.
            auto_detect_policy (bool): 리스크 변곡점 정책 자동 분석 여부. Defaults to True.
            auto_detect_events (bool): 시장 스트레스 이벤트 자동 색출 여부. Defaults to True.
            auto_detect_regime (bool): 5대 시장 국면 코호트 감사 자동 집행 여부. Defaults to True.
            cumulative_ratio_threshold (float): 핵심 피처 누적 기여도 임계 비율 (%). Defaults to DEFAULT_CUMULATIVE_RATIO_THRESHOLD.
            X_train (Optional[pd.DataFrame]): 하위 호환용 학습 피처 행렬. Defaults to None.
            X_test (Optional[pd.DataFrame]): 하위 호환용 평가 피처 행렬. Defaults to None.
            y_test (Optional[pd.Series]): 하위 호환용 실측 타깃 시계열. Defaults to None.

        Returns:
            ShapResult: 수리통계적 가산성 공리 검정 및 정책/국면 메타데이터가 캡슐화된 불변 DTO.

        Raises:
            ValueError: 입력 피처 데이터프레임이 유효하지 않거나 컬럼 불일치, 결측치가 존재할 경우 발생.
        """
        # 1. 입력 피처 데이터프레임 병합 및 컬럼 순서/결측치 무결성 검증
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

        # 2. 기저 추정기 식별 및 배경 데이터셋 대표 표본 추출
        underlying_model, resolved_model_name = resolve_underlying_model(
            model=model,
            fallback_name=model_name,
        )
        feature_names = resolved_evaluation_features.columns.tolist()
        evaluation_matrix = resolved_evaluation_features.to_numpy(dtype=np.float64)

        background_indices = _sample_background_indices(
            sample_count=len(resolved_training_features),
            maximum_sample_count=self.maximum_background_samples,
            random_state=self.random_state,
        )
        background_feature_array = resolved_training_features.to_numpy(dtype=np.float64)[
            background_indices
        ]

        # 3. 모델 아키텍처(ML 4종, 2D DL 3종, 3D TCN 1종, Ensemble)별 다형성 Explainer 컨텍스트 준비
        explainer_context = prepare_polymorphic_explainer_context(
            wrapper_model=model,
            underlying_model=underlying_model,
            training_features=resolved_training_features,
            evaluation_features=resolved_evaluation_features,
            background_indices=background_indices,
            background_feature_array=background_feature_array,
            evaluation_matrix=evaluation_matrix,
            feature_names=feature_names,
            random_state=self.random_state,
        )

        # 4. 1차 SHAP 기여도, 원시 예측값, 선택적 2차 교호작용 텐서 및 시계열 롤링 기여도 산출
        shap_values, base_value, shap_explanation = calculate_shap_values(
            explainer=explainer_context.explainer,
            evaluation_matrix=evaluation_matrix,
            feature_names=feature_names,
            explainer_input_matrix=explainer_context.evaluation_input,
        )
        raw_predictions = predict_model_values(
            model=model,
            evaluation_features=resolved_evaluation_features,
        )

        interaction_values: Optional[np.ndarray] = None
        if compute_interaction:
            interaction_values = calculate_interaction_values(
                explainer=explainer_context.explainer,
                evaluation_matrix=evaluation_matrix,
                shap_values=shap_values,
                predict_function=explainer_context.predict_function,
                explainer_evaluation_input=explainer_context.evaluation_input,
                explainer_background_input=explainer_context.background_input,
                is_index_encoded=explainer_context.is_index_encoded,
            )

        rolling_shap_dataframe = calculate_rolling_shap_dataframe(
            shap_values=shap_values,
            feature_names=feature_names,
            evaluation_index=resolved_evaluation_features.index,
            window_size=self.rolling_window_size,
        )

        # 5. 가산성 공리 검정, 전역 중요도 산출 및 시장 벤치마크 컨텍스트 결합 후 1차 ShapResult 생성
        additivity_audit = audit_additivity_axiom(
            shap_values=shap_values,
            base_value=base_value,
            raw_predictions=raw_predictions,
        )
        global_importance_dataframe = calculate_global_importance(
            shap_values=shap_values,
            feature_names=feature_names,
        )

        resolved_targets = evaluation_targets if evaluation_targets is not None else y_test
        resolved_benchmark, resolved_stress_events = _resolve_market_context(
            evaluation_index=resolved_evaluation_features.index,
            target_series=resolved_targets,
            benchmark_series=benchmark_series,
            auto_detect_events=auto_detect_events,
        )

        shap_result = create_shap_result(
            model_name=resolved_model_name,
            feature_names=feature_names,
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
            additivity_audit=additivity_audit,
            global_importance_dataframe=global_importance_dataframe,
        )

        # 6. 리스크 변곡점 정책 및 5대 시장 국면 코호트 감사 수행 후 불변 DTO O(1) 갱신
        inflection_policy_result = _resolve_policy_context(
            shap_result=shap_result,
            evaluation_features=resolved_evaluation_features,
            auto_detect_policy=auto_detect_policy,
            cumulative_ratio_threshold=cumulative_ratio_threshold,
        )
        regime_cohort_result = _resolve_regime_cohort_context(
            target_series=resolved_targets,
            raw_predictions=raw_predictions,
            shap_values=shap_values,
            feature_names=feature_names,
            evaluation_index=resolved_evaluation_features.index,
            auto_detect_regime=auto_detect_regime,
        )

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
    """함수형 패러다임 기반으로 챔피언 모델 설명 및 공리 감사를 즉시 집행하는 공개 진입점 함수.

    Args:
        model (Any): 설명 대상 학습 완료 모델 객체.
        training_features (pd.DataFrame): 베이스라인 산정용 학습 피처.
        evaluation_features (pd.DataFrame): 기여도 산출 대상 평가 피처.
        evaluation_targets (Optional[pd.Series]): 실측 타깃 시계열. Defaults to None.
        compute_interaction (bool): 2차 교호작용 텐서 연산 집행 여부. Defaults to True.
        model_name (Optional[str]): 모델 식별 명칭. Defaults to None.
        maximum_background_samples (int): 배경 데이터셋 표본 수. Defaults to DEFAULT_MAXIMUM_BACKGROUND_SAMPLES.
        random_state (int): 표본 난수 시드. Defaults to DEFAULT_RANDOM_STATE.
        rolling_window_size (int): 롤링 이동평균 윈도우. Defaults to DEFAULT_ROLLING_WINDOW_SIZE.
        auto_detect_regime (bool): 5대 시장 국면 감사 자동 집행 여부. Defaults to True.
        cumulative_ratio_threshold (float): 핵심 피처 누적 기여도 임계 비율 (%). Defaults to DEFAULT_CUMULATIVE_RATIO_THRESHOLD.

    Returns:
        ShapResult: 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.

    Raises:
        ValueError: 학습 및 평가 피처의 차원 불일치 또는 결측치 존재 시 발생.
    """
    # ShapExplainer 인스턴스 초기화 및 통합 설명 파이프라인 실행 위임
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
    # 기본 입력을 우선 선택하되 부재 시 하위 호환(X_train, X_test) 인자 적용
    resolved_training = primary_training if primary_training is not None else fallback_training
    resolved_evaluation = (
        primary_evaluation if primary_evaluation is not None else fallback_evaluation
    )

    if resolved_training is None or resolved_evaluation is None:
        raise ValueError("[_resolve_feature_dataframes] 학습 피처와 평가 피처는 필수 입력입니다.")

    return resolved_training, resolved_evaluation


def _validate_feature_consistency(
    training_features: pd.DataFrame,
    evaluation_features: pd.DataFrame,
) -> None:
    """학습 및 평가 피처 데이터셋의 컬럼 순서 일관성과 결측치 부재를 검증합니다."""
    # 1. 학습 및 평가 데이터프레임 간 컬럼 명단 및 순서 일치 확인
    if list(training_features.columns) != list(evaluation_features.columns):
        raise ValueError(
            "[_validate_feature_consistency] 학습 피처와 평가 피처의 컬럼 명단 및 순서가 일치하지 않습니다."
        )

    # 2. 피처 행렬 내부 NaN 결측치 존재 여부 확인
    if training_features.isna().any().any() or evaluation_features.isna().any().any():
        raise ValueError(
            "[_validate_feature_consistency] 피처 행렬 내부에 결측치(NaN)가 존재합니다."
        )


def _sample_background_indices(
    sample_count: int,
    maximum_sample_count: int,
    random_state: int,
) -> np.ndarray:
    """배경 데이터셋 추출을 위한 정수 위치 인덱스 배열을 난수 시드 기반으로 생성합니다."""
    # 전체 표본 수가 최대 허용치 이하이면 전수 인덱스 반환, 초과 시 비복원 무작위 추출
    if sample_count <= maximum_sample_count:
        return np.arange(sample_count, dtype=np.int64)

    index_series = pd.Series(np.arange(sample_count, dtype=np.int64))
    sampled_indices = index_series.sample(
        n=maximum_sample_count,
        random_state=random_state,
        replace=False,
    ).to_numpy(dtype=np.int64)
    return sampled_indices


def _resolve_market_context(
    evaluation_index: pd.Index,
    target_series: Optional[pd.Series],
    benchmark_series: Optional[pd.Series],
    auto_detect_events: bool,
) -> Tuple[Optional[pd.Series], Optional[List[Tuple[str, str]]]]:
    """시장 벤치마크 지수를 안전하게 수집하고 극단 국면 스트레스 이벤트를 자동 색출합니다."""
    # 이벤트 자동 탐지 비활성화 시 주입된 벤치마크만 그대로 반환
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
    """누적 기여도 임계치 기반 핵심 피처 자동 색출 및 리스크 변곡점 정책을 수립합니다."""
    # 정책 자동 분석 플래그 확인 후 핵심 피처 선별 및 다중 변곡점 추출 위임
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
    # 국면 감사 활성화 여부 및 타깃 시계열 존재 확인 후 국면 분석 모듈에 위임
    if not auto_detect_regime or target_series is None:
        return None

    prediction_series = pd.Series(raw_predictions, index=evaluation_index)
    shap_dataframe = pd.DataFrame(shap_values, index=evaluation_index, columns=feature_names)

    return analyze_regime_cohorts(
        y_true=target_series,
        y_pred=prediction_series,
        shap_df=shap_dataframe,
    )