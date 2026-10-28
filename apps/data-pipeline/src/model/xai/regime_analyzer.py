from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

from src.model.xai.shap_schema import (
    PERCENTAGE_MULTIPLIER,
    RegimeCohortResult,
    create_regime_cohort_result,
)


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 시장 국면 코호트 분할 임계 설정
DEFAULT_REGIME_PERCENTILE_THRESHOLD: float = 0.20  # 시장 급등/급락 및 극단 국면 분위수 임계치
DEFAULT_NORMAL_SIGMA_BOUND: float = 0.5            # 평시 안정 국면 표준편차 경계 배수

# 모델 스탠스 및 신호 정합성 판정 설정
DEFAULT_LONG_BIAS_THRESHOLD: float = 0.05          # 모델 Long 스탠스 판정 임계치
DEFAULT_SHORT_BIAS_THRESHOLD: float = -0.05        # 모델 Short 스탠스 판정 임계치
DEFAULT_ALIGNMENT_MIN_PREDICTION: float = 0.03     # 신호 정합성 판정용 최소 유의 예측 강도 임계치


# ==============================================================================
# Public API Functions
# ==============================================================================
class RegimeCohortAnalyzer:
    """5대 시장 국면별 코호트 마스킹, 피처 기여도 집계 및 신호 정합성 감사 분석기.

    Attributes:
        percentile_threshold (float): 시장 급등/급락 및 극단 국면 분위수 임계치.
        normal_sigma_bound (float): 평시 안정 국면 표준편차 배수.
    """

    def __init__(
        self,
        percentile_threshold: float = DEFAULT_REGIME_PERCENTILE_THRESHOLD,
        normal_sigma_bound: float = DEFAULT_NORMAL_SIGMA_BOUND,
    ) -> None:
        """RegimeCohortAnalyzer 인스턴스를 초기화합니다.

        Args:
            percentile_threshold (float): 국면 분위수 임계치. Defaults to DEFAULT_REGIME_PERCENTILE_THRESHOLD.
            normal_sigma_bound (float): 평시 표준편차 배수. Defaults to DEFAULT_NORMAL_SIGMA_BOUND.
        """
        # 시장 국면 분할용 임계 파라미터 상태 유지
        self.percentile_threshold: float = percentile_threshold
        self.normal_sigma_bound: float = normal_sigma_bound

    def analyze_cohorts(
        self,
        y_true: pd.Series,
        y_pred: pd.Series,
        shap_df: pd.DataFrame,
    ) -> RegimeCohortResult:
        """5대 시장 국면별 코호트를 마스킹하고 정량 감사표 및 평균 SHAP DTO를 산출합니다.

        Args:
            y_true (pd.Series): 실측 목표 수익률 시계열.
            y_pred (pd.Series): 모델 예측값 시계열.
            shap_df (pd.DataFrame): 평가 표본에 대한 피처별 SHAP 기여도 행렬.

        Returns:
            RegimeCohortResult: 5대 시장 국면 감사표 및 평균 기여도가 담긴 불변 DTO.

        Raises:
            ValueError: 입력 시계열 간 유효 인덱스 교집합이 존재하지 않을 경우 발생.
        """
        # 1. 내장 코호트 감사 알고리즘을 통해 국면별 감사표 및 평균 SHAP 통계량 산출
        audit_dataframe, mean_shap_dataframe, mean_predictions, sample_counts = _audit_regime_cohorts(
            y_true=y_true,
            y_pred=y_pred,
            shap_dataframe=shap_df,
            percentile_threshold=self.percentile_threshold,
            normal_sigma_bound=self.normal_sigma_bound,
        )

        # 2. 시장 국면 코호트 결과 불변 DTO 조립 및 반환
        return create_regime_cohort_result(
            regime_audit_dataframe=audit_dataframe,
            regime_mean_shap_dataframe=mean_shap_dataframe,
            regime_mean_predictions=mean_predictions,
            regime_sample_counts=sample_counts,
        )


def compute_historical_drawdown(
    realized_returns: pd.Series,
) -> pd.Series:
    """과거 실측 수익률 기반의 고점 대비 낙폭(Historical Drawdown) 시계열을 산출하는 공개 함수.

    Args:
        realized_returns (pd.Series): 실측 수익률 시계열.

    Returns:
        pd.Series: 고점 대비 낙폭(Historical Drawdown) 시계열.
    """
    # 내장 낙폭 연산 함수를 호출하여 시계열 반환
    return _calculate_historical_drawdown(realized_returns=realized_returns)


