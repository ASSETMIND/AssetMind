from dataclasses import dataclass
import math
import time
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple, Type
import numpy as np
import optuna
import pandas as pd

from src.model.dataset.walk_forward_splitter import WalkForwardSplitter
from src.model.evaluation import metrics
from src.model.evaluation.composite_score import Weights, get_trial_score

# Optuna 내부 로그 레벨 조정 (WARNING 이상만 출력)
optuna.logging.set_verbosity(optuna.logging.WARNING)
warnings.filterwarnings("ignore")


@dataclass
class OptimizationResult:
    """단일 모델의 하이퍼파라미터 최적화 수행 결과 및 감사 메타데이터를 보관하는 데이터 전송 객체(DTO)."""
    algorithm_name: str
    tuned_model: Any
    default_model: Any
    best_hyperparameters: Dict[str, Any]
    default_cross_validation_metrics: Dict[str, float]
    tuned_cross_validation_metrics: Dict[str, float]
    composite_optimization_score: float
    total_search_time_seconds: float
    trials_executed: int
    boundary_audit_dataframe: pd.DataFrame
    study: optuna.Study

    @property
    def has_boundary_hits(self) -> bool:
        """경계선에 도달한 파라미터의 존재 여부를 반환합니다."""
        return not self.boundary_audit_dataframe.empty

    def to_summary_dictionary(self) -> Dict[str, Any]:
        """주피터 노트북 정산 대시보드 출력을 위한 요약 딕셔너리를 생성합니다.

        Returns:
            Dict[str, Any]: 대시보드 렌더링용 포맷팅 딕셔너리.
        """
        formatted_parameters = ", ".join([
            f"{key}={value:.4f}" if isinstance(value, float) else f"{key}={value}"
            for key, value in self.best_hyperparameters.items()
            if key != "random_state"
        ])

        return {
            "알고리즘 (Algorithm)": self.algorithm_name,
            "탐색 횟수 (Trials)": f"{self.trials_executed} 회",
            "CV 평균 MDA": f"{self.tuned_cross_validation_metrics.get('mean_mda', 0.0) * 100.0:.2f}%",
            "CV 평균 Rank IC": f"{self.tuned_cross_validation_metrics.get('mean_rank_ic', 0.0):.4f}",
            "CV 평균 ICIR": f"{self.tuned_cross_validation_metrics.get('mean_icir', 0.0):.2f}",
            "CV 평균 Sharpe": f"{self.tuned_cross_validation_metrics.get('mean_sharpe', 0.0):.2f}",
            "CV 평균 Sortino": f"{self.tuned_cross_validation_metrics.get('mean_sortino', 0.0):.2f}",
            "CV 평균 MDD": f"{self.tuned_cross_validation_metrics.get('mean_mdd', 0.0) * 100.0:.2f}%",
            "CV 평균 t-stat": f"{self.tuned_cross_validation_metrics.get('mean_tstat', 0.0):.2f}",
            "CV 평균 RMSE": f"{self.tuned_cross_validation_metrics.get('mean_rmse', 0.0):.6f}",
            "CV 평균 MAE": f"{self.tuned_cross_validation_metrics.get('mean_mae', 0.0):.6f}",
            "복합 점수 (Composite)": f"{self.composite_optimization_score:.4f}",
            "최적 파라미터 (Best Parameters)": formatted_parameters,
            "소요 시간 (Search Time)": f"{self.total_search_time_seconds:.2f}s"
        }

