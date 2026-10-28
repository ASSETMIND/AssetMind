from typing import Any, Callable, List, Optional, Tuple
import numpy as np
import pandas as pd
import shap

from src.model.xai.shap_schema import (
    DEFAULT_ADDITIVITY_TOLERANCE,
    DEFAULT_ROLLING_WINDOW_SIZE,
    PERCENTAGE_MULTIPLIER,
    AdditivityAuditResult,
)


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 2차 교호작용(Pairwise Mobius Interaction) 수리 연산 설정
INTERACTION_PAIRWISE_WEIGHT: float = 0.5          # 피처 쌍(i, j) 간 교호작용 대칭 분배 가중치
INTERACTION_ZERO_TOLERANCE: float = 1e-12         # 선형 모델 2차 미분 교호작용 영행렬 판정 임계치
NUMERICAL_STABILITY_EPSILON: float = 1e-12        # 정규화 분모 0 나눗셈 방지용 수치 안정성 앱실론

# 시계열 롤링 집계 설정
ROLLING_MINIMUM_PERIODS: int = 1                  # 롤링 이동평균 산출 시 초기 구간 결측 방지 최소 관측치 수


# ==============================================================================
# Public API Functions
# ==============================================================================
def calculate_shap_values(
    explainer: Any,
    evaluation_matrix: np.ndarray,
    feature_names: List[str],
    explainer_input_matrix: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, float, shap.Explanation]:
    """SHAP Explainer를 구동하여 기여도 행렬, 스칼라 기댓값 및 표준화된 Explanation 객체를 산출합니다.

    Args:
        explainer (Any): 모델 유형에 맞게 초기화된 SHAP Explainer 인스턴스.
        evaluation_matrix (np.ndarray): 시각화 및 설명 기준이 되는 원시 평가 피처 행렬 (N, P).
        feature_names (List[str]): 평가 피처 컬럼 명칭 리스트.
        explainer_input_matrix (Optional[np.ndarray]): 3D 인덱스 인코딩 등 Explainer 전용 입력 행렬. Defaults to None.

    Returns:
        Tuple[np.ndarray, float, shap.Explanation]:
            - shap_values: (N, P) 차원의 1차 SHAP 기여도 행렬.
            - base_value: 전체 배경 표본 기준 스칼라 기댓값 E[f(x)].
            - standardized_explanation: 원시 피처값과 스칼라 기댓값이 정합된 표준 Explanation 객체.

    Raises:
        ValueError: 평가 행렬과 피처 명단의 열 차원이 일치하지 않을 경우 발생.
    """
    # 1. 입력 피처 행렬과 피처 명단의 차원 정합성 검증
    _validate_matrix_feature_alignment(
        evaluation_matrix=evaluation_matrix,
        feature_names=feature_names,
    )

    # 2. Explainer 실행 및 원시 SHAP 행렬, 스칼라 기댓값 추출
    effective_input = explainer_input_matrix if explainer_input_matrix is not None else evaluation_matrix
    raw_explanation = explainer(effective_input)

    shap_values = _extract_raw_shap_matrix(
        raw_explanation=raw_explanation,
        explainer=explainer,
        effective_input=effective_input,
    )
    base_value = _extract_scalar_base_value(
        raw_explanation=raw_explanation,
        explainer=explainer,
    )

    # 3. 다형성 모델 간 시각화 호환성을 보장하는 표준 Explanation 객체 조립
    standardized_explanation = _build_standardized_explanation(
        shap_values=shap_values,
        base_value=base_value,
        evaluation_matrix=evaluation_matrix,
        feature_names=feature_names,
    )

    return shap_values, base_value, standardized_explanation


