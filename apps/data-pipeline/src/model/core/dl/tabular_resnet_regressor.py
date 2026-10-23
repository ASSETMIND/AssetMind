from typing import Any, Dict

import torch.nn as nn

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
from src.model.core.dl.network.tabular_resnet_network import TabularResNetNetwork

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [모델 식별 규격 설정]
TABULAR_RESNET_MODEL_NAME: str = "TabularResNetRegressor"          # Tabular ResNet 회귀 모델 기본 식별 명칭

# [신경망 아키텍처 및 학습 루프 기본 하이퍼파라미터 설정]
DEFAULT_TABULAR_RESNET_PARAMS: Dict[str, Any] = {
    "hidden_dim": 128,                                             # 잔차 블록 내부 은닉 표현 차원 크기
    "num_blocks": 3,                                               # 적층할 Tabular ResNet 잔차 블록 개수
    "dropout_rate": 0.2,                                           # 잔차 분기 내부 과적합 방지 드롭아웃 비율
    "use_batch_norm": True,                                        # 잔차 블록 및 헤드 정규화(BatchNorm1d) 적용 여부
    "batch_size": DEFAULT_BATCH_SIZE,                              # 미니배치 학습 및 추론 시 배치 크기
    "max_epochs": DEFAULT_MAX_EPOCHS,                              # 최대 학습 에포크 횟수
    "learning_rate": DEFAULT_LEARNING_RATE,                        # AdamW 옵티마이저 학습률
    "weight_decay": DEFAULT_WEIGHT_DECAY,                          # AdamW 가중치 감쇠(L2 정규화) 계수
    "grad_clip_norm": DEFAULT_GRAD_CLIP_NORM,                      # 기울기 폭발 방지를 위한 그래디언트 클리핑 최대 노름
    "early_stopping_patience": DEFAULT_EARLY_STOPPING_PATIENCE,    # 검증 손실 미개선 허용 에포크 횟수
    "min_delta": DEFAULT_MIN_DELTA,                                # 검증 손실 유의미 개선 판정 최소 변화량
}


class TabularResNetRegressor(AbstractDLRegressor):
    """정형 데이터용 잔차 신경망(Tabular ResNet) 회귀 알고리즘 구체 클래스.

    AbstractDLRegressor의 공통 생명주기(fit, predict, save_artifact, load_artifact)와
    2D 텐서 변환 파이프라인을 상속받아 재사용하며, 분리된 TabularResNetNetwork 모듈에
    하이퍼파라미터와 입력 차원을 바인딩하여 신경망을 생성하는 역할을 전담합니다.

    Attributes:
        device (str): 모델 연산이 수행될 런타임 하드웨어 가속기 식별자('cpu', 'cuda', 'mps').
        network (Optional[nn.Module]): 학습 및 추론을 수행하는 Tabular ResNet 신경망 모듈.
        input_dim (Optional[int]): 입력 피처의 차원(컬럼 개수).
    """
    def __init__(
        self,
        model_name: str = TABULAR_RESNET_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        device: str = DEFAULT_REQUESTED_DEVICE,
        **hyperparameters: Any,
    ) -> None:
        """TabularResNetRegressor 인스턴스, 런타임 디바이스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 TABULAR_RESNET_MODEL_NAME.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            device (str): 요청 연산 디바이스('auto', 'cpu', 'cuda', 'mps'). 기본값은 'auto'.
            **hyperparameters (Any): 외부 설정 또는 Optuna에서 주입되는 가변 하이퍼파라미터.
        """
        # 1. 기본 하이퍼파라미터 사본에 외부 주입 커스텀 하이퍼파라미터 병합
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_TABULAR_RESNET_PARAMS,
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
        """설정된 하이퍼파라미터와 입력 피처 차원을 바인딩하여 Tabular ResNet 신경망을 생성합니다."""
        # 1. 신경망 아키텍처 구성에 필요한 하이퍼파라미터 추출 및 타입 변환
        hidden_dim: int = int(self.hyperparameters["hidden_dim"])
        num_blocks: int = int(self.hyperparameters["num_blocks"])
        dropout_rate: float = float(self.hyperparameters["dropout_rate"])
        use_batch_norm: bool = bool(self.hyperparameters["use_batch_norm"])

        # 2. 순수 신경망 모듈(TabularResNetNetwork) 인스턴스 생성 및 반환
        return TabularResNetNetwork(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_blocks=num_blocks,
            dropout_rate=dropout_rate,
            use_batch_norm=use_batch_norm,
        )