from typing import Any, Dict, Tuple

import torch.nn as nn

from src.model.core.base.abstract_dl_regressor import AbstractDLRegressor
from src.model.core.base.abstract_regressor import (
    DEFAULT_RANDOM_STATE,
    DEFAULT_REQUESTED_DEVICE,
)
from src.model.core.dl.network.dcn_v2_network import DCNv2Network

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [모델 식별 규격 설정]
DCN_V2_MODEL_NAME: str = "DCNv2Regressor"                          # DCNv2 회귀 모델 기본 식별 명칭

# [신경망 아키텍처 및 학습 루프 기본 하이퍼파라미터 설정]
DEFAULT_DCN_V2_PARAMS: Dict[str, Any] = {
    "num_cross_layers": 3,                                         # 명시적 고차 피처 교차(Cross) 레이어 적층 개수
    "deep_hidden_dims": (128, 64),                                 # 병렬 심층 신경망(Deep MLP) 계층별 은닉 차원 튜플
    "dropout_rate": 0.2,                                           # 심층 신경망 내부 과적합 방지 드롭아웃 비율
    "use_batch_norm": True,                                        # 심층 신경망 계층별 배치 정규화(BatchNorm1d) 적용 여부
}


class DCNv2Regressor(AbstractDLRegressor):
    """Deep & Cross Network v2(DCNv2) 회귀 알고리즘 구체 클래스.

    AbstractDLRegressor의 공통 생명주기(fit, predict, save_artifact, load_artifact)와
    2D 텐서 변환 파이프라인을 상속받아 재사용하며, 분리된 DCNv2Network 모듈에
    하이퍼파라미터와 입력 차원을 바인딩하여 신경망을 생성하는 역할을 전담합니다.

    Attributes:
        device (str): 모델 연산이 수행될 런타임 하드웨어 가속기 식별자('cpu', 'cuda', 'mps').
        network (Optional[nn.Module]): 학습 및 추론을 수행하는 DCNv2 신경망 모듈.
        input_dim (Optional[int]): 입력 피처의 차원(컬럼 개수).
    """
    def __init__(
        self,
        model_name: str = DCN_V2_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        device: str = DEFAULT_REQUESTED_DEVICE,
        **hyperparameters: Any,
    ) -> None:
        """DCNv2Regressor 인스턴스, 런타임 디바이스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 DCN_V2_MODEL_NAME.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            device (str): 요청 연산 디바이스('auto', 'cpu', 'cuda', 'mps'). 기본값은 'auto'.
            **hyperparameters (Any): 외부 설정 또는 Optuna에서 주입되는 가변 하이퍼파라미터.
        """
        # 1. 기본 하이퍼파라미터 사본에 외부 주입 커스텀 하이퍼파라미터 병합
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_DCN_V2_PARAMS,
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
        """설정된 하이퍼파라미터와 입력 피처 차원을 바인딩하여 Parallel DCNv2 신경망을 생성합니다."""
        # 1. 신경망 아키텍처 구성에 필요한 하이퍼파라미터 추출 및 타입 변환
        num_cross_layers: int = int(self.hyperparameters["num_cross_layers"])
        deep_hidden_dims: Tuple[int, ...] = tuple(
            int(dim) for dim in self.hyperparameters["deep_hidden_dims"]
        )
        dropout_rate: float = float(self.hyperparameters["dropout_rate"])
        use_batch_norm: bool = bool(self.hyperparameters["use_batch_norm"])

        # 2. 순수 신경망 모듈(DCNv2Network) 인스턴스 생성 및 반환
        return DCNv2Network(
            input_dim=input_dim,
            num_cross_layers=num_cross_layers,
            deep_hidden_dims=deep_hidden_dims,
            dropout_rate=dropout_rate,
            use_batch_norm=use_batch_norm,
        )