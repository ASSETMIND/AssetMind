from typing import Dict, Optional, Union
import numpy as np
import pandas as pd

from src.model.core.base.abstract_regressor import AbstractRegressor
from src.model.evaluation import metrics
from src.model.evaluation.composite_score import get_trial_score
from src.model.evaluation.criteria import Weights
from src.model.evaluation.schema import (
    EvaluationMetric,
    EvaluationResult,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [모델 평가 식별자 및 예측 시계열 변환 설정]
DEFAULT_ANONYMOUS_MODEL_NAME: str = "AnonymousRegressor"      # 모델 객체 없이 예측값만 평가할 때 사용할 기본 식별 명칭
PREDICTION_SERIES_SUFFIX: str = "_prediction"                 # 배열 형태의 예측값을 Series로 변환할 때 부여할 접미사
FROZEN_PRED_STD_ATTR: str = "pred_std_"                       # 학습 단계에서 동결된 예측값 표준편차 속성명

# [타겟 표준편차 정규화 및 안전 방어 설정]
DEFAULT_FALLBACK_STD: float = 1.0                             # 표본 부족 또는 분산 0 발생 시 적용할 안전한 기본 표준편차
MIN_SAMPLES_FOR_STD: int = 2                                  # 표본 표준편차 산출을 위한 최소 유효 관측치 개수
SAMPLE_STD_DDOF: int = 1                                      # 불편 추정량 산출을 위한 자유도 차감값


# ==============================================================================
# Public API Functions
# ==============================================================================
class ModelEvaluator:
    """단일 회귀 모델(ML/DL/Ensemble) 또는 예측값 시계열에 대해 10대 지표 및 복합 스코어를 산출하는 평가 엔진.

    AbstractRegressor 규격을 준수하는 모든 구체 모델에 대해 추론 집행, 10대 원자적 금융/통계 지표 산출,
    핵심 계층 가중 복합 스코어링을 수행하여 표준화된 불변 EvaluationResult DTO를 반환합니다.

    Attributes:
        weights (Weights): 핵심 평가 계층(ML, Factor) 복합 스코어링 가중치 DTO.
    """

    def __init__(self, weights: Optional[Weights] = None) -> None:
        """ModelEvaluator 인스턴스를 초기화합니다.

        Args:
            weights (Optional[Weights]): 복합 스코어링 가중치 DTO. 기본값은 None(기본 가중치 적용).
        """
        # 1. 외부 주입 가중치가 없을 경우 기본 Weights 인스턴스로 상태 초기화
        self.weights: Weights = weights or Weights()

    def evaluate(
        self,
        model: AbstractRegressor,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        target_std: Optional[float] = None,
    ) -> EvaluationResult:
        """학습 완료된 회귀 모델 인스턴스를 전달받아 추론을 집행하고 종합 평가 결과를 산출합니다.

        Args:
            model (AbstractRegressor): 평가 대상 학습 완료 회귀 모델(ML/DL/Ensemble) 인스턴스.
            X_test (pd.DataFrame): Out-of-Sample 테스트 피처 데이터프레임.
            y_test (pd.Series): Out-of-Sample 테스트 정답 타겟 시리즈.
            target_std (Optional[float]): RMSE/MAE 정규화용 타겟 표준편차. 기본값은 None.

        Returns:
            EvaluationResult: 모델 식별자, 예측 시리즈, 10대 지표 및 복합 스코어가 캡슐화된 불변 DTO.
        """
        # 1. 최상위 AbstractRegressor 다형성 인터페이스를 통해 예측 시계열 추론
        predictions: pd.Series = model.predict(X_test)

        # 2. 정답 및 예측 시계열을 1차원 실수형 NumPy 배열로 평탄화
        y_true_array: np.ndarray = _to_flattened_float_array(data=y_test)
        y_pred_array: np.ndarray = _to_flattened_float_array(data=predictions)

        # 3. 학습 단계에서 동결된 예측 표준편차를 추출하여 10대 평가지표 일괄 산출
        effective_pred_std: Optional[float] = getattr(model, FROZEN_PRED_STD_ATTR, None)
        metric_dict: Dict[EvaluationMetric, float] = _calculate_metrics(
            y_true=y_true_array,
            y_pred=y_pred_array,
            pred_std=effective_pred_std,
        )

        # 4. 정규화용 타겟 표준편차 및 가중 복합 스코어 산출 후 결과 DTO 반환
        effective_target_std: float = _calculate_std(
            y_true=y_true_array,
            provided_std=target_std,
        )
        composite_score: float = get_trial_score(
            metrics=metric_dict,
            weights=self.weights,
            target_std=effective_target_std,
        )

        return EvaluationResult(
            model_name=model.model_name,
            predictions=predictions,
            metrics=metric_dict,
            composite_score=composite_score,
        )

    def evaluate_predictions(
        self,
        y_true: Union[np.ndarray, pd.Series],
        y_pred: Union[np.ndarray, pd.Series],
        model_name: str = DEFAULT_ANONYMOUS_MODEL_NAME,
        target_std: Optional[float] = None,
    ) -> EvaluationResult:
        """모델 객체 없이 이미 산출된 예측값 및 정답 시계열 쌍을 직접 수신하여 평가를 집행합니다.

        Args:
            y_true (Union[np.ndarray, pd.Series]): 실제 정답 타겟 시계열.
            y_pred (Union[np.ndarray, pd.Series]): 모델 추론 예측값 시계열.
            model_name (str): 평가 대상 모델 식별 명칭. 기본값은 DEFAULT_ANONYMOUS_MODEL_NAME.
            target_std (Optional[float]): RMSE/MAE 정규화용 타겟 표준편차. 기본값은 None.

        Returns:
            EvaluationResult: 표준 지표 및 복합 스코어가 포함된 평가 결과 DTO.
        """
        # 1. 입력 예측값을 표준 Series 포맷으로 정규화하고 연산용 1차원 배열로 변환
        predictions_series: pd.Series = _normalize_prediction_series(
            y_pred=y_pred,
            model_name=model_name,
        )
        y_true_array: np.ndarray = _to_flattened_float_array(data=y_true)
        y_pred_array: np.ndarray = _to_flattened_float_array(data=predictions_series)

        # 2. 10대 원자적 평가지표 및 정규화용 타겟 표준편차 산출
        metric_dict: Dict[EvaluationMetric, float] = _calculate_metrics(
            y_true=y_true_array,
            y_pred=y_pred_array,
        )
        effective_target_std: float = _calculate_std(
            y_true=y_true_array,
            provided_std=target_std,
        )

        # 3. 가중 복합 스코어 산출 후 최종 평가 결과 DTO 반환
        composite_score: float = get_trial_score(
            metrics=metric_dict,
            weights=self.weights,
            target_std=effective_target_std,
        )

        return EvaluationResult(
            model_name=model_name,
            predictions=predictions_series,
            metrics=metric_dict,
            composite_score=composite_score,
        )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _normalize_prediction_series(
    y_pred: Union[np.ndarray, pd.Series],
    model_name: str,
) -> pd.Series:
    """다양한 형태의 예측값 입력을 표준 명칭이 부여된 Pandas Series 객체로 변환합니다."""
    # 1. 이미 Series인 경우 원본 오염 방지를 위해 사본 반환
    if isinstance(y_pred, pd.Series):
        return y_pred.copy()

    # 2. 배열 형태인 경우 1차원 실수형으로 평탄화하여 Series로 래핑 후 반환
    return pd.Series(
        data=_to_flattened_float_array(data=y_pred),
        name=f"{model_name}{PREDICTION_SERIES_SUFFIX}",
    )


def _to_flattened_float_array(
    data: Union[np.ndarray, pd.Series, pd.DataFrame],
) -> np.ndarray:
    """Series, DataFrame 또는 NumPy 배열을 1차원 실수형(float64) 배열로 평탄화합니다."""
    # 1. Pandas 객체인 경우 to_numpy를 통해 변환하고, 그 외에는 asarray로 변환하여 1차원 평탄화 반환
    if isinstance(data, (pd.Series, pd.DataFrame)):
        return data.to_numpy(dtype=np.float64).flatten()
    return np.asarray(data, dtype=np.float64).flatten()


def _calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    pred_std: Optional[float] = None,
) -> Dict[EvaluationMetric, float]:
    """10대 원자적 금융 및 통계 평가 지표를 일괄 연산하여 딕셔너리로 반환합니다."""
    # 1. 팩터 신호(Rank IC)의 순위 단조성 통계 유의성(t-stat, p-val) 산출
    factor_t_statistic, factor_p_value = metrics.rank_ic_tstat(
        y_true=y_true,
        y_pred=y_pred,
    )

    # 2. 4대 평가 계층(예측 오차, 팩터 품질, 금융 성과, 통계 유의성) 10대 지표 매핑 및 반환
    return {
        EvaluationMetric.MDA: metrics.mda(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.RMSE: metrics.rmse(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.MAE: metrics.mae(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.RANK_IC: metrics.rank_ic(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.ICIR: metrics.icir(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.SIGNAL_SHARPE: metrics.signal_sharpe(
            y_true=y_true, y_pred=y_pred, pred_std=pred_std
        ),
        EvaluationMetric.SORTINO_RATIO: metrics.sortino_ratio(
            y_true=y_true, y_pred=y_pred, pred_std=pred_std
        ),
        EvaluationMetric.MDD: metrics.mdd(
            y_true=y_true, y_pred=y_pred, pred_std=pred_std
        ),
        EvaluationMetric.FACTOR_T_STAT: factor_t_statistic,
        EvaluationMetric.FACTOR_P_VAL: factor_p_value,
    }


def _calculate_std(
    y_true: np.ndarray,
    provided_std: Optional[float] = None,
) -> float:
    """타겟 시계열의 표준편차를 계산하여 RMSE 및 MAE 정규화 기준 분모를 결정합니다."""
    # 1. 외부에서 유효한 양수 표준편차가 주입된 경우 즉시 해당 값을 반환
    if provided_std is not None and provided_std > 0.0 and np.isfinite(provided_std):
        return float(provided_std)

    # 2. 결측 및 무한대를 제외한 유효 관측치 추출 후 최소 표본 수 미달 시 기본값 반환
    finite_targets: np.ndarray = y_true[np.isfinite(y_true)]
    if len(finite_targets) < MIN_SAMPLES_FOR_STD:
        return DEFAULT_FALLBACK_STD

    # 3. 표본 표준편차 산출 및 0 이하 또는 비정상 수치 발생 시 기본값으로 방어하여 반환
    calculated_std: float = float(np.std(finite_targets, ddof=SAMPLE_STD_DDOF))
    return (
        calculated_std
        if (calculated_std > 0.0 and np.isfinite(calculated_std))
        else DEFAULT_FALLBACK_STD
    )