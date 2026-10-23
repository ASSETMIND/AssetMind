from typing import List, Sequence, Tuple

import torch
import torch.nn as nn

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [시계열 합성곱 및 회귀 신경망 출력 규격 설정]
REGRESSION_OUTPUT_DIM: int = 1    # 단일 연속형 타겟 회귀 출력 차원
DILATION_BASE: int = 2            # 계층별 수용장 확장을 위한 지수적 팽창(Dilation) 밑수
SHORTCUT_KERNEL_SIZE: int = 1     # 잔차 연결 시 채널 차원 정렬용 1x1 합성곱 커널 크기
LAST_TIMESTEP_INDEX: int = -1     # 인과적 시퀀스 내 현재 시점(t) 표상 추출 인덱스


class TCNNetwork(nn.Module):
    """다중 팽창 잔차 블록 스택과 최종 시점 회귀 헤드를 결합한 TCN 신경망 모듈.

    3D 인과적 시계열 텐서(Batch, Channels, Sequence_Length)를 입력받아 지수적으로
    팽창률(Dilation)이 증가하는 인과적 1D 합성곱 잔차 블록들을 통과시킨 뒤,
    마지막 시점(t)의 은닉 표상으로부터 단일 연속형 회귀 예측치를 산출합니다.

    Attributes:
        temporal_backbone (nn.Sequential): 지수적 팽창률이 적용된 다중 시계열 잔차 블록 스택.
        prediction_head (nn.Linear): 마지막 시점(t)의 은닉 채널 벡터를 회귀 예측치로 매핑하는 선형 헤드.
    """
    def __init__(
        self,
        input_dim: int,
        hidden_channels: Sequence[int],
        kernel_size: int,
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> None:
        """계층별 지수적 팽창률이 적용된 TCN 백본과 마지막 시점(t) 선형 회귀 헤드를 초기화합니다.

        Args:
            input_dim (int): 입력 시계열 텐서의 피처 채널 차원(컬럼 개수).
            hidden_channels (Sequence[int]): TCN 잔차 블록 계층별 출력 채널 수 시퀀스.
            kernel_size (int): 1D 인과적 합성곱(Causal Conv1d) 커널 크기.
            dropout_rate (float): 시계열 잔차 블록 내부에 적용할 과적합 방지 드롭아웃 비율.
            use_batch_norm (bool): 합성곱 계층별 배치 정규화(BatchNorm1d) 적용 여부.
        """
        super().__init__()
        # 1. 계층 깊이에 따라 수용장이 지수적으로 확장되는 TCN 잔차 백본 및 최종 채널 차원 생성
        self.temporal_backbone, final_channel_dim = self._build_temporal_backbone(
            input_dim=input_dim,
            hidden_channels=hidden_channels,
            kernel_size=kernel_size,
            dropout_rate=dropout_rate,
            use_batch_norm=use_batch_norm,
        )

        # 2. 마지막 시점(t)의 은닉 채널 표현을 단일 연속형 타겟으로 매핑하는 선형 회귀 헤드 초기화
        self.prediction_head: nn.Linear = nn.Linear(
            final_channel_dim, REGRESSION_OUTPUT_DIM
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """3D 시계열 텐서(B, C, L)를 통과시킨 뒤 마지막 시점(t)의 은닉 상태에서 예측치를 산출합니다.

        Args:
            x (torch.Tensor): (Batch_Size, Input_Dim, Sequence_Length) 형태의 3D 시계열 텐서.

        Returns:
            torch.Tensor: (Batch_Size, 1) 형태의 2D 연속형 회귀 예측치 텐서.
        """
        # 1. 다중 팽창 인과적 합성곱 백본을 통과시켜 시계열 문맥이 인코딩된 3D 특징 맵 산출
        encoded_sequence: torch.Tensor = self.temporal_backbone(x)

        # 2. 인과적 윈도우의 가장 마지막 시점(t, LAST_TIMESTEP_INDEX) 은닉 벡터 추출
        last_step_features: torch.Tensor = encoded_sequence[
            :, :, LAST_TIMESTEP_INDEX
        ]

        # 3. 선형 회귀 헤드를 통과시켜 최종 예측값 반환
        return self.prediction_head(last_step_features)


    @staticmethod
    def _build_temporal_backbone(
        input_dim: int,
        hidden_channels: Sequence[int],
        kernel_size: int,
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> Tuple[nn.Sequential, int]:
        """계층 깊이에 따라 팽창률(2^l)이 지수적으로 증가하는 잔차 블록 시퀀셜과 최종 채널 수를 생성합니다."""
        # 1. 계층 인덱스(l)에 따라 팽창률을 2^l로 산출하며 시계열 잔차 블록을 순차 적층
        blocks: List[nn.Module] = []
        current_channels: int = input_dim

        for layer_index, out_channels in enumerate(hidden_channels):
            dilation: int = DILATION_BASE**layer_index
            blocks.append(
                _TemporalResidualBlock(
                    in_channels=current_channels,
                    out_channels=out_channels,
                    kernel_size=kernel_size,
                    dilation=dilation,
                    dropout_rate=dropout_rate,
                    use_batch_norm=use_batch_norm,
                )
            )
            current_channels = out_channels

        # 2. 조립된 Sequential 백본 모듈과 최종 출력 채널 차원을 튜플로 반환
        return nn.Sequential(*blocks), current_channels


class _TemporalResidualBlock(nn.Module):
    """지수적 팽창(Dilation)과 좌측 인과적 패딩이 적용된 이중 1D 합성곱 잔차 블록 내부 모듈."""
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> None:
        """이중 인과적 합성곱 분기와 입출력 채널 정렬용 1x1 잔차 숏컷 레이어를 초기화합니다."""
        super().__init__()
        # 1. 좌측 인과적 패딩이 포함된 이중 Dilated Conv1d 잔차 분기 생성
        self.conv_branch: nn.Sequential = self._build_causal_conv_branch(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=kernel_size,
            dilation=dilation,
            dropout_rate=dropout_rate,
            use_batch_norm=use_batch_norm,
        )

        # 2. 입출력 채널 수가 다를 경우에만 1x1 합성곱으로 차원을 정렬하고 동일하면 항등 경로 유지
        self.residual_shortcut: nn.Module = (
            nn.Conv1d(
                in_channels=in_channels,
                out_channels=out_channels,
                kernel_size=SHORTCUT_KERNEL_SIZE,
            )
            if in_channels != out_channels
            else nn.Identity()
        )

        # 3. 잔차 합산 이후 적용할 비선형 활성화 함수 초기화
        self.output_activation: nn.Module = nn.SiLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """입력 3D 시퀀스에 인과적 합성곱 결과와 숏컷 텐서를 합산하여 비선형 출력을 반환합니다."""
        # 1. 인과적 합성곱 분기 출력과 잔차 숏컷 출력을 합산한 뒤 비선형 활성화 적용
        return self.output_activation(
            self.conv_branch(x) + self.residual_shortcut(x)
        )
        

    @staticmethod
    def _build_causal_conv_branch(
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> nn.Sequential:
        """미래 시점 참조를 차단하는 좌측 제로 패딩 기반의 이중 Dilated Conv1d 시퀀셜을 생성합니다."""
        # 1. [설계 의도] 합성곱 커널이 우측(t + 1 이후 미래)을 참조하지 못하도록 (kernel_size - 1) * dilation 만큼
        # 좌측에만 패딩을 부여하여 입출력 시퀀스 길이(L) 보존과 엄격한 시간적 인과성(Causality)을 보장함
        causal_left_padding: int = (kernel_size - 1) * dilation
        layers: List[nn.Module] = []
        channel_pairs: Tuple[Tuple[int, int], ...] = (
            (in_channels, out_channels),
            (out_channels, out_channels),
        )

        # 2. 이중 인과적 합성곱(Pad -> Conv1d -> Norm -> SiLU -> Dropout1d) 레이어 순차 적층
        for current_in, current_out in channel_pairs:
            layers.append(nn.ConstantPad1d((causal_left_padding, 0), 0.0))
            layers.append(
                nn.Conv1d(
                    in_channels=current_in,
                    out_channels=current_out,
                    kernel_size=kernel_size,
                    dilation=dilation,
                )
            )
            if use_batch_norm:
                layers.append(nn.BatchNorm1d(current_out))
            layers.append(nn.SiLU())
            layers.append(nn.Dropout1d(p=dropout_rate))

        # 3. 조립된 인과적 합성곱 분기 Sequential 컨테이너 반환
        return nn.Sequential(*layers)