def calculate_interaction_values(
    explainer: Any,
    evaluation_matrix: np.ndarray,
    shap_values: Optional[np.ndarray] = None,
    predict_function: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    explainer_evaluation_input: Optional[np.ndarray] = None,
    explainer_background_input: Optional[np.ndarray] = None,
    is_index_encoded: bool = False,
) -> Optional[np.ndarray]:
    """트리 모델 네이티브 교호작용 또는 비트리 모델 2차 유한차분 교호작용 텐서(N, P, P)를 산출합니다.

    Args:
        explainer (Any): 초기화된 SHAP Explainer 인스턴스.
        evaluation_matrix (np.ndarray): 원시 평가 피처 행렬 (N, P).
        shap_values (Optional[np.ndarray]): 사전 연산된 1차 SHAP 기여도 행렬 (N, P). Defaults to None.
        predict_function (Optional[Callable[[np.ndarray], np.ndarray]]): 배치 추론 함수. Defaults to None.
        explainer_evaluation_input (Optional[np.ndarray]): Explainer 전용 평가 입력 행렬. Defaults to None.
        explainer_background_input (Optional[np.ndarray]): Explainer 전용 배경 입력 행렬. Defaults to None.
        is_index_encoded (bool): 3D 시계열 보존용 정수 인덱스 인코딩 여부. Defaults to False.

    Returns:
        Optional[np.ndarray]: 산출된 (N, P, P) 차원의 2차 교호작용 텐서 (산출 불가 시 None).

    Raises:
        ValueError: 주입된 1차 SHAP 행렬이 2차원이 아닐 경우 발생.
    """
    # 1. TreeExplainer 등 네이티브 교호작용 연산 지원 시 우선 추출
    native_interaction_tensor = _try_native_tree_interaction(
        explainer=explainer,
        evaluation_matrix=evaluation_matrix,
    )
    if native_interaction_tensor is not None:
        return native_interaction_tensor

    # 2. 비트리(DL/Linear/Ensemble) 모델을 위한 필수 입력 유효성 확인
    if shap_values is None or predict_function is None:
        return None

    if shap_values.ndim != 2:
        raise ValueError(
            f"[calculate_interaction_values] shap_values는 2차원 행렬이어야 합니다. 입력 차원: {shap_values.ndim}"
        )

    # 3. 단일 배치 순전파 기반 2차 유한차분(Pairwise Mobius) 교호작용 텐서 연산
    effective_evaluation_input = (
        explainer_evaluation_input if explainer_evaluation_input is not None else evaluation_matrix
    )
    effective_background_input = (
        explainer_background_input if explainer_background_input is not None else evaluation_matrix
    )

    return _calculate_pairwise_interaction_values(
        predict_function=predict_function,
        evaluation_input=effective_evaluation_input,
        background_input=effective_background_input,
        shap_values=shap_values,
        is_index_encoded=is_index_encoded,
    )


def calculate_rolling_shap_dataframe(
    shap_values: np.ndarray,
    feature_names: List[str],
    evaluation_index: pd.Index,
    window_size: int = DEFAULT_ROLLING_WINDOW_SIZE,
) -> pd.DataFrame:
    """시계열 날짜 인덱스를 기준으로 각 피처의 SHAP 기여도 롤링 이동평균을 산출합니다.

    Args:
        shap_values (np.ndarray): (N, P) 차원의 원시 SHAP 기여도 행렬.
        feature_names (List[str]): 피처 컬럼 명칭 리스트.
        evaluation_index (pd.Index): 평가 데이터셋의 시계열 인덱스.
        window_size (int): 롤링 이동평균 윈도우 크기(영업일). Defaults to DEFAULT_ROLLING_WINDOW_SIZE.

    Returns:
        pd.DataFrame: 시계열 롤링 평균이 적용된 SHAP 기여도 데이터프레임.

    Raises:
        ValueError: window_size가 1 미만이거나 행렬과 인덱스/피처 차원이 불일치할 경우 발생.
    """
    # 1. 윈도우 크기 및 입력 행렬 차원 무결성 검증
    if window_size < 1:
        raise ValueError(f"[calculate_rolling_shap_dataframe] window_size는 1 이상이어야 합니다: {window_size}")

    _validate_matrix_feature_alignment(
        evaluation_matrix=shap_values,
        feature_names=feature_names,
    )

    # 2. 시계열 롤링 이동평균 데이터프레임 연산 및 반환
    return _compute_rolling_mean_dataframe(
        shap_values=shap_values,
        feature_names=feature_names,
        evaluation_index=evaluation_index,
        window_size=window_size,
    )


