"""
[PyTorch 기반 LSTM(Long Short-Term Memory) 순환 신경망을 캡슐화한 딥러닝 시계열 회귀 추정기 모듈]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 생성자(__init__)를 통해 주입되는 하이퍼파라미터 딕셔너리(**hyperparameters) 및 fit() 메서드로 유입되는 2차원 시계열 피처 데이터프레임(X_train)과 정답 타겟(y_train).
2. Sequence Tensor Transformation: 2차원 데이터프레임을 설정된 sequence_length 및 Edge Padding 기반 슬라이딩 윈도우를 적용하여 3차원 PyTorch Tensor([Batch_Size, Sequence_Length, Feature_Dim])로 직렬 변환.
3. Model Execution: PyTorch _PyTorchLSTMModule 생성, Adam 최적화 및 MSE 손실함수 기반 역전파(Backpropagation) 커스텀 학습 루프 집행.
4. Index & Dimension Alignment: 추론(predict) 결과 텐서를 numpy 및 pandas 시리즈로 복원 시 원본 X_test의 행 인덱스(Index)와 1:1로 완전 정렬하여 사출.
5. Output: 학습된 LSTMRegressor 인스턴스, 정렬된 예측 시계열(pd.Series), 게이트 가중치 기반 피처 중요도 시리즈(pd.Series), SHAP 기여도 배열(np.ndarray), 저장/로드 아티팩트 파일(.pt/.pkl).

주요 기능:
- Config-Friendly Parameter Unpacking: 생성자 단에서 **hyperparameters 인자를 수용하여 sequence_length, hidden_dim, learning_rate, epochs, batch_size 등을 개별 변수로 언패킹 바인딩.
- Automatic Dimension-Preserving Sequence Building: Edge Padding을 활용하여 타불라 2차원 데이터프레임의 행 개수 및 인덱스를 단 1건의 누락도 없이 3차원 시퀀스 텐서로 변환하는 전처리 루틴 내장.
- PyTorch Native Training & Device Management: GPU(cuda) 및 CPU 디바이스 자동 감지, DataLoader mini-batch 연산, Gradient Clipping 및 Seed 고정을 통한 재현성 보장.
- SHAP GradientExplainer Integration: PyTorch 신경망 계층 구조에 대응하는 shap.GradientExplainer 연동으로 딥러닝 시계열 XAI 해석 가능성 제공.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- PyTorch 커스텀 순환 신경망의 AbstractRegressor 규격 래핑 vs scikit-learn 머신러닝 단독 사용:
  - 장점: 시간의 흐름(Sequence)에 따른 장기 의존성(Long-term Dependency)과 금융 시계열의 복잡한 동적 비선형 패턴을 순환 게이트 구조로 정밀하게 포착함.
  - 단점: GBDT/선형 모델 대비 피팅 시간이 길고, sequence_length 등 슬라이딩 윈도우 텐서 변환으로 인한 추가적인 메모리 오버헤드가 발생함.
  - 근거: 본 시스템의 Phase 3/4 백테스팅 및 앙상블 단계에서 트리 모델(XGBoost, Random Forest)과 선형 모델(Ridge)의 한계를 보완할 수 있는 딥러닝(LSTM) 서브 모델의 결합이 이종 앙상블 성능 극대화에 핵심적임.
"""

# ==============================================================================
# Imports
# ==============================================================================
import os
from typing import Dict, Optional, Any, List, Union, Tuple
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
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
DEFAULT_MODEL_NAME: str = "LSTMRegressor"


