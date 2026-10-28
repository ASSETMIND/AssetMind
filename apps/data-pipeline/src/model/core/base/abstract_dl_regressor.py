from abc import abstractmethod
import random
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from src.common.exceptions import ModelTrainingExecutionError
from src.model.core.base.abstract_regressor import (
    DEFAULT_MODEL_NAME,
    DEFAULT_RANDOM_STATE,
    DEFAULT_REQUESTED_DEVICE,
    AbstractRegressor,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [학습 루프 및 최적화 기본 하이퍼파라미터 설정]
DEFAULT_BATCH_SIZE: int = 64  # 미니배치 학습 및 추론 시 기본 배치 크기
DEFAULT_MAX_EPOCHS: int = 100  # 최대 학습 에포크 횟수
DEFAULT_LEARNING_RATE: float = 1e-3  # 옵티마이저 기본 학습률
DEFAULT_WEIGHT_DECAY: float = 1e-4  # 가중치 감쇠(L2 정규화) 기본 계수
DEFAULT_GRAD_CLIP_NORM: float = 1.0  # 기울기 폭발 방지를 위한 그래디언트 클리핑 최대 노름
SINGLE_SAMPLE_BATCH_SIZE: int = 1  # BatchNorm1d 분산 산출 불능 방지를 위한 단일 샘플 잔여 배치 기준값

# [회귀 신경망 출력 규격 설정]
REGRESSION_OUTPUT_DIM: int = 1  # 단일 연속형 타겟 회귀 출력 차원

# [조기 종료(Early Stopping) 기본 제어 설정]
DEFAULT_EARLY_STOPPING_PATIENCE: int = 20    # 검증 손실 미개선 허용 에포크 횟수
DEFAULT_MIN_DELTA: float = 1e-5              # 검증 손실 유의미 개선 판정을 위한 최소 변화량

# [DL 모델 공통 학습 루프 기본 하이퍼파라미터 템플릿]
DEFAULT_DL_TRAINING_PARAMS: Dict[str, Any] = {
    "batch_size": DEFAULT_BATCH_SIZE,
    "max_epochs": DEFAULT_MAX_EPOCHS,
    "learning_rate": DEFAULT_LEARNING_RATE,
    "weight_decay": DEFAULT_WEIGHT_DECAY,
    "grad_clip_norm": DEFAULT_GRAD_CLIP_NORM,
    "early_stopping_patience": DEFAULT_EARLY_STOPPING_PATIENCE,
    "min_delta": DEFAULT_MIN_DELTA,
}


# ==============================================================================
# Main DL Regressor Class
# ==============================================================================
class AbstractDLRegressor(AbstractRegressor):
    """PyTorch 기반 딥러닝 회귀 모델(2D Tabular 및 3D Sequence 계열)의 추상 기본 클래스.

    Attributes:
        device (str): 모델 연산이 수행될 런타임 하드웨어 가속기 식별자('cpu', 'cuda', 'mps').
        network (Optional[nn.Module]): 하위 클래스에서 구축된 PyTorch 신경망 모듈.
        input_dim (Optional[int]): 입력 피처의 차원(컬럼 개수).
    """

    # --------------------------------------------------------------------------
    # Public API Functions
    # --------------------------------------------------------------------------
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        device: str = DEFAULT_REQUESTED_DEVICE,
        **hyperparameters: Any,
    ) -> None:
        """AbstractDLRegressor 인스턴스와 런타임 디바이스 상태를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 DEFAULT_MODEL_NAME.
            random_state (int): 난수 제어 시드. 기본값은 DEFAULT_RANDOM_STATE.
            device (str): 요청 연산 디바이스('auto', 'cpu', 'cuda', 'mps'). 기본값은 'auto'.
            **hyperparameters (Any): 신경망 구조 및 학습 루프 제어용 하이퍼파라미터.
        """
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_DL_TRAINING_PARAMS,
            custom_params=hyperparameters,
        )
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **merged_hyperparameters,
        )
        self.device: str = self._detect_device(requested_device=device)
        self.network: Optional[nn.Module] = None
        self.input_dim: Optional[int] = None

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[Union[pd.Series, np.ndarray]] = None,
        **kwargs: Any,
    ) -> "AbstractDLRegressor":
        """입력 데이터를 텐서로 변환하고 PyTorch 신경망 학습 및 조기 종료를 집행합니다.

        Args:
            X_train (pd.DataFrame): 훈련용 2D 피처 행렬.
            y_train (pd.Series): 훈련용 1D 타겟 시계열.
            X_val (Optional[pd.DataFrame]): 조기 종료용 검증 피처 행렬. 기본값은 None.
            y_val (Optional[pd.Series]): 조기 종료용 검증 타겟 시리즈. 기본값은 None.
            sample_weight (Optional[Union[pd.Series, np.ndarray]]): 관측치별 중요도 가중치. 기본값은 None.
            **kwargs (Any): 동적 런타임 학습 제어 인자.

        Returns:
            AbstractDLRegressor: 학습 및 최적 가중치 복원이 완료된 모델 인스턴스 자신(self).

        Raises:
            ModelTrainingExecutionError: 데이터 검증 실패 또는 신경망 학습 중 예외가 발생한 경우.
        """
        self._validate_train_data(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            sample_weight=sample_weight,
        )
        try:
            _set_reproducible_seed(seed=self.random_state)
            self.feature_names = X_train.columns.tolist()
            self.input_dim = len(self.feature_names)

            train_tensors, val_tensors = self._prepare_train_tensors(
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                sample_weight=sample_weight,
            )
            self.network = self._build_network(input_dim=self.input_dim).to(self.device)
            optimizer: torch.optim.Optimizer = self._create_optimizer(network=self.network)

            self._execute_training_loop(
                train_tensors=train_tensors,
                val_tensors=val_tensors,
                optimizer=optimizer,
            )
            self.is_fitted = True
            return self
        except ModelTrainingExecutionError:
            raise
        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"'{self.model_name}' DL 모델 학습 중 오류 발생: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            ) from error

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """학습된 PyTorch 신경망을 사용하여 배치 단위 추론을 수행합니다.

        Args:
            X_test (pd.DataFrame): 추론을 수행할 2D 피처 행렬.

        Returns:
            pd.Series: X_test 인덱스가 보존된 1D 예측값 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ModelTrainingExecutionError: 추론 데이터 결손, 피처 불일치 또는 추론 실패 시.
        """
        self._validate_fitted_state(operation_name="predict")
        aligned_features: pd.DataFrame = self._align_predict_features(X_test=X_test)
        try:
            predict_tensor: torch.Tensor = self._prepare_predict_tensors(
                X_test=aligned_features
            )
            raw_predictions: np.ndarray = self._execute_inference_loop(
                predict_tensor=predict_tensor
            )
            return self._format_prediction_series(
                predictions=raw_predictions,
                index=aligned_features.index,
            )
        except ModelTrainingExecutionError:
            raise
        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"'{self.model_name}' DL 모델 추론 중 오류 발생: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            ) from error

    # --------------------------------------------------------------------------
    # Internal Helper Functions
    # --------------------------------------------------------------------------
    @abstractmethod
    def _build_network(self, input_dim: int) -> nn.Module:
        """하위 딥러닝 아키텍처의 PyTorch 신경망 모듈(nn.Module)을 생성하여 반환합니다."""
        pass

    def _prepare_train_tensors(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> Tuple[
        Tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        Optional[Tuple[torch.Tensor, torch.Tensor]],
    ]:
        """학습 및 검증 데이터를 텐서로 변환하며, 피처 변환은 _prepare_predict_tensors에 위임합니다."""
        # [설계 의도] 피처 텐서 변환을 _prepare_predict_tensors로 일원화하여 2D 모델과
        # 3D 모델(TCN) 모두 본 메서드의 중복 오버라이딩 없이 동일한 학습 데이터 준비 파이프라인을 공유함
        x_train_tensor: torch.Tensor = self._prepare_predict_tensors(X_test=X_train)
        y_train_tensor: torch.Tensor = torch.tensor(
            y_train.values, dtype=torch.float32
        ).view(-1, 1)

        if sample_weight is not None:
            weight_array: np.ndarray = np.asarray(sample_weight, dtype=np.float32)
            weight_tensor: torch.Tensor = torch.tensor(
                weight_array, dtype=torch.float32
            ).view(-1, 1)
        else:
            weight_tensor = torch.ones_like(y_train_tensor)

        val_tensors: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
        if X_val is not None and y_val is not None:
            aligned_val_features: pd.DataFrame = self._align_predict_features(X_test=X_val)
            x_val_tensor: torch.Tensor = self._prepare_predict_tensors(
                X_test=aligned_val_features
            )
            y_val_tensor: torch.Tensor = torch.tensor(
                y_val.values, dtype=torch.float32
            ).view(-1, 1)
            val_tensors = (x_val_tensor, y_val_tensor)

        return (x_train_tensor, y_train_tensor, weight_tensor), val_tensors

    def _prepare_predict_tensors(self, X_test: pd.DataFrame) -> torch.Tensor:
        """추론용 데이터프레임을 2D 피처 텐서로 변환하며, 3D 모델(TCN)에서 오버라이딩을 허용합니다."""
        return torch.tensor(X_test.values, dtype=torch.float32)

    def _create_optimizer(self, network: nn.Module) -> torch.optim.Optimizer:
        """하이퍼파라미터 설정에 기반하여 AdamW 옵티마이저를 생성합니다."""
        learning_rate: float = float(
            self.hyperparameters.get("learning_rate", DEFAULT_LEARNING_RATE)
        )
        weight_decay: float = float(
            self.hyperparameters.get("weight_decay", DEFAULT_WEIGHT_DECAY)
        )
        return torch.optim.AdamW(
            network.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay,
        )

    def _execute_training_loop(
        self,
        train_tensors: Tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        val_tensors: Optional[Tuple[torch.Tensor, torch.Tensor]],
        optimizer: torch.optim.Optimizer,
    ) -> None:
        """에포크 학습 루프, 검증 손실 기반 조기 종료 및 최적 가중치 복원을 수행합니다."""
        batch_size: int = int(self.hyperparameters.get("batch_size", DEFAULT_BATCH_SIZE))
        max_epochs: int = int(self.hyperparameters.get("max_epochs", DEFAULT_MAX_EPOCHS))
        patience: int = int(
            self.hyperparameters.get(
                "early_stopping_patience", DEFAULT_EARLY_STOPPING_PATIENCE
            )
        )
        min_delta: float = float(self.hyperparameters.get("min_delta", DEFAULT_MIN_DELTA))
        grad_clip_norm: float = float(
            self.hyperparameters.get("grad_clip_norm", DEFAULT_GRAD_CLIP_NORM)
        )

        # [설계 의도] 매 에포크/배치마다 발생하는 CPU-GPU 메모리 전송 및 DataLoader collate 병목을
        # 원천 제거하기 위해 학습 및 검증 텐서를 루프 진입 전 타겟 디바이스에 일괄 사전 적재함
        device_train_tensors: Tuple[torch.Tensor, torch.Tensor, torch.Tensor] = (
            train_tensors[0].to(self.device),
            train_tensors[1].to(self.device),
            train_tensors[2].to(self.device),
        )
        device_val_tensors: Optional[Tuple[torch.Tensor, torch.Tensor]] = (
            (val_tensors[0].to(self.device), val_tensors[1].to(self.device))
            if val_tensors is not None
            else None
        )

        num_train_samples: int = int(device_train_tensors[0].size(0))
        # [설계 의도] 마지막 미니배치 샘플 수가 1개일 때 BatchNorm1d의 채널 분산 계산 불가(ValueError)를
        # 방지하기 위해 잔여 샘플이 1개인 경우에만 마지막 단일 표본 배치를 절삭함
        should_drop_last: bool = (
            num_train_samples > SINGLE_SAMPLE_BATCH_SIZE
            and (num_train_samples % batch_size) == SINGLE_SAMPLE_BATCH_SIZE
        )

        best_val_loss: float = float("inf")
        best_state_dict: Optional[Dict[str, torch.Tensor]] = None
        patience_counter: int = 0

        for _ in range(max_epochs):
            _train_one_epoch(
                network=self.network,
                train_tensors=device_train_tensors,
                optimizer=optimizer,
                batch_size=batch_size,
                should_drop_last=should_drop_last,
                grad_clip_norm=grad_clip_norm,
            )

            if device_val_tensors is not None:
                current_val_loss: float = _validate_one_epoch(
                    network=self.network,
                    val_tensors=device_val_tensors,
                    batch_size=batch_size,
                )
                if current_val_loss < (best_val_loss - min_delta):
                    best_val_loss = current_val_loss
                    # [설계 의도] copy.deepcopy의 파이썬 객체 그래프 탐색 오버헤드를 피하고
                    # 텐서 버퍼만 고속 복제하여 최적 가중치 스냅샷을 보존함
                    best_state_dict = {
                        key: value.detach().clone()
                        for key, value in self.network.state_dict().items()
                    }
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        break

        # [설계 의도] 조기 종료 시 마지막 과적합 에포크가 아닌 검증 손실 최저점의 가중치를 복원함
        if best_state_dict is not None:
            self.network.load_state_dict(best_state_dict)

    def _execute_inference_loop(self, predict_tensor: torch.Tensor) -> np.ndarray:
        """신경망을 평가 모드로 전환하고 미니배치 단위로 추론 결과를 산출합니다."""
        batch_size: int = int(self.hyperparameters.get("batch_size", DEFAULT_BATCH_SIZE))
        num_samples: int = int(predict_tensor.size(0))
        device_predict_tensor: torch.Tensor = predict_tensor.to(self.device)

        self.network.eval()
        batch_predictions: List[torch.Tensor] = []
        with torch.no_grad():
            for start_idx in range(0, num_samples, batch_size):
                batch_features: torch.Tensor = device_predict_tensor[
                    start_idx : start_idx + batch_size
                ]
                outputs: torch.Tensor = self.network(batch_features)
                batch_predictions.append(outputs)

        concatenated_outputs: torch.Tensor = torch.cat(batch_predictions, dim=0)
        return concatenated_outputs.cpu().numpy().ravel()

    def _serialize_artifact(self, model_artifact_path: str) -> None:
        """PyTorch 직렬화 엔진(torch.save)을 사용하여 모델 메타데이터와 신경망 가중치를 저장합니다."""
        checkpoint_payload: Dict[str, Any] = {
            "model_name": self.model_name,
            "random_state": self.random_state,
            "hyperparameters": self.hyperparameters,
            "feature_names": self.feature_names,
            "input_dim": self.input_dim,
            "is_fitted": self.is_fitted,
            "network_state_dict": (
                self.network.state_dict() if self.network is not None else None
            ),
        }
        torch.save(checkpoint_payload, model_artifact_path)

    @classmethod
    def _deserialize_artifact(cls, model_artifact_path: str) -> "AbstractDLRegressor":
        """저장된 PyTorch 체크포인트로부터 모델 인스턴스와 신경망 가중치를 복원합니다."""
        # [설계 의도] GPU에서 저장된 모델을 CPU/MPS 환경에서 로드할 때도 호환되도록 cpu로 선매핑함
        checkpoint_payload: Dict[str, Any] = torch.load(
            model_artifact_path,
            map_location="cpu",
            weights_only=False,
        )
        restored_instance: "AbstractDLRegressor" = cls(
            model_name=checkpoint_payload["model_name"],
            random_state=checkpoint_payload["random_state"],
            **checkpoint_payload.get("hyperparameters", {}),
        )
        restored_instance.feature_names = checkpoint_payload["feature_names"]
        restored_instance.input_dim = checkpoint_payload["input_dim"]
        restored_instance.is_fitted = checkpoint_payload["is_fitted"]

        if (
            restored_instance.input_dim is not None
            and checkpoint_payload.get("network_state_dict") is not None
        ):
            restored_instance.network = restored_instance._build_network(
                input_dim=restored_instance.input_dim
            ).to(restored_instance.device)
            restored_instance.network.load_state_dict(
                checkpoint_payload["network_state_dict"]
            )
            restored_instance.network.eval()

        return restored_instance


def _set_reproducible_seed(seed: int) -> None:
    """학습 재현성 보장을 위해 Python, NumPy, PyTorch 난수 시드를 일괄 고정합니다."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _compute_weighted_mse_loss(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    weights: torch.Tensor,
) -> torch.Tensor:
    """관측치별 가중치(sample_weight)가 반영된 평균 제곱 오차(MSE) 손실을 계산합니다."""
    squared_errors: torch.Tensor = (predictions - targets) ** 2
    weighted_errors: torch.Tensor = squared_errors * weights
    return torch.mean(weighted_errors)


def _train_one_epoch(
    network: nn.Module,
    train_tensors: Tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    optimizer: torch.optim.Optimizer,
    batch_size: int,
    should_drop_last: bool,
    grad_clip_norm: float,
) -> None:
    """단일 에포크에 대한 미니배치 순전파, 역전파, 그래디언트 클리핑 및 가중치 갱신을 수행합니다."""
    network.train()
    x_train, y_train, weight_train = train_tensors
    num_samples: int = int(x_train.size(0))

    # [설계 의도] DataLoader의 파이썬 루프 오버헤드와 매 배치 loss.item() GPU-CPU 강제 동기화를 제거하고,
    # 텐서 인덱스 셔플링 및 슬라이싱만으로 비동기 GPU 파이프라인이 끊김 없이 구동되도록 최적화함
    shuffled_indices: torch.Tensor = torch.randperm(
        num_samples, device=x_train.device
    )
    effective_samples: int = (
        num_samples - SINGLE_SAMPLE_BATCH_SIZE
        if should_drop_last
        else num_samples
    )

    for start_idx in range(0, effective_samples, batch_size):
        batch_indices: torch.Tensor = shuffled_indices[
            start_idx : start_idx + batch_size
        ]
        batch_x: torch.Tensor = x_train[batch_indices]
        batch_y: torch.Tensor = y_train[batch_indices]
        batch_weight: torch.Tensor = weight_train[batch_indices]

        optimizer.zero_grad(set_to_none=True)
        predictions: torch.Tensor = network(batch_x)
        loss: torch.Tensor = _compute_weighted_mse_loss(
            predictions=predictions,
            targets=batch_y,
            weights=batch_weight,
        )
        loss.backward()

        if grad_clip_norm > 0.0:
            torch.nn.utils.clip_grad_norm_(
                network.parameters(), max_norm=grad_clip_norm
            )
        optimizer.step()


def _validate_one_epoch(
    network: nn.Module,
    val_tensors: Tuple[torch.Tensor, torch.Tensor],
    batch_size: int,
) -> float:
    """검증 데이터셋에 대해 그래디언트 계산 없이 평균 제곱 오차(MSE) 손실을 평가합니다."""
    network.eval()
    x_val, y_val = val_tensors
    num_samples: int = int(x_val.size(0))

    # [설계 의도] 매 배치마다 .item()을 호출하지 않고 GPU 텐서 상에서 제곱 오차 합계를 누적한 뒤,
    # 에포크 종료 시점에 단 1회만 스칼라 동기화(.item())를 수행하여 검증 오버헤드를 최소화함
    squared_error_sum: torch.Tensor = torch.zeros(
        (), dtype=torch.float32, device=x_val.device
    )

    with torch.no_grad():
        for start_idx in range(0, num_samples, batch_size):
            batch_x: torch.Tensor = x_val[start_idx : start_idx + batch_size]
            batch_y: torch.Tensor = y_val[start_idx : start_idx + batch_size]
            predictions: torch.Tensor = network(batch_x)
            batch_squared_errors: torch.Tensor = (predictions - batch_y) ** 2
            squared_error_sum += torch.sum(batch_squared_errors)

    return float((squared_error_sum / num_samples).item())