"""
[AssetMind 모델링 계층의 ElasticNet(L1 + L2 정규화 선형 회귀) 알고리즘을 캡슐화한 추정기 구체 클래스 모듈]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 생성자(__init__)를 통해 주입되는 하이퍼파라미터 딕셔너리(**hyperparameters) 및 fit() 메서드로 유입되는 정규화된 학습 데이터셋(X_train, y_train).
2. Model Execution: __init__ 내부에서 하이퍼파라미터를 개별 멤버 변수로 언패킹하여 바인딩 후, scikit-learn ElasticNet 추정기 인스턴스화 및 L1/L2 복합 정규화 피팅 연산 집행.
3. Index & Dimension Alignment: 추론(predict) 결과 수치를 원본 입력 X_test의 행 인덱스(Index)와 완벽하게 정렬하여 pd.Series 구조로 사출.
4. Output: 학습된 ElasticNetRegressor 인스턴스, 정렬된 예측 시계열(pd.Series), 피처별 절대 회귀 계수(pd.Series), SHAP 기여도 배열(np.ndarray), 저장/로드 아티팩트 파일.

주요 기능:
- Config-Friendly Parameter Unpacking: 생성자 단에서 **hyperparameters 인자를 수용하여 내부 개별 인스턴스 변수로 파싱 및 사전 바인딩함으로써 YAML 및 Optuna 딕셔너리와의 호환성 극대화.
- L1 + L2 Hybrid Regularization: L1 정규화를 통한 불필요한 노이즈 팩터 희소화(Sparsity)와 L2 정규화를 통한 상관 팩터군 보존(Grouping Effect)을 동시에 달성.
- SHAP LinearExplainer Integration: shap.LinearExplainer를 연동하여 선형 회귀 계수 및 피처별 한계 기여도(Marginal Contribution) 수치 산출.
- Dimension Preservation: AbstractRegressor 계약에 따라 모든 출력 시리즈의 원본 행 인덱스 및 차원 일치성 보장.

Trade-off:
- 비선형 상호작용 포착에는 한계가 있으나, 다중공선성이 존재하는 고차원 금융 시계열 환경에서 과적합을 극도로 억제하고 안정적인 매크로 선형 신호를 학습함.
"""

import os
from typing import Any, Dict, List, Optional, Union
import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.linear_model import ElasticNet

from src.common.exceptions import (
    ModelArtifactError,
    ModelNotFittedError,
    ModelTrainingExecutionError,
    ShapCalculationError,
)
from src.model.core.abstract_regressor import AbstractRegressor


