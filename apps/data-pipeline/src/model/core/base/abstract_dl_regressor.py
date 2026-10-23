from abc import abstractmethod
import copy
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

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

# [조기 종료(Early Stopping) 기본 제어 설정]
DEFAULT_EARLY_STOPPING_PATIENCE: int = 10  # 검증 손실 미개선 허용 에포크 횟수
DEFAULT_MIN_DELTA: float = 1e-5  # 검증 손실 유의미 개선 판정을 위한 최소 변화량


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
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **hyperparameters,
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
        sample_weight: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> "AbstractDLRegressor":
        """입력 데이터를 텐서로 변환하고 PyTorch 신경망 학습 및 조기 종료를 집행합니다.

        Args:
            X_train (pd.DataFrame): 훈련용 2D 피처 행렬.
            y_train (pd.Series): 훈련용 1D 타겟 시계열.
            X_val (Optional[pd.DataFrame]): 조기 종료용 검증 피처 행렬. 기본값은 None.
            y_val (Optional[pd.Series]): 조기 종료용 검증 타겟 시리즈. 기본값은 None.
            sample_weight (Optional[pd.Series]): 관측치별 중요도 가중치. 기본값은 None.
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
        sample_weight: Optional[pd.Series] = None,
    ) -> Tuple[
        Tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        Optional[Tuple[torch.Tensor, torch.Tensor]],
    ]:
        """학습 및 검증 데이터를 2D 텐서로 변환하며, 3D 모델(TCN)에서 오버라이딩을 허용합니다."""
        # [설계 의도] 2D 정형 모델(ResNet, DCNv2, FT-Transformer)은 본 기본 구현을 재사용하고,
        # 3D 모델(TCN)만 본 메서드를 오버라이딩하여 2D -> 3D Causal Windowing을 수행함
        x_train_tensor: torch.Tensor = torch.tensor(
            X_train.values, dtype=torch.float32
        )
        y_train_tensor: torch.Tensor = torch.tensor(
            y_train.values, dtype=torch.float32
        ).view(-1, 1)

        if sample_weight is not None:
            weight_tensor: torch.Tensor = torch.tensor(
                np.asarray(sample_weight, dtype=np.float32),
                dtype=torch.float32,
            ).view(-1, 1)
        else:
            weight_tensor = torch.ones_like(y_train_tensor)

        val_tensors: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
        if (
            X_val is not None
            and y_val is not None
            and not X_val.empty
            and not y_val.empty
        ):
            aligned_val_features: pd.DataFrame = self._align_predict_features(X_test=X_val)
            x_val_tensor: torch.Tensor = torch.tensor(
                aligned_val_features.values, dtype=torch.float32
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

        train_dataset: TensorDataset = TensorDataset(*train_tensors)
        # [설계 의도] 마지막 미니배치 샘플 수가 1개일 때 BatchNorm1d의 채널 분산 계산 불가(ValueError)를
        # 방지하기 위해 잔여 샘플이 1개인 경우에만 drop_last를 활성화하며, shuffle=True를 통해 에포크별 표본 누락을 방지함
        should_drop_last: bool = (
            len(train_dataset) > SINGLE_SAMPLE_BATCH_SIZE
            and (len(train_dataset) % batch_size) == SINGLE_SAMPLE_BATCH_SIZE
        )
        train_loader: DataLoader = DataLoader(
            dataset=train_dataset,
            batch_size=batch_size,
            shuffle=True,
            drop_last=should_drop_last,
        )

        best_val_loss: float = float("inf")
        best_state_dict: Optional[Dict[str, Any]] = None
        patience_counter: int = 0

        for _ in range(max_epochs):
            _train_one_epoch(
                network=self.network,
                dataloader=train_loader,
                optimizer=optimizer,
                device=self.device,
                grad_clip_norm=grad_clip_norm,
            )

            if val_tensors is not None:
                current_val_loss: float = _validate_one_epoch(
                    network=self.network,
                    val_tensors=val_tensors,
                    batch_size=batch_size,
                    device=self.device,
                )
                if current_val_loss < (best_val_loss - min_delta):
                    best_val_loss = current_val_loss
                    best_state_dict = copy.deepcopy(self.network.state_dict())
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
        predict_dataset: TensorDataset = TensorDataset(predict_tensor)
        predict_loader: DataLoader = DataLoader(
            dataset=predict_dataset,
            batch_size=batch_size,
            shuffle=False,
        )

        self.network.eval()
        batch_predictions: List[np.ndarray] = []
        with torch.no_grad():
            for (batch_features,) in predict_loader:
                batch_features = batch_features.to(self.device)
                outputs: torch.Tensor = self.network(batch_features)
                batch_predictions.append(outputs.detach().cpu().numpy())

        return np.concatenate(batch_predictions, axis=0).ravel()

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
    squared_errors: torch.Tensor = (predictions.view(-1, 1) - targets.view(-1, 1)) ** 2
    weighted_errors: torch.Tensor = squared_errors * weights.view(-1, 1)
    return torch.mean(weighted_errors)


def _train_one_epoch(
    network: nn.Module,
    dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    device: str,
    grad_clip_norm: float,
) -> float:
    """단일 에포크에 대한 미니배치 순전파, 역전파, 그래디언트 클리핑 및 가중치 갱신을 수행합니다."""
    network.train()
    epoch_loss_sum: float = 0.0
    total_samples: int = 0

    for batch_x, batch_y, batch_weight in dataloader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)
        batch_weight = batch_weight.to(device)

        optimizer.zero_grad()
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

        batch_count: int = batch_x.size(0)
        epoch_loss_sum += float(loss.item()) * batch_count
        total_samples += batch_count

    return epoch_loss_sum / max(total_samples, 1)


def _validate_one_epoch(
    network: nn.Module,
    val_tensors: Tuple[torch.Tensor, torch.Tensor],
    batch_size: int,
    device: str,
) -> float:
    """검증 데이터셋에 대해 그래디언트 계산 없이 평균 제곱 오차(MSE) 손실을 평가합니다."""
    val_dataset: TensorDataset = TensorDataset(*val_tensors)
    val_loader: DataLoader = DataLoader(
        dataset=val_dataset,
        batch_size=batch_size,
        shuffle=False,
    )

    network.eval()
    val_loss_sum: float = 0.0
    total_samples: int = 0

    with torch.no_grad():
        for batch_x, batch_y in val_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            predictions: torch.Tensor = network(batch_x)
            unit_weights: torch.Tensor = torch.ones_like(batch_y)
            loss: torch.Tensor = _compute_weighted_mse_loss(
                predictions=predictions,
                targets=batch_y,
                weights=unit_weights,
            )
            batch_count: int = batch_x.size(0)
            val_loss_sum += float(loss.item()) * batch_count
            total_samples += batch_count

    return val_loss_sum / max(total_samples, 1)