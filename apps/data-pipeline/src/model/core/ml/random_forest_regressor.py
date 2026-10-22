from typing import Any, Dict, Optional

from sklearn.ensemble import RandomForestRegressor as SklearnRandomForestRegressor

from src.model.core.base.abstract_ml_regressor import AbstractMLRegressor
from src.model.core.base.abstract_regressor import DEFAULT_RANDOM_STATE

# ==============================================================================
# Constants & Configuration
# ==============================================================================
RANDOM_FOREST_MODEL_NAME: str = (
    "RandomForestRegressor"    # Random Forest 회귀 모델 기본 식별 명칭
)

DEFAULT_RANDOM_FOREST_PARAMS: Dict[str, Any] = {
    "n_estimators": 100,       # 배깅 앙상블을 구성할 결정 트리 개수
    "max_depth": None,         # 개별 트리의 최대 분할 깊이 (None일 경우 순수 노드까지 확장)
    "min_samples_split": 2,    # 내부 노드 분할에 필요한 최소 샘플 수
    "min_samples_leaf": 1,     # 리프 노드가 되기 위해 필요한 최소 샘플 수
    "max_features": 1.0,       # 노드 분할 시 탐색할 최대 피처 비율
    "bootstrap": True,         # 트리 생성 시 부트스트랩 복원 추출 사용 여부
    "n_jobs": -1,              # 병렬 학습에 사용할 CPU 코어 수 (-1은 가용 전체 코어 사용)
}


class RandomForestRegressor(AbstractMLRegressor):
    """Random Forest 배깅(Bagging) 앙상블 회귀 알고리즘 구체 클래스.

    AbstractMLRegressor의 공통 생명주기(fit, predict, get_feature_importance, save/load)를
    상속받아 재사용하며, Scikit-Learn RandomForestRegressor 추정기 생성을 전담합니다.

    Attributes:
        model (Optional[SklearnRandomForestRegressor]): 학습 및 추론을 수행하는
            Scikit-Learn RandomForestRegressor 추정기 인스턴스.
    """

    def __init__(
        self,
        model_name: str = RANDOM_FOREST_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        **hyperparameters: Any,
    ) -> None:
        """RandomForestRegressor 인스턴스 및 기본 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 RANDOM_FOREST_MODEL_NAME.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            **hyperparameters (Any): 외부 설정 또는 Optuna에서 주입되는 가변 하이퍼파라미터.
        """
        # 1. 기본 하이퍼파라미터 사본에 외부 주입 커스텀 하이퍼파라미터 병합
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_RANDOM_FOREST_PARAMS,
            custom_params=hyperparameters,
        )

        # 2. 상위 추상 클래스(AbstractMLRegressor) 공통 상태 및 메타데이터 초기화
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **merged_hyperparameters,
        )
        self.model: Optional[SklearnRandomForestRegressor] = None

    # --------------------------------------------------------------------------
    # Internal Helper Functions
    # --------------------------------------------------------------------------
    def _build_estimator(self) -> SklearnRandomForestRegressor:
        """설정된 하이퍼파라미터와 난수 시드를 바인딩하여 RandomForestRegressor 추정기 인스턴스를 생성합니다."""
        # 난수 시드 및 병합된 하이퍼파라미터를 주입하여 Scikit-Learn RandomForestRegressor 인스턴스 반환
        return SklearnRandomForestRegressor(
            random_state=self.random_state,
            **self.hyperparameters,
        )