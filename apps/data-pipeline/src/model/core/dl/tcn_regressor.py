from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

from src.model.core.base.abstract_dl_regressor import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_EARLY_STOPPING_PATIENCE,
    DEFAULT_GRAD_CLIP_NORM,
    DEFAULT_LEARNING_RATE,
    DEFAULT_MAX_EPOCHS,
    DEFAULT_MIN_DELTA,
    DEFAULT_WEIGHT_DECAY,
    AbstractDLRegressor,
)
from src.model.core.base.abstract_regressor import (
    DEFAULT_RANDOM_STATE,
    DEFAULT_REQUESTED_DEVICE,
)
from src.model.core.dl.network.tcn_network import TCNNetwork

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [모델 식별 및 3D 인과적 윈도우 패딩 규격 설정]
TCN_MODEL_NAME: str = "TCNRegressor"                                # TCN 회귀 모델 기본 식별 명칭
CAUSAL_PAD_MODE: str = "replicate"                                  # 초기 시점 윈도우 구성을 위한 좌측 경계 복제 패딩 모드

# [신경망 아키텍처 및 학습 루프 기본 하이퍼파라미터 설정]
DEFAULT_TCN_PARAMS: Dict[str, Any] = {
    "sequence_length": 20,                                          # 2D -> 3D 변환 시 참조할 과거 시계열 윈도우 길이(L)
    "hidden_channels": (64, 64, 64),                                # TCN 잔차 블록 계층별 출력 채널 수 튜플
    "kernel_size": 3,                                               # 1D 인과적 합성곱(Causal Conv1d) 커널 크기
    "dropout_rate": 0.2,                                            # 시계열 잔차 블록 내부 과적합 방지 드롭아웃 비율
    "use_batch_norm": True,                                         # 합성곱 계층별 배치 정규화(BatchNorm1d) 적용 여부
    "batch_size": DEFAULT_BATCH_SIZE,                               # 미니배치 학습 및 추론 시 배치 크기
    "max_epochs": DEFAULT_MAX_EPOCHS,                               # 최대 학습 에포크 횟수
    "learning_rate": DEFAULT_LEARNING_RATE,                         # AdamW 옵티마이저 학습률
    "weight_decay": DEFAULT_WEIGHT_DECAY,                           # AdamW 가중치 감쇠(L2 정규화) 계수
    "grad_clip_norm": DEFAULT_GRAD_CLIP_NORM,                       # 기울기 폭발 방지를 위한 그래디언트 클리핑 최대 노름
    "early_stopping_patience": DEFAULT_EARLY_STOPPING_PATIENCE,     # 검증 손실 미개선 허용 에포크 횟수
    "min_delta": DEFAULT_MIN_DELTA,                                 # 검증 손실 유의미 개선 판정 최소 변화량
}