class TimeSeriesOptimizer:
    """시계열 Walk-Forward 교차검증 기반 하이퍼파라미터 최적화 및 진단 클래스."""

    def __init__(
        self,
        splitter: WalkForwardSplitter,
        weights: Optional[Weights] = None,
        patience: int = 20,
        min_trials: int = 15,
        max_trials: int = 80,
        random_seed: int = 42
    ) -> None:
        """TimeSeriesOptimizer 인스턴스를 초기화합니다.

        Args:
            splitter (WalkForwardSplitter): 시계열 Walk-Forward CV 분할기 인스턴스.
            weights (Optional[Weights], optional): 4대 계층 가중치 설정. 기본값 None (기본 가중치 적용).
            patience (int, optional): 최고 점수 미갱신 시 조기 종료할 연속 Trial 수. 기본값 20.
            min_trials (int, optional): 조기 종료가 작동하기 전 보장할 최소 Trial 수. 기본값 15.
            max_trials (int, optional): 단일 최적화 세션당 최대 Trial 상한선. 기본값 80.
            random_seed (int, optional): 난수 재현성을 위한 시드 번호. 기본값 42.
        """
        self.splitter: WalkForwardSplitter = splitter
        self.weights: Weights = weights if weights is not None else Weights()
        self.patience: int = patience
        self.min_trials: int = min_trials
        self.max_trials: int = max_trials
        self.random_seed: int = random_seed

    def fit(
        self,
        algorithm_name: str,
        model_class: Type[Any],
        default_hyperparameters: Dict[str, Any],
        search_space: Dict[str, Any],
        feature_matrix: pd.DataFrame,
        target_series: pd.Series
    ) -> OptimizationResult:
        """외부에서 주입된 탐색 공간을 바탕으로 Walk-Forward HPO 및 단순 경계 진단, 80% Full Refit을 수행합니다.

        Args:
            algorithm_name (str): 알고리즘 식별 명칭.
            model_class (Type[Any]): AbstractRegressor를 상속받은 모델 클래스.
            default_hyperparameters (Dict[str, Any]): 비교 대조용 기본 파라미터 세트.
            search_space (Dict[str, Any]): 해당 모델의 탐색 공간 명세.
            feature_matrix (pd.DataFrame): 80% 학습 데이터 피처 행렬 (X_train).
            target_series (pd.Series): 80% 학습 데이터 타겟 벡터 (y_train).

        Returns:
            OptimizationResult: 최적화 완료 모델, 파라미터, 감사표, Study가 패키징된 DTO.
        """
        optimization_start_time: float = time.perf_counter()

        target_standard_deviation: float = float(target_series.std())
        if target_standard_deviation == 0.0 or math.isnan(target_standard_deviation):
            target_standard_deviation = 1.0

        # 1. Default 대조군 모델 Walk-Forward CV 평가 및 80% 피팅
        default_cross_validation_metrics = self._evaluate_cross_validation(
            model_class=model_class,
            hyperparameters=default_hyperparameters,
            feature_matrix=feature_matrix,
            target_series=target_series
        )
        default_model = model_class(**default_hyperparameters)
        default_model.fit(X_train=feature_matrix, y_train=target_series)

        # 2. 주입된 Search Space 기반 Optuna 베이지안 최적화 실행
        study, trials_executed = self._optimize_study(
            model_class=model_class,
            search_space=search_space,
            feature_matrix=feature_matrix,
            target_series=target_series,
            target_standard_deviation=target_standard_deviation,
            max_trials=self.max_trials
        )

        best_hyperparameters = dict(study.best_params)
        best_hyperparameters["random_state"] = self.random_seed

        # 3. 최적 파라미터와 Search Space의 순수 수치 경계 비교 감사표 사출
        boundary_audit_dataframe = self._audit_search_space_boundaries(
            algorithm_name=algorithm_name,
            best_parameters=best_hyperparameters,
            search_space=search_space
        )

        # 4. 최적 Trial 다차원 메트릭 추출
        best_attrs = study.best_trial.user_attrs
        best_composite_score = float(study.best_value)

        tuned_cross_validation_metrics = {
            "mean_mda": float(best_attrs.get("mean_mda", 0.0)),
            "mean_rank_ic": float(best_attrs.get("mean_rank_ic", 0.0)),
            "mean_icir": float(best_attrs.get("mean_icir", 0.0)),
            "mean_sharpe": float(best_attrs.get("mean_sharpe", 0.0)),
            "mean_sortino": float(best_attrs.get("mean_sortino", 0.0)),
            "mean_mdd": float(best_attrs.get("mean_mdd", 0.0)),
            "mean_tstat": float(best_attrs.get("mean_tstat", 0.0)),
            "mean_pval": float(best_attrs.get("mean_pval", 1.0)),
            "mean_rmse": float(best_attrs.get("mean_rmse", 0.0)),
            "mean_mae": float(best_attrs.get("mean_mae", 0.0)),
            "composite_score": best_composite_score
        }

        # 5. 최적 파라미터 기반 80% Full Train 전체 데이터 재학습 (Full Refit)
        tuned_model = model_class(**best_hyperparameters)
        tuned_model.fit(X_train=feature_matrix, y_train=target_series)

        total_search_time_seconds: float = time.perf_counter() - optimization_start_time

        return OptimizationResult(
            algorithm_name=algorithm_name,
            tuned_model=tuned_model,
            default_model=default_model,
            best_hyperparameters=best_hyperparameters,
            default_cross_validation_metrics=default_cross_validation_metrics,
            tuned_cross_validation_metrics=tuned_cross_validation_metrics,
            composite_optimization_score=best_composite_score,
            total_search_time_seconds=total_search_time_seconds,
            trials_executed=trials_executed,
            boundary_audit_dataframe=boundary_audit_dataframe,
            study=study
        )

    def _optimize_study(
        self,
        model_class: Type[Any],
        search_space: Dict[str, Any],
        feature_matrix: pd.DataFrame,
        target_series: pd.Series,
        target_standard_deviation: float,
        max_trials: int
    ) -> Tuple[optuna.Study, int]:
        """Optuna Study를 생성하고 조기 종료 조건 하에 베이지안 HPO를 집행합니다."""
        study_sampler = optuna.samplers.TPESampler(seed=self.random_seed)
        study = optuna.create_study(direction="maximize", sampler=study_sampler)
        trials_counter: List[int] = [0]

        def objective_function(trial: optuna.Trial) -> float:
            trials_counter[0] += 1
            parameters = self._sample_parameters(
                trial=trial,
                search_space=search_space
            )
            cv_metrics = self._evaluate_cross_validation(
                model_class=model_class,
                hyperparameters=parameters,
                feature_matrix=feature_matrix,
                target_series=target_series
            )
            # [설계 의도] Trial 감사 추적을 위해 10대 Fold 평균 메트릭 전수 기록
            for metric_key, metric_val in cv_metrics.items():
                trial.set_user_attr(metric_key, metric_val)

            # [설계 의도] composite_score.get_trial_score 단일 진실 공급원을 통한 목적함수 스칼라 산출
            trial_score = get_trial_score(
                metrics=cv_metrics,
                weights=self.weights,
                target_std=target_standard_deviation
            )
            return trial_score

        early_stopping_callback = self._create_early_stopping_callback(
            patience=self.patience,
            min_trials=self.min_trials
        )

        study.optimize(
            objective_function,
            n_trials=max_trials,
            callbacks=[early_stopping_callback],
            timeout=None
        )

        return study, trials_counter[0]

    def _evaluate_cross_validation(
        self,
        model_class: Type[Any],
        hyperparameters: Dict[str, Any],
        feature_matrix: pd.DataFrame,
        target_series: pd.Series
    ) -> Dict[str, float]:
        """확장 윈도우 Purged Walk-Forward CV를 순회하며 metrics.py 기반 다차원 평균 성능 지표를 산출합니다."""
        fold_mda: List[float] = []
        fold_rmse: List[float] = []
        fold_mae: List[float] = []
        fold_rank_ic: List[float] = []
        fold_icir: List[float] = []
        fold_sharpe: List[float] = []
        fold_sortino: List[float] = []
        fold_mdd: List[float] = []
        fold_tstat: List[float] = []
        fold_pval: List[float] = []

        for X_train_fold, y_train_fold, X_val_fold, y_val_fold in self.splitter.split_walk_forward(
            X=feature_matrix,
            y=target_series
        ):
            model_instance = model_class(**hyperparameters)
            model_instance.fit(X_train=X_train_fold, y_train=y_train_fold)

            preds = model_instance.predict(X_test=X_val_fold)
            y_val_arr = y_val_fold.to_numpy(dtype=np.float64).flatten()
            y_pred_arr = np.array(preds, dtype=np.float64).flatten()

            nw_t, nw_p = metrics.newey_west_tstat(y_val_arr, y_pred_arr)

            fold_mda.append(metrics.mda(y_val_arr, y_pred_arr))
            fold_rmse.append(metrics.rmse(y_val_arr, y_pred_arr))
            fold_mae.append(metrics.mae(y_val_arr, y_pred_arr))
            fold_rank_ic.append(metrics.rank_ic(y_val_arr, y_pred_arr))
            fold_icir.append(metrics.icir(y_val_arr, y_pred_arr, window_size=20))
            fold_sharpe.append(metrics.signal_sharpe(y_val_arr, y_pred_arr))
            fold_sortino.append(metrics.sortino_ratio(y_val_arr, y_pred_arr))
            fold_mdd.append(metrics.mdd(y_val_arr, y_pred_arr))
            fold_tstat.append(nw_t)
            fold_pval.append(nw_p)

        return {
            "mean_mda": float(np.mean(fold_mda)),
            "mean_rank_ic": float(np.mean(fold_rank_ic)),
            "mean_icir": float(np.mean(fold_icir)),
            "mean_sharpe": float(np.mean(fold_sharpe)),
            "mean_sortino": float(np.mean(fold_sortino)),
            "mean_mdd": float(np.mean(fold_mdd)),
            "mean_tstat": float(np.mean(fold_tstat)),
            "mean_pval": float(np.mean(fold_pval)),
            "mean_rmse": float(np.mean(fold_rmse)),
            "mean_mae": float(np.mean(fold_mae))
        }

    def _create_early_stopping_callback(
        self,
        patience: int,
        min_trials: int
    ) -> Callable[[optuna.Study, optuna.trial.FrozenTrial], None]:
        """Optuna 최고 점수가 N회 동안 갱신되지 않을 경우 탐색을 중단시키는 콜백 함수를 생성합니다."""
        best_score_holder: List[Optional[float]] = [None]
        no_improvement_count_holder: List[int] = [0]

        def callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
            if trial.state != optuna.trial.TrialState.COMPLETE:
                return

            current_value = trial.value
            if current_value is None:
                return

            if best_score_holder[0] is None or current_value > best_score_holder[0] + 1e-5:
                best_score_holder[0] = current_value
                no_improvement_count_holder[0] = 0
            else:
                no_improvement_count_holder[0] += 1

            if len(study.trials) >= min_trials and no_improvement_count_holder[0] >= patience:
                study.stop()

        return callback

    def _sample_parameters(self, trial: optuna.Trial, search_space: Dict[str, Any]) -> Dict[str, Any]:
        """외부 명세(search_space)에 따라 Optuna Trial에서 하이퍼파라미터를 동적 샘플링합니다."""
        sampled: Dict[str, Any] = {"random_state": self.random_seed}
        for param_name, config in search_space.items():
            param_type = config["type"]
            if param_type == "categorical":
                sampled[param_name] = trial.suggest_categorical(param_name, config["choices"])
            elif param_type == "int":
                sampled[param_name] = trial.suggest_int(param_name, config["low"], config["high"], step=config.get("step", 1))
            elif param_type == "float":
                sampled[param_name] = trial.suggest_float(
                    param_name,
                    config["low"],
                    config["high"],
                    step=config.get("step"),
                    log=config.get("log", False)
                )
        return sampled

    def _audit_search_space_boundaries(
        self,
        algorithm_name: str,
        best_parameters: Dict[str, Any],
        search_space: Dict[str, Any]
    ) -> pd.DataFrame:
        """최적 파라미터가 Search Space 끝점에 도달한 항목만 순수 수치 비교로 선별합니다.

        판정 수식:
        1. 이산형 / Step 변수: |value - bound| < 1e-6 (Exact Match)
        2. 연속형 로그 변수 (log=True): value <= low * 1.02 또는 value >= high * 0.98 (2% Log Ratio)
        3. 연속형 선형 변수 (log=False): (high - low) * 0.01 이내 접근 (1% Linear Span)

        Args:
            algorithm_name (str): 알고리즘 식별 명칭.
            best_parameters (Dict[str, Any]): 도출된 최적 하이퍼파라미터 세트.
            search_space (Dict[str, Any]): 주입된 탐색 공간 명세.

        Returns:
            pd.DataFrame: 경계 도달 파라미터 레코드 데이터프레임.
        """
        audit_records: List[Dict[str, str]] = []

        for param_name, config in search_space.items():
            param_type = config["type"]
            if param_type == "categorical" or param_name not in best_parameters:
                continue

            low: float = float(config["low"])
            high: float = float(config["high"])
            val: float = float(best_parameters[param_name])
            is_log: bool = config.get("log", False)
            has_step: bool = ("step" in config) or (param_type == "int")

            is_lower_hit: bool = False
            is_upper_hit: bool = False

            # [수리식 1] 이산형 / Step 변수 (Exact Match)
            if has_step:
                if abs(val - low) < 1e-6:
                    is_lower_hit = True
                elif abs(val - high) < 1e-6:
                    is_upper_hit = True

            # [수리식 2] 로그 스케일 변수 (2% Log Ratio)
            elif is_log:
                if val <= low * 1.02:
                    is_lower_hit = True
                elif val >= high * 0.98:
                    is_upper_hit = True

            # [수리식 3] 선형 실수 변수 (1% Linear Span)
            else:
                tolerance = (high - low) * 0.01
                if val <= low + tolerance:
                    is_lower_hit = True
                elif val >= high - tolerance:
                    is_upper_hit = True

            if is_lower_hit or is_upper_hit:
                boundary_status_str = "하한선 도달 (Min Hit)" if is_lower_hit else "상한선 도달 (Max Hit)"
                formatted_range_str = f"[{low} ~ {high}] ({'log' if is_log else ('step' if has_step else 'float')})"
                formatted_value_str = f"{val:.4f}" if isinstance(best_parameters[param_name], float) else str(best_parameters[param_name])

                audit_records.append({
                    "알고리즘 (Algorithm)": algorithm_name,
                    "파라미터 명칭": param_name,
                    "설정된 탐색 범위": formatted_range_str,
                    "선택된 최적값": formatted_value_str,
                    "경계 도달 상태": boundary_status_str
                })

        return pd.DataFrame(audit_records)