from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import os

import numpy as np
import joblib
import pandas as pd

from src.common.exceptions import (
    ModelArtifactError,
    ModelNotFittedError,
    ModelTrainingExecutionError
)

# ==============================================================================
# Constants
# ==============================================================================
DEFAULT_MODEL_NAME: str = "AbstractRegressor"

# ==============================================================================
# Main Regressor Class
# ==============================================================================
class AbstractRegressor(ABC):
    """AssetMind 모든 회귀 추정기(ML/DL/Ensemble)의 최상위 추상 기본 클래스."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        random_state: int = 42,
        **hyperparameters: Any,
    ) -> None:
        """AbstractRegressor 인스턴스를 초기화합니다."""
        self.model_name: str = model_name
        self.random_state: int = random_state
        self.hyperparameters: Dict[str, Any] = hyperparameters
        self.feature_names: Optional[List[str]] = None
        self.is_fitted: bool = False

    # --------------------------------------------------------------------------
    # Core Implementations
    # --------------------------------------------------------------------------
    @abstractmethod
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> "AbstractRegressor":
        """입력 데이터를 기반으로 모델 학습을 집행합니다.

        Args:
            X_train (pd.DataFrame): 훈련용 2D 피처 행렬.
            y_train (pd.Series): 훈련용 1D 타겟 시계열.
            X_val (Optional[pd.DataFrame]): 조기 종료용 검증 피처 행렬.
            y_val (Optional[pd.Series]): 조기 종료용 검증 타겟 시리즈.
            **kwargs (Any): 기타 알고리즘별 동적 런타임 제어 인자.
        """
        pass

    @abstractmethod
    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """주어진 피처 데이터셋에 대해 모델 추론을 수행합니다."""
        pass

    # --------------------------------------------------------------------------
    # Concrete Estimator Management Methods (파라미터 및 아티팩트 관리)
    # --------------------------------------------------------------------------
    def get_params(self) -> Dict[str, Any]:
        """모델 하이퍼파라미터 딕셔너리를 반환합니다."""
        return self.hyperparameters.copy()

    def set_params(self, **params: Any) -> "AbstractRegressor":
        """모델 하이퍼파라미터를 동적으로 갱신하며, 학습 상태를 초기화합니다."""
        self.hyperparameters.update(params)
        self.is_fitted = False
        return self

    def save_artifact(self, model_artifact_path: str) -> None:
        """학습된 모델 객체를 직렬화하여 파일 시스템에 저장합니다."""
        self._validate_fitted_state(operation_name="save_artifact")
        try:
            artifact_dir = os.path.dirname(model_artifact_path)
            if artifact_dir:
                os.makedirs(artifact_dir, exist_ok=True)
            joblib.dump(self, model_artifact_path)
        except Exception as error:
            raise ModelArtifactError(
                message=f"모델 아티팩트 저장 실패: {str(error)}",
                model_name=self.model_name,
                artifact_path=model_artifact_path,
                original_exception=error,
            ) from error

    @classmethod
    def load_artifact(cls, model_artifact_path: str) -> "AbstractRegressor":
        """파일 시스템으로부터 직렬화된 모델 객체를 복원합니다."""
        if not os.path.exists(model_artifact_path):
            raise ModelArtifactError(
                message=f"지정된 아티팩트 파일을 찾을 수 없습니다: {model_artifact_path}",
                artifact_path=model_artifact_path,
            )
        try:
            loaded_instance = joblib.load(model_artifact_path)
            return loaded_instance
        except Exception as error:
            raise ModelArtifactError(
                message=f"모델 아티팩트 역직렬화 로드 실패: {str(error)}",
                artifact_path=model_artifact_path,
                original_exception=error,
            ) from error

    # --------------------------------------------------------------------------
    # Feature Importance
    # --------------------------------------------------------------------------
    def get_feature_importance(self) -> pd.Series:
        """학습된 모델의 글로벌 피처 중요도를 산출합니다. (미지원 모델은 빈 Series 반환)"""
        return pd.Series(dtype=np.float64)

    # --------------------------------------------------------------------------
    # Protected Defensive Helpers
    # --------------------------------------------------------------------------
    def _validate_fitted_state(self, operation_name: str = "predict") -> None:
        """미학습 상태에서의 비정상 연산 호출을 사전에 차단합니다 (Fail-Fast)."""
        if not self.is_fitted:
            raise ModelNotFittedError(
                message=f"'{self.model_name}' 모델이 아직 학습되지 않았습니다. '{operation_name}()' 호출 전 'fit()'을 먼저 실행하세요.",
                model_name=self.model_name,
                operation_type=operation_name,
            )

    def _validate_train_data(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """학습 데이터셋의 결손 및 차원 불일치를 선제 검증합니다."""
        if X_train is None or y_train is None or X_train.empty or y_train.empty:
            raise ModelTrainingExecutionError(
                message="학습을 위한 입력 데이터셋(X_train 또는 y_train)이 비어 있습니다.",
                model_name=self.model_name,
            )
        if len(X_train) != len(y_train):
            raise ModelTrainingExecutionError(
                message=f"피처 행 개수({len(X_train)})와 타겟 행 개수({len(y_train)})가 일치하지 않습니다.",
                model_name=self.model_name,
            )

    def _validate_predict_data(self, X_test: pd.DataFrame) -> None:
        """추론 데이터셋의 유효성을 검증합니다."""
        if X_test is None or X_test.empty:
            raise ModelTrainingExecutionError(
                message="추론을 위한 입력 데이터셋(X_test)이 비어 있습니다.",
                model_name=self.model_name,
            )

    # --------------------------------------------------------------------------
    # Hardware Detection
    # --------------------------------------------------------------------------
    def _detect_device(
        self,
        requested_device: str = "auto",
        supported_devices: Tuple[str, ...] = ("cpu", "cuda", "mps"),
    ) -> str:
        """런타임 가용 하드웨어와 프레임워크 지원 스펙을 검증하여 최적 디바이스를 안전하게 선택합니다."""
        if requested_device != "auto":
            return requested_device if requested_device in supported_devices else "cpu"

        try:
            import torch
            if "cuda" in supported_devices and torch.cuda.is_available():
                return "cuda"
            if "mps" in supported_devices and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass

        return "cpu"