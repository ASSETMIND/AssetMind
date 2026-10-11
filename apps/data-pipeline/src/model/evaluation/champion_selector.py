from dataclasses import dataclass
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from src.model.core.abstract_regressor import AbstractRegressor
from src.model.evaluation.criteria import (
    FactorQualityGate,
    FinanceGate,
    MLValidityGate,
    OverfitGate,
    StatisticalGate,
    Weights,
    get_score_report,
)
from src.model.evaluation.composite_score import compute_layer_scores, get_score
from src.model.evaluation.schema import (
    EvaluationMetric,
    EvaluationResult,
)
from src.model.evaluation.model_evaluator import ModelEvaluator


# ==============================================================================
# 챔피언 선별 결과 캡슐화 불변 DTO (Data Transfer Object)
# ==============================================================================

@dataclass(frozen=True)
class ChampionSelectionResult:
    """최종 챔피언 모델 선별 결과 및 감사 메타데이터를 캡슐화한 불변 DTO.

    Attributes:
        champion_model_name (str): 리더보드 1위로 선정된 챔피언 모델 식별 명칭.
        champion_model (AbstractRegressor): 학습 완료된 챔피언 모델 인스턴스.
        champion_composite_score (float): 챔피언 모델의 2대 핵심 계층 가중 복합 스코어.
        champion_metrics (Dict[EvaluationMetric, float]): 챔피언 모델의 10대 원시 지표 맵.
        leaderboard (pd.DataFrame): 2단계 게이트를 통과한 적격 후보군 리더보드.
        audit_report (pd.DataFrame): 전 후보 모델의 게이트 통과 현황 및 위반 사유 감사 대시보드.
        evaluation_results (Dict[str, EvaluationResult]): 전 후보 모델의 평가 결과 DTO 맵.
        ml_validity_gate (MLValidityGate): 기계학습 기초 유효성 게이트 DTO (Tier 1).
        factor_quality_gate (FactorQualityGate): 팩터 신호 품질 게이트 DTO (Tier 2).
        finance_gate (FinanceGate): 금융 성과 및 리스크 게이트 DTO (Tier 3).
        statistical_gate (StatisticalGate): 알파 통계적 유의성 게이트 DTO (Tier 4).
        overfit_gate (OverfitGate): 일반화 과적합 감사 게이트 DTO (Tier 5).
        weights (Weights): 2대 핵심 계층(ML, Factor) 가중치 DTO.
        scoring_formula (str): 복합 스코어 수학적 계산 공식 명세.
        champion_layer_scores (Dict[str, float]): 챔피언 모델의 계층별 원천 부분 점수 (score_l1_ml, score_l2_factor).
    """
    champion_model_name: str
    champion_model: AbstractRegressor
    champion_composite_score: float
    champion_metrics: Dict[EvaluationMetric, float]
    leaderboard: pd.DataFrame
    audit_report: pd.DataFrame
    evaluation_results: Dict[str, EvaluationResult]
    ml_validity_gate: MLValidityGate
    factor_quality_gate: FactorQualityGate
    finance_gate: FinanceGate
    statistical_gate: StatisticalGate
    overfit_gate: OverfitGate
    weights: Weights
    scoring_formula: str
    champion_layer_scores: Dict[str, float]

    @property
    def gate_spec_report(self) -> pd.DataFrame:
        """5대 평가 게이트 기준 및 CompositeScore 계산 산식 명세를 담은 감사 데이터프레임을 생성합니다.

        Returns:
            pd.DataFrame: 평가 계층을 인덱스로 갖는 게이트웨이 명세 데이터프레임.
        """
        # [설계 의도] print() 출력문을 배제하고 노트북 display()에 최적화된 구조화 감사 테이블 동적 생성
        records = [
            {
                "평가 계층 (Tier)": "Tier 1: ML Validity Gate",
                "핵심 검증 지표": "MDA, RMSE Ratio",
                "임계 기준 (Threshold)": f"MDA ≥ {self.ml_validity_gate.min_mda * 100:.0f}%, RMSE Ratio ≤ {self.ml_validity_gate.max_rmse_ratio:.2f}",
                "통제 및 감사 목적": "기계학습 기본 방향성(50% 동전 던지기) 붕괴 및 타겟 분산 초과 발산 차단",
            },
            {
                "평가 계층 (Tier)": "Tier 2: Factor Quality Gate",
                "핵심 검증 지표": "Rank IC, ICIR",
                "임계 기준 (Threshold)": f"Rank IC > {self.factor_quality_gate.min_rank_ic:.2f}, ICIR ≥ {self.factor_quality_gate.min_icir:.2f}",
                "통제 및 감사 목적": "예측 신호의 횡단면 순위 단조성 및 시계열 정보 안정성 보장",
            },
            {
                "평가 계층 (Tier)": "Tier 3: Finance Gate",
                "핵심 검증 지표": "Sharpe, Sortino, MDD",
                "임계 기준 (Threshold)": f"Sharpe ≥ {self.finance_gate.min_sharpe:.2f}, Sortino ≥ {self.finance_gate.min_sortino:.2f}, MDD ≤ {self.finance_gate.max_mdd * 100:.0f}%",
                "통제 및 감사 목적": "포지션 진입 시 위험조정수익성 및 궤멸적 극단 하방 자본 파산 차단",
            },
            {
                "평가 계층 (Tier)": "Tier 4: Statistical Gate",
                "핵심 검증 지표": "Factor t-stat (p-value)",
                "임계 기준 (Threshold)": f"t-stat ≥ {self.statistical_gate.min_factor_tstat:.2f} (α=0.05 기각역)",
                "통제 및 감사 목적": "Newey-West HAC 보정 단일 알파 신호의 통계적 유의성 강제",
            },
            {
                "평가 계층 (Tier)": "Tier 5: Overfit Gate",
                "핵심 검증 지표": "GDR(Score), GDR(MDD), RIR, DSR",
                "임계 기준 (Threshold)": (
                    f"GDR(Score) ≤ {self.overfit_gate.max_gdr_score:.1f}%, "
                    f"GDR(MDD) ≤ {self.overfit_gate.max_gdr_mdd:.1f}%, "
                    f"RIR ≤ {self.overfit_gate.max_rir:.2f}, "
                    f"DSR ≥ {self.overfit_gate.min_dsr:.2f}"
                ),
                "통제 및 감사 목적": "Train CV 대비 Holdout Test 일반화 열화 및 다중 시도 편향 차단",
            },
            {
                "평가 계층 (Tier)": "Scoring Formula",
                "핵심 검증 지표": "Composite Score",
                "임계 기준 (Threshold)": self.scoring_formula,
                "통제 및 감사 목적": "백테스트 과적합 방지를 위해 순수 신호 품질(L1, L2)만 가중 선형 결합",
            },
        ]
        return pd.DataFrame(records).set_index("평가 계층 (Tier)")

    @property
    def champion_summary_report(self) -> pd.DataFrame:
        """최종 1위 챔피언 모델의 성적표 및 복합 스코어 세부 분해 명세 데이터프레임을 생성합니다.

        Returns:
            pd.DataFrame: 평가 항목을 인덱스로 갖는 챔피언 성적표 데이터프레임.
        """
        # [설계 의도] 블랙박스 처리되었던 Composite Score의 세부 기여도와 10대 원자적 지표를 단일 표로 일원화
        m = self.champion_metrics
        l1 = self.champion_layer_scores.get("score_l1_ml", 0.0)
        l2 = self.champion_layer_scores.get("score_l2_factor", 0.0)
        w1 = self.weights.layer_1_ml
        w2 = self.weights.layer_2_factor
        total_w = (w1 + w2) if (w1 + w2) > 0.0 else 1.0

        records = [
            {"항목": "선정 모델 식별 명칭", "값 / 수치": self.champion_model_name, "세부 설명 및 산출 공식": "5대 게이트 전수 통과 및 종합 리더보드 Rank 1위"},
            {"항목": "최종 복합 스코어", "값 / 수치": f"{self.champion_composite_score:.4f}", "세부 설명 및 산출 공식": f"Composite Score = ({w1:.2f}×L1 + {w2:.2f}×L2) / {total_w:.2f}"},
            {"항목": "Layer 1 (ML 기본 방향성)", "값 / 수치": f"{l1:.4f} (가중 기여: {w1 * l1 / total_w:+.4f})", "세부 설명 및 산출 공식": "Clip((MDA - 0.50) / 0.15, -1.0, 1.5)"},
            {"항목": "Layer 2 (팩터 신호 품질)", "값 / 수치": f"{l2:.4f} (가중 기여: {w2 * l2 / total_w:+.4f})", "세부 설명 및 산출 공식": "0.70×Clip(Rank IC/0.15, -1.0, 1.5) + 0.30×Clip(ICIR/1.5, 0.0, 1.0)"},
            {"항목": "MDA (방향성 적중률)", "값 / 수치": f"{m.get(EvaluationMetric.MDA, 0.0) * 100.0:.2f}%", "세부 설명 및 산출 공식": "Mean Directional Accuracy (부호 일치율)"},
            {"항목": "RMSE (평균 제곱근 오차)", "값 / 수치": f"{m.get(EvaluationMetric.RMSE, 0.0):.6f}", "세부 설명 및 산출 공식": "Root Mean Squared Error"},
            {"항목": "MAE (평균 절대 오차)", "값 / 수치": f"{m.get(EvaluationMetric.MAE, 0.0):.6f}", "세부 설명 및 산출 공식": "Mean Absolute Error"},
            {"항목": "Rank IC (순위 정보 계수)", "값 / 수치": f"{m.get(EvaluationMetric.RANK_IC, 0.0):.4f}", "세부 설명 및 산출 공식": "20일 비중첩 위상 평균 Spearman Rank Correlation"},
            {"항목": "ICIR (팩터 정보 비율)", "값 / 수치": f"{m.get(EvaluationMetric.ICIR, 0.0):.4f}", "세부 설명 및 산출 공식": "Rank IC 평균 / 시계열 표본 표준편차"},
            {"항목": "Signal Sharpe (샤프 지수)", "값 / 수치": f"{m.get(EvaluationMetric.SIGNAL_SHARPE, 0.0):.2f}", "세부 설명 및 산출 공식": "신호 기반 20일 보유 연율화 위험조정수익률"},
            {"항목": "Sortino Ratio (소르티노)", "값 / 수치": f"{m.get(EvaluationMetric.SORTINO_RATIO, 0.0):.2f}", "세부 설명 및 산출 공식": "하방 변동성 통제 연율화 소르티노 지수"},
            {"항목": "MDD (최대 낙폭)", "값 / 수치": f"{m.get(EvaluationMetric.MDD, 0.0) * 100.0:.2f}%", "세부 설명 및 산출 공식": "20일 비중첩 앙상블 및 롤링 윈도우 평균 최대 낙폭"},
            {"항목": "Factor t-stat (유의성)", "값 / 수치": f"{m.get(EvaluationMetric.FACTOR_T_STAT, 0.0):.2f}", "세부 설명 및 산출 공식": f"Newey-West HAC 보정 t-통계량 (p-val: {m.get(EvaluationMetric.FACTOR_P_VAL, 0.0):.4f})"},
        ]
        return pd.DataFrame(records).set_index("항목")


