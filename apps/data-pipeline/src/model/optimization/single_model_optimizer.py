"""
3대 단일 회귀 추정기(ElasticNet, XGBoost, RandomForest) 대상 Walk-Forward HPO 일괄 오케스트레이션 모듈.

[주요 아키텍처 및 책임]
1. 등록된 모델 클래스군을 순회하며 WalkForwardOptimizer 엔진을 통해 HPO를 일괄 집행합니다.
2. 각 모델의 Default 베이스라인 대비 Tuned 모델의 10대 지표 및 복합 스코어 변화량(Delta, Delta%)을 마스터 리더보드로 가공합니다.
3. search_space.py의 audit_search_space_boundaries()와 연계하여 전체 모델의 경계선 도달 현황을 단일 감사표로 통합합니다.
4. 모델별 재학습 인스턴스와 종합 성적표를 불변 BatchOptimizationResult DTO로 캡슐화하여 사출합니다.
"""

from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional, Type
import pandas as pd

from src.model.core.abstract_regressor import AbstractRegressor
from src.model.core.elasticnet_regressor import ElasticNetRegressor
from src.model.core.random_forest_regressor import RandomForestRegressor
from src.model.core.xgboost_regressor import XGBoostRegressor
from src.dataset.walk_forward_splitter import WalkForwardSplitter
from src.model.evaluation.criteria import Weights
from src.model.evaluation.schema import EvaluationMetric
from src.model.evaluation.model_evaluator import ModelEvaluator
from src.model.optimization.search_space import (
    audit_search_space_boundaries,
    get_search_spaces,
)
from src.model.optimization.walk_forward_optimizer import (
    SingleOptimizationResult,
    WalkForwardOptimizer,
)

# ==============================================================================
# 기본 단일 모델 레지스트리 (SSOT Registry)
# ==============================================================================
DEFAULT_MODEL_REGISTRY: Dict[str, Type[AbstractRegressor]] = {
    "ElasticNet": ElasticNetRegressor,
    "XGBoost": XGBoostRegressor,
    "RandomForest": RandomForestRegressor,
}


# ==============================================================================
# 일괄 최적화 결과 캡슐화 불변 DTO (Data Transfer Object)
# ==============================================================================

@dataclass(frozen=True)
class BatchOptimizationResult:
    """3대 모델 일괄 HPO 결과 및 통합 분석 메타데이터를 캡슐화한 불변 DTO.

    Attributes:
        results (Dict[str, SingleOptimizationResult]): 알고리즘 식별 명칭을 키로 하는 모델별 최적화 결과 DTO 맵.
        best_models (Dict[str, AbstractRegressor]): 각 모델별 전체 학습 데이터로 재학습 완료된 최적 모델 인스턴스 맵.
        leaderboard (pd.DataFrame): Default 대비 Tuned 개선율 및 10대 지표를 망라한 마스터 비교 리더보드.
        boundary_audit_summary (pd.DataFrame): 전체 모델의 파라미터 경계선 도달 현황을 집약한 통합 감사 데이터프레임.
        total_elapsed_seconds (float): 3대 모델 일괄 최적화에 소요된 총 런타임(초).
    """
    results: Dict[str, SingleOptimizationResult]
    best_models: Dict[str, AbstractRegressor]
    leaderboard: pd.DataFrame
    boundary_audit_summary: pd.DataFrame
    total_elapsed_seconds: float


# ==============================================================================
# 단일 모델 HPO 일괄 오케스트레이터 클래스 (Main Class)
# ==============================================================================