def audit_additivity_axiom(
    shap_values: np.ndarray,
    base_value: float,
    raw_predictions: np.ndarray,
    tolerance: float = DEFAULT_ADDITIVITY_TOLERANCE,
) -> AdditivityAuditResult:
    """Shapley 가산성 공리(Efficiency Axiom) 오차를 계산하고 수치 무결성 감사 결과를 반환합니다.

    Args:
        shap_values (np.ndarray): (N, P) 차원의 1차 SHAP 기여도 행렬.
        base_value (float): 모델 기준 기댓값 E[f(x)].
        raw_predictions (np.ndarray): 모델 원시 예측값 벡터 f(x).
        tolerance (float): 가산성 공리 충족 판정 허용 오차. Defaults to DEFAULT_ADDITIVITY_TOLERANCE.

    Returns:
        AdditivityAuditResult: 최대/평균 절대 오차 및 공리 충족 여부가 담긴 불변 DTO.

    Raises:
        ValueError: SHAP 행렬의 표본 수와 원시 예측값 길이가 일치하지 않을 경우 발생.
    """
    # 1. 표본 길이 일치 여부 검증
    if shap_values.shape[0] != len(raw_predictions):
        raise ValueError(
            f"[audit_additivity_axiom] 표본 수 불일치: "
            f"shap_values({shap_values.shape[0]}) != raw_predictions({len(raw_predictions)})"
        )

    # 2. 내장 가산성 잔차 연산을 통해 감사 결과 DTO 산출
    return _compute_additivity_residuals(
        shap_values=shap_values,
        base_value=base_value,
        raw_predictions=raw_predictions,
        tolerance=tolerance,
    )


