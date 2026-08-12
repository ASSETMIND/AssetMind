"""
[Random Forest(랜덤 포레스트) 앙상블 배깅 알고리즘을 캡슐화한 머신러닝 추정기 구체 클래스 모듈]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 생성자(__init__)를 통해 주입되는 하이퍼파라미터 딕셔너리(**hyperparameters) 및 fit() 메서드로 유입되는 학습 데이터셋(X_train, y_train).
2. Model Execution: __init__ 내부에서 하이퍼파라미터를 개별 멤버 변수로 언패킹하여 바인딩 후, sklearn.ensemble.RandomForestRegressor 추정기 인스턴스화 및 배깅 기반 피팅 연산 집행.
3. Index & Dimension Alignment: 추론(predict) 결과 수치를 원본 입력 X_test의 행 인덱스(Index)와 완벽하게 정렬하여 pd.Series 구조로 사출.
4. Output: 학습된 RandomForestRegressor 인스턴스, 정렬된 예측 시계열(pd.Series), 피처 중요도 시리즈(pd.Series), SHAP 기여도 배열(np.ndarray), 저장/로드 아티팩트 파일.

주요 기능:
- Config-Friendly Parameter Unpacking: 생성자 단에서 **hyperparameters 인자를 수용하여 내부 개별 인스턴스 변수로 파싱 및 사전 바인딩함으로써 YAML 및 Optuna 딕셔너리와의 호환성 극대화.
- Bagging Ensemble Decision Trees: 다수의 독립적 결정 트리(Decision Tree)의 무작위 샘플링(Bootstrap) 예측 결과를 평균화하여 과적합을 방지하고 일반화 성능 극대화.
- SHAP TreeExplainer Integration: shap.TreeExplainer를 연동하여 트리 앙상블 구조 기반의 정밀한 XAI(설명 가능한 AI) SHAP Value 산출.
- Robust Artifact Serialization: joblib 기반 직렬화를 지원하여 모델 상태, 피처 컬럼 세트 및 하이퍼파라미터 메타데이터를 물리 파일(.pkl)로 저장 및 복원.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- RandomForest 알고리즘의 AbstractRegressor 규격 래핑 및 SHAP TreeExplainer 결합 vs 단일 결정 트리 또는 그래디언트 부스팅 단독 사용:
  - 장점: 부트스트랩 샘플링과 피처 무작위 선택을 통해 시계열 노이즈에 강건(Robust)하며, 부스팅 계열(XGBoost)에 비해 하이퍼파라미터 민감도가 낮아 기본 성능 보장이 탁월함.
  - 단점: 트리의 개수(n_estimators)가 증가함에 따라 메모리 사용량이 비대해지고 추론 및 SHAP 계산 시간이 선형적으로 증가함.
  - 근거: Phase 2의 Stage 1 Quick Screening 및 Stage 2 Fine-Tuning에서 그래디언트 부스팅(XGBoost), 선형 모델(Ridge)과 함께 이종 앙상블의 핵심 축을 이루므로 정밀한 독립 서브 모델로서 Random Forest 구현이 필수적임.
"""

# ==============================================================================
# Imports
# ==============================================================================
import os
from typing import Dict, Optional, Any, List, Union
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor as SklearnRandomForestRegressor
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
DEFAULT_MODEL_NAME: str = "RandomForestRegressor"


