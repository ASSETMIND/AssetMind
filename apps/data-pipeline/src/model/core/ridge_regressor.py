"""
[L2 규제 기반 선형 회귀 알고리즘을 캡슐화한 Ridge 추정기 구체 클래스 모듈]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 생성자(__init__)를 통해 주입되는 하이퍼파라미터 딕셔너리(**hyperparameters) 및 fit() 메서드로 유입되는 학습 데이터셋(X_train, y_train).
2. Model Execution: __init__ 내부에서 하이퍼파라미터를 개별 멤버 변수로 언패킹하여 바인딩 후, scikit-learn Ridge 추정기 생성 및 피팅 연산 집행.
3. Index & Dimension Alignment: 추론(predict) 결과 수치를 원본 입력 X_test의 행 인덱스(Index)와 완벽하게 정렬하여 pd.Series 구조로 사출.
4. Output: 학습된 RidgeRegressor 인스턴스, 정렬된 예측 시계열(pd.Series), 피처별 회귀 계수(pd.Series), SHAP 기여도 배열(np.ndarray), 저장/로드 아티팩트 파일.

주요 기능:
- Config-Friendly Parameter Unpacking: 생성자 단에서 **hyperparameters 인자를 수용하여 내부 개별 인스턴스 변수로 파싱 및 사전 바인딩함으로써 YAML 및 Optuna 딕셔너리와의 호환성 극대화.
- L2 Regularization Regression: 다변량 금융 시계열 피처 간 다중공선성(Multicollinearity) 문제를 완화하고 과적합을 방지하는 L2 규제 회귀 모델 제공.
- SHAP LinearExplainer Integration: shap.LinearExplainer를 연동하여 선형 회귀 계수 및 피처간 상호작용에 기반한 XAI(설명 가능한 AI) 수치 추출.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 생성자에서 **hyperparameters 수용 후 내부 변수 분리 저장 vs 명시적 키워드 인자 선언:
  - 장점: Optuna Trial 파라미터나 외부 yml 설정 딕셔너리를 언패킹(**)하여 그대로 주입할 수 있어 팩토리 및 HPO 오케스트레이터와의 결합도가 극도로 낮아짐.
  - 단점: IDE의 자동완성이나 static type checker(mypy)가 기본 매개변수 목록을 시그니처 수준에서 즉시 감지하지 못하므로 Docstring 문서화에 의존해야 함.
  - 근거: 본 프로젝트는 외부 설정 기반(Config-Data-Driven) 및 Optuna 2-Stage HPO 파이프라인으로 구동됨. 동적으로 변하는 파라미터 조합을 유연하게 수용하는 것이 시스템 확장성에 훨씬 유리함.
"""

# ==============================================================================
# Imports
# ==============================================================================
import os
from typing import Dict, Optional, Any, List
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
import shap