def run_robust_regime_cohort_audit(
    y_true: pd.Series,
    y_pred: pd.Series,
    shap_df: pd.DataFrame,
    percentile_threshold: float = DEFAULT_REGIME_PERCENTILE_THRESHOLD,
    normal_sigma_bound: float = DEFAULT_NORMAL_SIGMA_BOUND,
) -> pd.DataFrame:
    """표본 중복을 허용한 5대 시장 국면별 집계 감사표를 생성하는 공개 함수.

    Args:
        y_true (pd.Series): 실측 수익률 시계열.
        y_pred (pd.Series): 모델 예측치 시계열.
        shap_df (pd.DataFrame): 피처별 SHAP 기여도 행렬.
        percentile_threshold (float): 국면 분위수 임계치. Defaults to DEFAULT_REGIME_PERCENTILE_THRESHOLD.
        normal_sigma_bound (float): 평시 표준편차 배수. Defaults to DEFAULT_NORMAL_SIGMA_BOUND.

    Returns:
        pd.DataFrame: 5대 시장 국면별 정량 감사 데이터프레임.

    Raises:
        ValueError: 입력 시계열 간 공통 인덱스가 없을 경우 발생.
    """
    # 국면 분석기 구동 후 요약 감사 데이터프레임만 추출하여 반환
    result = analyze_regime_cohorts(
        y_true=y_true,
        y_pred=y_pred,
        shap_df=shap_df,
        percentile_threshold=percentile_threshold,
        normal_sigma_bound=normal_sigma_bound,
    )
    return result.regime_audit_dataframe