# ==============================================================================
# Main Regressor Class
# ==============================================================================
class RandomForestRegressor(AbstractRegressor):
    """Random Forest 배깅 앙상블 회귀 알고리즘 구체 클래스.

    Attributes:
        model_name (str): 모델 인스턴스의 식별 명칭.
        is_fitted (bool): 모델의 학습 완료 여부를 나타내는 방어적 상태 플래그.
        n_estimators (int): 앙상블을 구성하는 결정 트리의 총 개수.
        max_depth (Optional[int]): 트리의 최대 깊이. None일 경우 완전 분할.
        min_samples_split (Union[int, float]): 노드 분할을 위한 최소 샘플 수 또는 비율.
        min_samples_leaf (Union[int, float]): 리프 노드가 가져야 할 최소 샘플 수 또는 비율.
        max_features (Optional[Union[str, int, float]]): 최적 분할을 위해 고려할 피처 수.
        random_state (Optional[int]): 난수 고정 시드값.
        n_jobs (int): 병렬 처리 코어 수.
        feature_names (Optional[List[str]]): 학습 시 주입된 피처 컬럼명 목록.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        **hyperparameters: Any,
    ) -> None:
        """RandomForestRegressor 인스턴스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 식별 명칭. 기본값은 DEFAULT_MODEL_NAME.
            **hyperparameters (Any): n_estimators, max_depth, min_samples_split 등 Random Forest 하이퍼파라미터 키-값 쌍.
        """
        # [설계 의도] 상위 추상 클래스 생성자를 호출하여 공통 식별명 및 상태 플래그 바인딩
        super().__init__(model_name=model_name)

        # [설계 의도] 외부 딕셔너리로 주입된 하이퍼파라미터들을 개별 인스턴스 변수로 파싱 및 기본값 설정
        self.n_estimators: int = int(hyperparameters.get("n_estimators", 100))
        self.max_depth: Optional[int] = hyperparameters.get("max_depth", None)
        if self.max_depth is not None:
            self.max_depth = int(self.max_depth)

        self.min_samples_split: Union[int, float] = hyperparameters.get(
            "min_samples_split", 2
        )
        self.min_samples_leaf: Union[int, float] = hyperparameters.get(
            "min_samples_leaf", 1
        )
        self.max_features: Optional[Union[str, int, float]] = (
            hyperparameters.get("max_features", "sqrt")
        )
        self.random_state: Optional[int] = hyperparameters.get("random_state", 42)
        self.n_jobs: int = int(hyperparameters.get("n_jobs", -1))

        self._internal_model: Optional[SklearnRandomForestRegressor] = None
        self.feature_names: Optional[List[str]] = None

    # --------------------------------------------------------------------------
    # Abstract Method Implementations (추상 메서드 구체 구현)
    # --------------------------------------------------------------------------
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> "RandomForestRegressor":
        """인스턴스 생성 시 바인딩된 하이퍼파라미터를 바탕으로 Random Forest 회귀 모델 학습을 수행합니다.

        Args:
            X_train (pd.DataFrame): 학습용 피처 데이터프레임.
            y_train (pd.Series): 학습용 정답 타겟 시계열.

        Returns:
            RandomForestRegressor: 학습이 완료된 모델 객체 자신(self).

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
            # [설계 의도] __init__에서 사전 바인딩된 개별 파라미터 변수들을 활용하여 scikit-learn RandomForestRegressor 인스턴스화
            self._internal_model = SklearnRandomForestRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                max_features=self.max_features,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
            )

            # [설계 의도] 내부 모델 피팅 실행
            self._internal_model.fit(X_train, y_train)

            # [설계 의도] 피처 정렬 검증 및 XAI/중요도 산출을 위해 피처 컬럼명을 저장하고 학습 완료 플래그 전환
            self.feature_names = list(X_train.columns)
            self.is_fitted = True

            return self

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"Random Forest 모델 학습 진행 중 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                hyperparameters={
                    "n_estimators": self.n_estimators,
                    "max_depth": self.max_depth,
                    "min_samples_split": self.min_samples_split,
                },
                original_exception=error,
            )

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """주어진 피처 데이터셋에 대해 Random Forest 회귀 예측을 수행합니다.

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
                message=f"Random Forest 모델 추론 중 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            )

    def get_feature_importance(self) -> pd.Series:
        """학습된 Random Forest 모델의 Feature Importance 수치를 산출합니다.

        Returns:
            pd.Series: 피처명을 인덱스로 가지고 트리 앙상블 평균 지니/MDI 중요도 수치를 값으로 가지는 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
        """
        # [방어적 프로그래밍] 미학습 상태 진입 차단
        self._validate_fitted_state(operation_name="get_feature_importance")

        # [설계 의도] 트리 앙상블 중요도(feature_importances_)를 피처명 인덱스와 매핑하여 시리즈로 반환
        feature_importance_array: np.ndarray = (
            self._internal_model.feature_importances_
        )
        feature_importance_series: pd.Series = pd.Series(
            data=feature_importance_array,
            index=self.feature_names,
            name="feature_importance",
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
            ShapCalculationError: TreeExplainer 연산 실패 시.
        """
        # [방어적 프로그래밍] 미학습 상태 진입 차단
        self._validate_fitted_state(operation_name="calculate_shap_values")

        if X_sample.empty:
            raise ShapCalculationError(
                message="SHAP 수치 계산을 위한 샘플 데이터셋(X_sample)이 비어 있습니다.",
                model_name=self.model_name,
                explainer_type="TreeExplainer",
            )

        try:
            # [설계 의도] 트리 앙상블 전용 shap.TreeExplainer를 활용하여 SHAP 수치 산출
            explainer: shap.TreeExplainer = shap.TreeExplainer(
                model=self._internal_model
            )
            shap_values_data: Union[np.ndarray, List[np.ndarray]] = (
                explainer.shap_values(X_sample)
            )

            # [설계 의도] 결과 타입이 list 형태일 경우 단일 array로 변환 처리
            if isinstance(shap_values_data, list):
                shap_values_array: np.ndarray = np.array(shap_values_data[0])
            else:
                shap_values_array = np.array(shap_values_data)

            return shap_values_array

        except Exception as error:
            raise ShapCalculationError(
                message=f"Random Forest SHAP 수치 계산 중 예기치 못한 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                explainer_type="TreeExplainer",
                original_exception=error,
            )

    def save_artifact(self, model_artifact_path: str) -> None:
        """학습된 Random Forest 모델 및 메타데이터 아티팩트를 지정된 경로에 직렬화 저장합니다.

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
                    "n_estimators": self.n_estimators,
                    "max_depth": self.max_depth,
                    "min_samples_split": self.min_samples_split,
                    "min_samples_leaf": self.min_samples_leaf,
                    "max_features": self.max_features,
                    "random_state": self.random_state,
                    "n_jobs": self.n_jobs,
                },
            }
            joblib.dump(artifact_payload, model_artifact_path)

        except Exception as error:
            raise ModelArtifactError(
                message=f"Random Forest 아티팩트 저장 실패 ({model_artifact_path}): {str(error)}",
                artifact_path=model_artifact_path,
                operation_type="save",
                original_exception=error,
            )

    def load_artifact(self, model_artifact_path: str) -> "RandomForestRegressor":
        """지정된 파일 경로로부터 Random Forest 모델 아티팩트를 로드하여 인스턴스 상태를 복원합니다.

        Args:
            model_artifact_path (str): 로드할 아티팩트 파일 경로.

        Returns:
            RandomForestRegressor: 복원된 모델 인스턴스 자신(self).

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
            self.n_estimators = hyperparameters.get("n_estimators", self.n_estimators)
            self.max_depth = hyperparameters.get("max_depth", self.max_depth)
            self.min_samples_split = hyperparameters.get("min_samples_split", self.min_samples_split)
            self.min_samples_leaf = hyperparameters.get("min_samples_leaf", self.min_samples_leaf)
            self.max_features = hyperparameters.get("max_features", self.max_features)
            self.random_state = hyperparameters.get("random_state", self.random_state)
            self.n_jobs = hyperparameters.get("n_jobs", self.n_jobs)

            return self

        except Exception as error:
            raise ModelArtifactError(
                message=f"Random Forest 아티팩트 로드 실패 ({model_artifact_path}): {str(error)}",
                artifact_path=model_artifact_path,
                operation_type="load",
                original_exception=error,
            )