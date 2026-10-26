from typing import Any, Dict, Optional, Tuple

import catboost as cb
import numpy as np
import pandas as pd

from src.model.core.base.abstract_ml_regressor import AbstractMLRegressor
from src.model.core.base.abstract_regressor import (
    DEFAULT_RANDOM_STATE,
    DEFAULT_REQUESTED_DEVICE,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
CATBOOST_MODEL_NAME: str = "CatBoostRegressor"                   # CatBoost 회귀 모델 기본 식별 명칭
CATBOOST_SUPPORTED_DEVICES: Tuple[str, ...] = ("cpu", "cuda")    # CatBoost 네이티브 엔진이 지원하는 하드웨어 가속기 목록
CATBOOST_TASK_TYPE_MAP: Dict[str, str] = {
    "cpu": "CPU",                                                # CPU 연산용 CatBoost task_type 매핑값
    "cuda": "GPU",                                               # CUDA 가속용 CatBoost task_type 매핑값
}

DEFAULT_CATBOOST_PARAMS: Dict[str, Any] = {
    "iterations": 100,                                           # 부스팅 라운드(대칭 결정 트리) 최대 개수
    "depth": 6,                                                  # 개별 대칭 트리(Oblivious Tree)의 최대 깊이
    "learning_rate": 0.1,                                        # 단계별 가중치 갱신 학습률(Shrinkage)
    "l2_leaf_reg": 3.0,                                          # 리프 노드 가중치에 대한 L2 정규화 계수
    "random_strength": 1.0,                                      # 트리 분할 점수 산출 시 추가할 무작위성 강도
    "loss_function": "RMSE",                                     # 회귀 학습 목적 함수 (평균 제곱근 오차)
    "thread_count": -1,                                          # 병렬 연산 스레드 개수 (-1은 가용 전체 코어 사용)
    "verbose": False,                                            # 학습 중 부스팅 라운드별 콘솔 로그 출력 여부
    "allow_writing_files": False,                                # 학습 중 임시 로그 디렉터리(catboost_info) 생성 억제 여부
}


class CatBoostRegressor(AbstractMLRegressor):
    """CatBoost 그래디언트 부스팅 회귀 알고리즘 구체 클래스.

    AbstractMLRegressor의 공통 생명주기(fit, predict, get_feature_importance, save/load)를
    상속받아 재사용하며, GPU 디바이스 자동 감지(task_type 매핑) 및 검증셋(eval_set) 조기 종료 바인딩을 전담합니다.

    Attributes:
        model (Optional[cb.CatBoostRegressor]): 학습 및 추론을 수행하는 CatBoost 추정기 인스턴스.
    """

    def __init__(
        self,
        model_name: str = CATBOOST_MODEL_NAME,
        random_state: int = DEFAULT_RANDOM_STATE,
        **hyperparameters: Any,
    ) -> None:
        """CatBoostRegressor 인스턴스, 런타임 디바이스 및 하이퍼파라미터를 초기화합니다.

        Args:
            model_name (str): 모델 고유 식별 명칭. 기본값은 CATBOOST_MODEL_NAME.
            random_state (int): 재현성 확보를 위한 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            **hyperparameters (Any): 외부 설정 또는 Optuna에서 주입되는 가변 하이퍼파라미터.
        """
        # 1. 기본 하이퍼파라미터 사본에 외부 주입 커스텀 하이퍼파라미터 병합
        merged_hyperparameters: Dict[str, Any] = self._merge_hyperparameters(
            default_params=DEFAULT_CATBOOST_PARAMS,
            custom_params=hyperparameters,
        )

        # 2. 런타임 가용 하드웨어를 탐색하여 CatBoost 전용 연산 규격(task_type)으로 변환 할당
        # [설계 의도] CatBoost는 Apple Silicon(mps) 미지원 및 'device' 대신 'task_type'('CPU'/'GPU') 인자를 요구하므로,
        # 공통 디바이스 감지 결과를 CatBoost 네이티브 파라미터 규격으로 매핑하여 인터페이스 통일성을 유지함
        requested_device: str = str(
            merged_hyperparameters.pop("device", DEFAULT_REQUESTED_DEVICE)
        )
        detected_device: str = self._detect_device(
            requested_device=requested_device,
            supported_devices=CATBOOST_SUPPORTED_DEVICES,
        )
        merged_hyperparameters.setdefault(
            "task_type",
            CATBOOST_TASK_TYPE_MAP[detected_device],
        )

        # 3. 상위 추상 클래스(AbstractMLRegressor) 공통 상태 및 메타데이터 초기화
        super().__init__(
            model_name=model_name,
            random_state=random_state,
            **merged_hyperparameters,
        )
        self.device: str = detected_device
        self.model: Optional[cb.CatBoostRegressor] = None

    # --------------------------------------------------------------------------
    # Internal Helper Functions
    # --------------------------------------------------------------------------
    def _build_estimator(self) -> cb.CatBoostRegressor:
        """설정된 하이퍼파라미터와 난수 시드를 바인딩하여 CatBoostRegressor 추정기 인스턴스를 생성합니다."""
        # 난수 시드 및 디바이스(task_type)가 포함된 하이퍼파라미터를 주입하여 CatBoostRegressor 인스턴스 반환
        return cb.CatBoostRegressor(
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
        """검증 데이터셋(eval_set)과 샘플 가중치를 구성하여 CatBoost 부스팅 학습을 집행합니다."""
        # 1. 검증셋(eval_set) 및 샘플 가중치가 포함된 학습 옵션 딕셔너리 구성
        fit_options: Dict[str, Any] = self._prepare_catboost_fit_options(
            X_val=X_val,
            y_val=y_val,
            sample_weight=sample_weight,
            **kwargs,
        )

        # 2. 내부 CatBoostRegressor 추정기 학습 실행
        self.model.fit(X_train, y_train, **fit_options)

    @staticmethod
    def _prepare_catboost_fit_options(
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        sample_weight: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """CatBoost fit 호출에 필요한 가중치 배열 및 조기 종료용 eval_set 옵션 딕셔너리를 구성합니다."""
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