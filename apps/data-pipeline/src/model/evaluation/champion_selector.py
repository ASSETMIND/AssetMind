from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.model.evaluation import metrics
from src.model.evaluation.criteria import (
    HardGate,
    SoftGate,
    Weights,
    get_score_report
)
from src.model.evaluation.composite_score import get_score

# ==============================================================================
# 1. 챔피언 선별 결과 캡슐화 불변 DTO (Data Transfer Object)
# ==============================================================================

@dataclass(frozen=True)
class ChampionSelectionResult:
    """최종 챔피언 모델 선별 결과 및 감사 메타데이터 DTO.
    
    Attributes:
        champion_model_name (str): 1위로 선정된 챔피언 모델 명칭.
        champion_model (Any): 학습 완료된 챔피언 모델 객체 인스턴스.
        champion_composite_score (float): 챔피언 모델의 최종 복합 스코어.
        champion_metrics (Dict[str, float]): 챔피언 모델의 10대 원시 지표 딕셔너리.
        leaderboard (pd.DataFrame): 적격 후보 모델들의 가중 복합 스코어 리더보드.
        audit_report (pd.DataFrame): 전 후보 모델의 2단계 게이트 통과/탈락 감사 대시보드.
    """
    champion_model_name: str
    champion_model: Any
    champion_composite_score: float
    champion_metrics: Dict[str, float]
    leaderboard: pd.DataFrame
    audit_report: pd.DataFrame


# ==============================================================================
# 2. 내부 연산 및 프로파일링 헬퍼 (Private Helpers)
# ==============================================================================

def _measure_inference_latency_ms(
    model: Any, 
    sample_input: pd.DataFrame, 
    n_runs: int = 100
) -> float:
    """단일 샘플에 대한 평균 추론 지연 시간(Latency ms)을 정밀 측정합니다."""
    # 워밍업 (JIT / 캐시 안정화)
    for _ in range(5):
        _ = model.predict(sample_input.iloc[0:1])
        
    latencies: List[float] = []
    single_sample = sample_input.iloc[0:1]
    
    for _ in range(n_runs):
        start_time = time.perf_counter()
        _ = model.predict(single_sample)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        latencies.append(elapsed_ms)
        
    # P95 지연 시간 반환
    return float(np.percentile(latencies, 95))

def _collect_model_metrics(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series
) -> Tuple[Dict[str, float], np.ndarray]:
    """단일 모델의 추론을 실행하고 10대 평가 지표를 산출합니다."""
    y_true_arr = y_test.to_numpy(dtype=np.float64).flatten()
    
    # 모델 추론
    preds = model.predict(X_test)
    y_pred_arr = np.array(preds, dtype=np.float64).flatten()
    
    # 추론 레이턴시 측정 (P95 ms 기준)
    latency_ms = _measure_inference_latency_ms(model, X_test)
    
    # 통계 검정 통계량
    nw_tstat, nw_pval = metrics.newey_west_tstat(y_true_arr, y_pred_arr)
    
    # 10대 지표 수집 (metrics.py 고유 인터페이스 직접 활용)
    metric_dict: Dict[str, float] = {
        "MDA": metrics.mda(y_true_arr, y_pred_arr),
        "RMSE": metrics.rmse(y_true_arr, y_pred_arr),
        "MAE": metrics.mae(y_true_arr, y_pred_arr),
        "Rank_IC": metrics.rank_ic(y_true_arr, y_pred_arr),
        "ICIR": metrics.icir(y_true_arr, y_pred_arr, window_size=20),
        "Signal_Sharpe": metrics.signal_sharpe(y_true_arr, y_pred_arr),
        "Sortino_Ratio": metrics.sortino_ratio(y_true_arr, y_pred_arr),
        "MDD": metrics.mdd(y_true_arr, y_pred_arr),
        "Factor_t_stat": nw_tstat,
        "Factor_p_val": nw_pval,
        "Latency": latency_ms
    }
    
    return metric_dict, y_pred_arr


# ==============================================================================
# 3. 최상위 챔피언 선별기 오케스트레이터 클래스 (Main Class)
# ==============================================================================

class ChampionSelector:
    """3대 회귀 모델군 대상 다차원 지표 평가 및 최적 챔피언 모델 선별 엔진."""

    def __init__(
        self,
        hard_gate: Optional[HardGate] = None,
        soft_gate: Optional[SoftGate] = None,
        weights: Optional[Weights] = None
    ) -> None:
        """ChampionSelector 인스턴스를 초기화합니다.

        Args:
            hard_gate: 하드 게이트 임계치 설정 (None일 경우 기본값).
            soft_gate: 소프트 게이트 임계치 설정 (None일 경우 기본값).
            weights: 4대 계층 가중치 설정 (None일 경우 기본값).
        """
        self.hard_gate = hard_gate or HardGate()
        self.soft_gate = soft_gate or SoftGate()
        self.weights = weights or Weights()

    def select_champion(
        self,
        models: Dict[str, Any],
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> ChampionSelectionResult:
        """후보 모델들을 전수 평가하고 최종 1위 챔피언 모델을 발탁합니다.

        Args:
            models: 모델 식별자명을 키로 하고 학습된 모델 객체를 값으로 갖는 딕셔너리.
            X_test: Out-of-Sample 평가용 피처 데이터프레임.
            y_test: Out-of-Sample 평가용 정답 타겟 시리즈.

        Returns:
            ChampionSelectionResult: 챔피언 모델과 평가 감사표가 포함된 결과 객체.

        Raises:
            ValueError: 전달된 후보 모델이 0개이거나 모든 모델이 하드/소프트 게이트에서 탈락한 경우 발생.
        """
        if not models:
            raise ValueError("[ChampionSelector] 평가할 후보 모델이 전달되지 않았습니다.")

        candidate_metrics: Dict[str, Dict[str, float]] = {}
        predictions_map: Dict[str, np.ndarray] = {}

        # 1. 전 후보 모델 10대 지표 수집
        for model_name, model_instance in models.items():
            model_metrics, preds = _collect_model_metrics(
                model=model_instance,
                X_test=X_test,
                y_test=y_test
            )
            candidate_metrics[model_name] = model_metrics
            predictions_map[model_name] = preds

        # 2. 전 후보 모델 감사 리포트 생성
        audit_report = get_score_report(
            candidates_metrics=candidate_metrics,
            hard_gate=self.hard_gate,
            soft_gate=self.soft_gate
        )

        # 3. 2단계 게이트 통과 모델 대상 복합 스코어 리더보드 산출
        leaderboard = get_score(
            candidates_metrics=candidate_metrics,
            hard_gate=self.hard_gate,
            soft_gate=self.soft_gate,
            weights=self.weights
        )

        # 4. 적격 모델 존재 여부 검증 (Fail-Fast 방어)
        if leaderboard.empty:
            raise ValueError(
                f"[ChampionSelector] 모든 후보 모델이 평가 게이트를 통과하지 못했습니다.\n"
                f"감사 리포트 확인 요망:\n{audit_report.to_string()}"
            )

        # 5. 1위 챔피언 모델 결정
        champion_name: str = str(leaderboard.index[0])
        champion_score: float = float(leaderboard.iloc[0]["composite_score"])
        champion_model_instance = models[champion_name]
        champion_raw_metrics = candidate_metrics[champion_name]

        return ChampionSelectionResult(
            champion_model_name=champion_name,
            champion_model=champion_model_instance,
            champion_composite_score=champion_score,
            champion_metrics=champion_raw_metrics,
            leaderboard=leaderboard,
            audit_report=audit_report
        )