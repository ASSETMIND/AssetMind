from typing import List

import torch
import torch.nn as nn

from src.model.core.base.abstract_dl_regressor import REGRESSION_OUTPUT_DIM


class TabularResNetNetwork(nn.Module):
    """입력 투영층, 다중 잔차 블록 스택 및 회귀 출력 헤드를 결합한 Tabular ResNet 신경망 모듈.

    2D 정형 피처 텐서를 은닉 차원으로 선형 투영한 뒤, 항등 경로(Skip-Connection)가 보장된
    Pre-Norm 잔차 블록들을 통과시켜 고차 비선형 표현을 학습하고 단일 회귀 예측치를 산출합니다.

    Attributes:
        input_projection (nn.Linear): 원본 입력 피처 차원을 은닉 표현 차원으로 매핑하는 선형 투영층.
        residual_blocks (nn.Sequential): 적층된 N개의 Tabular ResNet 잔차 블록 시퀀셜 모듈.
        prediction_head (nn.Sequential): 최종 잔차 표현을 단일 회귀 예측치로 변환하는 출력 헤드.
    """
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        num_blocks: int,
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> None:
        """입력 피처 투영층, N개의 잔차 블록 백본 및 최종 회귀 예측 헤드를 초기화합니다.

        Args:
            input_dim (int): 입력 정형 데이터의 피처 차원(컬럼 개수).
            hidden_dim (int): 잔차 블록 내부의 은닉 표현 차원 크기.
            num_blocks (int): 순차적으로 적층할 잔차 블록의 개수.
            dropout_rate (float): 잔차 분기 내부에 적용할 과적합 방지 드롭아웃 비율.
            use_batch_norm (bool): 블록 및 헤드 내부의 배치 정규화(BatchNorm1d) 적용 여부.
        """
        super().__init__()
        # 1. 입력 피처 차원을 은닉 차원으로 변환하는 선형 투영층 초기화
        self.input_projection: nn.Linear = nn.Linear(input_dim, hidden_dim)

        # 2. 지정된 블록 개수만큼 잔차 블록을 적층한 백본 모듈 생성
        self.residual_blocks: nn.Sequential = self._build_residual_backbone(
            hidden_dim=hidden_dim,
            num_blocks=num_blocks,
            dropout_rate=dropout_rate,
            use_batch_norm=use_batch_norm,
        )

        # 3. 은닉 표현을 단일 연속형 타겟으로 매핑하는 회귀 예측 헤드 생성
        self.prediction_head: nn.Sequential = self._build_prediction_head(
            hidden_dim=hidden_dim,
            use_batch_norm=use_batch_norm,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """2D 정형 피처 텐서를 입력받아 잔차 표현 학습을 거쳐 회귀 예측치를 산출합니다.

        Args:
            x (torch.Tensor):(Batch_Size, Input_Dim) 형태의 2D 정형 입력 피처 텐서.

        Returns:
            torch.Tensor: (Batch_Size, 1) 형태의 2D 연속형 회귀 예측치 텐서.
        """
        # 1. 원본 입력 피처를 은닉 차원 공간으로 선형 투영
        projected_features: torch.Tensor = self.input_projection(x)

        # 2. 적층된 잔차 블록을 통과시키며 항등 경로 기반의 비선형 표현 추출
        residual_features: torch.Tensor = self.residual_blocks(projected_features)

        # 3. 회귀 헤드를 통과시켜 최종 예측값 반환
        return self.prediction_head(residual_features)


    @staticmethod
    def _build_residual_backbone(
        hidden_dim: int,
        num_blocks: int,
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> nn.Sequential:
        """지정된 개수만큼의 Tabular ResNet 잔차 블록을 순차 적층한 백본 시퀀셜을 생성합니다."""
        # 1. 동일한 은닉 차원 규격을 공유하는 N개의 잔차 블록 리스트 구성
        blocks: List[nn.Module] = [
            _TabularResNetBlock(
                hidden_dim=hidden_dim,
                dropout_rate=dropout_rate,
                use_batch_norm=use_batch_norm,
            )
            for _ in range(num_blocks)
        ]

        # 2. 순차 연산을 위한 Sequential 컨테이너로 래핑하여 반환
        return nn.Sequential(*blocks)

    @staticmethod
    def _build_prediction_head(
        hidden_dim: int,
        use_batch_norm: bool,
    ) -> nn.Sequential:
        """최종 잔차 블록 출력을 정규화 및 활성화한 후 단일 타겟 차원으로 투영하는 헤드를 생성합니다."""
        # 1. Pre-Norm 잔차 구조의 마지막 출력 스케일을 안정화하기 위한 정규화·활성화 및 선형 출력층 결합
        layers: List[nn.Module] = []
        if use_batch_norm:
            layers.append(nn.BatchNorm1d(hidden_dim))
        layers.extend([nn.SiLU(), nn.Linear(hidden_dim, REGRESSION_OUTPUT_DIM)])
        return nn.Sequential(*layers)


class _TabularResNetBlock(nn.Module):
    """단일 잔차 연결(Skip-Connection)을 수행하는 Tabular ResNet 내부 블록 모듈."""

    def __init__(
        self,
        hidden_dim: int,
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> None:
        """잔차 분기 내부의 정규화층, 이중 선형 변환층 및 드롭아웃 레이어를 초기화합니다."""
        super().__init__()
        # 1. Pre-Norm 구조 기반의 비선형 잔차 분기 시퀀셜 모듈 초기화
        self.residual_branch: nn.Sequential = self._build_residual_branch(
            hidden_dim=hidden_dim,
            dropout_rate=dropout_rate,
            use_batch_norm=use_batch_norm,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """입력 텐서에 잔차 분기 연산 결과를 더해 항등 경로(x + F(x))를 보존합니다."""
        # 1. 원본 입력(항등 경로)과 비선형 잔차 분기 출력을 요소별 합산하여 반환
        return x + self.residual_branch(x)


    @staticmethod
    def _build_residual_branch(
        hidden_dim: int,
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> nn.Sequential:
        """Pre-Norm 구조(Norm -> Linear -> SiLU -> Dropout -> Linear -> Dropout)의 잔차 분기를 생성합니다."""
        # [설계 의도] 깊은 블록 적층 시에도 항등 경로(x)를 통한 그래디언트 흐름이 왜곡되지 않도록
        # 선형 변환 이전에 정규화를 수행하는 Pre-Norm 아키텍처를 구성함
        layers: List[nn.Module] = []
        if use_batch_norm:
            layers.append(nn.BatchNorm1d(hidden_dim))
        layers.extend(
            [
                nn.Linear(hidden_dim, hidden_dim),
                nn.SiLU(),
                nn.Dropout(p=dropout_rate),
                nn.Linear(hidden_dim, hidden_dim),
                nn.Dropout(p=dropout_rate),
            ]
        )
        return nn.Sequential(*layers)