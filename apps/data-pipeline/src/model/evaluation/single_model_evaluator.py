from typing import Dict, Optional, Union
import numpy as np
import pandas as pd

from src.model.core.abstract_regressor import AbstractRegressor
from src.model.evaluation import metrics
from src.model.evaluation.criteria import Weights
from src.model.evaluation.composite_score import get_trial_score
from src.model.evaluation.schema import (
    EvaluationMetric,
    EvaluationResult,
)


# ==============================================================================
# 1. 단일 모델 전담 평가 엔진 클래스 (Single Model Evaluator)
# ==============================================================================

class SingleModelEvaluator:
    """단일 회귀 모델 인스턴스 또는 예측값 시계열에 대해 10대 지표 및 복합 스코어를 산출하는 전담 평가 엔진.

    AbstractRegressor 규격을 준수하는 모든 구체 모델(단일 모델 및 향후 앙상블 모델)에 대해
    추론 집행, 10대 원자적 금융/통계 지표 산출, 4대 계층 가중 복합 스코어링을 수행하여
    표준화된 불변 EvaluationResult DTO를 사출합니다.
    """

    def __init__(self, weights: Optional[Weights] = None) -> None:
        """SingleModelEvaluator 인스턴스를 초기화합니다.

        Args:
            weights (Optional[Weights]): 4대 계층 복합 스코어링 가중치 DTO (None일 경우 기본 가중치 적용).
        """
        self.weights: Weights = weights or Weights()

    def evaluate(
        self,
        model: AbstractRegressor,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        target_std: Optional[float] = None,
    ) -> EvaluationResult:
        """학습 완료된 단일 모델 인스턴스를 전달받아 추론을 집행하고 종합 평가 결과를 산출합니다.

        Args:
            model (AbstractRegressor): 평가 대상 학습 완료 모델 인스턴스.
            X_test (pd.DataFrame): Out-of-Sample 테스트 피처 데이터프레임.
            y_test (pd.Series): Out-of-Sample 테스트 정답 타겟 시리즈.
            target_std (Optional[float]): RMSE/MAE 정규화용 타겟 표준편차 (None 시 y_test 표준편차 자동 산출).

        Returns:
            EvaluationResult: 모델 식별자, 예측 시계열 Series, 10대 지표 딕셔너리,
                복합 스코어가 캡슐화된 불변 결과 DTO.
        """
        # AbstractRegressor 다형성 인터페이스 규격을 통해 예측값 사출
        predictions: pd.Series = model.predict(X_test)

        y_true_array: np.ndarray = y_test.to_numpy(dtype=np.float64).flatten()
        y_pred_array: np.ndarray = predictions.to_numpy(dtype=np.float64).flatten()

        # 10대 원자적 지표 일괄 연산
        metric_dict: Dict[EvaluationMetric, float] = _calculate_metrics(
            y_true=y_true_array,
            y_pred=y_pred_array,
        )

        effective_target_std: float = _calculate_std(
            y_true=y_true_array,
            provided_std=target_std,
        )

        # 4대 계층 가중 복합 스코어 산출
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
        model_name: str = "AnonymousRegressor",
        target_std: Optional[float] = None,
    ) -> EvaluationResult:
        """모델 객체 없이 이미 산출된 예측값 및 정답 시계열 쌍을 직접 수신하여 평가를 집행합니다.

        (시계열 CV Fold 평가, OOF 메타 예측값 검증 및 백테스터에서 활용)

        Args:
            y_true (Union[np.ndarray, pd.Series]): 실제 정답 타겟 시계열.
            y_pred (Union[np.ndarray, pd.Series]): 모델 추론 예측값 시계열.
            model_name (str): 평가 대상 모델 식별 명칭 (기본값: 'AnonymousRegressor').
            target_std (Optional[float]): RMSE/MAE 정규화용 타겟 표준편차 (None 시 자동 산출).

        Returns:
            EvaluationResult: 표준 지표 및 복합 스코어가 포함된 평가 결과 DTO.
        """
        # 예측값 Series 포맷 표준화
        if isinstance(y_pred, pd.Series):
            predictions_series: pd.Series = y_pred.copy()
        else:
            predictions_series = pd.Series(
                data=np.asarray(y_pred, dtype=np.float64).flatten(),
                name=f"{model_name}_prediction",
            )

        y_true_array: np.ndarray = (
            y_true.to_numpy(dtype=np.float64).flatten()
            if isinstance(y_true, (pd.Series, pd.DataFrame))
            else np.asarray(y_true, dtype=np.float64).flatten()
        )
        y_pred_array: np.ndarray = predictions_series.to_numpy(dtype=np.float64).flatten()

        metric_dict: Dict[EvaluationMetric, float] = _calculate_metrics(
            y_true=y_true_array,
            y_pred=y_pred_array,
        )

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
            model_name=model_name,
            predictions=predictions_series,
            metrics=metric_dict,
            composite_score=composite_score,
        )


