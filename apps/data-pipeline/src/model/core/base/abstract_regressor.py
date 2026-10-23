from abc import ABC, abstractmethod
import os
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from src.common.exceptions import (
    ModelArtifactError,
    ModelNotFittedError,
    ModelTrainingExecutionError,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_MODEL_NAME: str = "AbstractRegressor"                  # 회귀 추정기 기본 식별 명칭
DEFAULT_RANDOM_STATE: int = 42                                 # 실험 재현성 보장을 위한 기본 난수 시드
DEFAULT_REQUESTED_DEVICE: str = "auto"                         # 하드웨어 가속기 기본 탐색 모드
SUPPORTED_DEVICES: Tuple[str, ...] = ("cpu", "cuda", "mps")    # 지원 연산 디바이스 목록
FEATURE_IMPORTANCE_SERIES_NAME: str = "feature_importance"     # 피처 중요도 반환 시리즈 표준 명칭


class AbstractRegressor(ABC):
    """모든 회귀 추정기(ML/DL/Ensemble)의 최상위 추상 기본 클래스.

    Attributes:
        model_name (str): 모델 고유 식별 명칭.
        random_state (int): 재현성 제어를 위한 난수 시드.
        hyperparameters (Dict[str, Any]): 모델 알고리즘 하이퍼파라미터 딕셔너리.
        feature_names (Optional[List[str]]): 학습 시점의 입력 피처 컬럼명 리스트.
        is_fitted (bool): 모델 학습 완료 여부 상태 플래그.
    """
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        **hyperparameters: Any,
    ) -> None:
        """AbstractRegressor 인스턴스의 공통 상태를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 DEFAULT_MODEL_NAME.
            random_state (int): 난수 제어 시드. 기본값은 DEFAULT_RANDOM_STATE.
            **hyperparameters (Any): 하위 모델별 동적 하이퍼파라미터.
        """
        # 모델 식별자, 시드, 하이퍼파라미터 및 학습 상태 메타데이터 초기화
        self.model_name: str = model_name
        self.random_state: int = random_state
        self.hyperparameters: Dict[str, Any] = hyperparameters
        self.feature_names: Optional[List[str]] = None
        self.is_fitted: bool = False

    # --------------------------------------------------------------------------
    # Public API Functions
    # --------------------------------------------------------------------------
    @abstractmethod
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> "AbstractRegressor":
        """입력 데이터를 기반으로 모델 학습을 집행합니다.

        Args:
            X_train (pd.DataFrame): 훈련용 2D 피처 행렬.
            y_train (pd.Series): 훈련용 1D 타겟 시계열.
            X_val (Optional[pd.DataFrame]): 조기 종료 및 검증용 피처 행렬. 기본값은 None.
            y_val (Optional[pd.Series]): 조기 종료 및 검증용 타겟 시리즈. 기본값은 None.
            sample_weight (Optional[pd.Series]): 관측치별 중요도 가중치. 기본값은 None.
            **kwargs (Any): 하위 알고리즘별 추가 런타임 제어 인자.

        Returns:
            AbstractRegressor: 학습이 완료된 모델 인스턴스 자신(self).

        Raises:
            ModelTrainingExecutionError: 입력 데이터 결손 또는 학습 중 오류가 발생한 경우.
        """
        pass

    @abstractmethod
    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """주어진 피처 데이터셋에 대해 모델 추론을 수행합니다.

        Args:
            X_test (pd.DataFrame): 추론을 수행할 2D 피처 행렬.

        Returns:
            pd.Series: X_test 인덱스가 보존된 1D 예측값 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ModelTrainingExecutionError: 추론 입력 데이터가 비어 있거나 피처가 불일치하는 경우.
        """
        pass

    def get_params(self) -> Dict[str, Any]:
        """현재 설정된 모델 하이퍼파라미터 사본을 반환합니다.

        Returns:
            Dict[str, Any]: 하이퍼파라미터 키-값 딕셔너리 사본.
        """
        # 외부 수정에 의한 내부 하이퍼파라미터 오염 방지를 위해 얕은 사본 반환
        return self.hyperparameters.copy()

    def set_params(self, **params: Any) -> "AbstractRegressor":
        """모델 하이퍼파라미터를 동적으로 갱신하고 학습 완료 상태를 초기화합니다.

        Args:
            **params (Any): 갱신할 하이퍼파라미터 키-값 인자.

        Returns:
            AbstractRegressor: 하이퍼파라미터가 갱신된 모델 인스턴스 자신(self).
        """
        # 1. 전달받은 하이퍼파라미터 딕셔너리 병합 갱신
        self.hyperparameters.update(params)

        # 2. 파라미터 변경에 따른 기존 학습 가중치 무효화 처리
        self.is_fitted = False
        return self

    def save_artifact(self, model_artifact_path: str) -> None:
        """학습된 모델 객체를 직렬화하여 지정된 파일 시스템 경로에 저장합니다.

        Args:
            model_artifact_path (str): 모델 아티팩트를 저장할 대상 파일 경로.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ModelArtifactError: 디렉터리 생성 또는 직렬화 중 오류가 발생한 경우.
        """
        # 1. 모델 학습 완료 상태 검증
        self._validate_fitted_state(operation_name="save_artifact")

        try:
            # 2. 아티팩트 저장 대상 상위 디렉터리 생성
            artifact_directory: str = os.path.dirname(model_artifact_path)
            if artifact_directory:
                os.makedirs(artifact_directory, exist_ok=True)

            # 3. 하위 계층별 직렬화 내장 함수를 호출하여 파일 저장
            self._serialize_artifact(model_artifact_path=model_artifact_path)
        except ModelArtifactError:
            raise
        except Exception as error:
            raise ModelArtifactError(
                message=f"모델 아티팩트 저장 실패: {str(error)}",
                model_name=self.model_name,
                artifact_path=model_artifact_path,
                original_exception=error,
            ) from error

    @classmethod
    def load_artifact(cls, model_artifact_path: str) -> "AbstractRegressor":
        """파일 시스템으로부터 직렬화된 모델 객체를 역직렬화하여 복원합니다.

        Args:
            model_artifact_path (str): 복원할 모델 아티팩트 파일 경로.

        Returns:
            AbstractRegressor: 복원된 회귀 모델 인스턴스.

        Raises:
            ModelArtifactError: 아티팩트 파일이 존재하지 않거나 복원 중 오류가 발생한 경우.
        """
        # 1. 지정된 경로의 아티팩트 파일 존재 여부 검증
        if not os.path.exists(model_artifact_path):
            raise ModelArtifactError(
                message=f"지정된 아티팩트 파일을 찾을 수 없습니다: {model_artifact_path}",
                artifact_path=model_artifact_path,
            )

        # 2. 하위 계층별 역직렬화 내장 함수를 호출하여 모델 인스턴스 복원
        try:
            return cls._deserialize_artifact(model_artifact_path=model_artifact_path)
        except ModelArtifactError:
            raise
        except Exception as error:
            raise ModelArtifactError(
                message=f"모델 아티팩트 역직렬화 로드 실패: {str(error)}",
                artifact_path=model_artifact_path,
                original_exception=error,
            ) from error

    def get_feature_importance(self) -> pd.Series:
        """학습된 모델의 글로벌 피처 중요도를 반환합니다.

        Returns:
            pd.Series: 피처 중요도 시리즈 (기본 구현은 미지원 모델을 위한 빈 Series 반환).
        """
        # 중요도 산출을 지원하지 않는 기본 모델을 위해 표준 명칭의 빈 시리즈 반환
        return pd.Series(dtype=np.float64, name=FEATURE_IMPORTANCE_SERIES_NAME)

    # --------------------------------------------------------------------------
    # Internal Helper Functions
    # --------------------------------------------------------------------------
    def _serialize_artifact(self, model_artifact_path: str) -> None:
        """모델 인스턴스를 기본 직렬화 엔진(joblib)으로 파일에 저장합니다."""
        # ML 및 Ensemble 모델은 기본 joblib 직렬화를 사용하며, DL 모델은 본 메서드를 오버라이딩함
        joblib.dump(self, model_artifact_path)

    @classmethod
    def _deserialize_artifact(cls, model_artifact_path: str) -> "AbstractRegressor":
        """기본 직렬화 엔진(joblib)을 사용하여 파일로부터 모델 인스턴스를 복원합니다."""
        # 파일 시스템에서 직렬화된 아티팩트를 읽어 모델 객체로 반환
        return joblib.load(model_artifact_path)

    @staticmethod
    def _merge_hyperparameters(
        default_params: Dict[str, Any],
        custom_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """원본 기본 하이퍼파라미터 딕셔너리 오염 없이 사용자 주입 파라미터를 병합합니다."""
        # 1. 기본 하이퍼파라미터 사본 생성
        merged_params: Dict[str, Any] = default_params.copy()

        # 2. 외부에서 주입된 커스텀 하이퍼파라미터 덮어쓰기 후 반환
        merged_params.update(custom_params)
        return merged_params

    def _validate_fitted_state(self, operation_name: str = "predict") -> None:
        """미학습 상태에서의 추론 또는 아티팩트 저장 호출을 사전에 차단합니다."""
        # 학습 완료 플래그(is_fitted)가 False인 경우 즉시 예외 발생
        if not self.is_fitted:
            raise ModelNotFittedError(
                message=(
                    f"'{self.model_name}' 모델이 아직 학습되지 않았습니다. "
                    f"'{operation_name}()' 호출 전 'fit()'을 먼저 실행하세요."
                ),
                model_name=self.model_name,
                operation_type=operation_name,
            )

    def _validate_train_data(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[pd.Series] = None,
    ) -> None:
        """학습·검증 데이터셋 및 가중치의 결손 여부와 행 길이 정합성을 검증합니다."""
        # 1. 학습용 피처(X_train) 및 타겟(y_train) 데이터셋의 비어 있음 여부 검증
        if X_train is None or y_train is None or X_train.empty or y_train.empty:
            raise ModelTrainingExecutionError(
                message="학습을 위한 입력 데이터셋(X_train 또는 y_train)이 비어 있습니다.",
                model_name=self.model_name,
            )

        # 2. 학습용 피처와 타겟 간 관측치 행 개수 일치 여부 검증
        if len(X_train) != len(y_train):
            raise ModelTrainingExecutionError(
                message=(
                    f"피처 행 개수({len(X_train)})와 "
                    f"타겟 행 개수({len(y_train)})가 일치하지 않습니다."
                ),
                model_name=self.model_name,
            )

        # 3. 샘플 가중치(sample_weight) 제공 시 학습 데이터와의 행 개수 일치 여부 검증
        if sample_weight is not None and len(sample_weight) != len(X_train):
            raise ModelTrainingExecutionError(
                message=(
                    f"학습 피처 행 개수({len(X_train)})와 "
                    f"샘플 가중치 개수({len(sample_weight)})가 일치하지 않습니다."
                ),
                model_name=self.model_name,
            )

        # 4. 검증 데이터셋(X_val, y_val)의 쌍(Pair) 구성 및 행 개수 정합성 검증
        if (X_val is None) != (y_val is None):
            raise ModelTrainingExecutionError(
                message="검증 데이터셋(X_val과 y_val)은 모두 제공되거나 모두 None이어야 합니다.",
                model_name=self.model_name,
            )
        if X_val is not None and y_val is not None:
            if X_val.empty or y_val.empty:
                raise ModelTrainingExecutionError(
                    message="검증 데이터셋(X_val 또는 y_val)이 비어 있습니다.",
                    model_name=self.model_name,
                )
            if len(X_val) != len(y_val):
                raise ModelTrainingExecutionError(
                    message=(
                        f"검증 피처 행 개수({len(X_val)})와 "
                        f"검증 타겟 행 개수({len(y_val)})가 일치하지 않습니다."
                    ),
                    model_name=self.model_name,
                )

    def _validate_predict_data(self, X_test: pd.DataFrame) -> None:
        """추론용 피처 데이터셋의 비어 있음 여부를 검증합니다."""
        # 추론 입력 데이터셋이 None이거나 행이 0개인 경우 예외 발생
        if X_test is None or X_test.empty:
            raise ModelTrainingExecutionError(
                message="추론을 위한 입력 데이터셋(X_test)이 비어 있습니다.",
                model_name=self.model_name,
            )

    def _align_predict_features(self, X_test: pd.DataFrame) -> pd.DataFrame:
        """추론 데이터를 검증하고 학습 시점의 피처 목록 및 컬럼 순서와 동일하게 정렬합니다."""
        # 1. 입력 피처 데이터셋의 유효성(비어 있지 않음) 검증
        self._validate_predict_data(X_test=X_test)

        # 2. 학습 시점의 피처 메타데이터가 기록되지 않은 경우 원본 그대로 반환
        if not self.feature_names:
            return X_test

        # 3. 학습된 필수 피처 중 입력 데이터셋에 누락된 컬럼이 존재하는지 검증
        missing_features: List[str] = [
            feature for feature in self.feature_names if feature not in X_test.columns
        ]
        if missing_features:
            raise ModelTrainingExecutionError(
                message=f"추론 데이터셋에 학습된 필수 피처가 누락되었습니다: {missing_features}",
                model_name=self.model_name,
            )

        # 4. 가중치 오매핑 방지를 위해 학습 시점과 동일한 피처 순서로 슬라이싱하여 반환
        return X_test[self.feature_names]

    def _format_prediction_series(
        self,
        predictions: np.ndarray,
        index: pd.Index,
    ) -> pd.Series:
        """1차원 추론 결과 배열을 원본 시계열 인덱스가 보존된 Series로 변환합니다."""
        # 1. 예측 결과 배열을 1차원 실수형(float64) NumPy 배열로 평탄화
        flattened_predictions: np.ndarray = np.asarray(
            predictions,
            dtype=np.float64,
        ).ravel()

        # 2. 평탄화된 예측값 개수와 원본 데이터 인덱스 길이의 정합성 검증
        if len(flattened_predictions) != len(index):
            raise ModelTrainingExecutionError(
                message=(
                    f"예측 결과 길이({len(flattened_predictions)})와 "
                    f"입력 데이터 인덱스 길이({len(index)})가 일치하지 않습니다."
                ),
                model_name=self.model_name,
            )

        # 3. 원본 인덱스와 모델 식별명이 매핑된 Series 객체 생성 및 반환
        return pd.Series(
            data=flattened_predictions,
            index=index,
            name=self.model_name,
            dtype=np.float64,
        )

    def _detect_device(
        self,
        requested_device: str = DEFAULT_REQUESTED_DEVICE,
        supported_devices: Tuple[str, ...] = SUPPORTED_DEVICES,
    ) -> str:
        """런타임 가용 하드웨어와 지원 목록을 대조하여 최적 연산 디바이스를 반환합니다."""
        # 1. 사용자가 특정 디바이스를 명시한 경우 지원 여부 확인 후 반환 (미지원 시 cpu 폴백)
        if requested_device != DEFAULT_REQUESTED_DEVICE:
            return requested_device if requested_device in supported_devices else "cpu"

        # 2. 자동(auto) 모드인 경우 가용 하드웨어 가속기(CUDA -> MPS)를 순차 탐색
        try:
            import torch

            if "cuda" in supported_devices and torch.cuda.is_available():
                return "cuda"
            if (
                "mps" in supported_devices
                and hasattr(torch.backends, "mps")
                and torch.backends.mps.is_available()
            ):
                return "mps"
        except ImportError:
            pass

        # 3. 가용한 하드웨어 가속기가 없는 경우 기본 CPU 디바이스 반환
        return "cpu"