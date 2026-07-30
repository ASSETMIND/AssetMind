"""
[AssetMind 모델링 계층의 모든 단일 및 앙상블 ML/DL 모델이 준수해야 하는 최상위 추상 규격 인터페이스 모듈]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 상위 파이프라인/서비스 계층으로부터 주입되는 정제된 학습/평가 데이터셋(X_train, y_train, X_test, y_test) 및 하이퍼파라미터 설정 객체.
2. Interface Contract Enforcement: 하위 구체 모델 클래스(Ridge, XGBoost, Random Forest, LSTM, Ensemble)가 fit, predict, evaluate, get_feature_importance, calculate_shap_values, save_artifact, load_artifact 계약을 엄격히 이행하도록 구조적 강제.
3. Dimension & Index Alignment: 추론(predict) 및 평가(evaluate) 단계에서 입력 데이터프레임의 행 인덱스(Index) 정렬 및 차원 보존 상태를 검증 및 유지.
4. Output: 학습이 완료된 모델 객체 자신(self), 원본 인덱스와 정렬된 예측 시리즈(pd.Series), 평가 지표 딕셔너리(Dict[str, float]), Feature Importance 시리즈(pd.Series), SHAP 행렬(np.ndarray) 반환.

주요 기능:
- Architectural Standardization: 모든 알고리즘(회귀, 트리, 딥러닝, 앙상블)의 인터페이스를 일원화하여 상위 오케스트레이터 및 팩토리 레이어와의 결합도를 최소화함.
- Defensive State Management: is_fitted 플래그 기반의 상태 검증 체계를 통해 미학습 인스턴스의 잘못된 추론 및 XAI 계산 시도를 사전에 차단하고 커스텀 예외(ModelNotFittedError)를 명시적으로 전파함.
- Vectorized Evaluation Metric Suite: 판다스/넘파이 벡터화 연산을 활용하여 RMSE, MAE, MDA(Mean Directional Accuracy) 지표를 원스톱으로 정확하게 산출함.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 추상 클래스(ABC) 기반 공통 규격 강제 및 공통 평가/검증 메서드 내장 vs 개별 모델 클래스 독자 구현:
  - 장점: 파이프라인 및 서비스 계층이 구체적인 ML 알고리즘의 내부 구현을 알 필요 없이 동일한 계약 메서드만 호출할 수 있어 완벽한 다형성(Polymorphism)과 개방 폐쇄 원칙(OCP)을 실현함.
  - 단점: 신규 알고리즘 추가 시 규격에 정의된 7개 추상 메서드를 반드시 모두 구현해야 하므로 초기 개발 오버헤드가 발생함.
  - 근거: 본 시스템은 18종의 파생 데이터셋과 다수 알고리즘을 평가하는 2-Stage HPO 및 Champion-Challenger 백테스팅 구조를 채택함. 모델 간 인터페이스 파편화를 허용할 경우 백테스팅 및 서빙 단계에서 차원 정렬 파괴나 런타임 타입 오류가 발생하므로 하드 인터페이스 계약을 강제하는 것이 시스템 안정성에 필수적임.
"""

# ==============================================================================
# Imports
# ==============================================================================
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, Tuple, Union
import numpy as np
import pandas as pd