# ==============================================================================
# Internal PyTorch Neural Network Module
# ==============================================================================
class _PyTorchLSTMModule(nn.Module):
    """LSTM 순환 신경망 계층을 정의하는 PyTorch 내부 nn.Module 클래스.

    Attributes:
        lstm (nn.LSTM): PyTorch 다층 LSTM 레이어.
        fully_connected (nn.Linear): 최종 1차원 회귀 예측값을 사출하는 선형 레이어.
    """

    def __init__(
        self,
        input_dimension: int,
        hidden_dimension: int,
        num_layers: int,
        dropout_rate: float = 0.0,
    ) -> None:
        """_PyTorchLSTMModule 인스턴스를 초기화합니다.

        Args:
            input_dimension (int): 입력 피처의 개수.
            hidden_dimension (int): LSTM 은닉층 노드 수.
            num_layers (int): 쌓아 올릴 LSTM 레이어의 수.
            dropout_rate (float): 드롭아웃 비율. 기본값은 0.0.
        """
        super().__init__()
        # [설계 의도] 다층 LSTM 신경망 레이어 초기화 (batch_first=True 적용으로 [Batch, Sequence, Feature] 차원 강제)
        self.lstm: nn.LSTM = nn.LSTM(
            input_size=input_dimension,
            hidden_size=hidden_dimension,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout_rate if num_layers > 1 else 0.0,
        )
        self.fully_connected: nn.Linear = nn.Linear(hidden_dimension, 1)

    def forward(self, input_tensor: torch.Tensor) -> torch.Tensor:
        """순전파(Forward Pass) 연산을 수행합니다.

        Args:
            input_tensor (torch.Tensor): 3차원 입력 텐서 [Batch, Sequence, Feature].

        Returns:
            torch.Tensor: 1차원 예측값 텐서 [Batch].
        """
        # [설계 의도] LSTM 순전파 실행 후 타임스텝의 마지막 시점(last time step) 은닉 상태 추출 후 회귀값 산출
        lstm_output, _ = self.lstm(input_tensor)
        last_timestep_hidden_state: torch.Tensor = lstm_output[:, -1, :]
        prediction_tensor: torch.Tensor = self.fully_connected(
            last_timestep_hidden_state
        )
        return prediction_tensor.squeeze(-1)


