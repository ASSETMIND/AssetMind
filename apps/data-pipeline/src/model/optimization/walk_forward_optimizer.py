"""
단일 회귀 추정기 대상 시계열 Expanding Walk-Forward CV 기반 Optuna HPO 연산 코어 모듈.

[핵심 아키텍처 및 단일 책임]
1. AbstractMLRegressor 다형성 규격을 준수하는 임의의 모델에 대해 Expanding Window 시계열 교차검증을 집행합니다.
2. ModelEvaluator와의 일원화된 데이터 계약을 통해 10대 원자적 지표를 추출하고 복합 목적함수를 극대화합니다.
3. Search Space의 선언적 메타데이터를 기반으로 _get_parameters()를 통해 파라미터를 동적 샘플링합니다.
4. 최적 파라미터의 경계선(상/하한) 도달 여부를 5대 핵심 수치 컬럼으로 간소화하여 감사합니다.
"""

from dataclasses import dataclass
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type
import numpy as np
import optuna
from optuna.pruners import MedianPruner, NopPruner
from optuna.samplers import TPESampler
import pandas as pd
from scipy import stats

from src.model.core.base.abstract_ml_regressor import AbstractMLRegressor
from src.dataset.walk_forward_splitter import WalkForwardSplitter
from src.model.evaluation.composite_score import compute_layer_scores, get_trial_score
from src.model.evaluation.criteria import Weights
from src.model.evaluation.schema import EvaluationMetric
from src.model.evaluation.model_evaluator import ModelEvaluator


# ==============================================================================
# 단일 최적화 결과 캡슐화 불변 DTO (Data Transfer Object)
# ==============================================================================

@dataclass(frozen=True)
class SingleOptimizationResult:
    """단일 모델 시계열 HPO 최적화 결과 및 수치 메타데이터를 캡슐화한 불변 DTO."""
    model_name: str
    best_params: Dict[str, Any]
    best_score: float
    default_score: float
    best_model: AbstractMLRegressor
    study: optuna.Study
    default_metrics: Dict[EvaluationMetric, float]
    tuned_metrics: Dict[EvaluationMetric, float]
    trial_history_df: pd.DataFrame
    boundary_audit_dataframe: pd.DataFrame
    has_boundary_hits: bool
    elapsed_seconds: float
    fold_stability_df: pd.DataFrame
    dsr: float

    @property
    def trials_executed(self) -> int:
        """유효 완료된 총 Trial 횟수를 단일 속성으로 사출하여 MLOps 로깅과의 결합도 완화"""
        return len([t for t in self.study.trials if t.value is not None])

    @property
    def total_search_time_seconds(self) -> float:
        """레거시 MLOps 트래커 호환을 위한 총 탐색 소요 시간(초) 프로퍼티"""
        return self.elapsed_seconds


# ==============================================================================
# 시계열 HPO 코어 연산 엔진 클래스 (Main Class)
# ==============================================================================