from src.common.exceptions import (
    ModelNotFittedError,
    ModelTrainingExecutionError,
    ModelEvaluationExecutionError,
    ModelArtifactError,
    ShapCalculationError,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_MODEL_NAME: str = "AbstractRegressor"


# ==============================================================================
# Main Abstract Class
# ==============================================================================
class AbstractRegressor(ABC):
    """AssetMind 머신러닝/딥러닝 알고리즘 컴포넌트의 최상위 추상 클래스.

    모든 단일 모델(Ridge, XGBoost, Random Forest, LSTM) 및 앙상블 모델은
    본 클래스를 상속받아 명시된 추상 메서드를 반드시 구현해야 합니다.

    Attributes:
        model_name (str): 모델 인스턴스의 식별 명칭.
        is_fitted (bool): 모델의 학습 완료 여부를 나타내는 방어적 상태 플래그.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        """AbstractRegressor 인스턴스를 초기화합니다.

        Args:
            model_name (str): 모델 식별 명칭. 기본값은 DEFAULT_MODEL_NAME.
        """
        # [설계 의도] 모델 식별명 및 미학습 상태 추적을 위한 초기 상태 플래그 바인딩
        self.model_name: str = model_name
        self.is_fitted: bool = False

    # --------------------------------------------------------------------------
    # Abstract Methods (하위 구현체 필수 계약)
    # --------------------------------------------------------------------------
    @abstractmethod
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        **hyperparameters: Any,
    ) -> "AbstractRegressor":
        """입력된 학습 데이터셋 및 하이퍼파라미터를 기반으로 모델 학습을 수행합니다.

        [Validation 데이터 주입 가이드]
        XGBoost, PyTorch LSTM 등 조기 종료(Early Stopping)에 Validation 세트가 필요한 모델의 경우,
        **hyperparameters를 통해 'eval_set=(X_val, y_val)' 형태로 동적 주입받아 처리합니다.

        Args:
            X_train (pd.DataFrame): 학습용 피처 데이터프레임.
            y_train (pd.Series): 학습용 정답 타겟 시계열.
            **hyperparameters (Any): 모델 알고리즘별 동적 하이퍼파라미터 키-값 쌍.

        Returns:
            AbstractRegressor: 학습이 완료된 모델 객체 자신(self).

        Raises:
            ModelTrainingExecutionError: 학습 중 데이터 타입 불일치, 수리적 발산 또는 알고리즘 실패 발생 시.
        """
        pass

    @abstractmethod
    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """주어진 피처 데이터셋에 대해 모델 예측을 수행합니다.

        [차원 보존 제약] 반환되는 pd.Series는 입력 X_test의 행 Index와
        완벽히 정렬되어야 합니다.

        Args:
            X_test (pd.DataFrame): 추론 대상 피처 데이터프레임.

        Returns:
            pd.Series: 입력 인덱스가 유지된 예측값 시계열 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
        """
        pass

    @abstractmethod
    def get_feature_importance(self) -> pd.Series:
        """학습된 모델의 Feature Importance 또는 회귀 계수(Coefficients)를 산출합니다.

        Returns:
            pd.Series: 피처명을 인덱스로 가지고 중요도 수치를 값으로 가지는 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
        """
        pass

    @abstractmethod
    def calculate_shap_values(self, X_sample: pd.DataFrame) -> np.ndarray:
        """XAI 분석을 위해 입력 샘플 데이터셋에 대한 SHAP Value를 계산합니다.

        Args:
            X_sample (pd.DataFrame): SHAP 값 산출 대상 입력 샘플 데이터프레임.

        Returns:
            np.ndarray: 피처별 SHAP 기여도 수치가 담긴 2차원 또는 3차원 넘파이 배열.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ShapCalculationError: SHAP Explainer 연산 중 실패 발생 시.
        """
        pass

    @abstractmethod
    def save_artifact(self, model_artifact_path: str) -> None:
        """학습된 모델 아티팩트(.pkl, .pt 등)를 지정된 파일 시스템 경로에 저장합니다.

        Args:
            model_artifact_path (str): 아티팩트를 물리적으로 저장할 파일 경로.

        Raises:
            ModelNotFittedError: 미학습 모델을 저장하려 할 경우.
            ModelArtifactError: 파일 I/O 또는 직렬화 실패 발생 시.
        """
        pass

    @abstractmethod
    def load_artifact(self, model_artifact_path: str) -> "AbstractRegressor":
        """지정된 파일 경로로부터 학습된 모델 아티팩트를 로드하여 객체 상태를 복원합니다.

        Args:
            model_artifact_path (str): 로드할 아티팩트 파일 경로.

        Returns:
            AbstractRegressor: 아티팩트가 로드되어 복원된 모델 인스턴스 자신(self).

        Raises:
            ModelArtifactError: 파일 존재 부재, 역직렬화 실패 또는 아티팩트 무결성 손상 시.
        """
        pass

    # --------------------------------------------------------------------------
    # Concrete Shared Methods (공통 공용 메서드)
    # --------------------------------------------------------------------------
    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series,
    ) -> Dict[str, float]:
        """모델의 추론 성능을 RMSE, MAE, MDA(Mean Directional Accuracy) 지표로 산출합니다.

        Args:
            X_test (pd.DataFrame): 성능 평가용 테스트 피처 데이터셋.
            y_test (pd.Series): 성능 평가용 테스트 정답 타겟 시계열 데이터.

        Returns:
            Dict[str, float]: RMSE, MAE, MDA 지표 명칭을 키로 하고 계산된 수치를 값으로 가지는 딕셔너리.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ModelEvaluationExecutionError: 입력 데이터 정합성 결여 또는 계산 중 오류 발생 시.
        """
        # 미학습 모델 호출 상태 검증
        self._validate_fitted_state(operation_name="evaluate")

        # 데이터 입력 정합성 검증
        if X_test.empty or y_test.empty:
            raise ModelEvaluationExecutionError(
                message="평가를 위한 입력 테스트 데이터셋이 비어 있습니다.",
                model_name=self.model_name,
            )

        if len(X_test) != len(y_test):
            raise ModelEvaluationExecutionError(
                message="테스트 피처 데이터와 타겟 데이터의 행 개수가 일치하지 않습니다.",
                model_name=self.model_name,
                y_true_shape=y_test.shape,
                y_pred_shape=(len(X_test),),
            )

        try:
            # [설계 의도] 추론을 통해 인덱스가 정렬된 예측값 시리즈 도출
            prediction_result: pd.Series = self.predict(X_test)

            # [설계 의도] RMSE 및 MAE 산출 (판다스/넘파이 벡터화 연산 적용)
            error_series: pd.Series = y_test - prediction_result
            root_mean_squared_error: float = float(
                np.sqrt(np.mean(np.square(error_series)))
            )
            mean_absolute_error: float = float(np.mean(np.abs(error_series)))

            # [설계 의도] 금융 시계열 필수 지표인 MDA(Mean Directional Accuracy) 산출
            # 직전 시점(t-1) 대비 실제 변동 방향과 모델이 예측한 변동 방향의 일치 비율 계산
            actual_directional_change: pd.Series = np.sign(
                y_test - y_test.shift(1)
            ).iloc[1:]
            predicted_directional_change: pd.Series = np.sign(
                prediction_result - y_test.shift(1)
            ).iloc[1:]

            if len(actual_directional_change) == 0:
                mean_directional_accuracy: float = 0.0
            else:
                directional_match_series: pd.Series = (
                    actual_directional_change == predicted_directional_change
                )
                mean_directional_accuracy = float(
                    np.mean(directional_match_series)
                )

            evaluation_metrics: Dict[str, float] = {
                "RMSE": root_mean_squared_error,
                "MAE": mean_absolute_error,
                "MDA": mean_directional_accuracy,
            }
            return evaluation_metrics

        except Exception as error:
            if isinstance(
                error, (ModelNotFittedError, ModelEvaluationExecutionError)
            ):
                raise error
            raise ModelEvaluationExecutionError(
                message=f"평가 지표 산출 중 예기치 못한 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                y_true_shape=y_test.shape,
                y_pred_shape=prediction_result.shape
                if "prediction_result" in locals()
                else None,
                original_exception=error,
            )

    # --------------------------------------------------------------------------
    # Protected Helper Methods (내부 검증 메서드)
    # --------------------------------------------------------------------------
    def _validate_fitted_state(self, operation_name: str) -> None:
        """모델 인스턴스의 학습 완료 여부를 검증합니다.

        Args:
            operation_name (str): 실행을 시도하는 메서드/작업 명칭.

        Raises:
            ModelNotFittedError: is_fitted 플래그가 False인 미학습 상태일 때 발생.
        """
        # [설계 의도] 미학습 상태에서 추론/평가/XAI 연산을 시도하는 정적 오류 흐름을 사전에 방어
        if not self.is_fitted:
            raise ModelNotFittedError(
                message=f"'{self.model_name}' 모델이 아직 학습되지 않았습니다. '{operation_name}()' 실행 전 'fit()'을 먼저 호출하세요.",
                model_name=self.model_name,
                operation_type=operation_name,
            )