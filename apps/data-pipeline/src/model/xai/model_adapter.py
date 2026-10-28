from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, List, Optional, Tuple
import numpy as np
import pandas as pd
import shap
import torch


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 재현성 및 트리 Explainer 기본 설정
DEFAULT_RANDOM_STATE: int = 42                                     # 마스커 및 Explainer 초기화용 기본 난수 시드
DEFAULT_TREE_FEATURE_PERTURBATION: str = "tree_path_dependent"     # 트리 모델 SHAP 경로 의존적 섭동 방식

# 프로젝트 사용 머신러닝 모델(4종) 판별 키워드 설정
TREE_MODEL_CLASS_KEYWORDS: Tuple[str, ...] = (                     # TreeExplainer 라우팅 대상 트리 모델(3종) 클래스 키워드
    "RandomForest",
    "XGB",
    "CatBoost",
)
LINEAR_MODEL_CLASS_KEYWORDS: Tuple[str, ...] = (                   # LinearExplainer 라우팅 대상 선형 모델(1종) 클래스 키워드
    "ElasticNet",
)

# 딥러닝 모델(2D 3종: TabularResNet, DCNv2, FT-Transformer / 3D 1종: TCN) 텐서 프로빙 설정
SEQUENCE_PROBE_SAMPLE_COUNT: int = 2                               # 3D 시퀀스 텐서(TCN) 변환 여부 판별용 최소 프로브 표본 수
SEQUENCE_3D_TENSOR_NDIM: int = 3                                   # TCN 모델 내부 입력 텐서 차원 수 (N, P, L)


# ==============================================================================
# Public API Functions
# ==============================================================================
@dataclass(frozen=True)
class PolymorphicExplainerContext:
    """다형성 모델별 최적화된 SHAP Explainer 및 입출력 추론 컨텍스트를 캡슐화한 불변 DTO.

    Attributes:
        explainer (Any): 모델 아키텍처에 맞게 초기화된 SHAP Explainer 인스턴스.
        evaluation_input (np.ndarray): Explainer에 투입할 평가 입력 행렬 (원시 행렬 또는 TCN 3D 매핑 인덱스).
        background_input (np.ndarray): Explainer 마스킹에 사용된 배경 입력 행렬.
        predict_function (Callable[[np.ndarray], np.ndarray]): 배치 입력 행렬을 받아 1D 예측값을 반환하는 추론 함수.
        is_index_encoded (bool): TCN 3D 인과 윈도우 보존을 위한 정수 위치 인덱스 인코딩 적용 여부.
    """

    explainer: Any
    evaluation_input: np.ndarray
    background_input: np.ndarray
    predict_function: Callable[[np.ndarray], np.ndarray]
    is_index_encoded: bool

    def __iter__(self) -> Iterator[Any]:
        """기존 튜플 언패킹 인터페이스와의 하위 호환성을 위한 이터레이터를 제공합니다."""
        yield self.explainer
        yield self.evaluation_input
        yield self.background_input
        yield self.predict_function
        yield self.is_index_encoded


def resolve_underlying_model(
    model: Any,
    fallback_name: Optional[str] = None,
) -> Tuple[Any, str]:
    """다형성 래퍼 객체로부터 내부 핵심 추정기 인스턴스와 모델 식별 명칭을 추출합니다.

    Args:
        model (Any): 챔피언 회귀 추정기 인스턴스 또는 다형성 래퍼 객체.
        fallback_name (Optional[str]): 외부에서 지정한 모델 식별 명칭. Defaults to None.

    Returns:
        Tuple[Any, str]: 언래핑된 내부 추정기 객체와 확정된 모델 식별 명칭.
    """
    # 1. 래퍼 객체 내부의 실제 추정기 인스턴스 추출
    underlying_model = _extract_wrapped_estimator(model=model)

    # 2. 우선순위(외부 주입 -> 모델 속성 -> 클래스명)에 따른 모델 명칭 확정
    resolved_model_name = _resolve_model_display_name(
        wrapper_model=model,
        underlying_model=underlying_model,
        fallback_name=fallback_name,
    )

    return underlying_model, resolved_model_name


