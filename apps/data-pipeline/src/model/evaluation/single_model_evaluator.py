import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pandas as pd

from src.model.optimization.single_model_optimizer import OptimizationRegistry


@dataclass
class ChampionModelDTO:
    """최종 발탁된 챔피언 모델 및 핵심 성능 지표 캡슐화 DTO."""

    name: str
    model: Any
    cv_mda: float
    cv_rmse: float
    composite_score: float
    test_mda: float
    test_rmse: float
    test_mae: float
    best_hyperparameters: Dict[str, Any]


class SingleModelEvaluator:
    """3대 튜닝 모델에 대한 실전 Holdout Test 세트 평가 및 최적 챔피언 모델 선발기."""

    def __init__(self, tracker: Optional[Any] = None) -> None:
        """SingleModelEvaluator 인스턴스를 초기화합니다.

        Args:
            tracker (Optional[Any]): MLflowTracker 인스턴스 (선택 사항).
        """
        # [설계 의도] MLflow Tracker 의존성 주입을 통한 관측성(Observability) 확보
        self.tracker: Optional[Any] = tracker
        self.comparison_dataframe: Optional[pd.DataFrame] = None
        self.ranked_dataframe: Optional[pd.DataFrame] = None
        self._optimization_registry: Optional[OptimizationRegistry] = None

    def evaluate(
        self,
        optimization_registry: OptimizationRegistry,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> pd.DataFrame:
        """
        3대 모델의 Holdout Test 추론 평가를 수행하고 전체 비교 정산표를 구축합니다.

        Args:
            optimization_registry: Step 2에서 사출된 HPO 최적화 결과 레지스트리
            X_test: 실전 검증용 20% Holdout Test 피처 행렬
            y_test: 실전 검증용 20% Holdout Test 타겟 시계열

        Returns:
            pd.DataFrame: 3대 모델의 튜닝 전후 CV 및 Test 실전 지표 비교 정산표
        """
        self._optimization_registry = optimization_registry
        comparison_records: List[Dict[str, Any]] = []

        print("=" * 122)
        print(" 🚀 [Default vs Tuned Model Performance Comparison Launch]")
        print(f" 🎯 Out-of-Sample Holdout Partition: Test Set {X_test.shape} (Pure Unseen Future)")
        print("=" * 122)

        for model_name, tuned_model in optimization_registry.tuned_models.items():
            default_cv_metrics = optimization_registry.default_cv_metrics[model_name]
            tuned_cv_metrics = optimization_registry.tuned_cv_metrics[model_name]

            # 1. 20% Holdout Test 세트 실전 추론 및 싱글 배치 레이턴시(ms) 정밀 측정
            inference_start_time: float = time.perf_counter()
            tuned_model.predict(X_test=X_test)
            tuned_infer_latency_ms: float = (time.perf_counter() - inference_start_time) * 1000.0
            tuned_test_metrics = tuned_model.evaluate(X_test=X_test, y_test=y_test)

            # 2. HPO 튜닝 전후 Walk-Forward CV 지표 개선폭(Delta) 계산
            cv_mda_delta: float = tuned_cv_metrics["mean_mda"] - default_cv_metrics["mean_mda"]
            cv_rmse_delta: float = tuned_cv_metrics["mean_rmse"] - default_cv_metrics["mean_rmse"]

            # 3. 비교 리포트 레코드 적재
            comparison_records.append({
                "알고리즘 (Algorithm)": model_name,
                "Default CV MDA": default_cv_metrics["mean_mda"],
                "Tuned CV MDA": tuned_cv_metrics["mean_mda"],
                "CV MDA 개선폭 (Δ)": f"{'+' if cv_mda_delta >= 0 else ''}{cv_mda_delta * 100.0:.2f}%p",
                "Default CV RMSE": default_cv_metrics["mean_rmse"],
                "Tuned CV RMSE": tuned_cv_metrics["mean_rmse"],
                "CV RMSE 개선폭 (Δ)": f"{'+' if cv_rmse_delta >= 0 else ''}{cv_rmse_delta:.6f}",
                "CV 복합 점수 (Composite)": tuned_cv_metrics["composite_score"],
                "Tuned Test MDA": tuned_test_metrics["MDA"],
                "Tuned Test RMSE": tuned_test_metrics["RMSE"],
                "Tuned Test MAE": tuned_test_metrics["MAE"],
                "추론 속도 (Latency)": f"{tuned_infer_latency_ms:.2f} ms"
            })

            # MLflow Tracker 연동 시 Holdout Test 지표 및 개선폭(Delta) 백엔드 자동 적재
            if self.tracker is not None:
                self.tracker.log_test_evaluation(
                    model_name=model_name,
                    test_metrics=tuned_test_metrics,
                    latency_ms=tuned_infer_latency_ms,
                    cv_mda_delta=cv_mda_delta,
                    cv_rmse_delta=cv_rmse_delta
                )

        self.comparison_dataframe = pd.DataFrame(comparison_records)
        return self.comparison_dataframe

    def get_best_model(self, criterion: str = "composite") -> ChampionModelDTO:
        """
        평가 결과 테이블을 기준으로 1위 챔피언 모델을 선발하고 MLflow 태깅을 완결합니다.

        Args:
            criterion (str): 정렬 기준 ('composite', 'mda', 'rmse'). 기본값 'composite'.

        Returns:
            ChampionModelDTO: 발탁된 챔피언 모델 인스턴스 및 핵심 성능 지표 캡슐화 객체.

        Raises:
            RuntimeError: evaluate()가 먼저 실행되지 않은 상태에서 호출된 경우.
        """
        if self.comparison_dataframe is None or self._optimization_registry is None:
            raise RuntimeError("먼저 evaluate() 메서드를 호출하여 모델 평가를 완료해야 합니다.")

        # 선발 기준에 따른 유연한 다차원 정렬 정책 지원
        if criterion == "mda":
            sort_columns = ["Tuned CV MDA", "CV 복합 점수 (Composite)", "Tuned CV RMSE"]
            sort_orders = [False, False, True]
        elif criterion == "rmse":
            sort_columns = ["Tuned CV RMSE", "CV 복합 점수 (Composite)", "Tuned CV MDA"]
            sort_orders = [True, False, False]
        else:  # 기본값: 복합 최적화 점수 기준
            sort_columns = ["CV 복합 점수 (Composite)", "Tuned CV MDA", "Tuned CV RMSE"]
            sort_orders = [False, False, True]

        self.ranked_dataframe = self.comparison_dataframe.sort_values(
            by=sort_columns,
            ascending=sort_orders
        ).reset_index(drop=True)

        champion_model_name: str = self.ranked_dataframe.iloc[0]["알고리즘 (Algorithm)"]
        champion_model: Any = self._optimization_registry.tuned_models[champion_model_name]

        # MLflow 전체 순위 태깅 및 최종 챔피언 비교 정산표 CSV 저장 위임
        if self.tracker is not None:
            self.tracker.log_benchmark_and_champion(
                ranked_dataframe=self.ranked_dataframe,
                champion_model_name=champion_model_name,
                summary_dataframe=self.comparison_dataframe
            )

        return ChampionModelDTO(
            name=champion_model_name,
            model=champion_model,
            cv_mda=self.ranked_dataframe.iloc[0]["Tuned CV MDA"],
            cv_rmse=self.ranked_dataframe.iloc[0]["Tuned CV RMSE"],
            composite_score=self.ranked_dataframe.iloc[0]["CV 복합 점수 (Composite)"],
            test_mda=self.ranked_dataframe.iloc[0]["Tuned Test MDA"],
            test_rmse=self.ranked_dataframe.iloc[0]["Tuned Test RMSE"],
            test_mae=self.ranked_dataframe.iloc[0]["Tuned Test MAE"],
            best_hyperparameters=self._optimization_registry.best_hyperparameters[champion_model_name]
        )

    @property
    def display_dataframe(self) -> pd.DataFrame:
        """대시보드 출력용으로 백분율 및 소수점 포맷팅이 적용된 데이터프레임을 생성합니다."""
        if self.comparison_dataframe is None:
            return pd.DataFrame()

        display_dataframe = self.comparison_dataframe.copy()
        display_dataframe["Default CV MDA"] = display_dataframe["Default CV MDA"].map(lambda x: f"{x * 100.0:.2f}%")
        display_dataframe["Tuned CV MDA"] = display_dataframe["Tuned CV MDA"].map(lambda x: f"{x * 100.0:.2f}%")
        display_dataframe["Default CV RMSE"] = display_dataframe["Default CV RMSE"].map(lambda x: f"{x:.6f}")
        display_dataframe["Tuned CV RMSE"] = display_dataframe["Tuned CV RMSE"].map(lambda x: f"{x:.6f}")
        display_dataframe["CV 복합 점수 (Composite)"] = display_dataframe["CV 복합 점수 (Composite)"].map(lambda x: f"{x:.4f}")
        display_dataframe["Tuned Test MDA"] = display_dataframe["Tuned Test MDA"].map(lambda x: f"{x * 100.0:.2f}%")
        display_dataframe["Tuned Test RMSE"] = display_dataframe["Tuned Test RMSE"].map(lambda x: f"{x:.6f}")
        display_dataframe["Tuned Test MAE"] = display_dataframe["Tuned Test MAE"].map(lambda x: f"{x:.6f}")
        display_dataframe.set_index("알고리즘 (Algorithm)", inplace=True)
        return display_dataframe