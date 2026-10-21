import copy
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from src.model.core.abstract_regressor import AbstractRegressor
from src.model.evaluation import metrics


# ==============================================================================
# Main Class/Functions
# ==============================================================================

class EnsembleRegressor(AbstractRegressor):
    """다종 이종 회귀 모델의 가중 결합(Weighted Blending) 추론을 전담하는 앙상블 모델 클래스입니다.

    Attributes:
        models (Dict[str, AbstractRegressor]): 앙상블에 참여하는 기저 모델 인스턴스 딕셔너리.
        weights (Dict[str, float]): 기저 모델별 정규화된 가중치 딕셔너리.
        is_fitted (bool): 앙상블 모델의 학습 완료 여부.
    """

    def __init__(
        self,
        models: Dict[str, AbstractRegressor],
        weights: Dict[str, float]
    ) -> None:
        """EnsembleRegressor 인스턴스를 초기화합니다.

        Args:
            models (Dict[str, AbstractRegressor]): 모델명을 키로 하는 기저 모델 객체 딕셔너리.
            weights (Dict[str, float]): 모델명을 키로 하는 결합 가중치 딕셔너리.

        Raises:
            ValueError: 모델 딕셔너리가 비어있거나 모델과 가중치의 키가 일치하지 않는 경우 발생.
        """
        # [설계 의도] 앙상블을 구성할 기저 모델이 존재하지 않는 잘못된 초기화 선제 차단
        if not models:
            raise ValueError("앙상블을 구성하기 위한 기저 모델(models)이 최소 1개 이상 필요합니다.")

        # [설계 의도] 모델 명단과 가중치 명단의 불일치로 인한 런타임 누락 결함 방어
        if set(models.keys()) != set(weights.keys()):
            raise ValueError(
                f"기저 모델 명단과 가중치 명단이 일치하지 않습니다. "
                f"(models: {list(models.keys())}, weights: {list(weights.keys())})"
            )

        # [설계 의도] 외부 원본 객체의 의도치 않은 상태 변이를 방지하기 위해 딥카피 수행
        self.models: Dict[str, AbstractRegressor] = copy.deepcopy(models)
        self.weights: Dict[str, float] = self._normalize_weights(weights=weights)
        self.is_fitted: bool = all(getattr(model, "is_fitted", False) for model in self.models.values())

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series
    ) -> EnsembleRegressor:
        """캡슐화된 모든 서브 기저 모델을 학습 데이터셋으로 순차 재학습(Full Refit)합니다.

        Args:
            X_train (pd.DataFrame): 훈련용 피처 행렬.
            y_train (pd.Series): 훈련용 타겟 시계열 벡터.

        Returns:
            EnsembleRegressor: 전체 서브 모델 학습이 완료된 앙상블 인스턴스 자신.
        """
        # [설계 의도] 가중 블렌딩의 모든 기저 모델을 동일한 80% 전체 학습 데이터로 동기화 학습
        for model_name, model_instance in self.models.items():
            model_instance.fit(X_train=X_train, y_train=y_train)

        self.is_fitted = True
        return self

    def predict(
        self,
        X_test: pd.DataFrame
    ) -> np.ndarray:
        """모든 서브 기저 모델의 개별 예측값을 산출한 후 최적 가중치로 선형 결합한 최종 예측값을 반환합니다.

        Args:
            X_test (pd.DataFrame): 추론 대상 피처 행렬.

        Returns:
            np.ndarray: 가중 합산된 최종 1차원 예측값 넘파이 배열.

        Raises:
            RuntimeError: 서브 모델 중 미학습 상태의 모델이 존재할 경우 발생.
        """
        # [설계 의도] 미학습 상태에서의 비정상 추론 방지 (Fail-Fast)
        if not self.is_fitted:
            raise RuntimeError("앙상블 모델이 학습되지 않았습니다. predict() 호출 전 fit()을 먼저 실행하십시오.")

        weighted_prediction_accumulator: Optional[np.ndarray] = None

        # [설계 의도] 각 기저 모델의 예측값에 정규화 가중치를 곱하여 누적 합산 (y_hat = sum(w_i * y_hat_i))
        for model_name, model_instance in self.models.items():
            model_weight: float = self.weights[model_name]
            individual_predictions: np.ndarray = np.asarray(
                model_instance.predict(X_test=X_test),
                dtype=np.float64
            ).flatten()

            if weighted_prediction_accumulator is None:
                weighted_prediction_accumulator = model_weight * individual_predictions
            else:
                weighted_prediction_accumulator += model_weight * individual_predictions

        return weighted_prediction_accumulator

    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict[str, float]:
        """앙상블 예측값에 대해 핵심 회귀 및 방향성 평가 지표를 산출합니다.

        Args:
            X_test (pd.DataFrame): 테스트 세트 피처 행렬.
            y_test (pd.Series): 테스트 세트 실제 타겟 벡터.

        Returns:
            Dict[str, float]: MDA, RMSE, MAE 메트릭 딕셔너리.
        """
        predictions: np.ndarray = self.predict(X_test=X_test)
        actual_targets: np.ndarray = y_test.to_numpy(dtype=np.float64).flatten()

        return {
            "MDA": float(metrics.mda(actual_targets, predictions)),
            "RMSE": float(metrics.rmse(actual_targets, predictions)),
            "MAE": float(metrics.mae(actual_targets, predictions))
        }

    def calculate_shap_values(
        self,
        X_sample: pd.DataFrame
    ) -> np.ndarray:
        """하위 서브 모델들의 개별 SHAP 기여도 행렬을 추출하고 가중 선형 결합하여 앙상블 통합 SHAP 행렬을 생성합니다.

        Args:
            X_sample (pd.DataFrame): SHAP 해석 대상 피처 행렬.

        Returns:
            np.ndarray: 앙상블 가중 결합된 2차원 통합 SHAP 값 행렬.

        Raises:
            RuntimeError: 서브 모델 중 SHAP 산출 메서드를 지원하지 않는 모델이 존재할 경우 발생.
        """
        # [설계 의도] 이종 앙상블의 선형 결합 속성을 활용하여 통합 SHAP 값 산출 (Phi_ensemble = sum(w_i * Phi_i))
        combined_shap_accumulator: Optional[np.ndarray] = None

        for model_name, model_instance in self.models.items():
            model_weight: float = self.weights[model_name]
            
            if not hasattr(model_instance, "calculate_shap_values"):
                raise RuntimeError(f"서브 모델 '{model_name}'은 calculate_shap_values 메서드를 지원하지 않습니다.")

            individual_shap_values: np.ndarray = np.asarray(
                model_instance.calculate_shap_values(X_sample=X_sample),
                dtype=np.float64
            )

            if combined_shap_accumulator is None:
                combined_shap_accumulator = model_weight * individual_shap_values
            else:
                combined_shap_accumulator += model_weight * individual_shap_values

        return combined_shap_accumulator

    def _normalize_weights(
        self,
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """주입된 가중치의 합이 1.0이 되도록 정규화하고 음수 가중치를 0으로 클리핑합니다.

        Args:
            weights (Dict[str, float]): 원시 가중치 딕셔너리.

        Returns:
            Dict[str, float]: 합이 1.0으로 정규화된 가중치 딕셔너리.
        """
        # [설계 의도] 앙상블 안정성을 위해 음수 가중치를 차단하고 Simplex 제약(sum(w)=1.0) 충족
        clipped_weights: Dict[str, float] = {
            model_name: max(0.0, float(weight_value))
            for model_name, weight_value in weights.items()
        }
        total_weight_sum: float = sum(clipped_weights.values())

        if total_weight_sum == 0.0:
            equal_weight_value: float = 1.0 / len(clipped_weights)
            return {model_name: equal_weight_value for model_name in clipped_weights}

        return {
            model_name: weight_value / total_weight_sum
            for model_name, weight_value in clipped_weights.items()
        }