class ElasticNetRegressor(AbstractRegressor):
    """L1(Lasso) 및 L2(Ridge) 정규화를 결합한 ElasticNet 선형 회귀 모델 래퍼 클래스입니다.

    Attributes:
        alpha (float): 전체 규제 강도 페널티 파라미터.
        l1_ratio (float): L1 규제 혼합 비율 (0.0=순수 Ridge, 1.0=순수 Lasso).
        fit_intercept (bool): 절편(상수항) 학습 여부.
        max_iter (int): 좌표 하강법(Coordinate Descent) 최대 반복 횟수.
        tol (float): 최적화 수렴 허용 오차.
        random_state (int): 좌표 선택 난수 시드.
        selection (str): 좌표 순회 방식 ('cyclic' 또는 'random').
    """

    def __init__(self, **hyperparameters: Any) -> None:
        """ElasticNetRegressor 인스턴스를 초기화하고 하이퍼파라미터를 언패킹합니다.

        Args:
            **hyperparameters (Any): 모델 초기화 파라미터 딕셔너리.
        """
        # [설계 의도] 부모 클래스(AbstractRegressor)에 고유 모델명 등록
        super().__init__(model_name="ElasticNet")

        # [설계 의도] 하이퍼파라미터 개별 멤버 변수 언패킹 및 기본값 바인딩
        self.alpha: float = float(hyperparameters.get("alpha", 1.0))
        self.l1_ratio: float = float(hyperparameters.get("l1_ratio", 0.5))
        self.fit_intercept: bool = bool(hyperparameters.get("fit_intercept", True))
        self.max_iter: int = int(hyperparameters.get("max_iter", 3000))
        self.tol: float = float(hyperparameters.get("tol", 1e-4))
        self.random_state: int = int(hyperparameters.get("random_state", 42))
        self.selection: str = str(hyperparameters.get("selection", "random"))

        self._internal_model: Optional[ElasticNet] = None

    # --------------------------------------------------------------------------
    # Core Lifecycle Methods (핵심 수명주기 메서드)
    # --------------------------------------------------------------------------
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        **hyperparameters: Any,
    ) -> "ElasticNetRegressor":
        """정규화된 학습 데이터셋에 대해 ElasticNet 회귀 모델을 학습시킵니다.

        Args:
            X_train (pd.DataFrame): 학습 피처 데이터프레임.
            y_train (pd.Series): 정답 타겟 시계열.
            **hyperparameters (Any): 런타임에 동적으로 재정의할 하이퍼파라미터.

        Returns:
            ElasticNetRegressor: 학습이 완료된 객체 자신(self).

        Raises:
            ModelTrainingExecutionError: 데이터 부재 또는 학습 중 원본 수치 오류 발생 시.
        """
        if hyperparameters:
            self.alpha = float(hyperparameters.get("alpha", self.alpha))
            self.l1_ratio = float(hyperparameters.get("l1_ratio", self.l1_ratio))
            self.fit_intercept = bool(hyperparameters.get("fit_intercept", self.fit_intercept))
            self.max_iter = int(hyperparameters.get("max_iter", self.max_iter))
            self.tol = float(hyperparameters.get("tol", self.tol))
            self.random_state = int(hyperparameters.get("random_state", self.random_state))
            self.selection = str(hyperparameters.get("selection", self.selection))

        if X_train.empty or y_train.empty:
            raise ModelTrainingExecutionError(
                message="학습용 X_train 또는 y_train 데이터프레임이 비어 있어 ElasticNet 학습을 진행할 수 없습니다.",
                model_name=self.model_name,
                hyperparameters={"alpha": self.alpha, "l1_ratio": self.l1_ratio},
            )

        try:
            # [설계 의도] scikit-learn ElasticNet 추정기 인스턴스 생성 및 피팅
            self._internal_model = ElasticNet(
                alpha=self.alpha,
                l1_ratio=self.l1_ratio,
                fit_intercept=self.fit_intercept,
                max_iter=self.max_iter,
                tol=self.tol,
                random_state=self.random_state,
                selection=self.selection,
            )

            # 결측치 방어 정렬
            aligned_features: pd.DataFrame = X_train.fillna(0.0)
            aligned_target: pd.Series = y_train.loc[X_train.index].fillna(0.0)

            self._internal_model.fit(aligned_features, aligned_target)

            # 상태 플래그 및 메타데이터 업데이트
            self.feature_names = list(X_train.columns)
            self.is_fitted = True

            return self

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"ElasticNet 모델 학습 중 예기치 못한 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                hyperparameters={
                    "alpha": self.alpha,
                    "l1_ratio": self.l1_ratio,
                    "fit_intercept": self.fit_intercept,
                    "max_iter": self.max_iter,
                    "random_state": self.random_state,
                },
                original_exception=error,
            )

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """입력된 테스트 피처셋에 대해 연속형 타겟 수익률을 예측합니다.

        Args:
            X_test (pd.DataFrame): 추론 대상 피처 데이터프레임.

        Returns:
            pd.Series: X_test 행 인덱스와 1:1로 정렬된 예측 수익률 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ModelInferenceExecutionError: 추론 연산 중 차원 불일치 등의 예외 발생 시.
        """
        self._validate_fitted_state(operation_name="predict")

        if X_test.empty:
            return pd.Series(dtype=float, index=X_test.index)

        try:
            aligned_test_features: pd.DataFrame = X_test.fillna(0.0)
            raw_predictions: np.ndarray = self._internal_model.predict(aligned_test_features)

            # [차원 보존 제약] 원본 입력 X_test의 행 인덱스를 완벽하게 유지한 Series 사출
            prediction_series: pd.Series = pd.Series(
                data=raw_predictions,
                index=X_test.index,
                name=f"{self.model_name}_prediction",
            )
            return prediction_series

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"ElasticNet 모델 추론 중 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            )
    def get_feature_importance(self) -> pd.Series:
        """학습된 회귀 계수 절대값(Absolute Coefficients) 기반 피처 중요도를 반환합니다.

        Returns:
            pd.Series: 피처명을 인덱스로 하는 계수 절대값 중요도 시리즈.

        Raises:
            ModelNotFittedError: 모델 미학습 상태일 때 발생.
        """
        self._validate_fitted_state(operation_name="get_feature_importance")

        if self._internal_model is None or self.feature_names is None:
            return pd.Series(dtype=float)

        # [설계 의도] 선형 회귀 계수 절대값(|beta_j|)을 중요도 지표로 활용
        absolute_coefficients: np.ndarray = np.abs(self._internal_model.coef_)
        return pd.Series(
            data=absolute_coefficients,
            index=self.feature_names,
            name="feature_importance",
        )

    def calculate_shap_values(self, X_sample: pd.DataFrame) -> np.ndarray:
        """shap.LinearExplainer를 사용하여 입력 샘플에 대한 SHAP 기여도 행렬을 산출합니다.

        Args:
            X_sample (pd.DataFrame): SHAP 분석 대상 샘플 데이터프레임.

        Returns:
            np.ndarray: [N_samples, N_features] 차원의 SHAP 기여도 배열.

        Raises:
            ModelNotFittedError: 모델 미학습 상태일 때 발생.
            ModelInferenceExecutionError: SHAP 연산 실패 시 발생.
        """
        self._validate_fitted_state(operation_name="calculate_shap_values")

        if X_sample.empty:
            return np.array([])

        try:
            # [설계 의도] scikit-learn 선형 모델 전용 shap.LinearExplainer 활용
            aligned_sample: pd.DataFrame = X_sample.fillna(0.0)
            shap_explainer: shap.LinearExplainer = shap.LinearExplainer(
                self._internal_model,
                masker=aligned_sample,
            )
            shap_values: Union[np.ndarray, List[np.ndarray]] = shap_explainer.shap_values(aligned_sample)

            if isinstance(shap_values, list):
                shap_values_array: np.ndarray = np.array(shap_values[0])
            else:
                shap_values_array = np.array(shap_values)

            return shap_values_array

        except Exception as error:
            if isinstance(error, ModelNotFittedError):
                raise error
            raise ShapCalculationError(
                message=f"ElasticNet SHAP 기여도 산출 중 오류가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                explainer_type="LinearExplainer",
                original_exception=error,
            )

    def save_artifact(self, file_path: str) -> None:
        """학습된 ElasticNet 모델 객체 및 하이퍼파라미터 상태를 .pkl 파일로 직렬화하여 저장합니다.

        Args:
            file_path (str): 저장할 대상 파일 경로.

        Raises:
            ModelNotFittedError: 모델 미학습 상태일 때 발생.
            ModelArtifactError: I/O 쓰기 권한 또는 직렬화 실패 시 발생.
        """
        self._validate_fitted_state(operation_name="save_artifact")

        model_artifact_path: str = file_path
        directory_path: str = os.path.dirname(model_artifact_path)
        if directory_path and not os.path.exists(directory_path):
            os.makedirs(directory_path, exist_ok=True)

        try:
            artifact_payload: Dict[str, Any] = {
                "internal_model": self._internal_model,
                "feature_names": self.feature_names,
                "is_fitted": self.is_fitted,
                "model_name": self.model_name,
                "hyperparameters": {
                    "alpha": self.alpha,
                    "l1_ratio": self.l1_ratio,
                    "fit_intercept": self.fit_intercept,
                    "max_iter": self.max_iter,
                    "tol": self.tol,
                    "random_state": self.random_state,
                    "selection": self.selection,
                },
            }
            joblib.dump(artifact_payload, model_artifact_path)

        except Exception as error:
            raise ModelArtifactError(
                message=f"ElasticNet 아티팩트 저장 실패 ({model_artifact_path}): {str(error)}",
                artifact_path=model_artifact_path,
                operation_type="save",
                original_exception=error,
            )

    def load_artifact(self, file_path: str) -> "ElasticNetRegressor":
        """물리 디스크에 저장된 .pkl 아티팩트를 역직렬화하여 인스턴스 상태를 복원합니다.

        Args:
            file_path (str): 로드할 아티팩트 파일 경로.

        Returns:
            ElasticNetRegressor: 역직렬화 복원이 완료된 객체 자신(self).

        Raises:
            ModelArtifactError: 파일 부재 또는 역직렬화 실패 시 발생.
        """
        model_artifact_path: str = file_path
        if not os.path.exists(model_artifact_path):
            raise ModelArtifactError(
                message=f"지정된 아티팩트 파일을 찾을 수 없습니다: {model_artifact_path}",
                artifact_path=model_artifact_path,
                operation_type="load",
            )

        try:
            artifact_payload: Dict[str, Any] = joblib.load(model_artifact_path)

            self._internal_model = artifact_payload.get("internal_model")
            self.feature_names = artifact_payload.get("feature_names")
            self.is_fitted = artifact_payload.get("is_fitted", True)
            self.model_name = artifact_payload.get("model_name", self.model_name)

            hyperparameters: Dict[str, Any] = artifact_payload.get("hyperparameters", {})
            self.alpha = hyperparameters.get("alpha", self.alpha)
            self.l1_ratio = hyperparameters.get("l1_ratio", self.l1_ratio)
            self.fit_intercept = hyperparameters.get("fit_intercept", self.fit_intercept)
            self.max_iter = hyperparameters.get("max_iter", self.max_iter)
            self.tol = hyperparameters.get("tol", self.tol)
            self.random_state = hyperparameters.get("random_state", self.random_state)
            self.selection = hyperparameters.get("selection", self.selection)

            return self

        except Exception as error:
            raise ModelArtifactError(
                message=f"ElasticNet 아티팩트 로드 실패 ({model_artifact_path}): {str(error)}",
                artifact_path=model_artifact_path,
                operation_type="load",
                original_exception=error,
            )