# ==============================================================================
# 챔피언 모델 선별 오케스트레이터 클래스 (Main Class)
# ==============================================================================

class ChampionModelSelector:
    """3대 회귀 모델군 대상 다차원 벤치마크 평가, 5대 도메인 게이트 감사 및 1위 챔피언 선발 오케스트레이터."""

    def __init__(
        self,
        ml_validity_gate: Optional[MLValidityGate] = None,
        factor_quality_gate: Optional[FactorQualityGate] = None,
        finance_gate: Optional[FinanceGate] = None,
        statistical_gate: Optional[StatisticalGate] = None,
        overfit_gate: Optional[OverfitGate] = None,
        weights: Optional[Weights] = None,
        evaluator: Optional[ModelEvaluator] = None,
    ) -> None:
        """ChampionModelSelector 인스턴스를 초기화합니다.

        Args:
            ml_validity_gate (Optional[MLValidityGate]): 머신러닝 기초 유효성 게이트 DTO (None일 경우 기본값 적용).
            factor_quality_gate (Optional[FactorQualityGate]): 팩터 신호 품질 게이트 DTO (None일 경우 기본값 적용).
            finance_gate (Optional[FinanceGate]): 금융 성과 및 리스크 게이트 DTO (None일 경우 기본값 적용).
            statistical_gate (Optional[StatisticalGate]): 알파 통계적 유의성 게이트 DTO (None일 경우 기본값 적용).
            overfit_gate (Optional[OverfitGate]): 일반화 과적합 감사 게이트 DTO (None일 경우 기본값 적용).
            weights (Optional[Weights]): 2대 핵심 계층(ML, Factor) 가중치 DTO (None일 경우 기본값 적용).
            evaluator (Optional[ModelEvaluator]): 모델 전담 평가 엔진 (None일 경우 신규 생성).
        """
        # [설계 의도] 5대 독립 도메인 게이트, 가중치 및 평가 엔진을 외부에서 유연하게 주입받도록 구성
        self.ml_validity_gate: MLValidityGate = ml_validity_gate or MLValidityGate()
        self.factor_quality_gate: FactorQualityGate = factor_quality_gate or FactorQualityGate()
        self.finance_gate: FinanceGate = finance_gate or FinanceGate()
        self.statistical_gate: StatisticalGate = statistical_gate or StatisticalGate()
        self.overfit_gate: OverfitGate = overfit_gate or OverfitGate()
        self.weights: Weights = weights or Weights()
        self.evaluator: ModelEvaluator = evaluator or ModelEvaluator(weights=self.weights)

    def select_champion(
        self,
        models: Dict[str, AbstractRegressor],
        X_test: pd.DataFrame,
        y_test: pd.Series,
        target_std: Optional[float] = None,
        optimization_results: Optional[Dict[str, Any]] = None,
        overfit_gate: Optional[OverfitGate] = None,
        cv_target_std: Optional[float] = None,
    ) -> ChampionSelectionResult:
        """후보 모델들을 전수 평가하고, 2단계 게이트 감사 및 리더보드 연산을 거쳐 최종 1위 챔피언 모델을 발탁합니다.

        Args:
            models (Dict[str, AbstractRegressor]): 모델 식별 명칭을 키로 하고 학습 완료된 모델 객체를 값으로 갖는 딕셔너리.
            X_test (pd.DataFrame): Out-of-Sample 평가용 테스트 피처 데이터프레임.
            y_test (pd.Series): Out-of-Sample 평가용 테스트 정답 타겟 시리즈.
            target_std (Optional[float]): RMSE/MAE 정규화용 타겟 표준편차 (None 시 y_test 표준편차 자동 산출).
            optimization_results (Optional[Dict[str, Any]]): 최적화 결과 딕셔너리 (None 시 사용 안 함).
            overfit_gate (Optional[OverfitGate]): 과적합 감사 게이트 (None 시 사용 안 함).

        Returns:
            ChampionSelectionResult: 챔피언 모델, 리더보드 및 감사 리포트가 바인딩된 결과 DTO.

        Raises:
            ValueError: 평가할 후보 모델이 비어 있거나, 모든 후보 모델이 게이트 검정에서 탈락한 경우 발생 (Fail-Fast).
        """
        # 후보 모델 입력 무결성 선제 검증
        if not models:
            raise ValueError("[ChampionModelSelector] 평가할 후보 모델 딕셔너리가 비어 있습니다.")

        # 1. 전 후보 모델 평가 집행
        candidate_evaluations: Dict[str, EvaluationResult] = _evaluate_all_candidates(
            evaluator=self.evaluator,
            models=models,
            X_test=X_test,
            y_test=y_test,
            target_std=target_std,
        )

        # 2. 메트릭 맵 분리
        candidate_metrics: Dict[str, Dict[EvaluationMetric, float]] = {
            model_name: eval_result.metrics
            for model_name, eval_result in candidate_evaluations.items()
        }

        # Optimization 단계의 CV 성적표 컨텍스트 구성 (Tier 3 대조용)
        cv_context: Dict[str, Dict[str, Any]] = {}
        if optimization_results:
            for m_name, opt_res in optimization_results.items():
                if m_name in candidate_evaluations:
                    # [설계 의도] opt_res 메타데이터 또는 외부 주입 cv_target_std를 안전하게 바인딩
                    extracted_cv_std = (
                        cv_target_std
                        if cv_target_std is not None
                        else getattr(opt_res, "target_std", getattr(opt_res, "cv_target_std", None))
                    )
                    extracted_cv_score_std: Optional[float] = None
                    fold_stability_df = getattr(opt_res, "fold_stability_df", None)
                    if fold_stability_df is not None and isinstance(fold_stability_df, pd.DataFrame):
                        if "Composite Score" in fold_stability_df.index and "Std (σ)" in fold_stability_df.columns:
                            extracted_cv_score_std = float(fold_stability_df.loc["Composite Score", "Std (σ)"])

                    cv_score_std = getattr(opt_res, "cv_score_std", None)
                    if cv_score_std is None and hasattr(opt_res, "fold_stability_df") and opt_res.fold_stability_df is not None:
                        if "Composite Score" in opt_res.fold_stability_df.index and "Std (σ)" in opt_res.fold_stability_df.columns:
                            cv_score_std = float(opt_res.fold_stability_df.loc["Composite Score", "Std (σ)"])

                    cv_context[m_name] = {
                        "cv_metrics": opt_res.tuned_metrics,
                        "cv_score": opt_res.best_score,
                        "test_score": candidate_evaluations[m_name].composite_score,
                        "dsr": getattr(opt_res, "dsr", 1.0),
                        "cv_target_std": extracted_cv_std,
                        "fold_rmses": getattr(opt_res, "fold_rmses", []),
                        "fold_mdds": getattr(opt_res, "fold_mdds", []),
                        "cv_horizon": getattr(opt_res, "cv_horizon", 203),
                        "test_horizon": len(X_test),
                        "cv_score_std": extracted_cv_score_std,
                    }

        # [설계 의도] 타겟 시계열 표준편차를 선제 산출하여 게이트 감사 및 리더보드 정규화 분모로 공유
        effective_target_std: float = (
            target_std
            if (target_std is not None and target_std > 0.0 and np.isfinite(target_std))
            else float(y_test.std(ddof=1)) if len(y_test) > 1 else 1.0
        )
        effective_overfit_gate: OverfitGate = overfit_gate or self.overfit_gate

        # 3. 5대 도메인 게이트(ML, Factor, Finance, Statistical, Overfit) 통합 감사 리포트 생성
        audit_report: pd.DataFrame = get_score_report(
            candidates_metrics=candidate_metrics,
            ml_gate=self.ml_validity_gate,
            factor_gate=self.factor_quality_gate,
            finance_gate=self.finance_gate,
            stat_gate=self.statistical_gate,
            overfit_gate=effective_overfit_gate,
            cv_context=cv_context if cv_context else None,
            target_std=effective_target_std,
        )

        # 4. 적격 모델 대상 2대 핵심 계층(ML, Factor) 복합 스코어 리더보드 산출
        # [정합성 보장] audit_report의 5대 도메인 게이트를 전수 통과한(QUALIFIED) 모델만 리더보드 산출 대상으로 한정
        qualified_model_names = [
            name for name, row in audit_report.iterrows() if row["final_verdict"] == "QUALIFIED"
        ]
        qualified_candidates_metrics = {
            name: candidate_metrics[name] for name in qualified_model_names if name in candidate_metrics
        }

        leaderboard: pd.DataFrame = get_score(
            candidates_metrics=qualified_candidates_metrics,
            ml_gate=self.ml_validity_gate,
            factor_gate=self.factor_quality_gate,
            finance_gate=self.finance_gate,
            stat_gate=self.statistical_gate,
            weights=self.weights,
            target_std=effective_target_std,
        )

        # 5. 적격 모델 존재 여부 검증
        if leaderboard.empty:
            raise ValueError(
                "[ChampionModelSelector] 모든 후보 모델이 평가 게이트를 통과하지 못했습니다.\n"
                f"감사 리포트 확인 요망:\n{audit_report.to_string()}"
            )

        # 6. 최종 1위 챔피언 모델 정보 사출
        champion_name: str = str(leaderboard.index[0])
        champion_score: float = float(leaderboard.iloc[0]["composite_score"])
        champion_model_instance: AbstractRegressor = models[champion_name]
        champion_raw_metrics: Dict[EvaluationMetric, float] = candidate_metrics[champion_name]

        # [설계 의도] 챔피언 모델의 복합 스코어 도출 산식 및 계층별 부분 점수 분해 메타데이터 추출
        champion_layer_scores: Dict[str, float] = compute_layer_scores(
            metrics=champion_raw_metrics,
            target_std=effective_target_std,
        )
        scoring_formula: str = (
            f"{self.weights.layer_1_ml:.2f}×L1(오차) + {self.weights.layer_2_factor:.2f}×L2(팩터품질)"
        )

        return ChampionSelectionResult(
            champion_model_name=champion_name,
            champion_model=champion_model_instance,
            champion_composite_score=champion_score,
            champion_metrics=champion_raw_metrics,
            leaderboard=leaderboard,
            audit_report=audit_report,
            evaluation_results=candidate_evaluations,
            ml_validity_gate=self.ml_validity_gate,
            factor_quality_gate=self.factor_quality_gate,
            finance_gate=self.finance_gate,
            statistical_gate=self.statistical_gate,
            overfit_gate=effective_overfit_gate,
            weights=self.weights,
            scoring_formula=scoring_formula,
            champion_layer_scores=champion_layer_scores,
        )


