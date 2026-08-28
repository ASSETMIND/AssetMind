import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from src.model.evaluation.champion_selector import (
    ChampionSelector,
    ChampionSelectionResult,
)
from src.model.evaluation.criteria import (
    HardGate,
    SoftGate,
    Weights,
)
from src.model.optimization.single_model_optimizer import OptimizationRegistry

@dataclass
class ChampionModelDTO:
    """최종 발탁된 챔피언 모델 및 다계층 핵심 성능 지표 캡슐화 DTO."""
    name: str
    model: Any
    cv_mda: float
    cv_rmse: float
    composite_score: float
    test_mda: float
    test_rmse: float
    test_mae: float
    test_rank_ic: float
    test_icir: float
    test_sharpe: float
    test_sortino: float
    test_mdd: float
    test_tstat: float
    test_pvalue: float
    best_hyperparameters: Dict[str, Any]


class SingleModelEvaluator:
    """3대 튜닝 모델에 대한 실전 Holdout Test 세트 평가 및 최적 챔피언 모델 선발기."""

    def __init__(
        self,
        tracker: Optional[Any] = None,
        hard_gate: Optional[HardGate] = None,
        soft_gate: Optional[SoftGate] = None,
        weights: Optional[Weights] = None
    ) -> None:
        """SingleModelEvaluator 인스턴스를 초기화합니다.

        Args:
            tracker (Optional[Any]): MLflowTracker 인스턴스 (선택 사항).
            hard_gate (Optional[HardGate]): 하드 게이트 설정 (선택 사항).
            soft_gate (Optional[SoftGate]): 소프트 게이트 설정 (선택 사항).
            weights (Optional[Weights]): 4대 계층 가중치 설정 (선택 사항).
        """
        # [설계 의도] MLOps 관측성 및 ChampionSelector 선별 엔진 의존성 주입
        self.tracker: Optional[Any] = tracker
        self.hard_gate: HardGate = hard_gate if hard_gate is not None else HardGate()
        self.soft_gate: SoftGate = soft_gate if soft_gate is not None else SoftGate()
        self.weights: Weights = weights if weights is not None else Weights()

        self.selector: ChampionSelector = ChampionSelector(
            hard_gate=self.hard_gate,
            soft_gate=self.soft_gate,
            weights=self.weights
        )
        self.selection_result: Optional[ChampionSelectionResult] = None
        self.comparison_dataframe: Optional[pd.DataFrame] = None
        self.ranked_dataframe: Optional[pd.DataFrame] = None
        self.audit_dataframe: Optional[pd.DataFrame] = None
        self._optimization_registry: Optional[OptimizationRegistry] = None

    def evaluate(
        self,
        optimization_registry: OptimizationRegistry,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> pd.DataFrame:
        """3대 모델의 Holdout Test 추론 평가를 수행하고 6대 계층 기반 10대 지표 정산표를 구축합니다.

        Args:
            optimization_registry: HPO 최적화 결과 레지스트리.
            X_test: 실전 검증용 20% Holdout Test 피처 행렬.
            y_test: 실전 검증용 20% Holdout Test 타겟 시계열.

        Returns:
            pd.DataFrame: 3대 모델의 튜닝 전후 CV 및 Test 실전 지표 비교 정산표.
        """
        self._optimization_registry = optimization_registry
        comparison_records: List[Dict[str, Any]] = []

        print("=" * 122)
        print(" 🚀 [Default vs Model Multi-Layer Performance Evaluation Launch]")
        print(f" 🎯 Out-of-Sample Holdout Partition: Test Set {X_test.shape} (Pure Unseen Future)")
        print("=" * 122)

        # 1. ChampionSelector에 후보 모델 평가, 2단계 게이트 감사 및 복합 스코어링 위임
        self.selection_result = self.selector.select_champion(
            models=optimization_registry.tuned_models,
            X_test=X_test,
            y_test=y_test
        )
        self.audit_dataframe = self.selection_result.audit_report
        leaderboard = self.selection_result.leaderboard

        # 2. HPO CV 지표 및 Test 실전 지표 통합 비교 레코드 조립
        for model_name, tuned_model in optimization_registry.tuned_models.items():
            default_cv_metrics = optimization_registry.default_cv_metrics[model_name]
            tuned_cv_metrics = optimization_registry.tuned_cv_metrics[model_name]

            cv_mda_delta: float = tuned_cv_metrics["mean_mda"] - default_cv_metrics["mean_mda"]
            cv_rmse_delta: float = tuned_cv_metrics["mean_rmse"] - default_cv_metrics["mean_rmse"]

            is_qualified = (
                self.audit_dataframe.loc[model_name, "is_qualified"]
                if model_name in self.audit_dataframe.index else "DISQUALIFIED"
            )

            # 리더보드 적격 모델 지표 추출 (탈락 모델 안전 Fallback)
            if model_name in leaderboard.index:
                row = leaderboard.loc[model_name]
                test_mda = float(row.get("MDA", 0.0))
                test_rmse = float(row.get("RMSE", 0.0))
                test_mae = float(row.get("MAE", 0.0))
                test_rank_ic = float(row.get("Rank_IC", 0.0))
                test_icir = float(row.get("ICIR", 0.0))
                test_sharpe = float(row.get("Signal_Sharpe", 0.0))
                test_sortino = float(row.get("Sortino_Ratio", 0.0))
                test_mdd = float(row.get("MDD", 0.0))
                test_tstat = float(row.get("Factor_t_stat", 0.0))
                test_pval = float(row.get("Factor_p_val", 1.0))
                latency_ms = float(row.get("Latency", 0.0))
                composite_score = float(row.get("composite_score", 0.0))
                rank_val = int(row.get("rank", 99))
            else:
                test_mda, test_rmse, test_mae, test_rank_ic, test_icir = 0.0, 0.0, 0.0, 0.0, 0.0
                test_sharpe, test_sortino, test_mdd, test_tstat, test_pval = 0.0, 0.0, 0.0, 0.0, 1.0
                latency_ms, composite_score, rank_val = 0.0, 0.0, 99

            comparison_records.append({
                "알고리즘 (Algorithm)": model_name,
                "Default CV MDA": default_cv_metrics["mean_mda"],
                "CV MDA": tuned_cv_metrics["mean_mda"],
                "CV MDA 개선폭 (Δ)": f"{'+' if cv_mda_delta >= 0 else ''}{cv_mda_delta * 100.0:.2f}%p",
                "Default CV RMSE": default_cv_metrics["mean_rmse"],
                "CV RMSE": tuned_cv_metrics["mean_rmse"],
                "CV RMSE 개선폭 (Δ)": f"{'+' if cv_rmse_delta >= 0 else ''}{cv_rmse_delta:.6f}",
                "Test MDA": test_mda,
                "Test RMSE": test_rmse,
                "Test MAE": test_mae,
                "Test Rank IC": test_rank_ic,
                "Test ICIR": test_icir,
                "Test Signal Sharpe": test_sharpe,
                "Test Sortino Ratio": test_sortino,
                "Test Max Drawdown": test_mdd,
                "Test Newey-West t-stat": test_tstat,
                "Test Newey-West p-value": test_pval,
                "추론 속도 (Latency)": f"{latency_ms:.2f} ms",
                "composite_score": composite_score,
                "rank": rank_val,
                "적격 판정 (Gate)": is_qualified
            })

            # 3. MLflow Tracker 연동 시 10대 지표 일괄 적재
            if self.tracker is not None:
                self.tracker.log_test_evaluation(
                    model_name=model_name,
                    test_metrics={
                        "MDA": test_mda,
                        "RMSE": test_rmse,
                        "MAE": test_mae,
                        "Rank_IC": test_rank_ic,
                        "ICIR": test_icir,
                        "Sharpe": test_sharpe,
                        "Sortino": test_sortino,
                        "MDD": test_mdd,
                        "t_stat": test_tstat,
                        "p_value": test_pval,
                    },
                    latency_ms=latency_ms,
                    cv_mda_delta=cv_mda_delta,
                    cv_rmse_delta=cv_rmse_delta
                )

        self.comparison_dataframe = pd.DataFrame(comparison_records)
        return self.comparison_dataframe

    def get_best_model(self, criterion: str = "composite") -> ChampionModelDTO:
        """2단계 게이트를 통과하고 복합 스코어가 가장 높은 1위 챔피언 모델을 선발합니다.

        Args:
            criterion (str): 정렬 기준 ('composite', 'mda', 'rmse', 'sharpe'). 기본값 'composite'.

        Returns:
            ChampionModelDTO: 발탁된 챔피언 모델 인스턴스 및 다차원 성능 지표 DTO.

        Raises:
            RuntimeError: evaluate()가 먼저 실행되지 않았거나 적격 모델이 없는 경우.
        """
        if self.comparison_dataframe is None or self._optimization_registry is None:
            raise RuntimeError("먼저 evaluate() 메서드를 호출하여 모델 평가를 완료해야 합니다.")

        df = self.comparison_dataframe.copy()

        # [설계 의도] 다차원 정렬 정책 분기
        if criterion == "mda":
            sort_cols = ["Test MDA", "composite_score"]
            sort_asc = [False, False]
        elif criterion == "rmse":
            sort_cols = ["Test RMSE", "composite_score"]
            sort_asc = [True, False]
        elif criterion == "sharpe":
            sort_cols = ["Test Signal Sharpe", "composite_score"]
            sort_asc = [False, False]
        else:  # 기본값: 복합 스코어 및 랭킹 기준
            sort_cols = ["composite_score", "Test MDA", "Test Rank IC"]
            sort_asc = [False, False, False]

        self.ranked_dataframe = df.sort_values(by=sort_cols, ascending=sort_asc).reset_index(drop=True)

        best_row = self.ranked_dataframe.iloc[0]
        champion_model_name: str = str(best_row["알고리즘 (Algorithm)"])
        champion_model: Any = self._optimization_registry.tuned_models[champion_model_name]

        # MLflow 전체 순위 태깅 및 최종 챔피언 정산표 저장
        if self.tracker is not None:
            self.tracker.log_benchmark_and_champion(
                ranked_dataframe=self.ranked_dataframe,
                champion_model_name=champion_model_name,
                summary_dataframe=self.comparison_dataframe
            )

        return ChampionModelDTO(
            name=champion_model_name,
            model=champion_model,
            cv_mda=float(best_row["CV MDA"]),
            cv_rmse=float(best_row["CV RMSE"]),
            composite_score=float(best_row["composite_score"]),
            test_mda=float(best_row["Test MDA"]),
            test_rmse=float(best_row["Test RMSE"]),
            test_mae=float(best_row["Test MAE"]),
            test_rank_ic=float(best_row["Test Rank IC"]),
            test_icir=float(best_row["Test ICIR"]),
            test_sharpe=float(best_row["Test Signal Sharpe"]),
            test_sortino=float(best_row["Test Sortino Ratio"]),
            test_mdd=float(best_row["Test Max Drawdown"]),
            test_tstat=float(best_row["Test Newey-West t-stat"]),
            test_pvalue=float(best_row["Test Newey-West p-value"]),
            best_hyperparameters=self._optimization_registry.best_hyperparameters[champion_model_name]
        )

    @property
    def display_dataframe(self) -> pd.DataFrame:
        """대시보드 출력용으로 10대 지표 포맷팅이 적용된 벤치마크 데이터프레임을 생성합니다."""
        if self.comparison_dataframe is None:
            return pd.DataFrame()

        display_cols = [
            "알고리즘 (Algorithm)",
            "Test MDA",
            "Test Rank IC",
            "Test ICIR",
            "Test Signal Sharpe",
            "Test Sortino Ratio",
            "Test Max Drawdown",
            "Test Newey-West t-stat",
            "Test RMSE",
            "Test MAE",
            "composite_score",
            "적격 판정 (Gate)",
            "추론 속도 (Latency)"
        ]

        valid_cols = [col for col in display_cols if col in self.comparison_dataframe.columns]
        display_df = self.comparison_dataframe[valid_cols].copy()

        # [설계 의도] 가독성을 위한 수치 백분율 및 소수점 포맷팅
        if "Test MDA" in display_df:
            display_df["Test MDA"] = display_df["Test MDA"].map(lambda x: f"{x * 100.0:.2f}%")
        if "Test Rank IC" in display_df:
            display_df["Test Rank IC"] = display_df["Test Rank IC"].map(lambda x: f"{x:.4f}")
        if "Test ICIR" in display_df:
            display_df["Test ICIR"] = display_df["Test ICIR"].map(lambda x: f"{x:.2f}")
        if "Test Signal Sharpe" in display_df:
            display_df["Test Signal Sharpe"] = display_df["Test Signal Sharpe"].map(lambda x: f"{x:.2f}")
        if "Test Sortino Ratio" in display_df:
            display_df["Test Sortino Ratio"] = display_df["Test Sortino Ratio"].map(lambda x: f"{x:.2f}")
        if "Test Max Drawdown" in display_df:
            display_df["Test Max Drawdown"] = display_df["Test Max Drawdown"].map(lambda x: f"{x * 100.0:.2f}%")
        if "Test Newey-West t-stat" in display_df:
            display_df["Test Newey-West t-stat"] = display_df["Test Newey-West t-stat"].map(lambda x: f"{x:.2f}")
        if "Test RMSE" in display_df:
            display_df["Test RMSE"] = display_df["Test RMSE"].map(lambda x: f"{x:.6f}")
        if "Test MAE" in display_df:
            display_df["Test MAE"] = display_df["Test MAE"].map(lambda x: f"{x:.6f}")
        if "composite_score" in display_df:
            display_df["composite_score"] = display_df["composite_score"].map(lambda x: f"{x:.4f}")

        display_df.set_index("알고리즘 (Algorithm)", inplace=True)
        return display_df