# ==============================================================================
# 2. 내부 수리 연산 및 정규화 서브루틴 (Private Helpers)
# ==============================================================================

def _calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[EvaluationMetric, float]:
    """10대 원자적 금융/통계 평가 지표를 metrics.py 모듈을 통해 일괄 연산합니다.

    Args:
        y_true (np.ndarray): 1차원 정답 타겟 배열.
        y_pred (np.ndarray): 1차원 예측값 배열.

    Returns:
        Dict[EvaluationMetric, float]: EvaluationMetric 표준 Enum을 키로 갖는 10대 지표 딕셔너리.
    """
    # Newey-West HAC 통계 검정치 산출 (t-stat, p-val 동시 추출)
    factor_t_statistic, factor_p_value = metrics.newey_west_tstat(
        y_true=y_true,
        y_pred=y_pred,
    )

    # schema.py에 정의된 10대 표준 Canonical Key에 맞춰 O(1) 매핑
    return {
        # Layer 1: 기계학습 기본 예측 오차
        EvaluationMetric.MDA: metrics.mda(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.RMSE: metrics.rmse(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.MAE: metrics.mae(y_true=y_true, y_pred=y_pred),
        # Layer 2: 퀀트 팩터 신호 품질
        EvaluationMetric.RANK_IC: metrics.rank_ic(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.ICIR: metrics.icir(y_true=y_true, y_pred=y_pred, window_size=20),
        # Layer 3: 금융 시뮬레이션 성과
        EvaluationMetric.SIGNAL_SHARPE: metrics.signal_sharpe(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.SORTINO_RATIO: metrics.sortino_ratio(y_true=y_true, y_pred=y_pred),
        EvaluationMetric.MDD: metrics.mdd(y_true=y_true, y_pred=y_pred),
        # Layer 4: 단일 신호 통계적 유의성
        EvaluationMetric.FACTOR_T_STAT: factor_t_statistic,
        EvaluationMetric.FACTOR_P_VAL: factor_p_value,
    }


def _calculate_std(
    y_true: np.ndarray,
    provided_std: Optional[float] = None,
) -> float:
    """타겟 시계열의 표준편차를 계산하여 RMSE/MAE 정규화 기준 분모를 결정합니다.

    Args:
        y_true (np.ndarray): 실제 타겟 시계열 배열.
        provided_std (Optional[float]): 외부에서 명시적으로 주입된 표준편차 (None 시 자동 연산).

    Returns:
        float: 0.0을 방어한 안전한 타겟 표준편차 수치.
    """
    if provided_std is not None and provided_std > 0.0 and np.isfinite(provided_std):
        return float(provided_std)

    # 유효값(Finite)만을 대상으로 표준편차 산출 및 분모 0 방어
    finite_targets = y_true[np.isfinite(y_true)]
    if len(finite_targets) < 2:
        return 1.0

    calculated_std = float(np.std(finite_targets, ddof=1))
    return calculated_std if (calculated_std > 0.0 and np.isfinite(calculated_std)) else 1.0