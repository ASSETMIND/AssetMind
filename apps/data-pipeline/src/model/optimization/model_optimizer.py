from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional, Tuple, Type
import pandas as pd

from src.dataset.walk_forward_splitter import WalkForwardSplitter
from src.model.core.base.abstract_regressor import AbstractRegressor
from src.model.core.dl.dcn_v2_regressor import DCNv2Regressor
from src.model.core.dl.ft_transformer_regressor import FTTransformerRegressor
from src.model.core.dl.tabular_resnet_regressor import TabularResNetRegressor
from src.model.core.dl.tcn_regressor import TCNRegressor
from src.model.core.ml.catboost_regressor import CatBoostRegressor
from src.model.core.ml.elasticnet_regressor import ElasticNetRegressor
from src.model.core.ml.random_forest_regressor import RandomForestRegressor
from src.model.core.ml.xgboost_regressor import XGBoostRegressor
from src.model.evaluation.criteria import Weights
from src.model.evaluation.model_evaluator import ModelEvaluator
from src.model.evaluation.schema import EvaluationMetric
from src.model.optimization.search_space import (
    audit_search_space_boundaries,
    get_search_spaces,
)
from src.model.optimization.walk_forward_optimizer import (
    SingleOptimizationResult,
    WalkForwardOptimizer,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [패밀리별 및 통합 회귀 모델 레지스트리 설정]
DEFAULT_ML_MODEL_REGISTRY: Dict[str, Type[AbstractRegressor]] = {
    "ElasticNet": ElasticNetRegressor,                             # 선형 L1/L2 정규화 회귀 모델
    "XGBoost": XGBoostRegressor,                                   # 익스트림 그래디언트 부스팅 트리 회귀 모델
    "RandomForest": RandomForestRegressor,                         # 배깅 기반 랜덤 포레스트 회귀 모델
    "CatBoost": CatBoostRegressor,                                 # 대칭 트리 기반 캣부스트 회귀 모델
}
DEFAULT_DL_MODEL_REGISTRY: Dict[str, Type[AbstractRegressor]] = {
    "TabularResNet": TabularResNetRegressor,                       # 2D 정형 잔차 신경망 회귀 모델
    "DCNv2": DCNv2Regressor,                                       # 2D 명시적 고차 교차 신경망 회귀 모델
    "FTTransformer": FTTransformerRegressor,                       # 2D 피처 토크나이저 트랜스포머 회귀 모델
    "TCN": TCNRegressor,                                           # 3D 인과적 시간 합성곱 신경망 회귀 모델
}
DEFAULT_MODEL_REGISTRY: Dict[str, Type[AbstractRegressor]] = {
    **DEFAULT_ML_MODEL_REGISTRY,
    **DEFAULT_DL_MODEL_REGISTRY,
}

# [시계열 교차검증 분할기 및 HPO 실행 기본 설정]
DEFAULT_N_SPLITS: int = 5                                          # Walk-Forward 교차검증 기본 Fold 수
DEFAULT_FORECAST_HORIZON: int = 20                                 # 미래 참조 누수 차단용 기본 예측 호라이즌(영업일)
DEFAULT_MIN_TRAIN_RATIO: float = 0.5                               # 초기 학습 윈도우 최소 보장 비율
DEFAULT_N_TRIALS: int = 50                                         # 모델별 Optuna 기본 탐색 시도 횟수
DEFAULT_PATIENCE: int = 20                                         # Optuna 조기 종료 허용 연속 미개선 Trial 수
DEFAULT_RANDOM_STATE: int = 42                                     # 실험 재현성 보장을 위한 기본 난수 시드
DEFAULT_N_JOBS: int = 1                                            # Optuna 기본 병렬 실행 워커 수

# [마스터 리더보드 정산 및 수치 포맷팅 설정]
RAW_SCORE_SORT_COLUMN: str = "_raw_score"                          # 리더보드 내림차순 정렬용 임시 스코어 컬럼명
LEADERBOARD_INDEX_NAME: str = "Rank"                               # 리더보드 최종 순위 인덱스 명칭
EXCLUDED_PARAM_KEY: str = "random_state"                           # 최적 파라미터 요약 문자열에서 제외할 시드 키
MIN_DENOMINATOR_THRESHOLD: float = 1e-3                            # 백분율 변화율 계산 시 영나눗셈 왜곡 방지 임계값
PERCENT_MULTIPLIER: float = 100.0                                  # 비율 수치를 백분율(%)로 변환하기 위한 승수

# [콘솔 진행 상태 로깅 및 영역별 왼쪽 정렬 폭 설정]
CPU_DEVICE_LABEL: str = "CPU"                                      # CPU 연산 디바이스 출력 라벨
GPU_DEVICE_LABEL: str = "GPU"                                      # GPU(CUDA/MPS) 가속 디바이스 출력 라벨
GPU_BACKEND_IDENTIFIERS: Tuple[str, ...] = ("cuda", "mps", "gpu")  # GPU 가속기로 판정할 런타임 백엔드 식별자 목록
DEVICE_TAG_WIDTH: int = 6                                          # 디바이스 태그([CPU], [GPU]) 영역 왼쪽 정렬 고정 폭
MODEL_NAME_WIDTH: int = 14                                         # 모델 식별 명칭 영역 왼쪽 정렬 고정 폭
STATUS_LABEL_WIDTH: int = 7                                        # 실행 상태 라벨(Running, Done) 영역 왼쪽 정렬 고정 폭
ELAPSED_TIME_WIDTH: int = 9                                        # 소요 시간 문자열 영역 왼쪽 정렬 고정 폭
TRIAL_STATUS_WIDTH: int = 26                                       # Trial 진행 및 종료 상태 영역 왼쪽 정렬 고정 폭


# ==============================================================================
# Public API Functions
# ==============================================================================
@dataclass(frozen=True)
class BatchOptimizationResult:
    """다중 회귀 모델(ML/DL) 일괄 HPO 결과 및 통합 분석 메타데이터를 캡슐화한 불변 DTO.

    Attributes:
        results (Dict[str, SingleOptimizationResult]): 모델 식별 명칭을 키로 하는 개별 최적화 결과 DTO 맵.
        best_models (Dict[str, AbstractRegressor]): 각 모델별 전체 학습 데이터로 재학습 완료된 최적 모델 인스턴스 맵.
        leaderboard (pd.DataFrame): Default 대비 Tuned 개선율 및 10대 지표를 망라한 마스터 비교 리더보드.
        boundary_audit_summary (pd.DataFrame): 전체 모델의 파라미터 경계선 도달 현황을 집약한 통합 감사 데이터프레임.
        total_elapsed_seconds (float): 전체 모델 일괄 최적화에 소요된 총 런타임(초).
    """

    results: Dict[str, SingleOptimizationResult]
    best_models: Dict[str, AbstractRegressor]
    leaderboard: pd.DataFrame
    boundary_audit_summary: pd.DataFrame
    total_elapsed_seconds: float


class ModelOptimizer:
    """전체 회귀 모델군(ML 4종 및 DL 4종) 대상 Walk-Forward CV HPO 배치 실행 및 리더보드 정산 오케스트레이터.

    Attributes:
        search_spaces (Dict[str, Dict[str, Dict[str, Any]]]): 모델별 하이퍼파라미터 탐색 공간 맵.
        splitter (WalkForwardSplitter): 시계열 Walk-Forward 교차검증 분할기.
        weights (Weights): 핵심 계층(ML, Factor) 복합 스코어 가중치 DTO.
        evaluator (ModelEvaluator): 10대 지표 및 복합 스코어 산출 평가 엔진.
        n_trials (int): 각 모델별 Optuna 최대 탐색 횟수.
        patience (int): Optuna 조기 종료 기준 연속 미개선 Trial 수.
        random_state (int): 재현성 확보용 난수 시드값.
        timeout (Optional[float]): 모델별 최적화 최대 허용 시간(초).
        n_jobs (int): Optuna 병렬 실행 워커 수.
    """

    def __init__(
        self,
        search_spaces: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
        splitter: Optional[WalkForwardSplitter] = None,
        weights: Optional[Weights] = None,
        evaluator: Optional[ModelEvaluator] = None,
        n_trials: int = DEFAULT_N_TRIALS,
        patience: int = DEFAULT_PATIENCE,
        random_state: int = DEFAULT_RANDOM_STATE,
        timeout: Optional[float] = None,
        n_jobs: int = DEFAULT_N_JOBS,
    ) -> None:
        """ModelOptimizer 인스턴스와 HPO 실행 제어 설정을 초기화합니다.

        Args:
            search_spaces (Optional[Dict[str, Dict[str, Dict[str, Any]]]]): 모델별 탐색 공간 맵. 기본값은 None.
            splitter (Optional[WalkForwardSplitter]): 시계열 교차검증 분할기. 기본값은 None.
            weights (Optional[Weights]): 복합 스코어 가중치 DTO. 기본값은 None.
            evaluator (Optional[ModelEvaluator]): 10대 지표 산출 평가 엔진. 기본값은 None.
            n_trials (int): 각 모델별 Optuna 시도 횟수. 기본값은 DEFAULT_N_TRIALS.
            patience (int): Optuna 조기 종료 기준 연속 Trial 수. 기본값은 DEFAULT_PATIENCE.
            random_state (int): 재현성 확보용 난수 시드값. 기본값은 DEFAULT_RANDOM_STATE.
            timeout (Optional[float]): 모델별 최적화 최대 허용 시간(초). 기본값은 None.
            n_jobs (int): Optuna 병렬 실행 워커 수. 기본값은 DEFAULT_N_JOBS.
        """
        # 1. 탐색 공간, 시계열 분할기, 가중치 및 평가 엔진 의존성 초기화
        self.search_spaces: Dict[str, Dict[str, Dict[str, Any]]] = (
            search_spaces if search_spaces is not None else get_search_spaces()
        )
        self.splitter: WalkForwardSplitter = splitter or WalkForwardSplitter(
            n_splits=DEFAULT_N_SPLITS,
            forecast_horizon=DEFAULT_FORECAST_HORIZON,
            min_train_ratio=DEFAULT_MIN_TRAIN_RATIO,
        )
        self.weights: Weights = weights or Weights()
        self.evaluator: ModelEvaluator = evaluator or ModelEvaluator(
            weights=self.weights
        )

        # 2. Optuna HPO 탐색 제어 파라미터 상태 저장
        self.n_trials: int = n_trials
        self.patience: int = patience
        self.random_state: int = random_state
        self.timeout: Optional[float] = timeout
        self.n_jobs: int = n_jobs

    def optimize_all(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model_registry: Optional[Dict[str, Type[AbstractRegressor]]] = None,
    ) -> BatchOptimizationResult:
        """등록된 모델군(ML/DL)에 대해 순차적으로 Walk-Forward HPO를 구동하고 종합 정산 결과를 반환합니다.

        Args:
            X_train (pd.DataFrame): HPO 학습용 전체 피처 데이터프레임.
            y_train (pd.Series): HPO 학습용 전체 타겟 시계열.
            model_registry (Optional[Dict[str, Type[AbstractRegressor]]]): 최적화할 모델 클래스 맵. 기본값은 None(8종 전체 실행).

        Returns:
            BatchOptimizationResult: 모델별 최적 모델, 마스터 리더보드 및 통합 감사표가 포함된 불변 DTO.

        Raises:
            ValueError: 입력 데이터셋이 비어 있거나 유효하지 않은 경우.
            KeyError: 실행 대상 모델의 탐색 공간 명세가 존재하지 않는 경우.
        """
        # 1. 학습용 입력 데이터셋 유효성 검증 및 활성 모델 레지스트리 확정
        _validate_optimization_inputs(X_train=X_train, y_train=y_train)
        active_registry: Dict[str, Type[AbstractRegressor]] = (
            model_registry or DEFAULT_MODEL_REGISTRY
        )

        # 2. 등록된 모델군을 순회하며 개별 Walk-Forward HPO 실행 및 최적 모델 수집
        start_total_time: float = time.perf_counter()
        optimization_results: Dict[str, SingleOptimizationResult] = {}
        best_models_map: Dict[str, AbstractRegressor] = {}
        total_models_count: int = len(active_registry)

        for index, (model_key, model_cls) in enumerate(
            active_registry.items(), start=1
        ):
            single_result: SingleOptimizationResult = _execute_single_model_hpo(
                index=index,
                total_models_count=total_models_count,
                model_key=model_key,
                model_cls=model_cls,
                search_spaces=self.search_spaces,
                splitter=self.splitter,
                weights=self.weights,
                evaluator=self.evaluator,
                n_trials=self.n_trials,
                patience=self.patience,
                random_state=self.random_state,
                timeout=self.timeout,
                n_jobs=self.n_jobs,
                X_train=X_train,
                y_train=y_train,
            )
            optimization_results[model_key] = single_result
            best_models_map[model_key] = single_result.best_model

        total_elapsed_seconds: float = time.perf_counter() - start_total_time

        # 3. 마스터 비교 리더보드 및 탐색 공간 경계 도달 감사표 생성 후 결과 DTO 반환
        leaderboard_df: pd.DataFrame = _build_master_leaderboard(
            results=optimization_results,
            max_trials=self.n_trials,
        )
        boundary_summary_df: pd.DataFrame = audit_search_space_boundaries(
            hpo_results=optimization_results
        )

        return BatchOptimizationResult(
            results=optimization_results,
            best_models=best_models_map,
            leaderboard=leaderboard_df,
            boundary_audit_summary=boundary_summary_df,
            total_elapsed_seconds=total_elapsed_seconds,
        )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_optimization_inputs(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> None:
    """HPO 학습에 주입될 피처 데이터프레임과 타겟 시리즈의 비어 있음 여부를 검증합니다."""
    # 1. 입력 피처 또는 타겟이 None이거나 비어 있는 경우 즉시 ValueError 발생
    if X_train is None or y_train is None or X_train.empty or y_train.empty:
        raise ValueError(
            "[ModelOptimizer] 학습 데이터셋(X_train 또는 y_train)이 비어 있습니다."
        )


def _detect_execution_device_label(
    model_cls: Type[AbstractRegressor],
    random_state: int,
) -> str:
    """모델 클래스의 런타임 할당 디바이스를 확인하여 'CPU' 또는 'GPU' 라벨을 반환합니다."""
    # 1. 임시 인스턴스의 device 속성 및 hyperparameters 내 가속기 설정(device, task_type)을 순차 탐색하여 판별
    try:
        probe_instance: AbstractRegressor = model_cls(random_state=random_state)
        hyperparameters: Dict[str, Any] = getattr(
            probe_instance, "hyperparameters", {}
        )
        candidate_devices: Tuple[Any, ...] = (
            getattr(probe_instance, "device", None),
            hyperparameters.get("device"),
            hyperparameters.get("task_type"),
        )
        for candidate in candidate_devices:
            if candidate is None:
                continue
            raw_device: str = str(candidate).lower()
            if any(
                raw_device.startswith(gpu_id)
                for gpu_id in GPU_BACKEND_IDENTIFIERS
            ):
                return GPU_DEVICE_LABEL
    except Exception:
        pass

    return CPU_DEVICE_LABEL


def _format_hpo_log_prefix(
    index: int,
    total_models_count: int,
    device_label: str,
    model_key: str,
) -> str:
    """순번, 디바이스 태그([CPU]/[GPU]), 모델명이 영역별로 왼쪽 정렬된 로그 접두사를 생성합니다."""
    # 1. 대괄호 내부 공백 없이 각 영역 전체를 고정 폭으로 왼쪽 정렬
    device_tag: str = f"[{device_label}]"
    return (
        f"[{index:02d}/{total_models_count:02d}] "
        f"{device_tag:<{DEVICE_TAG_WIDTH}s} "
        f"{model_key:<{MODEL_NAME_WIDTH}s} "
        f"HPO Tuning Run... "
    )


def _execute_single_model_hpo(
    index: int,
    total_models_count: int,
    model_key: str,
    model_cls: Type[AbstractRegressor],
    search_spaces: Dict[str, Dict[str, Dict[str, Any]]],
    splitter: WalkForwardSplitter,
    weights: Weights,
    evaluator: ModelEvaluator,
    n_trials: int,
    patience: int,
    random_state: int,
    timeout: Optional[float],
    n_jobs: int,
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> SingleOptimizationResult:
    """단일 모델에 대한 탐색 공간 검증, WalkForwardOptimizer 구동 및 진행 상태 로깅을 수행합니다."""
    # 1. 대상 모델의 하이퍼파라미터 탐색 공간 명세 존재 여부 확인
    model_search_space: Dict[str, Dict[str, Dict[str, Any]]] = search_spaces.get(model_key, {})
    if not model_search_space:
        raise KeyError(
            f"[{model_key}] 모델에 대한 Search Space 명세가 존재하지 않습니다."
        )

    # 2. 런타임 디바이스(CPU/GPU) 판별 후 영역별 왼쪽 정렬된 시작 로그 출력 및 최적화 집행
    device_label: str = _detect_execution_device_label(
        model_cls=model_cls,
        random_state=random_state,
    )
    log_prefix: str = _format_hpo_log_prefix(
        index=index,
        total_models_count=total_models_count,
        device_label=device_label,
        model_key=model_key,
    )
    print(log_prefix, end="", flush=True)

    optimizer: WalkForwardOptimizer = WalkForwardOptimizer(
        model_class=model_cls,
        search_space=model_search_space,
        splitter=splitter,
        weights=weights,
        evaluator=evaluator,
        model_name=model_key,
        n_trials=n_trials,
        patience=patience,
        random_state=random_state,
        timeout=timeout,
        n_jobs=n_jobs,
        progress_prefix=log_prefix,
    )
    single_result: SingleOptimizationResult = optimizer.optimize(
        X_train=X_train,
        y_train=y_train,
    )

    # 3. 조기 종료 여부 판정 및 실시간 진행 표시줄을 덮어쓰는 최종 완료 요약 로그 출력
    is_early_stopped: bool = single_result.trials_executed < n_trials
    run_status: str = (
        f"{single_result.trials_executed} Trials (Early Stopped)"
        if is_early_stopped
        else f"{single_result.trials_executed} Trials (Full Run)"
    )
    done_label: str = f"{'Done':<{STATUS_LABEL_WIDTH}s}"
    elapsed_str: str = f"{f'{single_result.elapsed_seconds:.2f}s':<{ELAPSED_TIME_WIDTH}s}"
    status_str: str = f"{run_status:<{TRIAL_STATUS_WIDTH}s}"

    print(
        f"\r{log_prefix}{done_label} ("
        f"{elapsed_str} | {status_str} | "
        f"Best Composite Score: {single_result.best_score:.4f})",
        flush=True,
    )
    return single_result


def _build_master_leaderboard(
    results: Dict[str, SingleOptimizationResult],
    max_trials: int,
) -> pd.DataFrame:
    """모델별 Default 대비 Tuned 지표를 대조하여 복합 스코어 순위가 부여된 마스터 리더보드를 생성합니다."""
    # 1. 각 모델의 최적화 결과를 순회하며 리더보드 비교 행 딕셔너리 리스트 생성
    rows: List[Dict[str, Any]] = [
        _create_leaderboard_row(
            model_key=model_key,
            result=result,
            max_trials=max_trials,
        )
        for model_key, result in results.items()
    ]

    # 2. 데이터프레임 변환 후 최적 복합 스코어 기준 내림차순 정렬 및 1위부터 Rank 인덱스 부여
    leaderboard_df: pd.DataFrame = pd.DataFrame(rows)
    leaderboard_df.sort_values(
        by=RAW_SCORE_SORT_COLUMN, ascending=False, inplace=True
    )
    leaderboard_df.drop(columns=[RAW_SCORE_SORT_COLUMN], inplace=True)
    leaderboard_df.reset_index(drop=True, inplace=True)
    leaderboard_df.index += 1
    leaderboard_df.index.name = LEADERBOARD_INDEX_NAME

    return leaderboard_df


def _create_leaderboard_row(
    model_key: str,
    result: SingleOptimizationResult,
    max_trials: int,
) -> Dict[str, Any]:
    """단일 모델의 Default 대비 Tuned 10대 평가지표 및 메타데이터 비교 행을 생성합니다."""
    # 1. 기본 모델과 튜닝된 모델의 평가 지표 딕셔너리 추출 및 최적 파라미터 문자열 포맷팅
    def_m: Dict[EvaluationMetric, float] = result.default_metrics
    tun_m: Dict[EvaluationMetric, float] = result.tuned_metrics
    param_str: str = _format_best_parameters(best_params=result.best_params)

    # 2. 복합 스코어 및 10대 지표의 변화량이 포맷팅된 단일 행 딕셔너리 구성 및 반환
    return {
        "Algorithm": model_key,
        "Trials": f"{result.trials_executed}/{max_trials}",
        "Composite Score": _format_metric_comparison(
            val_def=result.default_score,
            val_tuned=result.best_score,
            is_percent=False,
        ),
        "MDA": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.MDA, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.MDA, 0.0),
            is_percent=True,
        ),
        "RMSE": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.RMSE, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.RMSE, 0.0),
        ),
        "MAE": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.MAE, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.MAE, 0.0),
        ),
        "Rank IC": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.RANK_IC, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.RANK_IC, 0.0),
        ),
        "ICIR": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.ICIR, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.ICIR, 0.0),
        ),
        "Signal Sharpe": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.SIGNAL_SHARPE, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.SIGNAL_SHARPE, 0.0),
        ),
        "Sortino Ratio": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.SORTINO_RATIO, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.SORTINO_RATIO, 0.0),
        ),
        "MDD": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.MDD, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.MDD, 0.0),
            is_percent=True,
        ),
        "Factor t-stat": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.FACTOR_T_STAT, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.FACTOR_T_STAT, 0.0),
        ),
        "Factor p-val": _format_metric_comparison(
            val_def=def_m.get(EvaluationMetric.FACTOR_P_VAL, 0.0),
            val_tuned=tun_m.get(EvaluationMetric.FACTOR_P_VAL, 0.0),
            is_p_value=True,
        ),
        "Best Parameters": param_str,
        "Elapsed Time": f"{result.elapsed_seconds:.2f}s",
        RAW_SCORE_SORT_COLUMN: result.best_score,
    }


