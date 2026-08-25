from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Type
import pandas as pd

from src.model.dataset.splitter import DatasetSplitter
from src.model.optimization.time_series_optimizer import TimeSeriesOptimizer
from src.model.optimization.search_space import get_search_spaces
from src.model.core.abstract_regressor import AbstractRegressor
from src.model.core.elasticnet_regressor import ElasticNetRegressor
from src.model.core.xgboost_regressor import XGBoostRegressor
from src.model.core.random_forest_regressor import RandomForestRegressor


@dataclass
class OptimizationRegistry:
    """단일 모델 HPO 최적화 완료 산출물 및 지표 레지스트리 DTO."""

    hpo_results: Dict[str, Any]
    tuned_models: Dict[str, Any]
    default_models: Dict[str, Any]
    default_cv_metrics: Dict[str, Dict[str, float]]
    tuned_cv_metrics: Dict[str, Dict[str, float]]
    best_hyperparameters: Dict[str, Dict[str, Any]]

    @property
    def summary_dataframe(self) -> pd.DataFrame:
        """Optuna HPO 전체 실행 정산 대시보드 데이터프레임을 생성합니다."""
        return pd.DataFrame(
            [res.to_summary_dictionary() for res in self.hpo_results.values()]
        ).set_index("알고리즘 (Algorithm)")


class SingleModelOptimizer:
    """3대 회귀 모델군에 대한 Walk-Forward CV HPO 일괄 실행기."""

    def __init__(
        self,
        splitter: DatasetSplitter,
        tracker: Optional[Any] = None,
        patience: int = 20,
        min_trials: int = 15,
        max_trials: int = 80,
        random_seed: int = 42
    ) -> None:
        """
        일괄 최적화기를 초기화합니다.

        Args:
            splitter: 시계열 Walk-Forward 분할기 인스턴스
            tracker: MLflowTracker 인스턴스 (Optional)
            patience: 조기 종료 대기 Trial 수
            min_trials: 최소 탐색 Trial 수
            max_trials: 최대 탐색 Trial 수
            random_seed: 난수 시드
        """
        self.tracker = tracker
        self.time_series_optimizer = TimeSeriesOptimizer(
            splitter=splitter,
            patience=patience,
            min_trials=min_trials,
            max_trials=max_trials,
            random_seed=random_seed
        )

        # [설계 의도] 기본 모델 명세를 클래스 내부로 캡슐화하여 상위 노트북에서의 하드코딩 제거
        self.default_model_specifications: List[Tuple[str, Type[AbstractRegressor], Dict[str, Any]]] = [
            ("ElasticNet", ElasticNetRegressor, {"alpha": 0.1, "l1_ratio": 0.5, "random_state": random_seed}),
            ("XGBoost", XGBoostRegressor, {"objective": "reg:squarederror", "n_estimators": 100, "max_depth": 3, "learning_rate": 0.03, "subsample": 0.8, "colsample_bytree": 0.8, "random_state": random_seed}),
            ("RandomForest", RandomForestRegressor, {"criterion": "squared_error", "n_estimators": 100, "max_depth": 3, "min_samples_split": 4, "random_state": random_seed})
        ]

    def optimize_all(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        search_spaces: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> OptimizationRegistry:
        """
        3대 모델에 대해 순차적으로 Walk-Forward CV HPO를 집행하고 종합 레지스트리를 반환합니다.

        Args:
            X_train: 학습 세트 피처 행렬
            y_train: 학습 세트 타겟 시계열
            search_spaces: 사용자 정의 탐색 공간 (None일 경우 기본 표준 공간 사용)

        Returns:
            OptimizationRegistry: 전체 모델의 HPO 결과 및 모델 객체 캡슐화 DTO
        """
        effective_search_spaces = search_spaces if search_spaces is not None else get_search_spaces()

        hpo_results: Dict[str, Any] = {}
        tuned_models: Dict[str, Any] = {}
        default_models: Dict[str, Any] = {}
        default_cv_metrics: Dict[str, Dict[str, float]] = {}
        tuned_cv_metrics: Dict[str, Dict[str, float]] = {}
        best_hyperparameters: Dict[str, Dict[str, Any]] = {}

        print("=" * 122)
        print(f" [Stage 2 TimeSeries Walk-Forward HPO Launch] Target Models: {len(self.default_model_specifications)} | Early Stopping (Patience: {self.time_series_optimizer.patience})")
        print("=" * 122)

        for model_name, model_class, default_params in self.default_model_specifications:
            print(f"[{model_name}] Walk-Forward CV HPO Running ... ", end="", flush=True)

            result_dto = self.time_series_optimizer.fit(
                algorithm_name=model_name,
                model_class=model_class,
                default_hyperparameters=default_params,
                search_space=effective_search_spaces[model_name],
                feature_matrix=X_train,
                target_series=y_train
            )

            # 결과 바인딩
            hpo_results[model_name] = result_dto
            tuned_models[model_name] = result_dto.tuned_model
            default_models[model_name] = result_dto.default_model
            default_cv_metrics[model_name] = result_dto.default_cross_validation_metrics
            tuned_cv_metrics[model_name] = result_dto.tuned_cross_validation_metrics
            best_hyperparameters[model_name] = result_dto.best_hyperparameters

            # [설계 의도] MLflow Tracker 연동 시 1차 수치 및 파라미터 백엔드 자동 로깅
            if self.tracker is not None:
                self.tracker.log_hpo_result(model_name=model_name, result_dto=result_dto)

            print(
                f"Done ({result_dto.total_search_time_seconds:.2f}s | "
                f"Trials: {result_dto.trials_executed} | "
                f"Best CV MDA: {result_dto.tuned_cross_validation_metrics['mean_mda'] * 100:.2f}% | "
                f"CV RMSE: {result_dto.tuned_cross_validation_metrics['mean_rmse']:.4f})",
                flush=True
            )

        return OptimizationRegistry(
            hpo_results=hpo_results,
            tuned_models=tuned_models,
            default_models=default_models,
            default_cv_metrics=default_cv_metrics,
            tuned_cv_metrics=tuned_cv_metrics,
            best_hyperparameters=best_hyperparameters
        )