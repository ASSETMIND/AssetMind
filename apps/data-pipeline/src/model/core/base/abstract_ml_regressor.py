from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.common.exceptions import ModelTrainingExecutionError
from src.model.core.base.abstract_regressor import (
    DEFAULT_MODEL_NAME,
    DEFAULT_RANDOM_STATE,
    FEATURE_IMPORTANCE_SERIES_NAME,
    AbstractRegressor,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
IMPORTANCE_ATTRIBUTES: Tuple[str, ...] = (
    "feature_importances_",
    "coef_",
)  # 트리 기반 중요도 및 선형 회귀 계수 추출 대상 속성명


class AbstractMLRegressor(AbstractRegressor):
    """전통 머신러닝 회귀 모델(Scikit-Learn 및 GBDT 계열)의 추상 기본 클래스.

    Attributes:
        model (Optional[Any]): 하위 클래스에서 생성 및 학습된 내부 머신러닝 추정기 인스턴스.
    """
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        **hyperparameters: Any,
    ) -> None:
        """AbstractMLRegressor 인스턴스를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 DEFAULT_MODEL_NAME.
            random_state (int): 난수 제어 시드. 기본값은 DEFAULT_RANDOM_STATE.
            **hyperparameters (Any): 내부 머신러닝 추정기에 전달할 하이퍼파라미터.
        """
        # 1. 상위 추상 클래스(AbstractRegressor) 공통 메타데이터 초기화
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **hyperparameters,
        )

        # 2. 하위 ML 알고리즘 추정기 객체를 담을 상태 변수 초기화
        self.model: Optional[Any] = None

    # --------------------------------------------------------------------------
    # Public API Functions
    # --------------------------------------------------------------------------
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> "AbstractMLRegressor":
        """내부 머신러닝 추정기를 생성하고 학습 데이터셋으로 모델을 적합합니다.

        Args:
            X_train (pd.DataFrame): 훈련용 2D 피처 행렬.
            y_train (pd.Series): 훈련용 1D 타겟 시계열.
            X_val (Optional[pd.DataFrame]): 조기 종료용 검증 피처 행렬. 기본값은 None.
            y_val (Optional[pd.Series]): 조기 종료용 검증 타겟 시리즈. 기본값은 None.
            sample_weight (Optional[pd.Series]): 관측치별 중요도 가중치. 기본값은 None.
            **kwargs (Any): 하위 추정기 학습에 전달할 추가 런타임 제어 인자.

        Returns:
            AbstractMLRegressor: 학습이 완료된 모델 인스턴스 자신(self).

        Raises:
            ModelTrainingExecutionError: 입력 데이터 검증 실패 또는 추정기 학습 중 예외가 발생한 경우.
        """
        # 1. 학습·검증 데이터셋 및 샘플 가중치의 정합성 선제 검증
        self._validate_train_data(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            sample_weight=sample_weight,
        )

        try:
            # 2. 학습 피처 컬럼 순서 기록 및 검증용 피처(X_val) 컬럼 순서 정렬
            self.feature_names = X_train.columns.tolist()
            aligned_val_features: Optional[pd.DataFrame] = (
                self._align_predict_features(X_test=X_val)
                if X_val is not None
                else None
            )

            # 3. 하위 클래스별 구체 추정기 인스턴스 생성 및 학습 집행
            self.model = self._build_estimator()
            self._fit_estimator(
                X_train=X_train,
                y_train=y_train,
                X_val=aligned_val_features,
                y_val=y_val,
                sample_weight=sample_weight,
                **kwargs,
            )

            # 4. 학습 완료 상태 플래그 활성화 및 인스턴스 반환
            self.is_fitted = True
            return self
        except ModelTrainingExecutionError:
            raise
        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"'{self.model_name}' ML 모델 학습 중 오류 발생: {str(error)}",
                model_name=self.model_name,
                hyperparameters=self.hyperparameters,
                original_exception=error,
            ) from error

    def predict(self, X_test: pd.DataFrame) -> pd.Series:
        """학습된 머신러닝 추정기를 사용하여 추론을 수행합니다.

        Args:
            X_test (pd.DataFrame): 추론을 수행할 2D 피처 행렬.

        Returns:
            pd.Series: X_test 인덱스가 보존된 1D 예측값 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
            ModelTrainingExecutionError: 추론 데이터 결손, 필수 피처 누락 또는 추론 실패 시.
        """
        # 1. 모델 학습 완료 여부 검증 및 학습 피처 순서에 맞춘 입력 데이터 정렬
        self._validate_fitted_state(operation_name="predict")
        aligned_features: pd.DataFrame = self._align_predict_features(X_test=X_test)

        try:
            # 2. 내부 추정기 추론 실행 후 원본 인덱스가 보존된 Series로 변환하여 반환
            raw_predictions: np.ndarray = self._predict_estimator(
                X_test=aligned_features
            )
            return self._format_prediction_series(
                predictions=raw_predictions,
                index=aligned_features.index,
            )
        except ModelTrainingExecutionError:
            raise
        except Exception as error:
            raise ModelTrainingExecutionError(
                message=f"'{self.model_name}' ML 모델 추론 중 오류 발생: {str(error)}",
                model_name=self.model_name,
                original_exception=error,
            ) from error

    def get_feature_importance(self) -> pd.Series:
        """학습된 머신러닝 추정기로부터 내림차순 정렬된 피처 중요도 또는 회귀 계수 절댓값을 반환합니다.

        Returns:
            pd.Series: 피처명을 인덱스로 가지며 내림차순 정렬된 피처 중요도 시리즈.

        Raises:
            ModelNotFittedError: 모델이 학습되지 않은 상태에서 호출된 경우.
        """
        # 1. 모델 학습 완료 상태 검증
        self._validate_fitted_state(operation_name="get_feature_importance")

        # 2. 내부 추정기로부터 피처 중요도(또는 회귀 계수 절댓값)를 추출하여 반환
        return _extract_estimator_importance(
            estimator=self.model,
            feature_names=self.feature_names,
        )

    # --------------------------------------------------------------------------
    # Internal Helper Functions
    # --------------------------------------------------------------------------
    @abstractmethod
    def _build_estimator(self) -> Any:
        """하위 머신러닝 알고리즘의 추정기(Estimator) 인스턴스를 생성하여 반환합니다."""
        pass

    def _fit_estimator(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> None:
        """내부 추정기의 학습을 집행하며, GBDT 등 하위 모델 특성에 따라 오버라이딩을 허용합니다."""
        # 1. 런타임 추가 인자 사본 생성 및 샘플 가중치(sample_weight) 배열 바인딩
        # [설계 의도] 표준 Scikit-Learn 추정기는 기본 구현을 그대로 재사용하고,
        # eval_set 주입이 필요한 GBM 계열만 본 메서드를 선택적으로 확장하도록 분리함
        fit_kwargs: Dict[str, Any] = dict(kwargs)
        if sample_weight is not None:
            fit_kwargs["sample_weight"] = np.asarray(sample_weight, dtype=np.float64)

        # 2. 내부 추정기 학습 실행
        self.model.fit(X_train, y_train, **fit_kwargs)

    def _predict_estimator(self, X_test: pd.DataFrame) -> np.ndarray:
        """내부 추정기를 호출하여 정렬된 피처 행렬에 대한 1차원 실수형 예측 배열을 산출합니다."""
        # 추정기의 predict 결과를 표준 float64 NumPy 배열로 변환하여 반환
        return np.asarray(self.model.predict(X_test), dtype=np.float64)


    def _extract_estimator_importance(
        estimator: Any,
        feature_names: Optional[List[str]],
    ) -> pd.Series:
        """추정기 객체로부터 트리 중요도 또는 선형 회귀 계수 절댓값을 추출하여 내림차순 Series로 변환합니다."""
        # 1. 추정기 인스턴스가 존재하지 않는 경우 빈 표준 시리즈 반환
        if estimator is None:
            return pd.Series(dtype=np.float64, name=FEATURE_IMPORTANCE_SERIES_NAME)

        # 2. 지원 속성(feature_importances_, coef_)을 순차 탐색하여 중요도 추출
        for attribute_name in IMPORTANCE_ATTRIBUTES:
            if hasattr(estimator, attribute_name):
                raw_importance: np.ndarray = np.asarray(
                    getattr(estimator, attribute_name),
                    dtype=np.float64,
                ).ravel()

                # 3. 선형 모델의 회귀 계수(coef_)인 경우 영향력 크기 비교를 위해 절댓값 변환
                importance_values: np.ndarray = (
                    np.abs(raw_importance)
                    if attribute_name == "coef_"
                    else raw_importance
                )

                # 4. 학습 피처명 인덱스를 매핑하고 중요도 기준 내림차순 정렬하여 반환
                index_names: List[str] = (
                    feature_names
                    if feature_names and len(feature_names) == len(importance_values)
                    else [f"feature_{index}" for index in range(len(importance_values))]
                )
                return pd.Series(
                    data=importance_values,
                    index=index_names,
                    dtype=np.float64,
                    name=FEATURE_IMPORTANCE_SERIES_NAME,
                ).sort_values(ascending=False)

        # 5. 중요도 산출 속성이 없는 추정기인 경우 빈 표준 시리즈 반환
        return pd.Series(dtype=np.float64, name=FEATURE_IMPORTANCE_SERIES_NAME)