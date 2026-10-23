from typing import List, Sequence, Tuple

import torch
import torch.nn as nn

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [회귀 신경망 출력 규격 설정]
REGRESSION_OUTPUT_DIM: int = 1    # 단일 연속형 타겟 회귀 출력 차원


class DCNv2Network(nn.Module):
    """Cross Network와 Deep Network를 병렬(Parallel)로 결합하여 회귀 예측치를 산출하는 신경망 모듈.

    입력 정형 피처에 대해 명시적 다항 교차를 수행하는 Cross 분기와 암묵적 고차 비선형 표현을
    학습하는 Deep MLP 분기를 병렬로 통과시킨 뒤, 두 표현을 결합(Concatenation)하여
    단일 연속형 회귀 예측치를 산출합니다.

    Attributes:
        cross_network (_CrossNetworkV2): 명시적 고차 피처 교차를 수행하는 Cross Network 모듈.
        deep_network (nn.Sequential): 비선형 표현 학습을 수행하는 다층 퍼셉트론(Deep MLP) 백본.
        prediction_head (nn.Linear): 결합된 Cross·Deep 피처를 단일 회귀 출력으로 매핑하는 선형 헤드.
    """
    def __init__(
        self,
        input_dim: int,
        num_cross_layers: int,
        deep_hidden_dims: Sequence[int],
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> None:
        """병렬 구조의 Cross 분기, Deep MLP 분기 및 결합 선형 회귀 헤드를 초기화합니다.

        Args:
            input_dim (int): 입력 정형 데이터의 피처 차원(컬럼 개수).
            num_cross_layers (int): 명시적 피처 교차를 수행할 Cross 레이어 적층 개수.
            deep_hidden_dims (Sequence[int]): 병렬 Deep MLP 백본의 계층별 은닉 차원 시퀀스.
            dropout_rate (float): Deep MLP 내부에 적용할 과적합 방지 드롭아웃 비율.
            use_batch_norm (bool): Deep MLP 계층별 배치 정규화(BatchNorm1d) 적용 여부.
        """
        super().__init__()
        # 1. 명시적 다항 피처 교차를 수행하는 Cross Network 분기 초기화
        self.cross_network: _CrossNetworkV2 = _CrossNetworkV2(
            input_dim=input_dim,
            num_cross_layers=num_cross_layers,
        )

        # 2. 암묵적 비선형 고차 표현을 학습하는 Deep MLP 백본 분기 및 출력 차원 생성
        self.deep_network, deep_output_dim = self._build_deep_mlp_backbone(
            input_dim=input_dim,
            deep_hidden_dims=deep_hidden_dims,
            dropout_rate=dropout_rate,
            use_batch_norm=use_batch_norm,
        )

        # 3. [설계 의도] 명시적 교차 표현(Cross)과 암묵적 비선형 표현(Deep)이 서로를 덮어쓰지 않고
        # 독립적으로 회귀 헤드에 기여하도록 병렬 결합(Parallel Concatenation) 차원으로 선형 헤드를 구성함
        combined_dim: int = input_dim + deep_output_dim
        self.prediction_head: nn.Linear = nn.Linear(combined_dim, REGRESSION_OUTPUT_DIM)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """2D 정형 텐서를 두 분기에 병렬 통과시킨 후 결합하여 최종 회귀 예측치를 반환합니다.

        Args:
            x (torch.Tensor): (Batch_Size, Input_Dim) 형태의 2D 정형 입력 피처 텐서.

        Returns:
            torch.Tensor: (Batch_Size, 1) 형태의 2D 연속형 회귀 예측치 텐서.
        """
        # 1. Cross 분기와 Deep 분기에 원본 입력 텐서를 병렬 통과시켜 각 표현 추출
        cross_features: torch.Tensor = self.cross_network(x)
        deep_features: torch.Tensor = self.deep_network(x)

        # 2. 마지막 피처 차원(-1)을 기준으로 두 분기의 출력 텐서를 병렬 결합
        combined_features: torch.Tensor = torch.cat(
            [cross_features, deep_features], dim=-1
        )

        # 3. 결합된 고차 표현을 회귀 예측 헤드에 통과시켜 최종 예측값 반환
        return self.prediction_head(combined_features)


    @staticmethod
    def _build_deep_mlp_backbone(
        input_dim: int,
        deep_hidden_dims: Sequence[int],
        dropout_rate: float,
        use_batch_norm: bool,
    ) -> Tuple[nn.Sequential, int]:
        """비선형 고차 표현 학습을 수행하는 다층 퍼셉트론(Deep MLP) 백본과 최종 출력 차원을 생성합니다."""
        # 1. 계층별 은닉 차원 시퀀스를 순회하며 선형 변환, 정규화, 활성화, 드롭아웃 모듈 적층
        layers: List[nn.Module] = []
        current_dim: int = input_dim

        for hidden_dim in deep_hidden_dims:
            layers.append(nn.Linear(current_dim, hidden_dim))
            if use_batch_norm:
                layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.SiLU())
            layers.append(nn.Dropout(p=dropout_rate))
            current_dim = hidden_dim

        # 2. 조립된 Sequential 백본 모듈과 마지막 은닉층 출력 차원을 튜플로 반환
        return nn.Sequential(*layers), current_dim


class _CrossNetworkV2(nn.Module):
    """원본 피처와의 아다마르 곱(Hadamard Product)을 통해 명시적 다항 교차를 수행하는 내부 모듈."""
    def __init__(self, input_dim: int, num_cross_layers: int) -> None:
        """지정된 교차 차수(num_cross_layers)만큼의 Full-Rank 선형 변환 레이어 리스트를 초기화합니다."""
        super().__init__()
        # 1. [설계 의도] 팩터 수가 압축된 정형 금융 데이터셋에서는 저랭크 근사보다 Full-Rank 가중치 행렬(W_l)이
        # 팩터 간 비대칭 상호작용을 정보 손실 없이 포착하므로 표준 선형 변환 레이어를 적층함
        self.cross_layers: nn.ModuleList = nn.ModuleList(
            [nn.Linear(input_dim, input_dim, bias=True) for _ in range(num_cross_layers)]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """초기 입력(x_0)과 현재 계층(x_l)의 선형 변환을 요소곱하고 잔차를 더해 교차 피처를 산출합니다."""
        # 1. 초기 입력 피처(x_0)를 시작 상태로 설정하고 계층별 명시적 피처 교차(x_0 * Linear(x_l) + x_l) 수행
        current_features: torch.Tensor = x
        for cross_layer in self.cross_layers:
            current_features = x * cross_layer(current_features) + current_features

        # 2. 최종 적층 차수까지 교차가 완료된 피처 텐서 반환
        return current_features