from src.model.core.abstract_regressor import AbstractRegressor
from src.common.exceptions import (
    ModelNotFittedError,
    ModelTrainingExecutionError,
    ModelArtifactError,
    ShapCalculationError,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_MODEL_NAME: str = "RidgeRegressor"


# ==============================================================================
# Main Regressor Class
# ==============================================================================
class RidgeRegressor(AbstractRegressor):
    """L2 규제(Ridge) 선형 회귀 알고리즘 구체 클래스.

    Attributes:
        model_name (str): 모델 인스턴스의 식별 명칭.
        is_fitted (bool): 모델의 학습 완료 여부를 나타내는 방어적 상태 플래그.
        alpha (float): L2 정규화 가중치 수치.
        solver (str): 최적화 계산 알고리즘 solver.
        fit_intercept (bool): 절편(Intercept) 학습 여부.
        random_state (Optional[int]): 난수 고정 시드값.
        feature_names (Optional[List[str]]): 학습 시 주입된 피처 컬럼명 목록.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        **hyperparameters: Any,
    ) -> None:
        """RidgeRegressor 인스턴스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 식별 명칭. 기본값은 DEFAULT_MODEL_NAME.
            **hyperparameters (Any): alpha, solver, fit_intercept, random_state 등 Ridge 하이퍼파라미터 키-값 쌍.
        """
        # [설계 의도] 상위 추상 클래스 생성자를 호출하여 공통 식별명 및 상태 플래그 바인딩
        super().__init__(model_name=model_name)

        # [설계 의도] 외부 딕셔너리로 주입된 하이퍼파라미터들을 개별 인스턴스 변수로 파싱 및 기본값 설정
        self.alpha: float = float(hyperparameters.get("alpha", 1.0))
        self.solver: str = str(hyperparameters.get("solver", "auto"))
        self.fit_intercept: bool = bool(hyperparameters.get("fit_intercept", True))
        self.random_state: Optional[int] = hyperparameters.get("random_state", 42)

        self._internal_model: Optional[Ridge] = None
        self.feature_names: Optional[List[str]] = None

    # --------------------------------------------------------------------------
    # Abstract Method Implementations (추상 메서드 구체 구현)
    # --------------------------------------------------------------------------
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> "RidgeRegressor":
        """인스턴스 생성 시 바인딩된 하이퍼파라미터를 바탕으로 Ridge 회귀 모델 학습을 수행합니다.

        Args:
            X_train (pd.DataFrame): 학습용 피처 데이터프레임.
            y_train (pd.Series): 학습용 정답 타겟 시계열.

        Returns:
            RidgeRegressor: 학습이 완료된 모델 객체 자신(self).

        Raises:
            ModelTrainingExecutionError: 입력 데이터셋 부재, 행 개수 불일치 또는 scikit-learn 피팅 연산 실패 시.
        """
        # [방어적 프로그래밍] 입력 데이터셋 무결성 사전 검증
        if X_train.empty or y_train.empty:
            raise ModelTrainingExecutionError(
                message="학습을 위한 입력 데이터셋(X_train 또는 y_train)이 비어 있습니다.",
                model_name=self.model_name,
            )

        if len(X_train) != len(y_train):
            raise ModelTrainingExecutionError(
                message="학습 피처 데이터(X_train)와 타겟 데이터(y_train)의 행 개수가 일치하지 않습니다.",
                model_name=self.model_name,
            )

        try:
            # [설계 의도] __init__에서 사전 바인딩된 개별 파라미터 변수들을 활용하여 scikit-learn Ridge 피팅
            self._internal_model = Ridge(
                alpha=self.alpha,
                solver=self.solver,
                fit_intercept=self.fit_intercept,
                random_state=self.random_state,
            )
            self._internal_model.fit(X_train, y_train)

            # [설계 의도] 피처 정렬 검증 및 XAI/중요도 산출을 위해 피처 컬럼명을 저장하고 학습 완료 플래그 전환
            self.feature_names = list(X_train.columns)
            self.is_fitted = True

            return self

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"Ridge 모델 학습 진행 중 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                hyperparameters={
                    "alpha": self.alpha,
                    "solver": self.solver,
                    "fit_intercept": self.fit_intercept,
                },
                original_exception=error,
            )

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """주어진 피처 데이터셋에 대해 Ridge 회귀 예측을 수행합니다.

        [차원 보존 제약] 반환되는 pd.Series는 입력 X_test의 행 Index와 완벽히 정렬됩니다.

        Args:
            X_test (pd.DataFrame): 추론 대상 피처 데이터프레임.

        Returns:
            pd.Series: 입력 X_test의 인덱스가 유지된 예측 결과 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ModelTrainingExecutionError: 추론 연산 실패 시.
        """
        # [방어적 프로그래밍] 미학습 상태 진입 차단
        self._validate_fitted_state(operation_name="predict")

        if X_test.empty:
            raise ModelTrainingExecutionError(
                message="추론을 위한 입력 데이터셋(X_test)이 비어 있습니다.",
                model_name=self.model_name,
            )

        try:
            # [설계 의도] scikit-learn predict 실행 후 결과 배열을 입력 X_test의 행 인덱스와 완벽히 결합하여 사출
            raw_predictions: np.ndarray = self._internal_model.predict(X_test)
            prediction_series: pd.Series = pd.Series(
                data=raw_predictions,
                index=X_test.index,
                name="target_prediction",
            )
            return prediction_series

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"Ridge 모델 추론 중 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            )

    def get_feature_importance(self) -> pd.Series:
        """학습된 Ridge 회귀 모델의 회귀 계수(Coefficients)를 산출합니다.

        Returns:
            pd.Series: 피처명을 인덱스로 가지고 회귀 계수 수치를 값으로 가지는 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
        """
        # [방어적 프로그래밍] 미학습 상태 진입 차단
        self._validate_fitted_state(operation_name="get_feature_importance")

        # [설계 의도] 선형 회귀 모델의 계수(coef_)를 피처명 인덱스와 매핑하여 시리즈로 반환
        coefficients: np.ndarray = self._internal_model.coef_
        feature_importance_series: pd.Series = pd.Series(
            data=coefficients,
            index=self.feature_names,
            name="feature_coefficient",
        )
        return feature_importance_series

    def calculate_shap_values(self, X_sample: pd.DataFrame) -> np.ndarray:
        """XAI 분석을 위해 입력 샘플 데이터셋에 대한 SHAP Value를 계산합니다.

        Args:
            X_sample (pd.DataFrame): SHAP 기여도 산출 대상 피처 데이터프레임.

        Returns:
            np.ndarray: 피처별 SHAP 기여 수치가 담긴 2차원 넘파이 배열.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ShapCalculationError: LinearExplainer 연산 실패 시.
        """
        # [방어적 프로그래밍] 미학습 상태 진입 차단
        self._validate_fitted_state(operation_name="calculate_shap_values")

        if X_sample.empty:
            raise ShapCalculationError(
                message="SHAP 수치 계산을 위한 샘플 데이터셋(X_sample)이 비어 있습니다.",
                model_name=self.model_name,
                explainer_type="LinearExplainer",
            )

        try:
            # [설계 의도] 선형 회귀에 최적화된 shap.LinearExplainer를 구동하여 빠르게 SHAP Value 산출
            explainer: shap.LinearExplainer = shap.LinearExplainer(
                model=self._internal_model,
                masker=X_sample,
            )
            shap_explanation = explainer(X_sample)
            shap_values_array: np.ndarray = shap_explanation.values

            return shap_values_array

        except Exception as error:
            raise ShapCalculationError(
                message=f"Ridge SHAP 수치 계산 중 예기치 못한 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                explainer_type="LinearExplainer",
                original_exception=error,
            )

    def save_artifact(self, model_artifact_path: str) -> None:
        """학습된 Ridge 모델 및 메타데이터 아티팩트를 지정된 경로에 직렬화 저장합니다.

        Args:
            model_artifact_path (str): 아티팩트 파일(.pkl) 저장 물리 경로.

        Raises:
            ModelNotFittedError: 미학습 모델을 저장하려 할 경우.
            ModelArtifactError: 디렉터리 생성 실패 또는 직렬화 장애 발생 시.
        """
        # [방어적 프로그래밍] 미학습 상태 저장 시도 차단
        self._validate_fitted_state(operation_name="save_artifact")

        try:
            # [설계 의도] 저장 대상 디렉터리가 부재할 경우 자동으로 디렉터리 생성 처리
            artifact_directory: str = os.path.dirname(model_artifact_path)
            if artifact_directory and not os.path.exists(artifact_directory):
                os.makedirs(artifact_directory, exist_ok=True)

            # [설계 의도] 모델 객체, 하이퍼파라미터 및 학습 상태 플래그를 딕셔너리로 묶어 안전하게 직렬화
            artifact_payload: Dict[str, Any] = {
                "internal_model": self._internal_model,
                "feature_names": self.feature_names,
                "is_fitted": self.is_fitted,
                "model_name": self.model_name,
                "hyperparameters": {
                    "alpha": self.alpha,
                    "solver": self.solver,
                    "fit_intercept": self.fit_intercept,
                    "random_state": self.random_state,
                },
            }
            joblib.dump(artifact_payload, model_artifact_path)

        except Exception as error:
            raise ModelArtifactError(
                message=f"Ridge 아티팩트 저장 실패 ({model_artifact_path}): {str(error)}",
                artifact_path=model_artifact_path,
                operation_type="save",
                original_exception=error,
            )

    def load_artifact(self, model_artifact_path: str) -> "RidgeRegressor":
        """지정된 파일 경로로부터 Ridge 모델 아티팩트를 로드하여 인스턴스 상태를 복원합니다.

        Args:
            model_artifact_path (str): 로드할 아티팩트 파일 경로.

        Returns:
            RidgeRegressor: 복원된 모델 인스턴스 자신(self).

        Raises:
            ModelArtifactError: 파일 부재, 역직렬화 실패 시.
        """
        if not os.path.exists(model_artifact_path):
            raise ModelArtifactError(
                message=f"지정된 아티팩트 파일을 찾을 수 없습니다: {model_artifact_path}",
                artifact_path=model_artifact_path,
                operation_type="load",
            )

        try:
            # [설계 의도] joblib 역직렬화를 진행하고 내부 멤버 변수 상태를 완전히 복원
            artifact_payload: Dict[str, Any] = joblib.load(model_artifact_path)

            self._internal_model = artifact_payload.get("internal_model")
            self.feature_names = artifact_payload.get("feature_names")
            self.is_fitted = artifact_payload.get("is_fitted", True)
            self.model_name = artifact_payload.get("model_name", self.model_name)

            hyperparameters: Dict[str, Any] = artifact_payload.get("hyperparameters", {})
            self.alpha = hyperparameters.get("alpha", self.alpha)
            self.solver = hyperparameters.get("solver", self.solver)
            self.fit_intercept = hyperparameters.get("fit_intercept", self.fit_intercept)
            self.random_state = hyperparameters.get("random_state", self.random_state)

            return self

        except Exception as error:
            raise ModelArtifactError(
                message=f"Ridge 아티팩트 로드 실패 ({model_artifact_path}): {str(error)}",
                artifact_path=model_artifact_path,
                operation_type="load",
                original_exception=error,
            )