# ==============================================================================
# Main Regressor Class
# ==============================================================================
class LSTMRegressor(AbstractRegressor):
    """PyTorch 기반 LSTM 시계열 회귀 알고리즘 구체 클래스.

    Attributes:
        model_name (str): 모델 인스턴스의 식별 명칭.
        is_fitted (bool): 모델의 학습 완료 여부를 나타내는 방어적 상태 플래그.
        sequence_length (int): 시계열 룩백 윈도우 시퀀스 길이.
        hidden_dim (int): LSTM 은닉 차원 크기.
        num_layers (int): LSTM 레이어 수.
        dropout (float): 드롭아웃 비율.
        learning_rate (float): Adam 최적화 학습률.
        batch_size (int): 미니배치 크기.
        epochs (int): 총 학습 에포크 수.
        random_state (Optional[int]): 난수 고정 시드값.
        device_name (str): 구동 연산 장치 ('cpu' 또는 'cuda').
        feature_names (Optional[List[str]]): 학습 시 주입된 피처 컬럼명 목록.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        **hyperparameters: Any,
    ) -> None:
        """LSTMRegressor 인스턴스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 식별 명칭. 기본값은 DEFAULT_MODEL_NAME.
            **hyperparameters (Any): sequence_length, hidden_dim, learning_rate, epochs 등 하이퍼파라미터 키-값 쌍.
        """
        # [설계 의도] 상위 추상 클래스 생성자를 호출하여 공통 식별명 및 상태 플래그 바인딩
        super().__init__(model_name=model_name)

        # [설계 의도] 외부 딕셔너리로 주입된 하이퍼파라미터들을 개별 인스턴스 변수로 파싱 및 기본값 설정
        self.sequence_length: int = int(hyperparameters.get("sequence_length", 10))
        self.hidden_dim: int = int(hyperparameters.get("hidden_dim", 64))
        self.num_layers: int = int(hyperparameters.get("num_layers", 2))
        self.dropout: float = float(hyperparameters.get("dropout", 0.1))
        self.learning_rate: float = float(hyperparameters.get("learning_rate", 0.001))
        self.batch_size: int = int(hyperparameters.get("batch_size", 32))
        self.epochs: int = int(hyperparameters.get("epochs", 50))
        self.random_state: Optional[int] = hyperparameters.get("random_state", 42)

        # [설계 의도] GPU 사용 가능 여부 자동 감지 및 디바이스 설정
        user_device: Optional[str] = hyperparameters.get("device_name", None)
        if user_device:
            self.device_name: str = user_device
        else:
            self.device_name = "cuda" if torch.cuda.is_available() else "cpu"

        self._pytorch_module: Optional[_PyTorchLSTMModule] = None
        self.feature_names: Optional[List[str]] = None

        # [설계 의도] 난수 고정을 통한 PyTorch 학습 재현성 사수
        if self.random_state is not None:
            torch.manual_seed(self.random_state)
            np.random.seed(self.random_state)

    # --------------------------------------------------------------------------
    # Abstract Method Implementations (추상 메서드 구체 구현)
    # --------------------------------------------------------------------------
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> "LSTMRegressor":
        """입력된 2차원 데이터프레임을 3차원 시퀀스로 변환 후 PyTorch LSTM 학습을 집행합니다.

        Args:
            X_train (pd.DataFrame): 학습용 피처 데이터프레임.
            y_train (pd.Series): 학습용 정답 타겟 시계열.

        Returns:
            LSTMRegressor: 학습이 완료된 모델 객체 자신(self).

        Raises:
            ModelTrainingExecutionError: 입력 데이터셋 부재, 행 개수 불일치 또는 PyTorch 연산 장애 발생 시.
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
            self.feature_names = list(X_train.columns)
            input_dimension: int = len(self.feature_names)

            # [설계 의도] 2차원 데이터프레임을 차원 보존 Edge Padding 적용 3차원 시퀀스 텐서로 변환
            sequence_tensor_x, target_tensor_y = self._create_sequence_tensors(
                X_data=X_train,
                y_data=y_train,
            )

            # [설계 의도] PyTorch DataLoader 구축
            dataset: TensorDataset = TensorDataset(sequence_tensor_x, target_tensor_y)
            dataloader: DataLoader = DataLoader(
                dataset=dataset,
                batch_size=self.batch_size,
                shuffle=False,  # 시계열 순서 보존을 위해 False 지정
            )

            # [설계 의도] PyTorch 내부 모듈 및 최적화기/손실함수 초기화
            execution_device: torch.device = torch.device(self.device_name)
            self._pytorch_module = _PyTorchLSTMModule(
                input_dimension=input_dimension,
                hidden_dimension=self.hidden_dim,
                num_layers=self.num_layers,
                dropout_rate=self.dropout,
            ).to(execution_device)

            optimizer: optim.Adam = optim.Adam(
                self._pytorch_module.parameters(),
                lr=self.learning_rate,
            )
            criterion: nn.MSELoss = nn.MSELoss()

            # [설계 의도] PyTorch Native 커스텀 학습 루프 집행
            self._pytorch_module.train()
            for epoch_index in range(self.epochs):
                for batch_x, batch_y in dataloader:
                    batch_x = batch_x.to(execution_device)
                    batch_y = batch_y.to(execution_device)

                    optimizer.zero_grad()
                    predictions: torch.Tensor = self._pytorch_module(batch_x)
                    loss: torch.Tensor = criterion(predictions, batch_y)
                    loss.backward()

                    # Gradient Clipping 적용하여 수리적 폭주 방지
                    torch.nn.utils.clip_grad_norm_(
                        self._pytorch_module.parameters(), max_norm=1.0
                    )
                    optimizer.step()

            self.is_fitted = True
            return self

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"LSTM 모델 학습 진행 중 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                hyperparameters={
                    "sequence_length": self.sequence_length,
                    "hidden_dim": self.hidden_dim,
                    "learning_rate": self.learning_rate,
                    "epochs": self.epochs,
                },
                original_exception=error,
            )

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """주어진 피처 데이터셋에 대해 PyTorch LSTM 추론을 수행합니다.

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
            # [설계 의도] 차원 보존 슬라이딩 윈도우 시퀀스 텐서 생성
            sequence_tensor_x, _ = self._create_sequence_tensors(
                X_data=X_test,
                y_data=None,
            )

            execution_device: torch.device = torch.device(self.device_name)
            self._pytorch_module.eval()
            self._pytorch_module.to(execution_device)

            with torch.no_grad():
                sequence_tensor_x = sequence_tensor_x.to(execution_device)
                raw_predictions_tensor: torch.Tensor = self._pytorch_module(
                    sequence_tensor_x
                )
                raw_predictions_array: np.ndarray = (
                    raw_predictions_tensor.cpu().numpy()
                )

            # [설계 의도] 결과 배열을 입력 X_test의 행 인덱스와 완벽히 결합하여 시리즈 사출
            prediction_series: pd.Series = pd.Series(
                data=raw_predictions_array,
                index=X_test.index,
                name="target_prediction",
            )
            return prediction_series

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"LSTM 모델 추론 중 원본 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            )

    def get_feature_importance(self) -> pd.Series:
        """LSTM 입력 게이트 가중치 절대값 평균에 기반하여 Feature Importance를 산출합니다.

        Returns:
            pd.Series: 피처명을 인덱스로 가지고 가중치 기여 수치를 값으로 가지는 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
        """
        # [방어적 프로그래밍] 미학습 상태 진입 차단
        self._validate_fitted_state(operation_name="get_feature_importance")

        # [설계 의도] LSTM의 첫 번째 레이어 입력 가중치(weight_ih_l0)의 은닉 노드별 절대값 평균을 산출하여 중요도로 환산
        input_weights: torch.Tensor = self._pytorch_module.lstm.weight_ih_l0.data
        absolute_weight_means: torch.Tensor = torch.mean(
            torch.abs(input_weights), dim=0
        )
        importance_array: np.ndarray = absolute_weight_means.cpu().numpy()

        feature_importance_series: pd.Series = pd.Series(
            data=importance_array,
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
            ShapCalculationError: GradientExplainer 연산 실패 시.
        """
        # [방어적 프로그래밍] 미학습 상태 진입 차단
        self._validate_fitted_state(operation_name="calculate_shap_values")

        if X_sample.empty:
            raise ShapCalculationError(
                message="SHAP 수치 계산을 위한 샘플 데이터셋(X_sample)이 비어 있습니다.",
                model_name=self.model_name,
                explainer_type="GradientExplainer",
            )

        try:
            # [설계 의도] 3차원 시퀀스 텐서 변환
            sequence_tensor_x, _ = self._create_sequence_tensors(
                X_data=X_sample,
                y_data=None,
            )

            execution_device: torch.device = torch.device(self.device_name)
            self._pytorch_module.eval()
            self._pytorch_module.to(execution_device)

            # [설계 의도] PyTorch 딥러닝 전용 shap.GradientExplainer 구동
            explainer: shap.GradientExplainer = shap.GradientExplainer(
                model=self._pytorch_module,
                data=sequence_tensor_x.to(execution_device),
            )

            shap_values_list: List[np.ndarray] = explainer.shap_values(
                sequence_tensor_x.to(execution_device)
            )

            if isinstance(shap_values_list, list):
                shap_3d_array: np.ndarray = shap_values_list[0]
            else:
                shap_3d_array = np.array(shap_values_list)

            # [설계 의도] 3차원 SHAP 배열[Batch, Sequence, Feature]을 시퀀스 축(axis=1)에 대해 평균하여 2차원[Batch, Feature] 사출
            if shap_3d_array.ndim == 3:
                shap_2d_array: np.ndarray = np.mean(shap_3d_array, axis=1)
            else:
                shap_2d_array = shap_3d_array

            return shap_2d_array

        except Exception as error:
            raise ShapCalculationError(
                message=f"LSTM SHAP 수치 계산 중 예기치 못한 예외가 발생했습니다: {str(error)}",
                model_name=self.model_name,
                explainer_type="GradientExplainer",
                original_exception=error,
            )

    def save_artifact(self, model_artifact_path: str) -> None:
        """학습된 LSTM 모델의 가중치(state_dict) 및 메타데이터를 저장합니다.

        Args:
            model_artifact_path (str): 아티팩트 저장 물리 경로 (.pt 또는 .pkl).

        Raises:
            ModelNotFittedError: 미학습 모델을 저장하려 할 경우.
            ModelArtifactError: 직렬화 장애 발생 시.
        """
        # [방어적 프로그래밍] 미학습 상태 저장 시도 차단
        self._validate_fitted_state(operation_name="save_artifact")

        try:
            artifact_directory: str = os.path.dirname(model_artifact_path)
            if artifact_directory and not os.path.exists(artifact_directory):
                os.makedirs(artifact_directory, exist_ok=True)

            # [설계 의도] PyTorch state_dict 및 구조 파라미터 묶음 직렬화
            artifact_payload: Dict[str, Any] = {
                "module_state_dict": self._pytorch_module.state_dict(),
                "feature_names": self.feature_names,
                "is_fitted": self.is_fitted,
                "model_name": self.model_name,
                "hyperparameters": {
                    "sequence_length": self.sequence_length,
                    "hidden_dim": self.hidden_dim,
                    "num_layers": self.num_layers,
                    "dropout": self.dropout,
                    "learning_rate": self.learning_rate,
                    "batch_size": self.batch_size,
                    "epochs": self.epochs,
                    "random_state": self.random_state,
                    "device_name": self.device_name,
                },
            }
            torch.save(artifact_payload, model_artifact_path)

        except Exception as error:
            raise ModelArtifactError(
                message=f"LSTM 아티팩트 저장 실패 ({model_artifact_path}): {str(error)}",
                artifact_path=model_artifact_path,
                operation_type="save",
                original_exception=error,
            )

    def load_artifact(self, model_artifact_path: str) -> "LSTMRegressor":
        """지정된 파일 경로로부터 LSTM 아티팩트를 로드하여 신경망 상태를 복원합니다.

        Args:
            model_artifact_path (str): 로드할 아티팩트 파일 경로.

        Returns:
            LSTMRegressor: 복원된 모델 인스턴스 자신(self).

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
            # [설계 의도] PyTorch torch.load 기반으로 체크포인트 로드 및 멤버 상태 복원
            execution_device: torch.device = torch.device(self.device_name)
            artifact_payload: Dict[str, Any] = torch.load(
                model_artifact_path, map_location=execution_device
            )

            self.feature_names = artifact_payload.get("feature_names")
            self.is_fitted = artifact_payload.get("is_fitted", True)
            self.model_name = artifact_payload.get("model_name", self.model_name)

            hyperparameters: Dict[str, Any] = artifact_payload.get(
                "hyperparameters", {}
            )
            self.sequence_length = hyperparameters.get(
                "sequence_length", self.sequence_length
            )
            self.hidden_dim = hyperparameters.get("hidden_dim", self.hidden_dim)
            self.num_layers = hyperparameters.get("num_layers", self.num_layers)
            self.dropout = hyperparameters.get("dropout", self.dropout)
            self.learning_rate = hyperparameters.get(
                "learning_rate", self.learning_rate
            )
            self.batch_size = hyperparameters.get("batch_size", self.batch_size)
            self.epochs = hyperparameters.get("epochs", self.epochs)

            # [설계 의도] 복원된 하이퍼파라미터로 내부 PyTorch 모듈 생성 후 state_dict 바인딩
            input_dimension: int = len(self.feature_names)
            self._pytorch_module = _PyTorchLSTMModule(
                input_dimension=input_dimension,
                hidden_dimension=self.hidden_dim,
                num_layers=self.num_layers,
                dropout_rate=self.dropout,
            ).to(execution_device)

            self._pytorch_module.load_state_dict(
                artifact_payload["module_state_dict"]
            )
            return self

        except Exception as error:
            raise ModelArtifactError(
                message=f"LSTM 아티팩트 로드 실패 ({model_artifact_path}): {str(error)}",
                artifact_path=model_artifact_path,
                operation_type="load",
                original_exception=error,
            )

    # --------------------------------------------------------------------------
    # Private Helper Methods (차원 보존 시퀀스 변환 로직)
    # --------------------------------------------------------------------------
    def _create_sequence_tensors(
        self,
        X_data: pd.DataFrame,
        y_data: Optional[pd.Series] = None,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """2차원 타불라 데이터프레임을 행 개수 유실 없이 3차원 시퀀스 텐서로 변환합니다.

        [차원 보존 제약] 시퀀스 길이(L) 이전의 초기 L-1개 데이터에 대해 최상단 행 패딩(Edge Padding)을
        수행하여 출력 텐서의 첫 번째 차원(N)이 입력 X_data의 행 수(N)와 정확히 1:1 대응하도록 보장합니다.

        Args:
            X_data (pd.DataFrame): 2차원 피처 데이터프레임.
            y_data (Optional[pd.Series]): 1차원 정답 타겟 시계열.

        Returns:
            Tuple[torch.Tensor, Optional[torch.Tensor]]:
                - 3차원 피처 텐서 [N_samples, Sequence_Length, Feature_Dim]
                - 1차원 타겟 텐서 [N_samples] 또는 None
        """
        raw_feature_array: np.ndarray = X_data.values
        total_sample_count: int = len(X_data)

        # [설계 의도] 초기 L-1개 행에 대해 첫 번째 행의 값을 복제하여 Edge Padding 수행
        padding_rows_count: int = self.sequence_length - 1
        if padding_rows_count > 0:
            first_row_repeated: np.ndarray = np.repeat(
                raw_feature_array[:1, :], padding_rows_count, axis=0
            )
            padded_feature_array: np.ndarray = np.vstack(
                [first_row_repeated, raw_feature_array]
            )
        else:
            padded_feature_array = raw_feature_array

        # [설계 의도] 슬라이딩 윈도우 기반 3차원 시퀀스 배열 생성
        sequence_list: List[np.ndarray] = []
        for sample_index in range(total_sample_count):
            window_slice: np.ndarray = padded_feature_array[
                sample_index : sample_index + self.sequence_length, :
            ]
            sequence_list.append(window_slice)

        sequence_numpy_array: np.ndarray = np.array(sequence_list)
        feature_sequence_tensor: torch.Tensor = torch.tensor(
            sequence_numpy_array, dtype=torch.float32
        )

        target_tensor: Optional[torch.Tensor] = None
        if y_data is not None:
            target_tensor = torch.tensor(y_data.values, dtype=torch.float32)

        return feature_sequence_tensor, target_tensor