# ==============================================================================
# 내부 평가 순회 헬퍼 서브루틴 (Private Helpers)
# ==============================================================================

def _evaluate_all_candidates(
    evaluator: ModelEvaluator,
    models: Dict[str, AbstractRegressor],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    target_std: Optional[float] = None,
) -> Dict[str, EvaluationResult]:
    """후보 모델 딕셔너리를 순회하여 ModelEvaluator를 통해 일괄 평가를 집행합니다.

    Args:
        evaluator (ModelEvaluator): 단일 모델 평가 엔진.
        models (Dict[str, AbstractRegressor]): 후보 모델 딕셔너리.
        X_test (pd.DataFrame): 테스트 피처 행렬.
        y_test (pd.Series): 테스트 타겟 시리즈.
        target_std (Optional[float]): 타겟 표준편차.

    Returns:
        Dict[str, EvaluationResult]: 모델명을 키로 하고 EvaluationResult DTO를 값으로 갖는 딕셔너리.
    """
    # 단일 모델 평가 로직의 중복을 배제하고 ModelEvaluator의 다형성 인터페이스를 일괄 호출
    evaluation_results: Dict[str, EvaluationResult] = {}

    for model_name, model_instance in models.items():
        result: EvaluationResult = evaluator.evaluate(
            model=model_instance,
            X_test=X_test,
            y_test=y_test,
            target_std=target_std,
        )
        evaluation_results[model_name] = result

    return evaluation_results