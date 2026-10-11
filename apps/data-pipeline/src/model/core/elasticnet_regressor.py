from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet

from src.model.core.abstract_regressor import AbstractRegressor
from src.common.exceptions import ModelTrainingExecutionError

# ==============================================================================
# Constants & Default Hyperparameters
# ==============================================================================
ELASTICNET_MODEL_NAME: str = "ElasticNetRegressor"

DEFAULT_ELASTICNET_PARAMS: Dict[str, Any] = {
    "alpha": 1.0,
    "l1_ratio": 0.5,
    "max_iter": 1000,
    "tol": 1e-4,
    "selection": "cyclic",
}


# ==============================================================================
# Main Regressor Class
# ==============================================================================
class ElasticNetRegressor(AbstractRegressor):
    """ElasticNet(L1 + L2 규제 선형 회귀) 구체 클래스.

    AbstractRegressor 인터페이스 규격을 준수하며, 동적 하이퍼파라미터 주입,
    회귀 계수(Coefficients) 기반의 피처 중요도 산출 및 아티팩트 직렬화를 지원합니다.
    """

    def __init__(
        self,
        model_name: str = ELASTICNET_MODEL_NAME,
        random_state: int = 42,
        **hyperparameters: Any,
    ) -> None:
        """ElasticNetRegressor 인스턴스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 식별 명칭. 기본값은 'ElasticNetRegressor'.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 42.
            **hyperparameters (Any): Optuna 또는 외부 설정에서 주입되는 가변 파라미터.
        """
        _hyperparameters: Dict[str, Any] = DEFAULT_ELASTICNET_PARAMS.copy()
        _hyperparameters.update(hyperparameters)

        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **_hyperparameters,
        )

        self._model: Optional[ElasticNet] = None

    # --------------------------------------------------------------------------
    # Core Implementations
    # --------------------------------------------------------------------------
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> "ElasticNetRegressor":
        """입력 데이터를 기반으로 ElasticNet 모델 학습을 수행합니다.

        Args:
            X_train (pd.DataFrame): 학습용 피처 데이터프레임 (N, D).
            y_train (pd.Series): 학습용 정답 타겟 시계열 (N,).
            X_val (Optional[pd.DataFrame]): 인터페이스 다형성 준수용 인자 (선형 모델 미사용).
            y_val (Optional[pd.Series]): 인터페이스 다형성 준수용 인자 (선형 모델 미사용).
            sample_weight (Optional[pd.Series]): 관측치별 시간 감쇠 또는 중요도 가중치. 기본값은 None.
            **kwargs (Any): 기타 사이킷런 fit 런타임 제어 옵션.

        Returns:
            ElasticNetRegressor: 학습이 완료된 모델 인스턴스 자신(self).

        Raises:
            ModelTrainingExecutionError: 데이터셋 결손, 차원 불일치 또는 피팅 실패 시 발생.
        """
        # 학습 데이터셋 무결성 검증
        self._validate_train_data(X_train, y_train)

        try:
            # 하이퍼파라미터 바인딩 및 네이티브 에스티메이터 생성
            self._model = ElasticNet(
                random_state=self.random_state,
                **self.hyperparameters,
            )

            # 시간 감쇠 가중치 주입
            fit_kwargs: Dict[str, Any] = kwargs.copy()
            if sample_weight is not None:
                fit_kwargs["sample_weight"] = np.asarray(sample_weight, dtype=np.float64)

            # 네이티브 fit 연산 실행
            self._model.fit(X_train, y_train, **fit_kwargs)

            # 피처 메타데이터 보존 및 학습 완료 플래그 갱신
            self.feature_names = list(X_train.columns)
            self.is_fitted = True

            return self

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"ElasticNet 모델 학습 중 예외 발생: {str(error)}",
                model_name=self.model_name,
                hyperparameters=self.hyperparameters,
                original_exception=error,
            ) from error

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """주어진 피처 데이터셋에 대해 모델 추론을 수행하고 원본 인덱스를 보존한 Series를 반환합니다.

        Args:
            X_test (pd.DataFrame): 추론 대상 피처 데이터프레임.

        Returns:
            pd.Series: X_test의 인덱스(DatetimeIndex)와 정렬된 1차원 예측값 시리즈.

        Raises:
            ModelNotFittedError: 미학습 상태에서 호출 시 발생.
            ModelTrainingExecutionError: 데이터셋 결손 또는 추론 연산 실패 시 발생.
        """
        # 미학습 상태 및 추론 데이터 검증
        self._validate_fitted_state(operation_name="predict")
        # 검증 데이터셋의 유효성 검증
        self._validate_predict_data(X_test)

        try:
            raw_predictions: np.ndarray = self._model.predict(X_test)
            return pd.Series(
                data=np.asarray(raw_predictions, dtype=np.float64).flatten(),
                index=X_test.index,
                name=f"{self.model_name}_prediction",
            )
        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"ElasticNet 모델 추론 중 예외 발생: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            ) from error

    # --------------------------------------------------------------------------
    # Feature Importance
    # --------------------------------------------------------------------------
    def get_feature_importance(self) -> pd.Series:
        """학습된 회귀 계수(Coefficients)의 절댓값 크기를 기준으로 피처 중요도를 산출합니다.

        Returns:
            pd.Series: 피처명을 인덱스로 가지며 내림차순 정렬된 계수 절댓값 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출 시 발생.
        """
        # 미학습 상태 검증
        self._validate_fitted_state(operation_name="get_feature_importance")

        # 선형 회귀 계수의 절댓값을 피처 영향력 크기로 매핑
        feature_importances: np.ndarray = np.abs(self._model.coef_)
        index_names: List[str] = (
            self.feature_names
            if self.feature_names is not None
            else [f"feature_{i}" for i in range(len(feature_importances))]
        )

        importance_series: pd.Series = pd.Series(
            data=feature_importances,
            index=index_names,
            name="feature_importance",
        ).sort_values(ascending=False)

        return importance_series