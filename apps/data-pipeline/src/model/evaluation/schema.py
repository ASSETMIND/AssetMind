from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List
import pandas as pd


# ==============================================================================
# 1. 평가 계층 및 지표 표준 식별자 (Enums)
# ==============================================================================

class EvaluationLayer(str, Enum):
    """금융 ML 모델 평가 체계의 4대 계층 분류 식별자."""
    LAYER_1_ML_ERROR = "layer_1_ml_error"
    LAYER_2_FACTOR_QUALITY = "layer_2_factor_quality"
    LAYER_3_FINANCIAL_SIMULATION = "layer_3_financial_simulation"
    LAYER_4_STATISTICAL_SIGNIFICANCE = "layer_4_statistical_significance"


class EvaluationMetric(str, Enum):
    """10대 원자적 금융/통계 평가 지표의 표준 키(Canonical Key) 식별자.

    문자열 상속(str, Enum)을 통해 별도의 변환 없이 딕셔너리 키 및 직렬화 포맷으로 사용됩니다.
    """
    # Layer 1: 기계학습 기본 예측 오차 (Statistical Forecast Error)
    MDA = "mda"
    RMSE = "rmse"
    MAE = "mae"

    # Layer 2: 퀀트 팩터 신호 품질 (Quant Factor Signal Quality)
    RANK_IC = "rank_ic"
    ICIR = "icir"

    # Layer 3: 금융 시뮬레이션 성과 (Financial Strategy Simulation)
    SIGNAL_SHARPE = "signal_sharpe"
    SORTINO_RATIO = "sortino_ratio"
    MDD = "mdd"

    # Layer 4: 단일 신호 통계적 유의성 (Single-Model Signal Significance)
    FACTOR_T_STAT = "factor_t_stat"
    FACTOR_P_VAL = "factor_p_val"
    DSR = "deflated_sharpe_ratio"

@dataclass(frozen=True)
class OverfittingAuditResult:
    """모델의 검증(CV) 대비 테스트(Test) 일반화 열화 및 다중 시도 편향 감사 불변 DTO.

    Attributes:
        model_name (str): 평가 대상 모델 식별 명칭.
        gdr_score (float): 복합 스코어 일반화 열화율 (%).
        gdr_mdd (float): 최대 낙폭(MDD) 일반화 열화율 (%).
        rir (float): 잔차 팽창 비율 (RMSE_test / RMSE_cv).
        dsr (float): HPO 시도 횟수 보정 샤프 신뢰확률 ([0.0, 1.0]).
        is_passed (bool): 과적합 통제 게이트 전수 통과 여부.
        violations (List[str]): 과적합 임계치 위반 사유 리스트.
    """
    model_name: str
    gdr_score: float
    gdr_mdd: float
    rir: float
    dsr: float
    is_passed: bool
    violations: List[str]


# ==============================================================================
# 2. 지표 메타데이터 불변 DTO 및 전역 단일 진실 공급원(SSOT) 레지스트리
# ==============================================================================

@dataclass(frozen=True)
class MetricMetadata:
    """단일 평가 지표의 고유 속성 및 정규화 방향성을 캡슐화한 불변 메타데이터 DTO.

    Attributes:
        metric (EvaluationMetric): 평가 지표 표준 식별자.
        layer (EvaluationLayer): 소속된 평가 계층.
        is_greater_better (bool): 지표 수치가 클수록 우수한지 여부 (정규화/점수화 방향 결정).
        display_name (str): 리포팅 및 시각화용 공식 명칭.
        description (str): 지표에 대한 수리/금융적 정의.
    """
    metric: EvaluationMetric
    layer: EvaluationLayer
    is_greater_better: bool
    display_name: str
    description: str