class SingleModelOptimizer:
    """3대 회귀 모델군 대상 Walk-Forward CV HPO 배치 실행 및 리더보드 정산 오케스트레이터."""

    def __init__(
        self,
        search_spaces: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
        splitter: Optional[WalkForwardSplitter] = None,
        weights: Optional[Weights] = None,
        evaluator: Optional[ModelEvaluator] = None,
        n_trials: int = 50,
        patience: int = 20,
        random_state: int = 42,
        timeout: Optional[float] = None,
        n_jobs: int = 1,
    ) -> None:
        """SingleModelOptimizer 인스턴스를 초기화합니다.

        Args:
            search_spaces (Optional[Dict[str, Dict[str, Dict[str, Any]]]]): 모델별 탐색 공간 맵 (None 시 기본 템플릿 사용).
            splitter (Optional[WalkForwardSplitter]): 시계열 교차검증 분할기 (None 시 기본 5-Fold 분할기 생성).
            weights (Optional[Weights]): 2대 핵심 계층(ML, Factor) 복합 스코어 가중치 DTO.
            evaluator (Optional[ModelEvaluator]): 10대 지표 전담 산출 평가 엔진.
            n_trials (int): 각 모델별 Optuna 시도 횟수 (기본값: 50).
            patience (int): Optuna 조기 종료 기준 연속 Trial 수 (기본값: 20).
            random_state (int): 재현성 확보용 난수 시드값 (기본값: 42).
            timeout (Optional[float]): 모델별 최적화 최대 허용 시간(초). 기본값은 None.
            n_jobs (int): Optuna 병렬 실행 워커 수 (기본값: 1).
        """
        self.search_spaces: Dict[str, Dict[str, Dict[str, Any]]] = (
            search_spaces if search_spaces is not None else get_search_spaces()
        )
        self.splitter: WalkForwardSplitter = splitter or WalkForwardSplitter(
            n_splits=5, forecast_horizon=20, min_train_ratio=0.5
        )
        self.weights: Weights = weights or Weights()
        self.evaluator: ModelEvaluator = evaluator or ModelEvaluator(weights=self.weights)
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
        """등록된 모델군에 대해 순차적으로 Walk-Forward HPO를 구동하고 종합 정산 결과를 반환합니다.

        Args:
            X_train (pd.DataFrame): HPO 학습용 전체 피처 데이터프레임.
            y_train (pd.Series): HPO 학습용 전체 타겟 시계열.
            model_registry (Optional[Dict[str, Type[AbstractRegressor]]]): 최적화할 모델 클래스 맵 (None 시 3대 모델 실행).

        Returns:
            BatchOptimizationResult: 모델별 최적 모델, 마스터 리더보드 및 통합 감사표가 포함된 불변 DTO.

        Raises:
            ValueError: 입력 데이터셋이 비어 있거나 유효하지 않은 경우 발생.
        """
        if X_train is None or y_train is None or X_train.empty or y_train.empty:
            raise ValueError("[SingleModelOptimizer] 학습 데이터셋(X_train 또는 y_train)이 비어 있습니다.")

        active_registry = model_registry or DEFAULT_MODEL_REGISTRY
        start_total_time: float = time.perf_counter()

        optimization_results: Dict[str, SingleOptimizationResult] = {}
        best_models_map: Dict[str, AbstractRegressor] = {}

        total_models_count: int = len(active_registry)

        for index, (model_key, model_cls) in enumerate(active_registry.items(), start=1):
            model_search_space = self.search_spaces.get(model_key, {})
            if not model_search_space:
                raise KeyError(f"[{model_key}] 모델에 대한 Search Space 명세가 존재하지 않습니다.")

            # 장시간 연산 시 무응답 대기 방지를 위한 시작 로그 즉시 사출 (flush=True)
            print(
                f"[{index:02d}/{total_models_count:02d}] {model_key} HPO Tuning Run... ",
                end="",
                flush=True,
            )

            optimizer = WalkForwardOptimizer(
                model_class=model_cls,
                search_space=model_search_space,
                splitter=self.splitter,
                weights=self.weights,
                evaluator=self.evaluator,
                model_name=model_key,
                n_trials=self.n_trials,
                patience=self.patience,
                random_state=self.random_state,
                timeout=self.timeout,
                n_jobs=self.n_jobs,
            )

            single_result: SingleOptimizationResult = optimizer.optimize(
                X_train=X_train,
                y_train=y_train,
            )

            optimization_results[model_key] = single_result
            best_models_map[model_key] = single_result.best_model

            # 조기 종료 발동 여부 및 정산 성과를 단일 라인으로 즉시 피드백
            is_early_stopped: bool = single_result.trials_executed < self.n_trials
            run_status: str = (
                f"{single_result.trials_executed} Trials (Early Stopped)"
                if is_early_stopped
                else f"{single_result.trials_executed} Trials (Full Run)"
            )
            print(
                f"Done ({single_result.elapsed_seconds:.2f}s | {run_status} | "
                f"Best Composite Score: {single_result.best_score:.4f})",
                flush=True,
            )

        total_elapsed_seconds: float = time.perf_counter() - start_total_time

        # 마스터 비교 리더보드 및 통합 경계 감사표 생성
        leaderboard_df = self._build_master_leaderboard(results=optimization_results)
        boundary_summary_df = audit_search_space_boundaries(hpo_results=optimization_results)

        return BatchOptimizationResult(
            results=optimization_results,
            best_models=best_models_map,
            leaderboard=leaderboard_df,
            boundary_audit_summary=boundary_summary_df,
            total_elapsed_seconds=total_elapsed_seconds,
        )

    # --------------------------------------------------------------------------
    # 내부 리더보드 정산 및 포맷팅 서브루틴 (Private Helpers)
    # --------------------------------------------------------------------------
    def _build_master_leaderboard(
        self,
        results: Dict[str, SingleOptimizationResult],
    ) -> pd.DataFrame:
        """Default vs Tuned 지표를 대조하여 요청된 형식의 마스터 리더보드 DataFrame을 생성합니다."""
        rows: List[Dict[str, Any]] = []

        for model_key, res in results.items():
            def_m = res.default_metrics
            tun_m = res.tuned_metrics

            # 파라미터 문자열 정제 (random_state 제외 및 가독성 확보)
            clean_params = {k: v for k, v in res.best_params.items() if k != "random_state"}
            param_str = ", ".join(
                f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                for k, v in clean_params.items()
            )

            row: Dict[str, Any] = {
                "Algorithm": model_key,
                "Trials": f"{res.trials_executed}/{self.n_trials}",
                "Composite Score": self._format_metric_comparison(
                    val_def=res.default_score,
                    val_tuned=res.best_score,
                    is_percent=False,
                ),
                "MDA": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.MDA, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.MDA, 0.0),
                    is_percent=True,
                ),
                "RMSE": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.RMSE, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.RMSE, 0.0),
                ),
                "MAE": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.MAE, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.MAE, 0.0),
                ),
                "Rank IC": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.RANK_IC, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.RANK_IC, 0.0),
                ),
                "ICIR": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.ICIR, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.ICIR, 0.0),
                ),
                "Signal Sharpe": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.SIGNAL_SHARPE, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.SIGNAL_SHARPE, 0.0),
                ),
                "Sortino Ratio": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.SORTINO_RATIO, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.SORTINO_RATIO, 0.0),
                ),
                "MDD": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.MDD, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.MDD, 0.0),
                    is_percent=True,
                ),
                "Factor t-stat": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.FACTOR_T_STAT, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.FACTOR_T_STAT, 0.0),
                ),
                "Factor p-val": self._format_metric_comparison(
                    val_def=def_m.get(EvaluationMetric.FACTOR_P_VAL, 0.0),
                    val_tuned=tun_m.get(EvaluationMetric.FACTOR_P_VAL, 0.0),
                    is_p_value=True,
                ),
                "Best Parameters": param_str,
                "Elapsed Time": f"{res.elapsed_seconds:.2f}s",
                "_raw_score": res.best_score,  # 정렬용 내부 메타데이터
            }
            rows.append(row)

        leaderboard_df = pd.DataFrame(rows)
        # 최적 복합 스코어 기준 내림차순 정렬 후 1위부터 Rank 인덱스 부여
        leaderboard_df.sort_values(by="_raw_score", ascending=False, inplace=True)
        leaderboard_df.drop(columns=["_raw_score"], inplace=True)
        leaderboard_df.reset_index(drop=True, inplace=True)
        leaderboard_df.index += 1
        leaderboard_df.index.name = "Rank"

        return leaderboard_df

    @staticmethod
    def _format_metric_comparison(
        val_def: float,
        val_tuned: float,
        is_percent: bool = False,
        is_p_value: bool = False,
    ) -> str:
        """수치 왜곡 없는 안전한 비교 포맷팅을 집행합니다."""
        delta: float = val_tuned - val_def

        if is_p_value:
            # p-value는 유의수준 임계치와의 비교가 핵심이므로 백분율 상대비교를 배제하고 절대값 이동 표기
            return f"{val_tuned:.4f} (from {val_def:.4f})"
        elif is_percent:
            delta_pp: float = delta * 100.0
            return f"{val_tuned * 100.0:.2f}% ({delta_pp:+.2f}%p)"
        else:
            # 분모가 0.01 미만으로 극소일 경우 상대비율(%) 왜곡 방지를 위해 단순 차분(Δ)으로 대체
            if abs(val_def) < 1e-3:
                return f"{val_tuned:.4f} (Δ {delta:+.4f})"
            delta_pct: float = (delta / abs(val_def)) * 100.0
            return f"{val_tuned:.4f} ({delta_pct:+.2f}%)"