from typing import Any, Dict, Optional

from sklearn.linear_model import ElasticNet

from src.model.core.base.abstract_ml_regressor import AbstractMLRegressor
from src.model.core.base.abstract_regressor import DEFAULT_RANDOM_STATE

# ==============================================================================
# Constants & Configuration
# ==============================================================================
ELASTICNET_MODEL_NAME: str = "ElasticNetRegressor"    # ElasticNet 회귀 모델 기본 식별 명칭

DEFAULT_ELASTICNET_PARAMS: Dict[str, Any] = {
    "alpha": 1.0,                                     # 전체 정규화(L1 + L2) 강도 제어 계수
    "l1_ratio": 0.5,                                  # L1(Lasso) 대 L2(Ridge) 혼합 비율 (0 <= l1_ratio <= 1)
    "max_iter": 1000,                                 # 좌표 하강법(Coordinate Descent) 최대 반복 횟수
    "tol": 1e-4,                                      # 최적화 수렴 판정 허용 오차 임계값
    "selection": "cyclic",                            # 회귀 계수 갱신 순회 방식 ('cyclic' 또는 'random')
}


class ElasticNetRegressor(AbstractMLRegressor):
    """ElasticNet(L1 + L2 규제 선형 회귀) 구체 클래스.

    AbstractMLRegressor의 공통 생명주기(fit, predict, get_feature_importance, save/load)를
    상속받아 재사용하며, Scikit-Learn ElasticNet 추정기 생성을 전담합니다.

    Attributes:
        model (Optional[ElasticNet]): 학습 및 추론을 수행하는 Scikit-Learn ElasticNet 추정기 인스턴스.
    """

    def __init__(
        self,
        model_name: str = ELASTICNET_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        **hyperparameters: Any,
    ) -> None:
        """ElasticNetRegressor 인스턴스 및 기본 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 ELASTICNET_MODEL_NAME.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            **hyperparameters (Any): 외부 설정 또는 Optuna에서 주입되는 가변 하이퍼파라미터.
        """
        # 1. 기본 하이퍼파라미터 사본에 외부 주입 커스텀 하이퍼파라미터 병합
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_ELASTICNET_PARAMS,
            custom_params=hyperparameters,
        )

        # 2. 상위 추상 클래스(AbstractMLRegressor) 공통 상태 및 메타데이터 초기화
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **merged_hyperparameters,
        )
        self.model: Optional[ElasticNet] = None


    # --------------------------------------------------------------------------
    # Internal Helper Functions
    # --------------------------------------------------------------------------
    def _build_estimator(self) -> ElasticNet:
        """설정된 하이퍼파라미터와 난수 시드를 바인딩하여 ElasticNet 추정기 인스턴스를 생성합니다."""
        # 난수 시드 및 병합된 하이퍼파라미터를 주입하여 Scikit-Learn ElasticNet 인스턴스 반환
        return ElasticNet(
            random_state=self.random_state,
            **self.hyperparameters,
        )