def calculate_global_importance(
    shap_values: np.ndarray,
    feature_names: List[str],
) -> pd.DataFrame:
    """피처별 전역 평균 절대 기여도(Mean |SHAP|), 상대 비중, 누적 비중 및 순위표를 산출합니다.

    Args:
        shap_values (np.ndarray): (N, P) 차원의 1차 SHAP 기여도 행렬.
        feature_names (List[str]): 피처 컬럼 명칭 리스트.

    Returns:
        pd.DataFrame: 중요도 내림차순으로 정렬된 전역 피처 중요도 감사 데이터프레임.

    Raises:
        ValueError: SHAP 행렬의 열 개수와 피처 명단 길이가 일치하지 않을 경우 발생.
    """
    # 1. 행렬 열 차원 및 피처 명단 정합성 검증
    _validate_matrix_feature_alignment(
        evaluation_matrix=shap_values,
        feature_names=feature_names,
    )

    # 2. 전역 피처 중요도 및 누적 기여도 테이블 산출
    return _compute_feature_importance_table(
        shap_values=shap_values,
        feature_names=feature_names,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_matrix_feature_alignment(
    evaluation_matrix: np.ndarray,
    feature_names: List[str],
) -> None:
    """2차원 행렬의 열 개수와 피처 명칭 리스트의 길이 일치 여부를 검증합니다."""
    # 입력 배열 차원 및 피처 수 일치 확인
    if evaluation_matrix.ndim != 2 or evaluation_matrix.shape[1] != len(feature_names):
        raise ValueError(
            f"[_validate_matrix_feature_alignment] 행렬 열 차원({evaluation_matrix.shape})과 "
            f"피처 개수({len(feature_names)})가 일치하지 않습니다."
        )


def _extract_raw_shap_matrix(
    raw_explanation: Any,
    explainer: Any,
    effective_input: np.ndarray,
) -> np.ndarray:
    """Explanation 결과 또는 Explainer로부터 (N, P) 2차원 원시 SHAP 기여도 행렬을 추출합니다."""
    # 1. Explanation 객체 속성 또는 shap_values 메서드로부터 원시 배열 추출
    if hasattr(raw_explanation, "values"):
        shap_values = np.asarray(raw_explanation.values, dtype=np.float64)
    else:
        shap_values = np.asarray(explainer.shap_values(effective_input), dtype=np.float64)

    # 2. 단일 출력 회귀 모델의 끝 차원(N, P, 1)을 (N, P)로 정규화
    if shap_values.ndim == 3 and shap_values.shape[-1] == 1:
        shap_values = np.squeeze(shap_values, axis=-1)

    return shap_values


def _extract_scalar_base_value(
    raw_explanation: Any,
    explainer: Any,
) -> float:
    """Explanation 객체 또는 Explainer로부터 스칼라 기준 기댓값(Base Value)을 추출합니다."""
    # base_values 배열 평균 또는 expected_value 속성에서 단일 스칼라 기댓값 도출
    if hasattr(raw_explanation, "base_values"):
        base_values = np.asarray(raw_explanation.base_values, dtype=np.float64)
        return float(np.mean(base_values))

    if hasattr(explainer, "expected_value"):
        expected_value = explainer.expected_value
        if isinstance(expected_value, (list, tuple, np.ndarray)):
            return float(np.asarray(expected_value, dtype=np.float64).ravel()[0])
        return float(expected_value)

    return 0.0


def _build_standardized_explanation(
    shap_values: np.ndarray,
    base_value: float,
    evaluation_matrix: np.ndarray,
    feature_names: List[str],
) -> shap.Explanation:
    """원시 피처 행렬과 1차원 기댓값 배열을 결합하여 표준 shap.Explanation 객체를 생성합니다."""
    # [설계 의도] 3D 인덱스 매핑 모델 등에서도 시각화 모듈이 실제 피처값(evaluation_matrix)을 참조하도록 표준화
    return shap.Explanation(
        values=shap_values,
        base_values=np.full(shap_values.shape[0], base_value, dtype=np.float64),
        data=evaluation_matrix,
        feature_names=feature_names,
    )


def _try_native_tree_interaction(
    explainer: Any,
    evaluation_matrix: np.ndarray,
) -> Optional[np.ndarray]:
    """TreeExplainer 계열이 지원하는 네이티브 2차 교호작용 행렬 연산을 시도합니다."""
    # shap_interaction_values 인터페이스 존재 시 호출 및 4차원 단일 타깃 축 축소
    if not hasattr(explainer, "shap_interaction_values"):
        return None

    try:
        interaction_tensor = np.asarray(
            explainer.shap_interaction_values(evaluation_matrix),
            dtype=np.float64,
        )
        if interaction_tensor.ndim == 4 and interaction_tensor.shape[-1] == 1:
            interaction_tensor = np.squeeze(interaction_tensor, axis=-1)
        return interaction_tensor
    except Exception:
        return None


def _calculate_pairwise_interaction_values(
    predict_function: Callable[[np.ndarray], np.ndarray],
    evaluation_input: np.ndarray,
    background_input: np.ndarray,
    shap_values: np.ndarray,
    is_index_encoded: bool = False,
) -> np.ndarray:
    """단일 배치 순전파 기반 2차 유한차분(Pairwise Mobius)으로 (N, P, P) 교호작용 텐서를 연산합니다."""
    sample_count, feature_count = shap_values.shape
    if feature_count < 2:
        return shap_values[:, :, np.newaxis].copy()

    # 1. 배경 분포 대표 기준점(Reference Row) 및 기준 예측값 산출
    baseline_row, baseline_prediction = _select_reference_baseline_row(
        predict_function=predict_function,
        background_input=background_input,
        is_index_encoded=is_index_encoded,
    )

    # 2. 1차 단독 섭동 및 2차 피처 쌍 섭동 결합 배치 생성 후 단일 순전파 추론 수행
    feature_pairs: List[Tuple[int, int]] = [
        (first_idx, second_idx)
        for first_idx in range(feature_count)
        for second_idx in range(first_idx + 1, feature_count)
    ]
    combined_queries = _build_perturbation_batches(
        baseline_row=baseline_row,
        evaluation_input=evaluation_input,
        feature_pairs=feature_pairs,
    )
    combined_predictions = predict_function(combined_queries)

    singleton_count = sample_count * feature_count
    singleton_predictions = combined_predictions[:singleton_count].reshape(feature_count, sample_count)
    pair_predictions = combined_predictions[singleton_count:].reshape(len(feature_pairs), sample_count)

    # 3. 2차 유한차분(Mobius) 비대각 교호작용 텐서 산출 및 선형 모델 공변동 폴백 보정
    interaction_tensor = _compute_mobius_interaction_tensor(
        singleton_predictions=singleton_predictions,
        pair_predictions=pair_predictions,
        baseline_prediction=baseline_prediction,
        sample_count=sample_count,
        feature_count=feature_count,
        feature_pairs=feature_pairs,
    )
    interaction_tensor = _apply_linear_cosynergy_fallback(
        interaction_tensor=interaction_tensor,
        shap_values=shap_values,
        feature_pairs=feature_pairs,
    )

    # 4. 대각 주효과 성분 보정으로 행 합계와 1차 SHAP 기여도 간 정합성 보장
    return _reconcile_diagonal_main_effects(
        interaction_tensor=interaction_tensor,
        shap_values=shap_values,
    )


def _select_reference_baseline_row(
    predict_function: Callable[[np.ndarray], np.ndarray],
    background_input: np.ndarray,
    is_index_encoded: bool,
) -> Tuple[np.ndarray, float]:
    """인덱스 인코딩 여부에 따라 배경 데이터셋의 대표 기준 행(Medoid 또는 평균)과 예측값을 도출합니다."""
    # [설계 의도] 3D 인덱스 매핑 모델은 평균 인덱스가 무의미하므로 예측값 평균에 가장 가까운 Medoid 표본을 선택
    if is_index_encoded:
        background_predictions = predict_function(background_input)
        medoid_position = int(np.argmin(np.abs(background_predictions - np.mean(background_predictions))))
        baseline_row = background_input[medoid_position : medoid_position + 1].copy()
    else:
        baseline_row = np.mean(background_input, axis=0, keepdims=True)

    baseline_prediction = float(predict_function(baseline_row)[0])
    return baseline_row, baseline_prediction


def _build_perturbation_batches(
    baseline_row: np.ndarray,
    evaluation_input: np.ndarray,
    feature_pairs: List[Tuple[int, int]],
) -> np.ndarray:
    """단일 순전파 추론을 위해 1차 개별 피처 섭동 배치와 2차 피처 쌍 섭동 배치를 단일 행렬로 조립합니다."""
    sample_count, feature_count = evaluation_input.shape
    pair_count = len(feature_pairs)

    # 1. 1차 개별 피처 섭동 배치 (N * P, P) 구성
    singleton_batch = np.repeat(baseline_row, sample_count * feature_count, axis=0)
    for feature_index in range(feature_count):
        start_row = feature_index * sample_count
        end_row = start_row + sample_count
        singleton_batch[start_row:end_row, feature_index] = evaluation_input[:, feature_index]

    # 2. 2차 피처 쌍 섭동 배치 (N * C(P, 2), P) 구성
    pair_batch = np.repeat(baseline_row, sample_count * pair_count, axis=0)
    for pair_index, (first_feature, second_feature) in enumerate(feature_pairs):
        start_row = pair_index * sample_count
        end_row = start_row + sample_count
        pair_batch[start_row:end_row, first_feature] = evaluation_input[:, first_feature]
        pair_batch[start_row:end_row, second_feature] = evaluation_input[:, second_feature]

    # 3. GPU/CPU 호출 오버헤드 최소화를 위한 단일 쿼리 행렬 병합
    return np.vstack([singleton_batch, pair_batch])


def _compute_mobius_interaction_tensor(
    singleton_predictions: np.ndarray,
    pair_predictions: np.ndarray,
    baseline_prediction: float,
    sample_count: int,
    feature_count: int,
    feature_pairs: List[Tuple[int, int]],
) -> np.ndarray:
    """단독 및 쌍 섭동 예측치로부터 비대각 2차 유한차분 교호작용 텐서를 연산합니다."""
    # 피처 쌍별 유한차분(0.5 * (f_ij - f_i - f_j + f_0)) 대칭 할당
    interaction_tensor = np.zeros((sample_count, feature_count, feature_count), dtype=np.float64)

    for pair_index, (first_feature, second_feature) in enumerate(feature_pairs):
        pairwise_delta = INTERACTION_PAIRWISE_WEIGHT * (
            pair_predictions[pair_index]
            - singleton_predictions[first_feature]
            - singleton_predictions[second_feature]
            + baseline_prediction
        )
        interaction_tensor[:, first_feature, second_feature] = pairwise_delta
        interaction_tensor[:, second_feature, first_feature] = pairwise_delta

    return interaction_tensor


def _apply_linear_cosynergy_fallback(
    interaction_tensor: np.ndarray,
    shap_values: np.ndarray,
    feature_pairs: List[Tuple[int, int]],
) -> np.ndarray:
    """순수 선형 모델에서 2차 미분 교호작용이 0일 경우 정규화된 1차 SHAP 공변동 시너지로 보정합니다."""
    # [설계 의도] ElasticNet 등 선형 회귀기에서도 의존성 파트너 선정이 가능하도록 1차 기여도 공변동 반영
    if float(np.max(np.abs(interaction_tensor))) > INTERACTION_ZERO_TOLERANCE:
        return interaction_tensor

    for first_feature, second_feature in feature_pairs:
        scale_denominator = (
            float(
                np.sqrt(
                    np.mean(
                        shap_values[:, first_feature] ** 2 + shap_values[:, second_feature] ** 2
                    )
                )
            )
            + NUMERICAL_STABILITY_EPSILON
        )
        co_synergy = (
            INTERACTION_PAIRWISE_WEIGHT
            * (shap_values[:, first_feature] * shap_values[:, second_feature])
            / scale_denominator
        )
        interaction_tensor[:, first_feature, second_feature] = co_synergy
        interaction_tensor[:, second_feature, first_feature] = co_synergy

    return interaction_tensor


def _reconcile_diagonal_main_effects(
    interaction_tensor: np.ndarray,
    shap_values: np.ndarray,
) -> np.ndarray:
    """교호작용 텐서의 행 합계가 1차 SHAP 기여도와 일치하도록 대각선 주효과 성분을 역산 보정합니다."""
    # 비대각 교호작용 총합을 1차 SHAP 값에서 차감하여 대각 성분에 주입
    feature_count = shap_values.shape[1]
    off_diagonal_sum = np.sum(interaction_tensor, axis=2)
    diagonal_indices = np.arange(feature_count)
    interaction_tensor[:, diagonal_indices, diagonal_indices] = shap_values - off_diagonal_sum
    return interaction_tensor


def _compute_rolling_mean_dataframe(
    shap_values: np.ndarray,
    feature_names: List[str],
    evaluation_index: pd.Index,
    window_size: int,
) -> pd.DataFrame:
    """원시 SHAP 배열을 데이터프레임으로 변환하고 지정된 윈도우 크기의 롤링 평균을 연산합니다."""
    # 시계열 인덱스 기반 롤링 이동평균 산출
    raw_shap_dataframe = pd.DataFrame(shap_values, index=evaluation_index, columns=feature_names)
    return raw_shap_dataframe.rolling(window=window_size, min_periods=ROLLING_MINIMUM_PERIODS).mean()


def _compute_additivity_residuals(
    shap_values: np.ndarray,
    base_value: float,
    raw_predictions: np.ndarray,
    tolerance: float,
) -> AdditivityAuditResult:
    """기댓값과 SHAP 합산으로 재구성된 예측치와 실제 모델 예측치 간의 잔차를 검정합니다."""
    # 재구성 예측값 산출 및 허용 오차 이내 가산성 공리 충족 여부 판정
    reconstructed_predictions = base_value + np.sum(shap_values, axis=1)
    absolute_errors = np.abs(raw_predictions - reconstructed_predictions)

    maximum_error = float(np.max(absolute_errors))
    mean_error = float(np.mean(absolute_errors))
    is_satisfied = bool(maximum_error <= tolerance)

    return AdditivityAuditResult(
        maximum_absolute_error=maximum_error,
        mean_absolute_error=mean_error,
        is_axiom_satisfied=is_satisfied,
        tolerance=tolerance,
        sample_count=len(raw_predictions),
    )


def _compute_feature_importance_table(
    shap_values: np.ndarray,
    feature_names: List[str],
) -> pd.DataFrame:
    """피처별 평균 절대 SHAP 값, 백분율 비중, 누적 비중 및 순위 데이터프레임을 생성합니다."""
    # 1. 피처별 평균 절대 기여도 및 전체 대비 상대 비중(%) 산출
    mean_absolute_shap = np.mean(np.abs(shap_values), axis=0)
    total_importance = float(np.sum(mean_absolute_shap))

    if total_importance > 0.0:
        importance_ratio = (mean_absolute_shap / total_importance) * PERCENTAGE_MULTIPLIER
    else:
        importance_ratio = np.zeros_like(mean_absolute_shap)

    # 2. 내림차순 정렬 및 누적 비중, 순위 부여
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