def _format_best_parameters(best_params: Dict[str, Any]) -> str:
    """난수 시드 키를 제외한 최적 하이퍼파라미터 딕셔너리를 가독성 높은 문자열로 변환합니다."""
    # 1. 제외 대상 키(random_state)를 필터링한 후 실수형은 소수점 4자리로 정제하여 결합 반환
    clean_params: Dict[str, Any] = {
        key: value
        for key, value in best_params.items()
        if key != EXCLUDED_PARAM_KEY
    }
    return ", ".join(
        f"{key}={value:.4f}" if isinstance(value, float) else f"{key}={value}"
        for key, value in clean_params.items()
    )


def _format_metric_comparison(
    val_def: float,
    val_tuned: float,
    is_percent: bool = False,
    is_p_value: bool = False,
) -> str:
    """기본 모델 수치 대비 튜닝 모델 수치의 변화량을 지표 특성에 맞춰 문자열로 포맷팅합니다."""
    # 1. 튜닝 전후 절대 차분 계산 및 p-value 여부에 따른 절대값 이동 표기 반환
    delta: float = val_tuned - val_def
    if is_p_value:
        return f"{val_tuned:.4f} (from {val_def:.4f})"

    # 2. 백분율 지표(MDA, MDD)인 경우 퍼센트포인트(%p) 증감으로 표기하여 반환
    if is_percent:
        delta_pp: float = delta * PERCENT_MULTIPLIER
        return f"{val_tuned * PERCENT_MULTIPLIER:.2f}% ({delta_pp:+.2f}%p)"

    # 3. 일반 실수 지표는 분모 극소값 여부를 확인하여 단순 차분(Δ) 또는 상대 변화율(%)로 반환
    if abs(val_def) < MIN_DENOMINATOR_THRESHOLD:
        return f"{val_tuned:.4f} (Δ {delta:+.4f})"
    delta_pct: float = (delta / abs(val_def)) * PERCENT_MULTIPLIER
    return f"{val_tuned:.4f} ({delta_pct:+.2f}%)"