from typing import Any, Dict

import torch.nn as nn

from src.model.core.base.abstract_dl_regressor import AbstractDLRegressor
from src.model.core.base.abstract_regressor import (
    DEFAULT_RANDOM_STATE,
    DEFAULT_REQUESTED_DEVICE,
)
from src.model.core.dl.network.ft_transformer_network import FTTransformerNetwork

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [모델 식별 규격 설정]
FT_TRANSFORMER_MODEL_NAME: str = "FTTransformerRegressor"           # FT-Transformer 회귀 모델 기본 식별 명칭

# [신경망 아키텍처 및 학습 루프 기본 하이퍼파라미터 설정]
DEFAULT_FT_TRANSFORMER_PARAMS: Dict[str, Any] = {
    "d_token": 64,                                                  # 개별 피처 토큰 및 [CLS] 토큰의 임베딩 차원 크기
    "num_heads": 4,                                                 # Multi-Head Self-Attention 어텐션 헤드 개수
    "num_layers": 3,                                                # 적층할 Transformer Encoder 레이어 개수
    "ffn_factor": 2.0,                                              # 토큰 차원(d_token) 대비 FFN 은닉층 확장 배수
    "dropout_rate": 0.2,                                            # 어텐션 및 FFN 내부 과적합 방지 드롭아웃 비율
}


class FTTransformerRegressor(AbstractDLRegressor):
    """Feature Tokenizer Transformer(FT-Transformer) 회귀 알고리즘 구체 클래스.

    AbstractDLRegressor의 공통 생명주기(fit, predict, save_artifact, load_artifact)와
    2D 텐서 변환 파이프라인을 상속받아 재사용하며, 분리된 FTTransformerNetwork 모듈에
    하이퍼파라미터와 입력 차원을 바인딩하여 신경망을 생성하는 역할을 전담합니다.

    Attributes:
        device (str): 모델 연산이 수행될 런타임 하드웨어 가속기 식별자('cpu', 'cuda', 'mps').
        network (Optional[nn.Module]): 학습 및 추론을 수행하는 FT-Transformer 신경망 모듈.
        input_dim (Optional[int]): 입력 피처의 차원(컬럼 개수).
    """
    def __init__(
        self,
        model_name: str = FT_TRANSFORMER_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        device: str = DEFAULT_REQUESTED_DEVICE,
        **hyperparameters: Any,
    ) -> None:
        """FTTransformerRegressor 인스턴스, 런타임 디바이스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 FT_TRANSFORMER_MODEL_NAME.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            device (str): 요청 연산 디바이스('auto', 'cpu', 'cuda', 'mps'). 기본값은 'auto'.
            **hyperparameters (Any): 외부 설정 또는 Optuna에서 주입되는 가변 하이퍼파라미터.
        """
        # 1. 기본 하이퍼파라미터 사본에 외부 주입 커스텀 하이퍼파라미터 병합
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_FT_TRANSFORMER_PARAMS,
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
        """설정된 하이퍼파라미터와 입력 피처 차원을 바인딩하여 FT-Transformer 신경망을 생성합니다."""
        # 1. 신경망 아키텍처 구성에 필요한 하이퍼파라미터 추출 및 타입 변환
        d_token: int = int(self.hyperparameters["d_token"])
        num_heads: int = int(self.hyperparameters["num_heads"])
        num_layers: int = int(self.hyperparameters["num_layers"])
        ffn_factor: float = float(self.hyperparameters["ffn_factor"])
        dropout_rate: float = float(self.hyperparameters["dropout_rate"])

        # 2. 순수 신경망 모듈(FTTransformerNetwork) 인스턴스 생성 및 반환
        return FTTransformerNetwork(
            input_dim=input_dim,
            d_token=d_token,
            num_heads=num_heads,
            num_layers=num_layers,
            ffn_factor=ffn_factor,
            dropout_rate=dropout_rate,
        )