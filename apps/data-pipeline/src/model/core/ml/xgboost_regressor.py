from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb

from src.model.core.base.abstract_ml_regressor import AbstractMLRegressor
from src.model.core.base.abstract_regressor import (
    DEFAULT_RANDOM_STATE,
    DEFAULT_REQUESTED_DEVICE,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
XGBOOST_MODEL_NAME: str = "XGBoostRegressor"                     # XGBoost 회귀 모델 기본 식별 명칭
XGBOOST_SUPPORTED_DEVICES: Tuple[str, ...] = ("cpu", "cuda",)    # XGBoost 네이티브 엔진이 지원하는 하드웨어 가속기 목록

DEFAULT_XGBOOST_PARAMS: Dict[str, Any] = {
    "n_estimators": 100,                                         # 부스팅 라운드(결정 트리) 최대 개수
    "max_depth": 6,                                              # 개별 부스팅 트리의 최대 깊이
    "learning_rate": 0.1,                                        # 단계별 가중치 갱신 학습률(Shrinkage)
    "subsample": 1.0,                                            # 트리 생성 시 학습 샘플 서브샘플링 비율
    "colsample_bytree": 1.0,                                     # 트리별 피처 컬럼 서브샘플링 비율
    "min_child_weight": 1,                                       # 자식 노드에 필요한 최소 헤시안(Hessian) 가중치 합
    "gamma": 0.0,                                                # 리프 노드 추가 분할을 위한 최소 손실 감소량
    "reg_alpha": 0.0,                                            # 가중치에 대한 L1 정규화 계수
    "reg_lambda": 1.0,                                           # 가중치에 대한 L2 정규화 계수
    "n_jobs": -1,                                                # 병렬 연산 스레드 개수 (-1은 가용 전체 코어 사용)
    "objective": "reg:squarederror",                             # 회귀 학습 목적 함수 (평균 제곱 오차)
}


class XGBoostRegressor(AbstractMLRegressor):
    """XGBoost 그래디언트 부스팅 회귀 알고리즘 구체 클래스.

    AbstractMLRegressor의 공통 생명주기(fit, predict, get_feature_importance, save/load)를
    상속받아 재사용하며, GPU 디바이스 자동 감지 및 검증셋(eval_set) 조기 종료 바인딩을 전담합니다.

    Attributes:
        model (Optional[xgb.XGBRegressor]): 학습 및 추론을 수행하는 XGBoost 추정기 인스턴스.
    """

    def __init__(
        self,
        model_name: str = XGBOOST_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        **hyperparameters: Any,
    ) -> None:
        """XGBoostRegressor 인스턴스, 런타임 디바이스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 XGBOOST_MODEL_NAME.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            **hyperparameters (Any): 외부 설정 또는 Optuna에서 주입되는 가변 하이퍼파라미터.
        """
        # 1. 기본 하이퍼파라미터 사본에 외부 주입 커스텀 하이퍼파라미터 병합
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_XGBOOST_PARAMS,
            custom_params=hyperparameters,
        )

        # 2. 런타임 가용 하드웨어를 탐색하여 지원 범위(cpu, cuda) 내 최적 디바이스 할당
        # [설계 의도] XGBoost는 Apple Silicon(mps)을 지원하지 않으므로 cpu와 cuda 범위 내에서만 디바이스를 할당함
        requested_device: str = str(
            merged_hyperparameters.get("device", DEFAULT_REQUESTED_DEVICE)
        )
        detected_device: str = self._detect_device(
            requested_device=requested_device,
            supported_devices=XGBOOST_SUPPORTED_DEVICES,
        )
        merged_hyperparameters["device"] = detected_device

        # 3. 상위 추상 클래스(AbstractMLRegressor) 공통 상태 및 메타데이터 초기화
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **merged_hyperparameters,
        )
        self.device: str = detected_device
        self.model: Optional[xgb.XGBRegressor] = None

    # --------------------------------------------------------------------------
    # Internal Helper Functions
    # --------------------------------------------------------------------------
    def _build_estimator(self) -> xgb.XGBRegressor:
        """설정된 하이퍼파라미터와 난수 시드를 바인딩하여 XGBRegressor 추정기 인스턴스를 생성합니다."""
        # 난수 시드 및 디바이스가 포함된 하이퍼파라미터를 주입하여 XGBRegressor 인스턴스 반환
        return xgb.XGBRegressor(
            random_state=self.random_state,
            **self.hyperparameters,
        )

    def _fit_estimator(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> None:
        """검증 데이터셋(eval_set)과 샘플 가중치를 구성하여 XGBoost 부스팅 학습을 집행합니다."""
        # 1. 검증셋(eval_set) 및 샘플 가중치가 포함된 학습 옵션 딕셔너리 구성
        fit_options: Dict[str, Any] = self._prepare_xgboost_fit_options(
            X_val=X_val,
            y_val=y_val,
            sample_weight=sample_weight,
            **kwargs,
        )

        # 2. 내부 XGBRegressor 추정기 학습 실행
        self.model.fit(X_train, y_train, **fit_options)

    @staticmethod
    def _prepare_xgboost_fit_options(
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """XGBoost fit 호출에 필요한 가중치 배열 및 조기 종료용 eval_set 옵션 딕셔너리를 구성합니다."""
        # 1. 런타임 추가 인자 사본 생성 및 샘플 가중치(sample_weight) 배열 바인딩
        fit_options: Dict[str, Any] = dict(kwargs)
        if sample_weight is not None:
            fit_options["sample_weight"] = np.asarray(sample_weight, dtype=np.float64)

        # 2. 검증 데이터셋(X_val, y_val) 제공 시 조기 종료용 eval_set 바인딩 및 로그 출력 억제
        # [설계 의도] 검증 데이터셋이 유효한 경우 조기 종료를 위한 eval_set을 바인딩하고 콘솔 로그 비대화를 억제함
        if (
            X_val is not None
            and y_val is not None
            and not X_val.empty
            and not y_val.empty
        ):
            fit_options["eval_set"] = [(X_val, y_val)]
            fit_options.setdefault("verbose", False)

        return fit_options