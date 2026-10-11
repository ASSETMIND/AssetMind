from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import xgboost as xgb

from src.model.core.abstract_regressor import AbstractRegressor
from src.common.exceptions import ModelTrainingExecutionError

# ==============================================================================
# Constants & Default Hyperparameters
# ==============================================================================
XGBOOST_MODEL_NAME: str = "XGBoostRegressor"

DEFAULT_XGBOOST_PARAMS: Dict[str, Any] = {
    "n_estimators": 100,
    "max_depth": 6,
    "learning_rate": 0.1,
    "subsample": 1.0,
    "colsample_bytree": 1.0,
    "min_child_weight": 1,
    "gamma": 0.0,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "n_jobs": -1,
    "objective": "reg:squarederror",
}

# ==============================================================================
# Main Regressor Class
# ==============================================================================
class XGBoostRegressor(AbstractRegressor):
    """XGBoost 그래디언트 부스팅 회귀 알고리즘 구체 클래스.

    AbstractRegressor 인터페이스 규격을 준수하며, 동적 하이퍼파라미터 주입,
    조기 종료 캡슐화, SHAP 기여도 연산 및 아티팩트 직렬화를 지원합니다.
    """

    def __init__(
        self,
        model_name: str = XGBOOST_MODEL_NAME,
        random_state: int = 42,
        **hyperparameters: Any,
    ) -> None:
        """XGBoostRegressor 인스턴스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 식별 명칭. 기본값은 'XGBoostRegressor'.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 42.
            **hyperparameters (Any): Optuna 또는 외부 설정에서 유입되는 가변 파라미터.
        """
        # 기본 파라미터 템플릿에 외부 주입 파라미터를 병합하여 완전한 설정 딕셔너리 구성
        _hyperparameters: Dict[str, Any] = DEFAULT_XGBOOST_PARAMS.copy()
        _hyperparameters.update(hyperparameters)

        # XGBoost 전용 디바이스 파라미터 안전 바인딩
        target_device = _hyperparameters.get("device", "auto")
        _hyperparameters["device"] = self._detect_device(
            requested_device=target_device,
            supported_devices=("cpu", "cuda"),
        )

        # 부모 추상 클래스 생성자에 바인딩하여 상태 및 파라미터 단일 관리
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **_hyperparameters,
        )

        self._model: Optional[xgb.XGBRegressor] = None

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
    ) -> "XGBoostRegressor":
        """입력 데이터를 기반으로 XGBoost 회귀 모델 학습을 수행합니다.

        Args:
            X_train (pd.DataFrame): 학습용 피처 데이터프레임 (N, D).
            y_train (pd.Series): 학습용 정답 타겟 시계열 (N,).
            X_val (Optional[pd.DataFrame]): 조기 종료용 검증 피처 데이터프레임. 기본값은 None.
            y_val (Optional[pd.Series]): 조기 종료용 검증 정답 시계열. 기본값은 None.
            sample_weight (Optional[pd.Series]): 관측치별 가중치 시리즈. 기본값은 None.
            **kwargs (Any): early_stopping_rounds, verbose 등 런타임 제어 옵션.

        Returns:
            XGBoostRegressor: 학습이 완료된 모델 인스턴스 자신(self).

        Raises:
            ModelTrainingExecutionError: 데이터 결손, 규격 불일치 또는 피팅 연산 실패 시 발생.
        """
        # 학습 데이터셋의 유효성 검증
        self._validate_train_data(X_train, y_train)

        try:
            # 전체 하이퍼파라미터 딕셔너리를 동적으로 언패킹하여 네이티브 모델 생성
            self._model = xgb.XGBRegressor(
                random_state=self.random_state,
                **self.hyperparameters,
            )   

            fit_options: Dict[str, Any] = kwargs.copy()

            # 시간 감쇠 가중치 주입
            if sample_weight is not None:
                fit_options["sample_weight"] = np.asarray(sample_weight, dtype=np.float64)

            # 검증 데이터가 주어졌을 경우 eval_set 구성 및 무음 모드(verbose=False) 기본 적용
            if X_val is not None and y_val is not None:
                if not X_val.empty and not y_val.empty:
                    fit_options["eval_set"] = [(X_val, y_val)]
                    fit_options.setdefault("verbose", False)

            # 네이티브 fit 연산 실행
            self._model.fit(X_train, y_train, **fit_options)

            # 사후 인덱스 추적 및 피처 중요도 매핑을 위해 컬럼명 보존 및 상태 갱신
            self.feature_names = list(X_train.columns)
            self.is_fitted = True

            return self

        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"XGBoost 모델 학습 중 예외 발생: {str(error)}",
                model_name=self.model_name,
                hyperparameters=self.hyperparameters,
                original_exception=error,
            ) from error

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """주어진 피처 데이터셋에 대해 모델 추론을 수행하고 입력 인덱스를 보존한 Series를 반환합니다.

        Args:
            X_test (pd.DataFrame): 추론 대상 피처 데이터프레임.

        Returns:
            pd.Series: X_test의 행 인덱스(DatetimeIndex)와 정렬된 1차원 예측값 시리즈.

        Raises:
            ModelNotFittedError: 미학습 상태에서 호출 시 발생.
            ModelTrainingExecutionError: 데이터셋 결손 또는 추론 연산 실패 시 발생.
        """
        # 미학습 상태에서의 비정상 추론 시도를 사전에 차단
        self._validate_fitted_state(operation_name="predict")
        # 검증 데이터셋의 유효성 검증
        self._validate_predict_data(X_test)

        try:
            # 네이티브 추론 결과를 1차원 배열로 평탄화하고 원본 DatetimeIndex를 바인딩하여 반환
            raw_predictions: np.ndarray = self._model.predict(X_test)
            return pd.Series(
                data=np.asarray(raw_predictions, dtype=np.float64).flatten(),
                index=X_test.index,
                name=f"{self.model_name}_prediction",
            )
        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"XGBoost 모델 추론 중 예외 발생: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            ) from error

    # --------------------------------------------------------------------------
    # Feature Importance & XAI Methods
    # --------------------------------------------------------------------------
    def get_feature_importance(self) -> pd.Series:
        """학습된 트리의 분할 기여도(Gain/Weight) 기반 글로벌 피처 중요도를 산출합니다.

        Returns:
            pd.Series: 피처명을 인덱스로 가지며 내림차순 정렬된 중요도 수치 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출 시 발생.
        """
        # 미학습 상태 검증
        self._validate_fitted_state(operation_name="get_feature_importance")

        # 내부 모델의 feature_importances_ 속성을 추출하고 피처명과 매핑
        feature_importances: np.ndarray = self._model.feature_importances_
        index_names: List[str] = (
            self.feature_names
            if self.feature_names is not None
            else [f"feature_{i}" for i in range(len(feature_importances))]
        )

        # 상위 영향력 피처를 즉시 파악할 수 있도록 내림차순 정렬 후 사출
        importance_series: pd.Series = pd.Series(
            data=feature_importances,
            index=index_names,
            name="feature_importance",
        ).sort_values(ascending=False)

        return importance_series