def predict_model_values(
    model: Any,
    evaluation_features: pd.DataFrame,
) -> np.ndarray:
    """챔피언 모델의 다형성 추론 인터페이스를 일원화하여 평가 데이터의 1차원 예측값 벡터를 산출합니다.

    Args:
        model (Any): 예측을 수행할 학습 완료 모델 또는 래퍼 객체.
        evaluation_features (pd.DataFrame): 추론 대상 평가 피처 데이터프레임.

    Returns:
        np.ndarray: (N,) 차원으로 평탄화된 실수형 원시 예측값 배열.

    Raises:
        ValueError: 전달된 모델 객체에 유효한 추론 메서드(predict 또는 predict_raw)가 없을 경우 발생.
    """
    # 1. 모델 추론 인터페이스 호출 및 원시 예측 결과 획득
    raw_predictions = _invoke_model_prediction(
        model=model,
        evaluation_features=evaluation_features,
    )

    # 2. 1차원 실수형 NumPy 배열로 정규화하여 반환
    return _normalize_prediction_array(raw_predictions=raw_predictions)


def prepare_polymorphic_explainer_context(
    wrapper_model: Any,
    underlying_model: Any,
    training_features: pd.DataFrame,
    evaluation_features: pd.DataFrame,
    background_indices: np.ndarray,
    background_feature_array: np.ndarray,
    evaluation_matrix: np.ndarray,
    feature_names: List[str],
    random_state: int = DEFAULT_RANDOM_STATE,
) -> PolymorphicExplainerContext:
    """8종 단일 모델(ML 4종, 2D DL 3종, 3D TCN 1종) 및 앙상블을 판별하여 최적 Explainer 컨텍스트를 생성합니다.

    Args:
        wrapper_model (Any): 최상위 모델 래퍼 객체 (DL 추론 루프 또는 앙상블 객체 포함).
        underlying_model (Any): 언래핑된 내부 추정기 인스턴스.
        training_features (pd.DataFrame): 학습 피처 데이터프레임 (TCN 3D 텐서 윈도우 구성용).
        evaluation_features (pd.DataFrame): 평가 피처 데이터프레임.
        background_indices (np.ndarray): 배경 표본 추출용 정수 위치 인덱스 배열.
        background_feature_array (np.ndarray): 추출된 2D 배경 피처 배열.
        evaluation_matrix (np.ndarray): 2D 평가 피처 행렬.
        feature_names (List[str]): 피처 컬럼 명칭 리스트.
        random_state (int): 마스커 및 샘플링 재현성 난수 시드. Defaults to DEFAULT_RANDOM_STATE.

    Returns:
        PolymorphicExplainerContext: 초기화된 Explainer, 입출력 행렬 및 추론 함수가 담긴 불변 컨텍스트.
    """
    # 1. 트리 기반 머신러닝 패밀리 (RandomForest, XGBoost, CatBoost)
    if _is_tree_based_model(underlying_model=underlying_model):
        return _build_tree_explainer_context(
            wrapper_model=wrapper_model,
            underlying_model=underlying_model,
            evaluation_matrix=evaluation_matrix,
            background_feature_array=background_feature_array,
            feature_names=feature_names,
        )

    # 2. 선형 회귀 머신러닝 패밀리 (ElasticNet)
    if _is_linear_based_model(underlying_model=underlying_model):
        return _build_linear_explainer_context(
            wrapper_model=wrapper_model,
            underlying_model=underlying_model,
            evaluation_matrix=evaluation_matrix,
            background_feature_array=background_feature_array,
            feature_names=feature_names,
        )

    # 3. 3D 시계열 딥러닝 패밀리 (TCN: 내부 2D -> 3D Causal Windowing 변환 모델)
    if _is_sequence_3d_deep_learning_model(model=wrapper_model, sample_features=training_features):
        return _build_3d_sequence_explainer_context(
            wrapper_model=wrapper_model,
            training_features=training_features,
            evaluation_features=evaluation_features,
            background_indices=background_indices,
            feature_names=feature_names,
            random_state=random_state,
        )

    # 4. 2D 정형 딥러닝 패밀리 (TabularResNet, DCNv2, FT-Transformer)
    if _is_deep_learning_regressor(model=wrapper_model):
        return _build_2d_deep_learning_explainer_context(
            wrapper_model=wrapper_model,
            evaluation_matrix=evaluation_matrix,
            background_feature_array=background_feature_array,
            random_state=random_state,
        )

    # 5. 내부에 3D TCN 서브 모델을 포함한 하이브리드 메타 앙상블 패밀리
    nested_3d_models = _collect_nested_3d_deep_learning_models(
        model=wrapper_model,
        sample_features=training_features,
    )
    if nested_3d_models:
        return _build_hybrid_ensemble_explainer_context(
            wrapper_model=wrapper_model,
            nested_3d_models=nested_3d_models,
            training_features=training_features,
            evaluation_features=evaluation_features,
            background_indices=background_indices,
            background_feature_array=background_feature_array,
            evaluation_matrix=evaluation_matrix,
            feature_names=feature_names,
            random_state=random_state,
        )

    # 6. 2D 모델들로만 구성된 일반 메타 앙상블 모델
    return _build_general_explainer_context(
        wrapper_model=wrapper_model,
        evaluation_matrix=evaluation_matrix,
        background_feature_array=background_feature_array,
        feature_names=feature_names,
        random_state=random_state,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _extract_wrapped_estimator(model: Any) -> Any:
    """래퍼 객체에서 _model 또는 model 속성을 탐색하여 기저 추정기를 반환합니다."""
    # 내부 추정기 속성 존재 여부 순차 확인
    raw_underlying = getattr(model, "_model", None)
    if raw_underlying is None:
        raw_underlying = getattr(model, "model", None)
    return raw_underlying if raw_underlying is not None else model


def _resolve_model_display_name(
    wrapper_model: Any,
    underlying_model: Any,
    fallback_name: Optional[str],
) -> str:
    """외부 지정 명칭, 래퍼 속성, 클래스 이름 순으로 모델 식별 명칭을 결정합니다."""
    # 유효한 문자열 명칭 탐색 및 반환
    if fallback_name is not None and len(fallback_name.strip()) > 0:
        return fallback_name
    if hasattr(wrapper_model, "model_name") and isinstance(getattr(wrapper_model, "model_name"), str):
        return getattr(wrapper_model, "model_name")
    if hasattr(wrapper_model, "name") and isinstance(getattr(wrapper_model, "name"), str):
        return getattr(wrapper_model, "name")
    return underlying_model.__class__.__name__


def _invoke_model_prediction(
    model: Any,
    evaluation_features: pd.DataFrame,
) -> Any:
    """모델 객체의 predict 또는 predict_raw 인터페이스를 호출합니다."""
    # 표준 추론 메서드 유무 검증 및 실행
    if hasattr(model, "predict"):
        return model.predict(evaluation_features)
    if hasattr(model, "predict_raw"):
        return model.predict_raw(evaluation_features)
    raise ValueError("[_invoke_model_prediction] 전달된 모델 객체에 predict 인터페이스가 존재하지 않습니다.")


def _normalize_prediction_array(raw_predictions: Any) -> np.ndarray:
    """추론 결과 객체를 1차원 float64 NumPy 배열로 변환합니다."""
    # Pandas 객체를 배열로 추출 후 1차원 벡터로 평탄화
    if isinstance(raw_predictions, (pd.Series, pd.DataFrame)):
        raw_predictions = raw_predictions.to_numpy()
    return np.asarray(raw_predictions, dtype=np.float64).flatten()


def _is_tree_based_model(underlying_model: Any) -> bool:
    """기저 추정기가 프로젝트 트리 모델(RandomForest, XGBoost, CatBoost)인지 판별합니다."""
    # 클래스 명칭 내 트리 모델 키워드 포함 여부 확인
    model_class_name = underlying_model.__class__.__name__
    return any(keyword in model_class_name for keyword in TREE_MODEL_CLASS_KEYWORDS)


def _is_linear_based_model(underlying_model: Any) -> bool:
    """기저 추정기가 프로젝트 선형 회귀 모델(ElasticNet)인지 판별합니다."""
    # 클래스 명칭 내 선형 모델 키워드 포함 여부 확인
    model_class_name = underlying_model.__class__.__name__
    return any(keyword in model_class_name for keyword in LINEAR_MODEL_CLASS_KEYWORDS)


def _is_deep_learning_regressor(model: Any) -> bool:
    """전달된 객체가 PyTorch 기반 AbstractDLRegressor 계열(TabularResNet, DCNv2, FT-Transformer, TCN)인지 판별합니다."""
    # 딥러닝 회귀 베이스 클래스의 핵심 추론 인터페이스 보유 여부 확인
    return (
        hasattr(model, "network")
        and hasattr(model, "_execute_inference_loop")
        and hasattr(model, "_prepare_predict_tensors")
    )


def _is_sequence_3d_deep_learning_model(
    model: Any,
    sample_features: pd.DataFrame,
) -> bool:
    """딥러닝 모델이 내부에서 2D 입력을 3D 시퀀스 텐서(N, P, L)로 변환하는 TCN 모델인지 판별합니다."""
    # 소규모 프로브 슬라이스를 주입하여 생성된 텐서의 차원이 3차원인지 확인
    if not _is_deep_learning_regressor(model=model):
        return False
    probe_slice = sample_features.iloc[: min(SEQUENCE_PROBE_SAMPLE_COUNT, len(sample_features))]
    probe_tensor = model._prepare_predict_tensors(X_test=probe_slice)
    return isinstance(probe_tensor, torch.Tensor) and probe_tensor.ndim == SEQUENCE_3D_TENSOR_NDIM


def _collect_nested_3d_deep_learning_models(
    model: Any,
    sample_features: pd.DataFrame,
) -> List[Any]:
    """메타 앙상블 모델 내부에 포함된 3D TCN 서브 모델 목록을 재귀 탐색합니다."""
    discovered_models: List[Any] = []
    visited_object_ids: set[int] = set()

    # 객체 그래프를 재귀 순회하며 3D TCN 모델 수집
    def _walk_object_graph(current_object: Any) -> None:
        if current_object is None or id(current_object) in visited_object_ids:
            return
        visited_object_ids.add(id(current_object))

        if _is_sequence_3d_deep_learning_model(model=current_object, sample_features=sample_features):
            discovered_models.append(current_object)
            return

        if isinstance(current_object, dict):
            for value in current_object.values():
                _walk_object_graph(value)
        elif isinstance(current_object, (list, tuple, set)):
            for item in current_object:
                _walk_object_graph(item)
        elif hasattr(current_object, "__dict__"):
            for attribute_name, attribute_value in vars(current_object).items():
                if not attribute_name.startswith("__"):
                    _walk_object_graph(attribute_value)

    _walk_object_graph(model)
    return discovered_models


def _sanitize_tree_explainer_categorical(explainer: Any) -> None:
    """수치형 데이터셋 대상 XGBoost TreeEnsemble의 잘못된 범주형 플래그를 초기화합니다."""
    # TreeEnsemble 내부 범주형 피처 인덱스 및 플래그 해제
    tree_ensemble = getattr(explainer, "model", None)
    if tree_ensemble is not None:
        if getattr(tree_ensemble, "cat_feature_indices", None) is not None:
            tree_ensemble.cat_feature_indices = None
        if getattr(tree_ensemble, "_xgb_enable_categorical", False):
            tree_ensemble._xgb_enable_categorical = False


def _build_index_encoding_matrices(
    background_count: int,
    evaluation_count: int,
    feature_count: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """TCN 3D 시계열 채널 마스킹을 위해 배경 및 평가 표본의 위치 인덱스 행렬(N, P)을 생성합니다."""
    # 배경 표본(0 ~ background_count-1)과 평가 표본(background_count ~ 총합-1) 인덱스 브로드캐스팅
    background_index_matrix = np.broadcast_to(
        np.arange(background_count, dtype=np.float64)[:, None],
        (background_count, feature_count),
    ).copy()
    evaluation_index_matrix = np.broadcast_to(
        np.arange(background_count, background_count + evaluation_count, dtype=np.float64)[:, None],
        (evaluation_count, feature_count),
    ).copy()
    return background_index_matrix, evaluation_index_matrix


def _build_tree_explainer_context(
    wrapper_model: Any,
    underlying_model: Any,
    evaluation_matrix: np.ndarray,
    background_feature_array: np.ndarray,
    feature_names: List[str],
) -> PolymorphicExplainerContext:
    """트리 모델(RandomForest, XGBoost, CatBoost)을 위한 TreeExplainer 컨텍스트를 생성합니다."""
    # TreeExplainer 생성, 범주형 플래그 정제 및 2D 추론 함수 바인딩
    explainer = shap.TreeExplainer(
        model=underlying_model,
        feature_perturbation=DEFAULT_TREE_FEATURE_PERTURBATION,
    )
    _sanitize_tree_explainer_categorical(explainer=explainer)
    predict_function = _build_general_2d_predict_function(
        model=wrapper_model,
        feature_names=feature_names,
    )
    return PolymorphicExplainerContext(
        explainer=explainer,
        evaluation_input=evaluation_matrix,
        background_input=background_feature_array,
        predict_function=predict_function,
        is_index_encoded=False,
    )


def _build_linear_explainer_context(
    wrapper_model: Any,
    underlying_model: Any,
    evaluation_matrix: np.ndarray,
    background_feature_array: np.ndarray,
    feature_names: List[str],
) -> PolymorphicExplainerContext:
    """선형 모델(ElasticNet)을 위한 LinearExplainer 컨텍스트를 생성합니다."""
    # 배경 데이터 마스커 기반 LinearExplainer 및 2D 추론 함수 바인딩
    explainer = shap.LinearExplainer(
        model=underlying_model,
        masker=background_feature_array,
    )
    predict_function = _build_general_2d_predict_function(
        model=wrapper_model,
        feature_names=feature_names,
    )
    return PolymorphicExplainerContext(
        explainer=explainer,
        evaluation_input=evaluation_matrix,
        background_input=background_feature_array,
        predict_function=predict_function,
        is_index_encoded=False,
    )


def _build_3d_sequence_explainer_context(
    wrapper_model: Any,
    training_features: pd.DataFrame,
    evaluation_features: pd.DataFrame,
    background_indices: np.ndarray,
    feature_names: List[str],
    random_state: int,
) -> PolymorphicExplainerContext:
    """3D 시계열 딥러닝 모델(TCN)을 위한 채널별 인과 윈도우 보존 Explainer 컨텍스트를 생성합니다."""
    # 1. 학습(배경) 및 평가 데이터의 3D 인과 윈도우 텐서를 사전 생성하여 결합
    training_3d_tensor = wrapper_model._prepare_predict_tensors(X_test=training_features).detach().cpu()
    background_3d_tensor = training_3d_tensor[background_indices]
    evaluation_3d_tensor = wrapper_model._prepare_predict_tensors(X_test=evaluation_features).detach().cpu()
    combined_3d_tensor = torch.cat([background_3d_tensor, evaluation_3d_tensor], dim=0).contiguous()

    # 2. 표본 위치 인덱스 행렬 및 3D 채널 인덱싱 추론 함수 구성
    feature_count = len(feature_names)
    background_index_matrix, evaluation_index_matrix = _build_index_encoding_matrices(
        background_count=len(background_3d_tensor),
        evaluation_count=len(evaluation_3d_tensor),
        feature_count=feature_count,
    )
    predict_3d_function = _build_deep_learning_3d_channel_predict_function(
        model=wrapper_model,
        combined_3d_tensor=combined_3d_tensor,
        feature_count=feature_count,
    )

    # 3. 독립 인덱스 마스커 기반 SHAP Explainer 생성
    masker = shap.maskers.Independent(
        background_index_matrix,
        max_samples=len(background_3d_tensor),
    )
    explainer = shap.Explainer(
        model=predict_3d_function,
        masker=masker,
        seed=random_state,
    )
    return PolymorphicExplainerContext(
        explainer=explainer,
        evaluation_input=evaluation_index_matrix,
        background_input=background_index_matrix,
        predict_function=predict_3d_function,
        is_index_encoded=True,
    )


def _build_2d_deep_learning_explainer_context(
    wrapper_model: Any,
    evaluation_matrix: np.ndarray,
    background_feature_array: np.ndarray,
    random_state: int,
) -> PolymorphicExplainerContext:
    """2D 정형 딥러닝 모델(TabularResNet, DCNv2, FT-Transformer) 전용 Explainer 컨텍스트를 생성합니다."""
    # PyTorch 텐서 직결 추론 함수 및 독립 마스커 기반 Explainer 생성
    predict_2d_function = _build_deep_learning_2d_predict_function(model=wrapper_model)
    masker = shap.maskers.Independent(
        background_feature_array,
        max_samples=len(background_feature_array),
    )
    explainer = shap.Explainer(
        model=predict_2d_function,
        masker=masker,
        seed=random_state,
    )
    return PolymorphicExplainerContext(
        explainer=explainer,
        evaluation_input=evaluation_matrix,
        background_input=background_feature_array,
        predict_function=predict_2d_function,
        is_index_encoded=False,
    )


def _build_hybrid_ensemble_explainer_context(
    wrapper_model: Any,
    nested_3d_models: List[Any],
    training_features: pd.DataFrame,
    evaluation_features: pd.DataFrame,
    background_indices: np.ndarray,
    background_feature_array: np.ndarray,
    evaluation_matrix: np.ndarray,
    feature_names: List[str],
    random_state: int,
) -> PolymorphicExplainerContext:
    """3D TCN 서브 모델을 포함한 하이브리드 메타 앙상블 전용 Explainer 컨텍스트를 생성합니다."""
    # 1. 2D 통합 행렬 및 표본 위치 인덱스 행렬 구축
    combined_2d_matrix = np.vstack([background_feature_array, evaluation_matrix])
    background_index_matrix, evaluation_index_matrix = _build_index_encoding_matrices(
        background_count=len(background_feature_array),
        evaluation_count=len(evaluation_matrix),
        feature_count=len(feature_names),
    )

    # 2. 2D 피처와 3D TCN 서브 모델 텐서를 동기화하는 하이브리드 추론 함수 생성
    predict_hybrid_function = _build_hybrid_ensemble_predict_function(
        wrapper_model=wrapper_model,
        nested_3d_models=nested_3d_models,
        training_features=training_features,
        evaluation_features=evaluation_features,
        background_indices=background_indices,
        combined_2d_matrix=combined_2d_matrix,
        feature_names=feature_names,
    )

    # 3. 인덱스 마스커 기반 SHAP Explainer 생성
    masker = shap.maskers.Independent(
        background_index_matrix,
        max_samples=len(background_feature_array),
    )
    explainer = shap.Explainer(
        model=predict_hybrid_function,
        masker=masker,
        seed=random_state,
    )
    return PolymorphicExplainerContext(
        explainer=explainer,
        evaluation_input=evaluation_index_matrix,
        background_input=background_index_matrix,
        predict_function=predict_hybrid_function,
        is_index_encoded=True,
    )


def _build_general_explainer_context(
    wrapper_model: Any,
    evaluation_matrix: np.ndarray,
    background_feature_array: np.ndarray,
    feature_names: List[str],
    random_state: int,
) -> PolymorphicExplainerContext:
    """2D 모델 기반 메타 앙상블 모델을 위한 Explainer 컨텍스트를 생성합니다."""
    # 일반 DataFrame 변환 추론 함수 및 독립 마스커 기반 Explainer 생성
    predict_general_function = _build_general_2d_predict_function(
        model=wrapper_model,
        feature_names=feature_names,
    )
    masker = shap.maskers.Independent(
        background_feature_array,
        max_samples=len(background_feature_array),
    )
    explainer = shap.Explainer(
        model=predict_general_function,
        masker=masker,
        seed=random_state,
    )
    return PolymorphicExplainerContext(
        explainer=explainer,
        evaluation_input=evaluation_matrix,
        background_input=background_feature_array,
        predict_function=predict_general_function,
        is_index_encoded=False,
    )


def _build_deep_learning_2d_predict_function(
    model: Any,
) -> Callable[[np.ndarray], np.ndarray]:
    """2D 딥러닝 회귀 모델(TabularResNet, DCNv2, FT-Transformer) 전용 고속 배치 추론 함수를 생성합니다."""
    # NumPy 배치를 연속된 float32 PyTorch 텐서로 변환하여 추론 루프 직결 호출
    def _predict_batch(feature_matrix: np.ndarray) -> np.ndarray:
        array_2d = np.asarray(feature_matrix, dtype=np.float32)
        if array_2d.ndim == 1:
            array_2d = array_2d.reshape(1, -1)
        predict_tensor = torch.from_numpy(np.ascontiguousarray(array_2d))
        return np.asarray(
            model._execute_inference_loop(predict_tensor=predict_tensor),
            dtype=np.float64,
        ).ravel()

    return _predict_batch


def _build_deep_learning_3d_channel_predict_function(
    model: Any,
    combined_3d_tensor: torch.Tensor,
    feature_count: int,
) -> Callable[[np.ndarray], np.ndarray]:
    """3D TCN 모델에서 각 피처 채널별 인과적 시계열 윈도우를 보존하여 추론하는 함수를 생성합니다."""
    channel_indices = torch.arange(feature_count, dtype=torch.long).unsqueeze(0)

    # [설계 의도] SHAP 마스커가 전달한 (Batch, P) 표본 인덱스 행렬을 기반으로
    # 각 피처 채널마다 해당 표본 시점의 실제 3D 인과 윈도우(길이 L)를 벡터화 결합하여 추론
    def _predict_3d_coalitions(index_matrix: np.ndarray) -> np.ndarray:
        index_array = np.rint(np.asarray(index_matrix, dtype=np.float64)).astype(np.int64)
        if index_array.ndim == 1:
            index_array = index_array.reshape(1, -1)
        index_tensor = torch.from_numpy(np.ascontiguousarray(index_array)).to(dtype=torch.long)
        coalition_3d_tensor = combined_3d_tensor[index_tensor, channel_indices].contiguous()
        return np.asarray(
            model._execute_inference_loop(predict_tensor=coalition_3d_tensor),
            dtype=np.float64,
        ).ravel()

    return _predict_3d_coalitions


@contextmanager
def _bind_3d_submodel_tensors(
    submodels_and_tensors: List[Tuple[Any, torch.Tensor]],
    index_tensor: torch.Tensor,
    channel_indices: torch.Tensor,
) -> Iterator[None]:
    """앙상블 내부의 3D TCN 서브 모델들이 마스킹된 인덱스에 대응하는 3D 텐서를 참조하도록 임시 바인딩합니다."""
    original_methods: List[Tuple[Any, Any]] = []
    try:
        # 서브 모델별 텐서 준비 메서드를 마스킹된 3D 조합 텐서 반환 람다로 임시 교체
        for submodel, combined_3d_tensor in submodels_and_tensors:
            original_methods.append((submodel, submodel._prepare_predict_tensors))
            bound_tensor = combined_3d_tensor[index_tensor, channel_indices].contiguous()
            submodel._prepare_predict_tensors = lambda X_test, _bound=bound_tensor: _bound
        yield
    finally:
        # 컨텍스트 종료 시 원본 텐서 준비 메서드로 안전하게 복원
        for submodel, original_method in original_methods:
            submodel._prepare_predict_tensors = original_method


def _build_hybrid_ensemble_predict_function(
    wrapper_model: Any,
    nested_3d_models: List[Any],
    training_features: pd.DataFrame,
    evaluation_features: pd.DataFrame,
    background_indices: np.ndarray,
    combined_2d_matrix: np.ndarray,
    feature_names: List[str],
) -> Callable[[np.ndarray], np.ndarray]:
    """3D TCN 서브 모델을 포함한 메타 앙상블 모델의 시계열 윈도우 정합성을 보장하는 추론 함수를 생성합니다."""
    feature_count = len(feature_names)
    channel_indices = torch.arange(feature_count, dtype=torch.long).unsqueeze(0)
    submodels_and_tensors: List[Tuple[Any, torch.Tensor]] = []

    # 1. 각 3D TCN 서브 모델의 배경 및 평가 3D 텐서를 사전 계산하여 결합 보관
    for submodel in nested_3d_models:
        training_3d_tensor = submodel._prepare_predict_tensors(X_test=training_features).detach().cpu()
        background_3d_tensor = training_3d_tensor[background_indices]
        evaluation_3d_tensor = submodel._prepare_predict_tensors(X_test=evaluation_features).detach().cpu()
        combined_3d_tensor = torch.cat([background_3d_tensor, evaluation_3d_tensor], dim=0).contiguous()
        submodels_and_tensors.append((submodel, combined_3d_tensor))

    column_indices = np.arange(feature_count, dtype=np.int64)[None, :]

    # 2. 인덱스 행렬로부터 2D DataFrame과 3D TCN 텐서를 동시 조립하여 앙상블 추론 수행
    def _predict_hybrid_coalitions(index_matrix: np.ndarray) -> np.ndarray:
        index_array = np.rint(np.asarray(index_matrix, dtype=np.float64)).astype(np.int64)
        if index_array.ndim == 1:
            index_array = index_array.reshape(1, -1)
        coalition_2d_matrix = combined_2d_matrix[index_array, column_indices]
        coalition_dataframe = pd.DataFrame(coalition_2d_matrix, columns=feature_names)
        index_tensor = torch.from_numpy(np.ascontiguousarray(index_array)).to(dtype=torch.long)

        with _bind_3d_submodel_tensors(
            submodels_and_tensors=submodels_and_tensors,
            index_tensor=index_tensor,
            channel_indices=channel_indices,
        ):
            return predict_model_values(
                model=wrapper_model,
                evaluation_features=coalition_dataframe,
            )

    return _predict_hybrid_coalitions


def _build_general_2d_predict_function(
    model: Any,
    feature_names: List[str],
) -> Callable[[np.ndarray], np.ndarray]:
    """일반 2D 래퍼 및 머신러닝 모델을 위한 DataFrame 변환 기반 배치 추론 함수를 생성합니다."""
    # 피처명 보존 여부에 따라 원시 배열 또는 DataFrame으로 변환하여 추론 수행
    def _predict_2d(feature_matrix: np.ndarray) -> np.ndarray:
        array_2d = np.asarray(feature_matrix, dtype=np.float64)
        if array_2d.ndim == 1:
            array_2d = array_2d.reshape(1, -1)
        if hasattr(model, "predict") and not hasattr(model, "feature_names"):
            return np.asarray(model.predict(array_2d), dtype=np.float64).ravel()
        dataframe = pd.DataFrame(array_2d, columns=feature_names)
        return predict_model_values(model=model, evaluation_features=dataframe)

    return _predict_2d