# 지표별 계층 소속 및 스코어링 방향성(is_greater_better)을 단일 지점에서 선언하여,
# composite_score.py나 criteria.py에서 if/else 하드코딩 없이 O(1) 참조하도록 구성
METRIC_REGISTRY: Dict[EvaluationMetric, MetricMetadata] = {
    EvaluationMetric.MDA: MetricMetadata(
        metric=EvaluationMetric.MDA,
        layer=EvaluationLayer.LAYER_1_ML_ERROR,
        is_greater_better=True,
        display_name="MDA",
        description="평균 방향성 적중률 (Mean Directional Accuracy)",
    ),
    EvaluationMetric.RMSE: MetricMetadata(
        metric=EvaluationMetric.RMSE,
        layer=EvaluationLayer.LAYER_1_ML_ERROR,
        is_greater_better=False,
        display_name="RMSE",
        description="평균 제곱근 오차 (Root Mean Squared Error)",
    ),
    EvaluationMetric.MAE: MetricMetadata(
        metric=EvaluationMetric.MAE,
        layer=EvaluationLayer.LAYER_1_ML_ERROR,
        is_greater_better=False,
        display_name="MAE",
        description="평균 절대 오차 (Mean Absolute Error)",
    ),
    EvaluationMetric.RANK_IC: MetricMetadata(
        metric=EvaluationMetric.RANK_IC,
        layer=EvaluationLayer.LAYER_2_FACTOR_QUALITY,
        is_greater_better=True,
        display_name="Rank IC",
        description="스피어만 순위 정보 계수 (Spearman Rank Information Coefficient)",
    ),
    EvaluationMetric.ICIR: MetricMetadata(
        metric=EvaluationMetric.ICIR,
        layer=EvaluationLayer.LAYER_2_FACTOR_QUALITY,
        is_greater_better=True,
        display_name="ICIR",
        description="팩터 정보 비율 (Information Coefficient Information Ratio)",
    ),
    EvaluationMetric.SIGNAL_SHARPE: MetricMetadata(
        metric=EvaluationMetric.SIGNAL_SHARPE,
        layer=EvaluationLayer.LAYER_3_FINANCIAL_SIMULATION,
        is_greater_better=True,
        display_name="Signal Sharpe",
        description="신호 기반 연율화 샤프 지수",
    ),
    EvaluationMetric.SORTINO_RATIO: MetricMetadata(
        metric=EvaluationMetric.SORTINO_RATIO,
        layer=EvaluationLayer.LAYER_3_FINANCIAL_SIMULATION,
        is_greater_better=True,
        display_name="Sortino Ratio",
        description="하방 변동성 통제 연율화 소르티노 지수",
    ),
    EvaluationMetric.MDD: MetricMetadata(
        metric=EvaluationMetric.MDD,
        layer=EvaluationLayer.LAYER_3_FINANCIAL_SIMULATION,
        is_greater_better=False,
        display_name="MDD",
        description="최대 낙폭 비율 (Maximum Drawdown)",
    ),
    EvaluationMetric.FACTOR_T_STAT: MetricMetadata(
        metric=EvaluationMetric.FACTOR_T_STAT,
        layer=EvaluationLayer.LAYER_4_STATISTICAL_SIGNIFICANCE,
        is_greater_better=True,
        display_name="Factor t-stat",
        description="Newey-West HAC 보정 t-통계량",
    ),
    EvaluationMetric.FACTOR_P_VAL: MetricMetadata(
        metric=EvaluationMetric.FACTOR_P_VAL,
        layer=EvaluationLayer.LAYER_4_STATISTICAL_SIGNIFICANCE,
        is_greater_better=False,
        display_name="Factor p-val",
        description="단일 알파 유의성 p-값 (양측 검정)",
    ),
    EvaluationMetric.DSR: MetricMetadata(
        metric=EvaluationMetric.DSR,
        layer=EvaluationLayer.LAYER_4_STATISTICAL_SIGNIFICANCE,
        is_greater_better=True,
        display_name="DSR",
        description="다중 시도 편향 보정 샤프 비율 (Deflated Sharpe Ratio)",
    )
}


# ==============================================================================
# 3. 평가 실행 결과 캡슐화 불변 DTO (Evaluation Result)
# ==============================================================================

@dataclass(frozen=True)
class EvaluationResult:
    """단일 모델의 추론 및 지표 산출 결과를 캡슐화하는 불변 DTO.

    Attributes:
        model_name (str): 평가 대상 모델 식별 명칭.
        predictions (pd.Series): 테스트 셋에 대한 1차원 추론 결과 시리즈 (DatetimeIndex 보존).
        metrics (Dict[EvaluationMetric, float]): 10대 표준 평가 지표 결과 딕셔너리.
        composite_score (float): 4대 계층 가중치가 반영된 복합 스코어.
        evaluated_at (str): 평가 집행 시각 타임스탬프 (ISO 8601 포맷).
    """
    model_name: str
    predictions: pd.Series
    metrics: Dict[EvaluationMetric, float]
    composite_score: float
    evaluated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def get_metric(self, metric: EvaluationMetric) -> float:
        """지정된 표준 지표 값을 반환합니다. 누락 시 0.0을 반환합니다."""
        return self.metrics.get(metric, 0.0)

    def to_dict(self) -> Dict[str, float]:
        """직렬화 및 로깅을 위해 지표 키를 문자열로 매핑한 딕셔너리를 반환합니다."""
        return {metric.value: score for metric, score in self.metrics.items()}