class TCNRegressor(AbstractDLRegressor):
    """Temporal Convolutional Network(TCN) 3D 시계열 회귀 알고리즘 구체 클래스.

    AbstractDLRegressor의 공통 생명주기(fit, predict, save_artifact, load_artifact)를
    상속받아 재사용하며, 2D 정형 입력의 3D 인과적 슬라이딩 윈도우(Causal Windowing) 변환과
    분리된 TCNNetwork 모듈 생성을 전담합니다.

    Attributes:
        device (str): 모델 연산이 수행될 런타임 하드웨어 가속기 식별자('cpu', 'cuda', 'mps').
        network (Optional[nn.Module]): 학습 및 추론을 수행하는 TCN 신경망 모듈.
        input_dim (Optional[int]): 입력 피처의 채널 차원(컬럼 개수).
    """
    def __init__(
        self,
        model_name: str = TCN_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        device: str = DEFAULT_REQUESTED_DEVICE,
        **hyperparameters: Any,
    ) -> None:
        """TCNRegressor 인스턴스, 런타임 디바이스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 TCN_MODEL_NAME.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            device (str): 요청 연산 디바이스('auto', 'cpu', 'cuda', 'mps'). 기본값은 'auto'.
            **hyperparameters (Any): 외부 설정 또는 Optuna에서 주입되는 가변 하이퍼파라미터.
        """
        # 1. 기본 하이퍼파라미터 사본에 외부 주입 커스텀 하이퍼파라미터 병합
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_TCN_PARAMS,
            custom_params=hyperparameters,
        )

        # 2. 상위 추상 클래스(AbstractDLRegressor) 공통 상태 및 디바이스 초기화
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            device=device,
            **merged_hyperparameters,
        )


    def _build_network(self, input_dim: int) -> nn.Module:
        """설정된 하이퍼파라미터와 입력 피처 차원을 바인딩하여 Dilated Causal TCN 신경망을 생성합니다."""
        # 1. 신경망 아키텍처 구성에 필요한 하이퍼파라미터 추출 및 타입 변환
        hidden_channels: Tuple[int, ...] = tuple(
            int(channel) for channel in self.hyperparameters["hidden_channels"]
        )
        kernel_size: int = int(self.hyperparameters["kernel_size"])
        dropout_rate: float = float(self.hyperparameters["dropout_rate"])
        use_batch_norm: bool = bool(self.hyperparameters["use_batch_norm"])

        # 2. 순수 신경망 모듈(TCNNetwork) 인스턴스 생성 및 반환
        return TCNNetwork(
            input_dim=input_dim,
            hidden_channels=hidden_channels,
            kernel_size=kernel_size,
            dropout_rate=dropout_rate,
            use_batch_norm=use_batch_norm,
        )

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
        """2D 학습 및 검증 데이터프레임을 미래 참조 누수가 차단된 3D Causal Window 텐서로 변환합니다."""
        # 1. 시계열 윈도우 길이(L) 추출 및 학습 피처/타겟 텐서 변환
        sequence_length: int = max(1, int(self.hyperparameters["sequence_length"]))

        x_train_tensor: torch.Tensor = self._convert_to_causal_3d_tensor(
            features_df=X_train,
            sequence_length=sequence_length,
        )
        y_train_tensor: torch.Tensor = torch.tensor(
            y_train.values, dtype=torch.float32
        ).view(-1, 1)

        # 2. 샘플 가중치 텐서 구성 (미지정 시 동일 가중치 1.0 부여)
        if sample_weight is not None:
            weight_tensor: torch.Tensor = torch.tensor(
                np.asarray(sample_weight, dtype=np.float32),
                dtype=torch.float32,
            ).view(-1, 1)
        else:
            weight_tensor = torch.ones_like(y_train_tensor)

        # 3. 검증 데이터가 유효한 경우 피처 정렬 후 동일한 3D Causal Window 텐서로 변환
        val_tensors: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
        if (
            X_val is not None
            and y_val is not None
            and not X_val.empty
            and not y_val.empty
        ):
            aligned_val_features: pd.DataFrame = self._align_predict_features(
                X_test=X_val
            )
            x_val_tensor: torch.Tensor = self._convert_to_causal_3d_tensor(
                features_df=aligned_val_features,
                sequence_length=sequence_length,
            )
            y_val_tensor: torch.Tensor = torch.tensor(
                y_val.values, dtype=torch.float32
            ).view(-1, 1)
            val_tensors = (x_val_tensor, y_val_tensor)

        # 4. 학습 텐서 튜플과 검증 텐서 튜플 반환
        return (x_train_tensor, y_train_tensor, weight_tensor), val_tensors

    def _prepare_predict_tensors(self, X_test: pd.DataFrame) -> torch.Tensor:
        """추론용 2D 데이터프레임을 행 길이(N) 손실 없는 3D Causal Window 텐서로 변환합니다."""
        # 1. 설정된 시퀀스 길이를 적용하여 2D 추론 피처를 3D 인과적 윈도우 텐서로 변환 및 반환
        sequence_length: int = max(1, int(self.hyperparameters["sequence_length"]))
        return self._convert_to_causal_3d_tensor(
            features_df=X_test,
            sequence_length=sequence_length,
        )

    @staticmethod
    def _convert_to_causal_3d_tensor(
        features_df: pd.DataFrame,
        sequence_length: int,
    ) -> torch.Tensor:
        """2D 피처 행렬(N, F)을 좌측 경계 패딩 및 Unfold 연산을 통해 3D 시퀀스 텐서(N, F, L)로 변환합니다."""
        # 1. [설계 의도] 시점 t의 윈도우가 [t - L + 1, ..., t] 과거 구간만 참조하도록 좌측에만 (L - 1)만큼
        # 초기 관측치를 복제 패딩하여, 미래 정보 누수(Look-ahead Bias)와 샘플 수(N) 손실을 동시에 방지함
        features_2d: torch.Tensor = torch.tensor(
            features_df.values, dtype=torch.float32
        )
        channel_first_tensor: torch.Tensor = features_2d.transpose(0, 1).unsqueeze(0)
        left_padding_size: int = sequence_length - 1

        # 2. 시간축 좌측 경계에 복제 패딩(replicate) 적용
        padded_tensor: torch.Tensor = F.pad(
            channel_first_tensor,
            pad=(left_padding_size, 0),
            mode=CAUSAL_PAD_MODE,
        ).squeeze(0)

        # 3. 슬라이딩 윈도우(unfold) 추출 후 (Batch_Size, Channels, Sequence_Length) 차원으로 정렬하여 반환
        unfolded_windows: torch.Tensor = padded_tensor.unfold(
            dimension=1,
            size=sequence_length,
            step=1,
        )
        return unfolded_windows.permute(1, 0, 2).contiguous()