class WalkForwardOptimizer:
    """단일 회귀 모델 클래스 대상 Expanding Walk-Forward HPO 집행 엔진."""

    def __init__(
        self,
        model_class: Type[AbstractMLRegressor],
        search_space: Dict[str, Dict[str, Any]],
        splitter: WalkForwardSplitter,
        weights: Optional[Weights] = None,
        evaluator: Optional[ModelEvaluator] = None,
        model_name: Optional[str] = None,
        n_trials: int = 50,
        patience: Optional[int] = 20,
        random_state: int = 42,
        timeout: Optional[float] = None,
        n_jobs: int = 1,
        robustness_penalty_lambda: float = 0.5,
        # [설계 의도] 시장 레짐 이질성(폭락/횡보/상승)으로 인한 우수 모델 오탈락 방지를 위해 Pruning 기본 비활성화
        pruning: bool = False,
    ) -> None:
        """WalkForwardOptimizer 인스턴스를 초기화합니다.

        Args:
            model_class (Type[AbstractMLRegressor]): 최적화할 모델 클래스 생성자.
            search_space (Dict[str, Dict[str, Any]]): 모델별 파라미터 탐색 공간 명세.
            splitter (WalkForwardSplitter): Expanding Window 시계열 교차검증 분할기.
            weights (Optional[Weights]): 2대 핵심 계층(ML, Factor) 복합 스코어링 가중치 DTO.
            evaluator (Optional[ModelEvaluator]): 10대 지표 전담 산출 평가 엔진.
            model_name (Optional[str]): 모델 식별 명칭 (None 시 클래스명 자동 추론).
            n_trials (int): Optuna 시도 횟수 (기본값: 50).
            patience (Optional[int]): Optuna 조기 종료 기준 연속 Trial 수 (기본값: 20).
            random_state (int): 난수 시드값 (기본값: 42).
            timeout (Optional[float]): 최적화 최대 허용 시간(초). 기본값은 None.
            n_jobs (int): Optuna 병렬 실행 워커 수 (기본값: 1).
            robustness_penalty_lambda (float): 로버스트성 페널티 하이퍼파라미터 (기본값: 0.1).
            pruning (bool): Optuna Pruning 기능 사용 여부 (기본값: True).
        """
        self.model_class: Type[AbstractMLRegressor] = model_class
        self.search_space: Dict[str, Dict[str, Any]] = search_space
        self.splitter: WalkForwardSplitter = splitter
        self.weights: Weights = weights or Weights()
        self.evaluator: ModelEvaluator = evaluator or ModelEvaluator(weights=self.weights)
        self.model_name: str = model_name or getattr(model_class, "model_name", model_class.__name__)
        self.n_trials: int = n_trials
        # [설계 의도] 파라미터 차원(D) 대비 성급한 조기 종료를 방지하기 위해 차원 비례 동적 Patience 적용
        param_dim: int = len(self.search_space)
        self.patience: Optional[int] = (
            max(25, 3 * param_dim) if (patience is not None and patience > 0) else patience
        )
        self.random_state: int = random_state
        self.timeout: Optional[float] = timeout
        self.n_jobs: int = n_jobs
        self.robustness_penalty_lambda: float = robustness_penalty_lambda
        self.pruning: bool = pruning

    def optimize(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> SingleOptimizationResult:
        """전체 학습 데이터셋을 바탕으로 Default 베이스라인 측정 및 Walk-Forward HPO를 완결합니다.

        Args:
            X_train (pd.DataFrame): HPO 학습용 전체 피처 데이터프레임.
            y_train (pd.Series): HPO 학습용 전체 정답 타겟 시리즈.

        Returns:
            SingleOptimizationResult: 최적화 수치 메타데이터가 캡슐화된 불변 DTO.

        Raises:
            ValueError: 입력 데이터셋이 비어 있거나 결손된 경우 발생 (Fail-Fast).
        """
        if X_train is None or y_train is None or X_train.empty or y_train.empty:
            raise ValueError(f"[{self.model_name}] 최적화 대상 데이터셋(X_train 또는 y_train)이 비어 있습니다.")

        start_time: float = time.perf_counter()

        # 스케일 정규화 기준 분모(target_std)를 시작 시점에 1회만 연산하여 오버헤드 박멸
        finite_targets = y_train.to_numpy(dtype=np.float64).flatten()
        finite_targets = finite_targets[np.isfinite(finite_targets)]
        target_std: float = float(np.std(finite_targets, ddof=1)) if len(finite_targets) > 1 else 1.0
        if target_std <= 0.0 or not np.isfinite(target_std):
            target_std = 1.0

        # 1. Default 베이스라인 사전 Walk-Forward CV 평가 (비교 기준선 확립)
        default_score, default_metrics = self._evaluate_cv_folds(
            model_params={},
            X_train=X_train,
            y_train=y_train,
            target_std=target_std,
        )

        # 2. Optuna HPO 집행 (다변량 TPE Sampler 및 MedianPruner 구성)
        sampler = TPESampler(
            seed=self.random_state,
            multivariate=True,
            group=True,
        )
        pruner = (
            MedianPruner(n_startup_trials=5, n_warmup_steps=1)
            if self.pruning
            else NopPruner()
        )
        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
            pruner=pruner,
            study_name=f"{self.model_name}_HPO",
        )

        # 기본 모델 파라미터 세트 웜스타트(enqueue_trial) 주입
        try:
            default_estimator = self.model_class(random_state=self.random_state)
            raw_params = default_estimator.get_params()
            warmstart_params: Dict[str, Any] = {}

            for param_name, spec in self.search_space.items():
                if param_name not in raw_params:
                    continue

                val = raw_params[param_name]
                if val is None:
                    continue

                param_type: str = spec.get("type", "float")

                if param_type == "categorical":
                    if val in spec.get("choices", []):
                        warmstart_params[param_name] = val
                elif param_type == "int":
                    try:
                        int_val = int(val)
                        low = spec["low"]
                        high = spec["high"]
                        warmstart_params[param_name] = int(np.clip(int_val, low, high))
                    except (ValueError, TypeError):
                        continue
                elif param_type == "float":
                    try:
                        flt_val = float(val)
                        low = float(spec["low"])
                        high = float(spec["high"])
                        is_log = spec.get("log", False)
                        # log=True인 파라미터가 0.0 이하일 경우 탐색 하한(low)으로 클리핑하여 발산 방어
                        if is_log and flt_val <= 0.0:
                            flt_val = low
                        warmstart_params[param_name] = float(np.clip(flt_val, low, high))
                    except (ValueError, TypeError):
                        continue

            if warmstart_params:
                study.enqueue_trial(warmstart_params)
        except Exception:
            pass

        objective_fn = self._create_objective(
            X_train=X_train,
            y_train=y_train,
            target_std=target_std,
        )
        # patience > 0 일 경우 조기 종료 감시 콜백을 등록하여 고속 탈출 집행
        callbacks = [_EarlyStoppingCallback(patience=self.patience)] if self.patience > 0 else None
        
        study.optimize(
            objective_fn,
            n_trials=self.n_trials,
            timeout=self.timeout,
            n_jobs=self.n_jobs,
            show_progress_bar=False,
            callbacks=callbacks,
        )

        elapsed_seconds: float = time.perf_counter() - start_time

        # 3. 최적 파라미터 바인딩 및 5-Fold CV 상세 평가 선행 집행
        best_params: Dict[str, Any] = study.best_params.copy()
        best_params["random_state"] = self.random_state
        best_score: float = float(study.best_value)

        # [설계 의도] Full Refit 이전에 5-Fold 상세 평가를 수행하여 Fold별 최적 반복수(best_iteration) 수집
        _, _, best_fold_details, fold_best_iterations = self._evaluate_cv_folds_detailed(
            model_params=best_params,
            X_train=X_train,
            y_train=y_train,
            target_std=target_std,
        )

        # 4. CV 최적 반복수(Best Iteration) 주입 및 전체 학습셋 대상 최종 Refit (개선 2 적용)
        refit_params = best_params.copy()
        if fold_best_iterations:
            optimal_n_estimators = int(np.round(np.mean(fold_best_iterations)))
            refit_params["n_estimators"] = max(1, optimal_n_estimators)
            best_params["n_estimators"] = refit_params["n_estimators"]

        # [설계 의도] Full Refit 시에는 검증 세트가 없으므로 조기 종료 파라미터 완전 제거
        refit_params.pop("early_stopping_rounds", None)
        best_params.pop("early_stopping_rounds", None)

        n_train_samples = len(X_train)
        train_weights = np.exp((np.log(2.0) / 1008.0) * (np.arange(n_train_samples) - (n_train_samples - 1)))
        train_weights = train_weights / np.mean(train_weights)

        best_model: AbstractMLRegressor = self.model_class(**refit_params)
        best_model.fit(X_train=X_train, y_train=y_train, sample_weight=train_weights)

        # [설계 의도] Out-of-Sample 평가 시 미래 정보 누수(Look-ahead Bias)를 차단하기 위해 Train 예측 표준편차를 동결 저장
        in_sample_predictions = best_model.predict(X_test=X_train)
        best_model.pred_std_ = float(np.std(in_sample_predictions, ddof=1)) if len(in_sample_predictions) > 1 else 1.0

        # Best Trial에 캐싱된 10대 지표 맵 추출
        raw_tuned_metrics = study.best_trial.user_attrs.get("metrics", {})
        tuned_metrics: Dict[EvaluationMetric, float] = {
            EvaluationMetric(k): v for k, v in raw_tuned_metrics.items()
        }

        # 5. 경계선 감사, 이력 정형화 및 DSR 감사표 생성
        boundary_audit_df, has_hits = self._audit_boundaries(
            best_params=best_params,
            search_space=self.search_space,
        )
        trial_history_df = self._build_trial_history_df(study=study)

        # DSR 연산 (실제 Sharpe가 도출된 검증 윈도우 표본 수 204 Rows 주입)
        best_sharpe: float = tuned_metrics.get(EvaluationMetric.SIGNAL_SHARPE, 0.0)
        val_sample_size: int = max(20, int(len(y_train) * (1.0 - self.splitter.min_train_ratio) / self.splitter.n_splits))
        dsr_val: float = self._calculate_dsr(
            study=study,
            best_sharpe=best_sharpe,
            eval_horizon=val_sample_size,
            y_train=y_train,
        )

        fold_stability_df = self._build_fold_stability_df(
            fold_details=best_fold_details,
            dsr=dsr_val,
        )

        return SingleOptimizationResult(
            model_name=self.model_name,
            best_params=best_params,
            best_score=best_score,
            default_score=default_score,
            best_model=best_model,
            study=study,
            default_metrics=default_metrics,
            tuned_metrics=tuned_metrics,
            trial_history_df=trial_history_df,
            boundary_audit_dataframe=boundary_audit_df,
            has_boundary_hits=has_hits,
            elapsed_seconds=elapsed_seconds,
            fold_stability_df=fold_stability_df,
            dsr=dsr_val,
        )


    # --------------------------------------------------------------------------
    # 내부 최적화 서브루틴 (Private Helpers)
    # --------------------------------------------------------------------------
    def _create_objective(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        target_std: float,
    ) -> Callable[[optuna.Trial], float]:
        """Optuna Trial을 수신하는 시계열 교차검증 목적 함수 클로저를 생성합니다."""
        def objective(trial: optuna.Trial) -> float:
            model_params: Dict[str, Any] = self._get_parameters(
                trial=trial,
                search_space=self.search_space,
            )
            trial_score, fold_metrics = self._evaluate_cv_folds(
                model_params=model_params,
                X_train=X_train,
                y_train=y_train,
                target_std=target_std,
                trial=trial,
            )
            trial.set_user_attr("metrics", {m.value: v for m, v in fold_metrics.items()})
            return trial_score

        return objective

    def _get_parameters(
        self,
        trial: optuna.Trial,
        search_space: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """선언적 Search Space 메타데이터를 파싱하여 Optuna Trial에 최적화된 파라미터를 제안합니다."""
        suggested_params: Dict[str, Any] = {}

        for param_name, spec in search_space.items():
            # 선언적 조건부 파라미터(Conditional Search Space) 분기 평가
            if "depends_on" in spec:
                dep_param: str = spec["depends_on"]["param"]
                dep_value: Any = spec["depends_on"]["value"]
                if suggested_params.get(dep_param) != dep_value:
                    continue

            param_type: str = spec.get("type", "float")

            if param_type == "categorical":
                suggested_params[param_name] = trial.suggest_categorical(
                    name=param_name,
                    choices=spec["choices"],
                )
            elif param_type == "int":
                step = spec.get("step", 1)
                log = spec.get("log", False)
                if step > 1:
                    suggested_params[param_name] = trial.suggest_int(
                        name=param_name, low=spec["low"], high=spec["high"], step=step
                    )
                else:
                    suggested_params[param_name] = trial.suggest_int(
                        name=param_name, low=spec["low"], high=spec["high"], log=log
                    )
            elif param_type == "float":
                step = spec.get("step")
                log = spec.get("log", False)
                if step is not None:
                    suggested_params[param_name] = trial.suggest_float(
                        name=param_name, low=spec["low"], high=spec["high"], step=step
                    )
                else:
                    suggested_params[param_name] = trial.suggest_float(
                        name=param_name, low=spec["low"], high=spec["high"], log=log
                    )
            else:
                raise ValueError(f"[{self.model_name}] 지원하지 않는 Search Space 타입: {param_type}")

        return suggested_params

    def _evaluate_cv_folds(
        self,
        model_params: Dict[str, Any],
        X_train: pd.DataFrame,
        y_train: pd.Series,
        target_std: float,
        trial: Optional[optuna.Trial] = None,
    ) -> Tuple[float, Dict[EvaluationMetric, float]]:
        """Walk-Forward CV 5개 Fold를 순회하며 ModelEvaluator에 지표 연산을 위임합니다."""
        fold_metrics_collection: List[Dict[EvaluationMetric, float]] = []
        fold_scores: List[float] = []

        # WalkForwardSplitter 시계열 순회 (Expanding Window & Purged Embargo 적용)
        instantiation_params = model_params.copy()
        instantiation_params.setdefault("random_state", self.random_state)

        fold_rirs: List[float] = []

        for fold_idx, (X_tr_fold, y_tr_fold, X_val_fold, y_val_fold) in enumerate(
            self.splitter.split_walk_forward(X=X_train, y=y_train)
        ):
            n_samples = len(X_tr_fold)
            fold_weights = np.exp((np.log(2.0) / 1008.0) * (np.arange(n_samples) - (n_samples - 1)))
            fold_weights = fold_weights / np.mean(fold_weights)

            fold_model: AbstractMLRegressor = self.model_class(**instantiation_params)
            fold_model.fit(X_train=X_tr_fold, y_train=y_tr_fold, sample_weight=fold_weights)

            val_predictions: pd.Series = fold_model.predict(X_test=X_val_fold)

            # Layer 4의 단일 진실 공급원인 ModelEvaluator에 지표 연산 위임 (중복 연산 배제)
            eval_result = self.evaluator.evaluate_predictions(
                y_true=y_val_fold,
                y_pred=val_predictions,
                model_name=self.model_name,
                target_std=target_std,
            )
            fold_metrics_collection.append(eval_result.metrics)
            fold_scores.append(eval_result.composite_score)

            # [설계 의도] 타깃 변동성(target_std)을 보정한 NRMSE 비율로 전환하고, 
            # 트리 모델의 과적합 수렴(Train 오차 ≈ 0)에 따른 분모 붕괴를 방어하기 위해 NRMSE 하한선(0.5) 강제
            tr_predictions = fold_model.predict(X_test=X_tr_fold)
            tr_rmse = float(np.sqrt(np.mean((y_tr_fold.to_numpy() - tr_predictions.to_numpy()) ** 2)))
            val_rmse = eval_result.metrics.get(EvaluationMetric.RMSE, target_std)

            tr_std = float(y_tr_fold.std(ddof=1)) if len(y_tr_fold) > 1 and y_tr_fold.std(ddof=1) > 0 else 1.0
            val_std = float(y_val_fold.std(ddof=1)) if len(y_val_fold) > 1 and y_val_fold.std(ddof=1) > 0 else 1.0

            tr_nrmse = tr_rmse / tr_std
            val_nrmse = val_rmse / val_std
            fold_rirs.append(val_nrmse / max(0.5, tr_nrmse))

            # Fold 단위 Intra-Trial 가지치기(Pruning) 집행
            if trial is not None and self.pruning:
                current_running_mean: float = float(np.mean(fold_scores))
                trial.report(current_running_mean, step=fold_idx)
                if trial.should_prune():
                    raise optuna.TrialPruned()

        if not fold_metrics_collection:
            return 0.0, {}

        # 5개 Fold의 10대 지표 평균 집계 (Factor p-val은 t-stat 기반 사후 산출)
        averaged_metrics: Dict[EvaluationMetric, float] = {}
        for metric_enum in EvaluationMetric:
            if metric_enum == EvaluationMetric.FACTOR_P_VAL:
                continue
            values = [f_map[metric_enum] for f_map in fold_metrics_collection if metric_enum in f_map]
            averaged_metrics[metric_enum] = float(np.mean(values)) if values else 0.0

        # 비선형 통계량인 p-val의 산술평균 왜곡 방지: 집계된 t-stat으로부터 이론적 양측 p-value 산출
        avg_t_stat = averaged_metrics.get(EvaluationMetric.FACTOR_T_STAT, 0.0)
        averaged_metrics[EvaluationMetric.FACTOR_P_VAL] = float(2.0 * stats.norm.sf(np.abs(avg_t_stat)))

        # [설계 의도] 옌센 부등식 왜곡 방어: 비선형 지표 평균 스코어 대신 각 Fold 실현 스코어의 산술평균을 기준선(base_score)으로 일원화
        fold_scores_arr = np.array(fold_scores, dtype=np.float64)
        base_score: float = float(np.mean(fold_scores_arr)) if len(fold_scores_arr) > 0 else 0.0

        # [소르티노형 하방 편차 페널티] 실현 평균 점수(base_score) 이하로 붕괴된 Fold의 손실 변동성만 선택적 감점
        downside_diff = np.minimum(0.0, fold_scores_arr - base_score)
        downside_std: float = float(np.sqrt(np.mean(downside_diff ** 2)))

        # [설계 의도] OverfitGate 평가 기준(max_rir = 1.20)과 임계치를 일원화하여,
        # Fold 평균 RIR이 1.20을 초과하여 일반화 오차가 팽창할 때만 초과분에 비례해 목적함수 감점
        mean_rir: float = float(np.mean(fold_rirs)) if fold_rirs else 1.0
        rir_penalty: float = max(0.0, (mean_rir - 1.20) * 0.5)

        # [설계 의도] Tier 3/4 평가 게이트(MDD <= 0.30, t-stat >= 1.96) 실격을 사전 방어하는 소프트 배리어 페널티 연동
        # 1. MDD 한도(30%) 초과 시 초과 낙폭에 비례하여 목적함수 감점 (최대 낙폭 억제 유도)
        avg_mdd: float = averaged_metrics.get(EvaluationMetric.MDD, 0.0)
        mdd_penalty: float = max(0.0, avg_mdd - 0.30) * 1.0

        # 2. Factor t-stat 유의수준(1.96, p<0.05) 미달 시 정규화 결손율에 비례하여 감점 (가짜 알파 차단 유도)
        avg_t_stat: float = averaged_metrics.get(EvaluationMetric.FACTOR_T_STAT, 0.0)
        tstat_penalty: float = max(0.0, (1.96 - avg_t_stat) / 1.96) * 0.30

        total_penalty: float = min(0.50, rir_penalty + mdd_penalty + tstat_penalty)

        robust_trial_score: float = (
            base_score
            - (self.robustness_penalty_lambda * downside_std)
            - total_penalty
        )

        return float(robust_trial_score), averaged_metrics

    def _audit_boundaries(
        self,
        best_params: Dict[str, Any],
        search_space: Dict[str, Dict[str, Any]],
    ) -> Tuple[pd.DataFrame, bool]:
        """간소화된 5대 정예 컬럼 기반 파라미터 경계선 감사표를 생성합니다."""
        audit_records: List[Dict[str, Any]] = []

        for param_name, spec in search_space.items():
            if param_name not in best_params or spec.get("type") == "categorical":
                continue

            optimal_val = best_params[param_name]
            low = spec.get("low")
            high = spec.get("high")

            is_lower_hit = low is not None and (
                optimal_val <= low or np.isclose(float(optimal_val), float(low), atol=1e-7)
            )
            is_upper_hit = high is not None and (
                optimal_val >= high or np.isclose(float(optimal_val), float(high), atol=1e-7)
            )

            if is_lower_hit or is_upper_hit:
                audit_records.append({
                    "알고리즘 (Algorithm)": self.model_name,
                    "파라미터 명칭": param_name,
                    "탐색 하한 (Low)": low,
                    "탐색 상한 (High)": high,
                    "최적 파라미터 값 (Optimal Value)": optimal_val,
                })

        columns = [
            "알고리즘 (Algorithm)",
            "파라미터 명칭",
            "탐색 하한 (Low)",
            "탐색 상한 (High)",
            "최적 파라미터 값 (Optimal Value)",
        ]
        has_hits: bool = len(audit_records) > 0
        audit_df = pd.DataFrame(audit_records) if has_hits else pd.DataFrame(columns=columns)

        return audit_df, has_hits

    def _build_trial_history_df(self, study: optuna.Study) -> pd.DataFrame:
        """전체 Trial 완료 이력을 추출하고 복합 스코어 기준 내림차순 랭킹표로 가공합니다."""
        records: List[Dict[str, Any]] = []

        for trial in study.trials:
            if trial.state != optuna.trial.TrialState.COMPLETE:
                continue

            row: Dict[str, Any] = {
                "Trial No": trial.number,
                "Composite Score": round(float(trial.value), 4),
            }
            row.update(trial.params)
            row["Duration (s)"] = round(trial.duration.total_seconds(), 2) if trial.duration else 0.0
            records.append(row)

        history_df = pd.DataFrame(records)
        if not history_df.empty:
            history_df.sort_values(by="Composite Score", ascending=False, inplace=True)
            history_df.reset_index(drop=True, inplace=True)
            history_df.index += 1
            history_df.index.name = "Rank"

        return history_df


    def _calculate_dsr(
        self,
        study: optuna.Study,
        best_sharpe: float,
        eval_horizon: Optional[int] = None,
        y_train: Optional[pd.Series] = None,
        annual_factor: float = 252.0 / 20.0,
    ) -> float:
        """Bailey & López de Prado(2014) 통계 이론에 기반하여 HPO 다중 시도 편향을 보정한 DSR을 산출합니다."""
        from scipy import stats
        sharpe_list = [
            float(t.user_attrs.get("metrics", {}).get(EvaluationMetric.SIGNAL_SHARPE.value, np.nan))
            for t in study.trials
            if t.state == optuna.trial.TrialState.COMPLETE and "metrics" in t.user_attrs
        ]
        valid_sharpes = [s for s in sharpe_list if np.isfinite(s)]
        n_trials = len(valid_sharpes)
        if n_trials < 5:
            return 1.0

        sharpe_arr = np.array(valid_sharpes, dtype=np.float64)
        var_trials = float(np.var(sharpe_arr, ddof=1))
        if var_trials <= 1e-8:
            return 1.0

        std_trials = float(np.sqrt(var_trials))

        # 1. Bailey & López de Prado(2014) 극값 이론: H0(True SR=0) 하 기대 최대 샤프 임계치 (연율화 단위)
        euler_mascheroni = 0.5772156649
        z_inv_1 = stats.norm.ppf(1.0 - 1.0 / n_trials)
        z_inv_2 = stats.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
        sr_star_annual = std_trials * ((1.0 - euler_mascheroni) * z_inv_1 + euler_mascheroni * z_inv_2)

        # 2. 관측 주기 단위(Non-annualized)로 통일 변환
        sqrt_factor = np.sqrt(max(1e-6, annual_factor))
        sr_obs = best_sharpe / sqrt_factor
        sr_star_obs = sr_star_annual / sqrt_factor

        # 3. 실현 검증 관측치 수(T) 및 타겟 수익률 비정규성 통계량(왜도/첨도) 추출
        t_samples = eval_horizon if eval_horizon is not None and eval_horizon > 2 else 204

        if y_train is not None and len(y_train) > 2:
            targets = y_train.to_numpy(dtype=np.float64).flatten()
            targets = targets[np.isfinite(targets)]
            skew = float(stats.skew(targets))
            kurt = float(stats.kurtosis(targets, fisher=False))
        else:
            skew = 0.0
            kurt = 3.0

        if t_samples < 2:
            return 1.0

        # 4. 점근 표준오차 분모 항 및 DSR 검정 통계량 산출
        denom = np.sqrt(max(1e-6, 1.0 - skew * sr_obs + ((kurt - 1.0) / 4.0) * (sr_obs ** 2)))
        z_stat = ((sr_obs - sr_star_obs) * np.sqrt(t_samples - 1)) / denom

        dsr_prob = float(stats.norm.cdf(z_stat))
        return float(np.clip(dsr_prob, 0.0, 1.0))

    def _build_fold_stability_df(
        self,
        fold_details: List[Dict[str, float]],
        dsr: float,
    ) -> pd.DataFrame:
        """5-Fold의 복합 스코어 및 2대 핵심 계층(ML, Factor) 분산 안정성을 정규화한 감사표를 생성합니다."""
        df_folds = pd.DataFrame(fold_details)
        records: List[Dict[str, Any]] = []

        # [설계 의도] 개편된 복합 스코어 규격에 맞춰 2대 신호 품질 계층(ML, Factor) 및 composite_score만 감사 집행
        for col in ["composite_score", "score_l1_ml", "score_l2_factor"]:
            if col not in df_folds.columns:
                continue

            vals = df_folds[col].values
            mean_v = float(np.mean(vals))
            std_v = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
            stability_idx = float(mean_v / std_v) if std_v > 1e-6 else np.inf

            display_name = "Composite Score" if col == "composite_score" else col.replace("score_", "").upper()
            row = {
                "Metric Dimension": display_name,
                "Fold 1": vals[0] if len(vals) > 0 else 0.0,
                "Fold 2": vals[1] if len(vals) > 1 else 0.0,
                "Fold 3": vals[2] if len(vals) > 2 else 0.0,
                "Fold 4": vals[3] if len(vals) > 3 else 0.0,
                "Fold 5": vals[4] if len(vals) > 4 else 0.0,
                "Mean (μ)": mean_v,
                "Std (σ)": std_v,
                "Stability Index (μ/σ)": stability_idx,
                "DSR": dsr if col == "composite_score" else np.nan,
            }
            records.append(row)

        return pd.DataFrame(records).set_index("Metric Dimension")

    def _evaluate_cv_folds_detailed(
        self,
        model_params: Dict[str, Any],
        X_train: pd.DataFrame,
        y_train: pd.Series,
        target_std: float,
    ) -> Tuple[float, Dict[EvaluationMetric, float], List[Dict[str, float]], List[int]]:
        """최적 파라미터를 대상으로 5개 Fold를 완전 순회하며 안정성 감사용 세부 점수 및 최적 반복수를 사출합니다."""
        fold_metrics_collection: List[Dict[EvaluationMetric, float]] = []
        fold_scores: List[float] = []
        fold_details: List[Dict[str, float]] = []
        fold_best_iterations: List[int] = []

        safe_std: float = target_std if (target_std > 0.0 and np.isfinite(target_std)) else 1.0

        instantiation_params = model_params.copy()
        instantiation_params.setdefault("random_state", self.random_state)
        # [설계 의도] 부스팅 모델의 경우 Fold 검증 세트를 활용해 과적합 직전 최적 반복수(best_iteration)를 탐색
        is_boosting = "XGBoost" in self.model_name
        if is_boosting and "early_stopping_rounds" not in instantiation_params:
            instantiation_params["early_stopping_rounds"] = 20

        for X_tr_fold, y_tr_fold, X_val_fold, y_val_fold in self.splitter.split_walk_forward(
            X=X_train, y=y_train
        ):
            n_samples = len(X_tr_fold)
            fold_weights = np.exp((np.log(2.0) / 1008.0) * (np.arange(n_samples) - (n_samples - 1)))
            fold_weights = fold_weights / np.mean(fold_weights)

            fold_model: AbstractMLRegressor = self.model_class(**instantiation_params)
            
            # [설계 의도] XGBoost 부스팅 모델에 한해 Fold 검증 세트를 전달하여 조기 종료 지점 기록
            if is_boosting:
                try:
                    fold_model.fit(
                        X_train=X_tr_fold,
                        y_train=y_tr_fold,
                        sample_weight=fold_weights,
                        eval_set=[(X_val_fold, y_val_fold)],
                        verbose=False,
                    )
                except TypeError:
                    fold_model.fit(X_train=X_tr_fold, y_train=y_tr_fold, sample_weight=fold_weights)
            else:
                fold_model.fit(X_train=X_tr_fold, y_train=y_tr_fold, sample_weight=fold_weights)

            # [설계 의도] 래퍼 객체 및 내부 원본 모델(_model, model 등) 전수 스캔하여 best_iteration 안전 추출
            inner_estimator = (
                getattr(fold_model, "_model", None)
                or getattr(fold_model, "model", None)
                or getattr(fold_model, "_estimator", None)
                or getattr(fold_model, "estimator", None)
                or fold_model
            )
            best_iter = (
                getattr(fold_model, "best_iteration_", None)
                or getattr(fold_model, "best_iteration", None)
                or getattr(inner_estimator, "best_iteration_", None)
                or getattr(inner_estimator, "best_iteration", None)
            )
            if best_iter is not None:
                fold_best_iterations.append(int(best_iter) + 1)

            val_predictions: pd.Series = fold_model.predict(X_test=X_val_fold)

            eval_result = self.evaluator.evaluate_predictions(
                y_true=y_val_fold,
                y_pred=val_predictions,
                model_name=self.model_name,
                target_std=safe_std,
            )
            fold_metrics_collection.append(eval_result.metrics)
            fold_scores.append(eval_result.composite_score)

            # Fold별 2대 핵심 계층 점수 역산출 (개편된 compute_layer_scores SSOT 계약 준수)
            layer_scores = compute_layer_scores(
                metrics=eval_result.metrics,
                target_std=safe_std,
            )

            fold_details.append({
                "composite_score": float(eval_result.composite_score),
                "score_l1_ml": layer_scores["score_l1_ml"],
                "score_l2_factor": layer_scores["score_l2_factor"],
            })

        if not fold_metrics_collection:
            return 0.0, {}, []

        # 5개 Fold의 10대 지표 평균 집계 (Factor p-val은 t-stat 기반 사후 산출)
        averaged_metrics: Dict[EvaluationMetric, float] = {}
        for metric_enum in EvaluationMetric:
            if metric_enum == EvaluationMetric.FACTOR_P_VAL:
                continue
            values = [f_map[metric_enum] for f_map in fold_metrics_collection if metric_enum in f_map]
            averaged_metrics[metric_enum] = float(np.mean(values)) if values else 0.0

        # 비선형 통계량인 p-val의 산술평균 왜곡 방지: 집계된 t-stat으로부터 이론적 양측 p-value 산출
        avg_t_stat = averaged_metrics.get(EvaluationMetric.FACTOR_T_STAT, 0.0)
        averaged_metrics[EvaluationMetric.FACTOR_P_VAL] = float(2.0 * stats.norm.sf(np.abs(avg_t_stat)))

        # [설계 의도] 옌센 부등식 왜곡 방어: 비선형 지표 평균 스코어 대신 각 Fold 실현 스코어의 산술평균을 기준선(base_score)으로 일원화
        fold_scores_arr = np.array(fold_scores, dtype=np.float64)
        base_score: float = float(np.mean(fold_scores_arr)) if len(fold_scores_arr) > 0 else 0.0

        # [소르티노형 하방 편차 페널티] 실현 평균 점수(base_score) 이하로 붕괴된 Fold의 손실 변동성만 선택적 감점
        downside_diff = np.minimum(0.0, fold_scores_arr - base_score)
        downside_std: float = float(np.sqrt(np.mean(downside_diff ** 2)))

        # [설계 의도] _evaluate_cv_folds와 수치 정합성을 맞추기 위해 소프트 배리어 페널티 동일 반영
        avg_mdd: float = averaged_metrics.get(EvaluationMetric.MDD, 0.0)
        mdd_penalty: float = max(0.0, avg_mdd - 0.30) * 1.0

        avg_t_stat: float = averaged_metrics.get(EvaluationMetric.FACTOR_T_STAT, 0.0)
        tstat_penalty: float = max(0.0, (1.96 - avg_t_stat) / 1.96) * 0.30

        total_penalty: float = min(0.50, mdd_penalty + tstat_penalty)

        robust_trial_score: float = (
            base_score
            - (self.robustness_penalty_lambda * downside_std)
            - total_penalty
        )

        return float(robust_trial_score), averaged_metrics, fold_details, fold_best_iterations

# ==============================================================================
# Optuna 조기 종료 전담 콜백 (Early Stopping Callback)
# ==============================================================================

class _EarlyStoppingCallback:
    """목적함수(Composite Score) 개선 정체 시 불필요한 Walk-Forward CV 반복을 조기 차단하는 콜백."""

    def __init__(self, patience: int) -> None:
        """_EarlyStoppingCallback 인스턴스를 초기화합니다.

        Args:
            patience (int): 최고 점수 미갱신 시 허용할 최대 연속 Trial 횟수 (0 이하 시 비활성화).
        """
        self.patience: int = patience
        self.best_score: Optional[float] = None
        self.no_improvement_count: int = 0

    def __call__(self, study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        """각 Trial 완료 시점에 최고 스코어 갱신 여부를 판정하고 조기 탈출을 트리거합니다.

        Args:
            study (optuna.Study): 현재 실행 중인 Optuna Study 객체.
            trial (optuna.trial.FrozenTrial): 방금 종료된 Trial 객체.
        """
        if self.patience <= 0 or trial.value is None:
            return

        current_score: float = float(trial.value)
        if self.best_score is None or current_score > self.best_score:
            self.best_score = current_score
            self.no_improvement_count = 0
        else:
            self.no_improvement_count += 1
            if self.no_improvement_count >= self.patience:
                # 지정된 patience 도달 시 Optuna 최적화 루프를 즉시 인터럽트
                study.stop()