def analyze_regime_cohorts(
    y_true: pd.Series,
    y_pred: pd.Series,
    shap_df: pd.DataFrame,
    percentile_threshold: float = DEFAULT_REGIME_PERCENTILE_THRESHOLD,
    normal_sigma_bound: float = DEFAULT_NORMAL_SIGMA_BOUND,
) -> RegimeCohortResult:
    """5대 시장 국면 코호트 감사를 집행하고 종합 DTO를 사출하는 공개 함수.

    Args:
        y_true (pd.Series): 실측 수익률 시계열.
        y_pred (pd.Series): 모델 예측치 시계열.
        shap_df (pd.DataFrame): 피처별 SHAP 기여도 행렬.
        percentile_threshold (float): 국면 분위수 임계치. Defaults to DEFAULT_REGIME_PERCENTILE_THRESHOLD.
        normal_sigma_bound (float): 평시 표준편차 배수. Defaults to DEFAULT_NORMAL_SIGMA_BOUND.

    Returns:
        RegimeCohortResult: 국면 감사표 및 평균 SHAP 행렬이 포함된 불변 DTO.

    Raises:
        ValueError: 입력 시계열 간 공통 인덱스가 없을 경우 발생.
    """
    # 분석기 인스턴스 생성 및 코호트 감사 위임
    analyzer = RegimeCohortAnalyzer(
        percentile_threshold=percentile_threshold,
        normal_sigma_bound=normal_sigma_bound,
    )
    return analyzer.analyze_cohorts(
        y_true=y_true,
        y_pred=y_pred,
        shap_df=shap_df,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _align_regime_inputs(
    y_true: pd.Series,
    y_pred: pd.Series,
    shap_dataframe: pd.DataFrame,
) -> Tuple[pd.Series, pd.Series, pd.DataFrame]:
    """실측 타깃, 예측값, SHAP 데이터프레임 간의 공통 시계열 인덱스를 검증하고 정렬합니다."""
    # 세 입력 객체의 교집합 인덱스 산출 및 빈 인덱스 방어
    common_index = shap_dataframe.index.intersection(y_true.index).intersection(y_pred.index)
    if len(common_index) == 0:
        raise ValueError("[_align_regime_inputs] 유효한 공통 시계열 인덱스가 존재하지 않습니다.")

    return (
        y_true.loc[common_index],
        y_pred.loc[common_index],
        shap_dataframe.loc[common_index],
    )


def _calculate_historical_drawdown(
    realized_returns: pd.Series,
) -> pd.Series:
    """단순 합산 기준 롤링 누적 수익률 기반 역사적 고점 대비 낙폭 시계열을 연산합니다."""
    # 누적 수익률과 누적 최고점(Rolling Peak) 간의 차분 계산
    rolling_cumulative = realized_returns.cumsum()
    rolling_peak = rolling_cumulative.cummax()
    return rolling_cumulative - rolling_peak


def _identify_regime_cohort_indices(
    y_true: pd.Series,
    y_pred: pd.Series,
    historical_drawdown: pd.Series,
    percentile_threshold: float,
    normal_sigma_bound: float,
) -> List[Tuple[str, pd.Index]]:
    """실측 수익률, 모델 예측 및 역사적 낙폭으로부터 5대 시장 국면 인덱스를 분할합니다."""
    # 1. 모델 실현 손익(PnL) 및 실측 수익률 중심/산포 통계량 계산
    model_realized_pnl = np.sign(y_pred) * y_true
    return_std = float(y_true.std())
    return_mean = float(y_true.mean())

    # 2. 5대 시장 국면별 조건 마스킹 및 해당 거래일 인덱스 추출
    normal_index = y_true[
        (y_true >= return_mean - normal_sigma_bound * return_std)
        & (y_true <= return_mean + normal_sigma_bound * return_std)
    ].index
    market_bull_index = y_true[
        y_true >= y_true.quantile(1.0 - percentile_threshold)
    ].index
    peak_alpha_index = model_realized_pnl[
        model_realized_pnl >= model_realized_pnl.quantile(1.0 - percentile_threshold)
    ].index
    market_bear_index = y_true[
        y_true <= y_true.quantile(percentile_threshold)
    ].index
    mdd_stress_index = historical_drawdown[
        historical_drawdown <= historical_drawdown.quantile(percentile_threshold)
    ].index

    return [
        ("Normal", normal_index),
        ("Market Bull", market_bull_index),
        ("Peak Model Alpha", peak_alpha_index),
        ("Market Bear", market_bear_index),
        ("Historical MDD Stress", mdd_stress_index),
    ]


def _calculate_cohort_factor_rankings(
    cohort_shap: pd.DataFrame,
) -> Tuple[str, float, float, str, float, float]:
    """부호 상쇄 왜곡을 방어한 평균 절대 기여도 기준 상위 1위 및 2위 팩터를 도출합니다."""
    # 1. 피처별 부호 보존 평균/표준편차 및 평균 절대 SHAP 기준 내림차순 정렬
    factor_mean_shaps = cohort_shap.mean(axis=0)
    factor_std_shaps = cohort_shap.std(axis=0)
    sorted_factors = cohort_shap.abs().mean(axis=0).sort_values(ascending=False)

    # 2. 1위 주도 팩터 및 기여도 통계량 추출
    top1_factor = str(sorted_factors.index[0])
    top1_impact = float(factor_mean_shaps[top1_factor])
    top1_std = (
        float(factor_std_shaps[top1_factor])
        if not np.isnan(factor_std_shaps[top1_factor])
        else 0.0
    )

    # 3. 2위 주도 팩터 존재 시 추출 (단일 피처일 경우 기본값 처리)
    if len(sorted_factors) > 1:
        top2_factor = str(sorted_factors.index[1])
        top2_impact = float(factor_mean_shaps[top2_factor])
        top2_std = (
            float(factor_std_shaps[top2_factor])
            if not np.isnan(factor_std_shaps[top2_factor])
            else 0.0
        )
    else:
        top2_factor = "-"
        top2_impact = 0.0
        top2_std = 0.0

    return top1_factor, top1_impact, top1_std, top2_factor, top2_impact, top2_std


def _calculate_effective_code_synchrony(
    cohort_shap: pd.DataFrame,
) -> float:
    """국면 표본에 대한 팩터 기여도의 정량적 신호 일치도(ECS) 평균을 연산합니다."""
    # 개별 관측일의 절대 기여도 합 대비 순 기여도 합의 비율(|Σ SHAP| / Σ |SHAP|) 산출
    abs_shap_sum = cohort_shap.abs().sum(axis=1)
    net_shap_sum = cohort_shap.sum(axis=1).abs()
    ecs_series = np.where(abs_shap_sum > 0.0, net_shap_sum / abs_shap_sum, 1.0)
    return float(np.mean(ecs_series))


def _determine_model_stance(
    mean_prediction: float,
) -> str:
    """모델 평균 예측 강도에 따른 국면별 포지션 스탠스를 판정합니다."""
    # Long/Short 편향 임계치 기준 포지션 방향성 라벨 반환
    if mean_prediction > DEFAULT_LONG_BIAS_THRESHOLD:
        return f"Long 편향 (+{mean_prediction:.3f})"
    if mean_prediction < DEFAULT_SHORT_BIAS_THRESHOLD:
        return f"Short 편향 ({mean_prediction:.3f})"
    return f"Neutral ({mean_prediction:.3f})"


def _evaluate_signal_alignment(
    mean_target: float,
    mean_prediction: float,
) -> str:
    """모델 예측 방향과 실측 시장 방향 간의 유의미한 정합성을 진단합니다."""
    # 부호 일치 여부 및 최소 유의 예측 강도 초과 여부 검증
    is_aligned = (np.sign(mean_target) == np.sign(mean_prediction)) and (
        abs(mean_prediction) > DEFAULT_ALIGNMENT_MIN_PREDICTION
    )
    return "정합 (Hit)" if is_aligned else "괴리 (Divergence)"


def _evaluate_single_regime_cohort(
    regime_name: str,
    cohort_y_true: pd.Series,
    cohort_y_pred: pd.Series,
    cohort_shap: pd.DataFrame,
    total_samples: int,
) -> Tuple[Dict[str, Any], pd.Series, float, int]:
    """단일 시장 국면 코호트의 주도 팩터, ECS, 정합성 지표를 연산하고 감사 레코드를 생성합니다."""
    # 1. 코호트 내 주도 팩터 순위(1·2위) 및 신호 일치도(ECS) 산출
    top1_factor, top1_impact, top1_std, top2_factor, top2_impact, top2_std = (
        _calculate_cohort_factor_rankings(cohort_shap=cohort_shap)
    )
    mean_ecs = _calculate_effective_code_synchrony(cohort_shap=cohort_shap)

    # 2. 코호트 평균 예측/실측 수익률 및 모델 스탠스, 신호 정합성 판정
    sample_count = len(cohort_shap)
    mean_prediction = float(cohort_y_pred.mean())
    mean_target = float(cohort_y_true.mean())
    model_stance = _determine_model_stance(mean_prediction=mean_prediction)
    alignment_status = _evaluate_signal_alignment(
        mean_target=mean_target,
        mean_prediction=mean_prediction,
    )

    # 3. 국면 감사 요약 레코드 조립 및 원시 통계량 반환
    sample_ratio_pct = (sample_count / total_samples) * PERCENTAGE_MULTIPLIER
    audit_record: Dict[str, Any] = {
        "시장 국면 (Regime)": regime_name,
        "표본 수 (N)": f"{sample_count}일",
        "비율 (%)": f"{sample_ratio_pct:.1f}%",
        "실측 수익률 (Mean y)": f"{mean_target:+.4f}",
        "모델 예측치 (Mean f(x))": f"{mean_prediction:+.4f}",
        "모델 스탠스": model_stance,
        "신호 정합성": alignment_status,
        "주도 팩터 1위": top1_factor,
        "1위 기여도": f"{top1_impact:+.4f} (±{top1_std:.4f})",
        "주도 팩터 2위": top2_factor,
        "2위 기여도": f"{top2_impact:+.4f} (±{top2_std:.4f})",
        "신호 일치도 (ECS)": f"{mean_ecs:.3f}",
    }

    return audit_record, cohort_shap.mean(axis=0), mean_prediction, sample_count


def _audit_regime_cohorts(
    y_true: pd.Series,
    y_pred: pd.Series,
    shap_dataframe: pd.DataFrame,
    percentile_threshold: float,
    normal_sigma_bound: float,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float], Dict[str, int]]:
    """5대 시장 국면별 집계 감사표, 평균 SHAP 행렬 및 상태 통계량을 전수 산출합니다."""
    # 1. 입력 시계열 간 공통 인덱스 정렬 및 역사적 낙폭(Drawdown) 산출
    aligned_y_true, aligned_y_pred, aligned_shap = _align_regime_inputs(
        y_true=y_true,
        y_pred=y_pred,
        shap_dataframe=shap_dataframe,
    )
    historical_drawdown = _calculate_historical_drawdown(realized_returns=aligned_y_true)

    # 2. 5대 시장 국면별 해당 거래일 인덱스 분할
    regimes = _identify_regime_cohort_indices(
        y_true=aligned_y_true,
        y_pred=aligned_y_pred,
        historical_drawdown=historical_drawdown,
        percentile_threshold=percentile_threshold,
        normal_sigma_bound=normal_sigma_bound,
    )

    # 3. 각 시장 국면 코호트별 통계량 집계 및 감사 레코드 수집
    audit_records: List[Dict[str, Any]] = []
    mean_shap_records: Dict[str, pd.Series] = {}
    mean_predictions: Dict[str, float] = {}
    sample_counts: Dict[str, int] = {}
    total_samples = len(aligned_shap)

    for regime_name, cohort_index in regimes:
        valid_index = aligned_shap.index.intersection(cohort_index)
        if len(valid_index) == 0:
            continue

        record, mean_shap_series, mean_pred, count = _evaluate_single_regime_cohort(
            regime_name=regime_name,
            cohort_y_true=aligned_y_true.loc[valid_index],
            cohort_y_pred=aligned_y_pred.loc[valid_index],
            cohort_shap=aligned_shap.loc[valid_index],
            total_samples=total_samples,
        )
        audit_records.append(record)
        mean_shap_records[regime_name] = mean_shap_series
        mean_predictions[regime_name] = mean_pred
        sample_counts[regime_name] = count

    # 4. 최종 국면 감사 데이터프레임 및 국면별 평균 SHAP 행렬 변환
    audit_dataframe = pd.DataFrame(audit_records).set_index("시장 국면 (Regime)")
    mean_shap_dataframe = pd.DataFrame(mean_shap_records).T

    return audit_dataframe, mean_shap_dataframe, mean_predictions, sample_counts