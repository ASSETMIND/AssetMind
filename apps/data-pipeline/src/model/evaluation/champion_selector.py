from dataclasses import dataclass
from typing import Dict, Optional
import numpy as np
import pandas as pd

from src.model.core.abstract_regressor import AbstractRegressor
from src.model.evaluation.criteria import (
    HardGate,
    SoftGate,
    Weights,
    get_score_report,
)
from src.model.evaluation.composite_score import get_score
from src.model.evaluation.schema import (
    EvaluationMetric,
    EvaluationResult,
)
from src.model.evaluation.single_model_evaluator import SingleModelEvaluator


# ==============================================================================
# 챔피언 선별 결과 캡슐화 불변 DTO (Data Transfer Object)
# ==============================================================================

@dataclass(frozen=True)
class ChampionSelectionResult:
    """최종 챔피언 모델 선별 결과 및 감사 메타데이터를 캡슐화한 불변 DTO.

    Attributes:
        champion_model_name (str): 리더보드 1위로 선정된 챔피언 모델 식별 명칭.
        champion_model (AbstractRegressor): 학습 완료된 챔피언 모델 인스턴스.
        champion_composite_score (float): 챔피언 모델의 4대 계층 가중 복합 스코어.
        champion_metrics (Dict[EvaluationMetric, float]): 챔피언 모델의 10대 원시 지표 맵.
        leaderboard (pd.DataFrame): 2단계 게이트를 통과한 적격 후보군 리더보드.
        audit_report (pd.DataFrame): 전 후보 모델의 게이트 통과 현황 및 위반 사유 감사 대시보드.
        evaluation_results (Dict[str, EvaluationResult]): 전 후보 모델의 평가 결과 DTO 맵.
    """
    champion_model_name: str
    champion_model: AbstractRegressor
    champion_composite_score: float
    champion_metrics: Dict[EvaluationMetric, float]
    leaderboard: pd.DataFrame
    audit_report: pd.DataFrame
    evaluation_results: Dict[str, EvaluationResult]


# ==============================================================================
# 챔피언 모델 선별 오케스트레이터 클래스 (Main Class)
# ==============================================================================

class ChampionModelSelector:
    """3대 회귀 모델군 대상 다차원 벤치마크 평가, 게이트 감사 및 1위 챔피언 선발 오케스트레이터."""

    def __init__(
        self,
        hard_gate: Optional[HardGate] = None,
        soft_gate: Optional[SoftGate] = None,
        weights: Optional[Weights] = None,
        evaluator: Optional[SingleModelEvaluator] = None,
    ) -> None:
        """ChampionModelSelector 인스턴스를 초기화합니다.

        Args:
            hard_gate (Optional[HardGate]): 하드 게이트 임계치 설정 DTO (None일 경우 기본값 적용).
            soft_gate (Optional[SoftGate]): 소프트 게이트 임계치 설정 DTO (None일 경우 기본값 적용).
            weights (Optional[Weights]): 4대 계층 가중치 설정 DTO (None일 경우 기본값 적용).
            evaluator (Optional[SingleModelEvaluator]): 단일 모델 전담 평가 엔진 (None일 경우 신규 생성).
        """
        # 게이트 기준, 가중치 및 평가 엔진을 외부에서 유연하게 주입받도록 구성
        self.hard_gate: HardGate = hard_gate or HardGate()
        self.soft_gate: SoftGate = soft_gate or SoftGate()
        self.weights: Weights = weights or Weights()
        self.evaluator: SingleModelEvaluator = evaluator or SingleModelEvaluator(weights=self.weights)

    def select_champion(
        self,
        models: Dict[str, AbstractRegressor],
        X_test: pd.DataFrame,
        y_test: pd.Series,
        target_std: Optional[float] = None,
    ) -> ChampionSelectionResult:
        """후보 모델들을 전수 평가하고, 2단계 게이트 감사 및 리더보드 연산을 거쳐 최종 1위 챔피언 모델을 발탁합니다.

        Args:
            models (Dict[str, AbstractRegressor]): 모델 식별 명칭을 키로 하고 학습 완료된 모델 객체를 값으로 갖는 딕셔너리.
            X_test (pd.DataFrame): Out-of-Sample 평가용 테스트 피처 데이터프레임.
            y_test (pd.Series): Out-of-Sample 평가용 테스트 정답 타겟 시리즈.
            target_std (Optional[float]): RMSE/MAE 정규화용 타겟 표준편차 (None 시 y_test 표준편차 자동 산출).

        Returns:
            ChampionSelectionResult: 챔피언 모델, 리더보드 및 감사 리포트가 바인딩된 결과 DTO.

        Raises:
            ValueError: 평가할 후보 모델이 비어 있거나, 모든 후보 모델이 게이트 검정에서 탈락한 경우 발생 (Fail-Fast).
        """
        # 후보 모델 입력 무결성 선제 검증
        if not models:
            raise ValueError("[ChampionModelSelector] 평가할 후보 모델 딕셔너리가 비어 있습니다.")

        # 1. 전 후보 모델 평가 집행 (SingleModelEvaluator 위임)
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

        # 3. 전 후보 모델 2단계 게이트 감사 리포트 생성
        audit_report: pd.DataFrame = get_score_report(
            candidates_metrics=candidate_metrics,
            hard_gate=self.hard_gate,
            soft_gate=self.soft_gate,
        )

        # 4. 적격 모델 대상 4대 계층 가중 복합 스코어 리더보드 산출
        effective_target_std: float = (
            target_std
            if (target_std is not None and target_std > 0.0 and np.isfinite(target_std))
            else float(y_test.std(ddof=1)) if len(y_test) > 1 else 1.0
        )

        # [설계 의도] get_score에 target_std를 전달하여 Optimization과 일치된 절대 스코어로 리더보드 산출
        leaderboard: pd.DataFrame = get_score(
            candidates_metrics=candidate_metrics,
            hard_gate=self.hard_gate,
            soft_gate=self.soft_gate,
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

        return ChampionSelectionResult(
            champion_model_name=champion_name,
            champion_model=champion_model_instance,
            champion_composite_score=champion_score,
            champion_metrics=champion_raw_metrics,
            leaderboard=leaderboard,
            audit_report=audit_report,
            evaluation_results=candidate_evaluations,
        )


# ==============================================================================
# 내부 평가 순회 헬퍼 서브루틴 (Private Helpers)
# ==============================================================================

def _evaluate_all_candidates(
    evaluator: SingleModelEvaluator,
    models: Dict[str, AbstractRegressor],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    target_std: Optional[float] = None,
) -> Dict[str, EvaluationResult]:
    """후보 모델 딕셔너리를 순회하여 SingleModelEvaluator를 통해 일괄 평가를 집행합니다.

    Args:
        evaluator (SingleModelEvaluator): 단일 모델 평가 엔진.
        models (Dict[str, AbstractRegressor]): 후보 모델 딕셔너리.
        X_test (pd.DataFrame): 테스트 피처 행렬.
        y_test (pd.Series): 테스트 타겟 시리즈.
        target_std (Optional[float]): 타겟 표준편차.

    Returns:
        Dict[str, EvaluationResult]: 모델명을 키로 하고 EvaluationResult DTO를 값으로 갖는 딕셔너리.
    """
    # 단일 모델 평가 로직의 중복을 배제하고 SingleModelEvaluator의 다형성 인터페이스를 일괄 호출
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