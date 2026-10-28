import torch
import torch.nn as nn

from src.model.core.base.abstract_dl_regressor import REGRESSION_OUTPUT_DIM

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [토큰 시퀀스 및 회귀 신경망 출력 규격 설정]
CLS_TOKEN_COUNT: int = 1                # 전역 문맥 집계를 위한 [CLS] 토큰 개수
CLS_TOKEN_INDEX: int = 0                # 시퀀스 내 [CLS] 토큰의 위치 인덱스
TRANSFORMER_ACTIVATION: str = "gelu"    # 트랜스포머 FFN 블록 내부 활성화 함수


class FTTransformerNetwork(nn.Module):
    """Feature Tokenizer, Transformer Encoder 및 [CLS] 회귀 헤드를 결합한 신경망 모듈.

    2D 정형 입력 피처들을 개별 토큰 임베딩 시퀀스로 변환하고 [CLS] 토큰을 결합한 뒤,
    Pre-Norm 구조의 Transformer Encoder를 통해 피처 간 고차 상호작용을 학습하여
    단일 연속형 회귀 예측치를 산출합니다.

    Attributes:
        feature_tokenizer (_FeatureTokenizer): 연속형 피처들을 토큰 벡터 시퀀스로 투영하는 모듈.
        transformer_encoder (nn.TransformerEncoder): Multi-Head Self-Attention 기반 인코더 스택.
        prediction_head (nn.Sequential): [CLS] 토큰 문맥 표현을 회귀 예측치로 변환하는 출력 헤드.
    """
    def __init__(
        self,
        input_dim: int,
        d_token: int,
        num_heads: int,
        num_layers: int,
        ffn_factor: float,
        dropout_rate: float,
    ) -> None:
        """토크나이저, Pre-Norm 트랜스포머 인코더 스택 및 최종 예측 헤드를 초기화합니다.

        Args:
            input_dim (int): 입력 정형 데이터의 피처 차원(컬럼 개수).
            d_token (int): 개별 피처 토큰 및 [CLS] 토큰의 임베딩 차원 크기.
            num_heads (int): Multi-Head Self-Attention의 어텐션 헤드 개수.
            num_layers (int): 적층할 Transformer Encoder 레이어 개수.
            ffn_factor (float): 토큰 차원(d_token) 대비 FFN 은닉층 차원 확장 배수.
            dropout_rate (float): 어텐션 및 FFN 내부에 적용할 과적합 방지 드롭아웃 비율.
        """
        super().__init__()
        # 1. 스칼라 피처들을 독립 벡터 토큰으로 변환하고 [CLS] 토큰을 부착하는 토크나이저 초기화
        self.feature_tokenizer: _FeatureTokenizer = _FeatureTokenizer(
            input_dim=input_dim,
            d_token=d_token,
        )

        # 2. 피처 토큰 간 문맥적 상호작용을 학습하는 Pre-Norm Transformer 인코더 스택 생성
        self.transformer_encoder: nn.TransformerEncoder = (
            self._build_transformer_encoder(
                d_token=d_token,
                num_heads=num_heads,
                num_layers=num_layers,
                ffn_factor=ffn_factor,
                dropout_rate=dropout_rate,
            )
        )

        # 3. 집계된 [CLS] 토큰 상태를 단일 연속형 타겟으로 매핑하는 회귀 예측 헤드 생성
        self.prediction_head: nn.Sequential = self._build_prediction_head(
            d_token=d_token,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """피처 토큰 시퀀스에 Self-Attention을 수행한 뒤 [CLS] 상태로부터 회귀 예측치를 산출합니다.

        Args:
            x (torch.Tensor): (Batch_Size, Input_Dim) 형태의 2D 정형 입력 피처 텐서.

        Returns:
            torch.Tensor: (Batch_Size, 1) 형태의 2D 연속형 회귀 예측치 텐서.
        """
        # 1. 2D 입력 피처 행렬을 [CLS] 토큰이 포함된 3D 토큰 시퀀스(B, 1 + F, D)로 변환
        token_sequence: torch.Tensor = self.feature_tokenizer(x)

        # 2. Transformer Encoder 스택을 통과시켜 피처 간 Self-Attention 문맥 표현 산출
        encoded_sequence: torch.Tensor = self.transformer_encoder(token_sequence)

        # 3. 시퀀스 첫 번째 위치(CLS_TOKEN_INDEX)의 전역 집계 표현 추출 후 회귀 예측치 반환
        cls_representation: torch.Tensor = encoded_sequence[:, CLS_TOKEN_INDEX, :]
        return self.prediction_head(cls_representation)


    @staticmethod
    def _build_transformer_encoder(
        d_token: int,
        num_heads: int,
        num_layers: int,
        ffn_factor: float,
        dropout_rate: float,
    ) -> nn.TransformerEncoder:
        """Pre-Norm(norm_first=True) 구조의 TransformerEncoder 모듈을 조립하여 반환합니다."""
        # 1. [설계 의도] 정형 데이터 학습 시 초기 어텐션 그래디언트 불안정을 억제하기 위해
        # Warm-up 없이도 수렴이 안정적인 Pre-LayerNorm(norm_first=True) 아키텍처를 강제함
        feedforward_dim: int = max(1, int(d_token * ffn_factor))
        encoder_layer: nn.TransformerEncoderLayer = nn.TransformerEncoderLayer(
            d_model=d_token,
            nhead=num_heads,
            dim_feedforward=feedforward_dim,
            dropout=dropout_rate,
            activation=TRANSFORMER_ACTIVATION,
            batch_first=True,
            norm_first=True,
        )

        # 2. 단일 인코더 레이어를 지정된 층수(num_layers)만큼 적층하여 반환
        return nn.TransformerEncoder(
            encoder_layer=encoder_layer,
            num_layers=num_layers,
            enable_nested_tensor=False,
        )

    @staticmethod
    def _build_prediction_head(d_token: int) -> nn.Sequential:
        """[CLS] 토큰 임베딩을 정규화 및 활성화한 후 단일 타겟 차원으로 투영하는 헤드를 생성합니다."""
        # 1. Pre-Norm 인코더 최종 출력의 스케일 안정화를 위한 LayerNorm, SiLU 및 선형 출력층 결합
        return nn.Sequential(
            nn.LayerNorm(d_token),
            nn.SiLU(),
            nn.Linear(d_token, REGRESSION_OUTPUT_DIM),
        )


class _FeatureTokenizer(nn.Module):
    """연속형 스칼라 피처들을 독립된 벡터 토큰으로 선형 투영하고 [CLS] 토큰을 결합하는 내부 모듈."""

    def __init__(self, input_dim: int, d_token: int) -> None:
        """피처별 고유 가중치·편향 파라미터와 전역 집계용 [CLS] 토큰 파라미터를 초기화합니다."""
        super().__init__()
        # 1. 피처별 독립 선형 투영을 위한 가중치(W), 편향(b) 및 [CLS] 토큰 학습 파라미터 선언
        self.feature_weights: nn.Parameter = nn.Parameter(
            torch.empty(input_dim, d_token)
        )
        self.feature_biases: nn.Parameter = nn.Parameter(
            torch.empty(input_dim, d_token)
        )
        self.cls_token: nn.Parameter = nn.Parameter(
            torch.empty(1, CLS_TOKEN_COUNT, d_token)
        )

        # 2. 학습 초기 분산 안정성을 위한 파라미터 가중치 초기화 수행
        self._initialize_parameters()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """2D 입력 텐서(B, F)를 3D 토큰 시퀀스 텐서(B, 1 + F, D)로 변환합니다."""
        # 1. [설계 의도] 단일 선형층으로 피처를 혼합하지 않고 각 피처(x_j)를 고유 임베딩 공간(W_j * x_j + b_j)으로
        # 독립 투영함으로써 후행 Self-Attention이 피처 간 문맥적 상호작용을 직접 학습하도록 유도함
        feature_tokens: torch.Tensor = (
            x.unsqueeze(-1) * self.feature_weights.unsqueeze(0)
            + self.feature_biases.unsqueeze(0)
        )

        # 2. 배치 크기(B)에 맞춰 [CLS] 토큰을 확장한 뒤 피처 토큰 시퀀스 전면(dim=1)에 결합하여 반환
        batch_cls_token: torch.Tensor = self.cls_token.expand(x.size(0), -1, -1)
        return torch.cat([batch_cls_token, feature_tokens], dim=1)


    def _initialize_parameters(self) -> None:
        """토큰 임베딩 가중치의 초기 분산 안정성을 위해 Xavier 균등 분포 및 영점 초기화를 수행합니다."""
        # 1. 가중치 및 [CLS] 토큰은 Xavier Uniform으로, 편향은 0으로 초기화
        nn.init.xavier_uniform_(self.feature_weights)
        nn.init.zeros_(self.feature_biases)
        nn.init.xavier_uniform_(self.cls_token)