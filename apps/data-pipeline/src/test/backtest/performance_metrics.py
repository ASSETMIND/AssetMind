from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# Constants & Configuration
# ==============================================================================
TRADING_DAYS_PER_YEAR: int = 252            # 연간 표준 영업일 수
DEFAULT_RISK_FREE_RATE: float = 0.0         # 기본 무위험 수익률 (연율화 0.0%)
EPSILON_NUMERICAL_STABILITY: float = 1e-12  # 영분모 방지를 위한 하한 상수
DEFAULT_NEWEY_WEST_LAG: int = 20            # Newey-West HAC 자기상관 보정 기본 시차 (20영업일)

COLUMN_STRATEGY_RETURN: str = "strategy_return"
COLUMN_NAV: str = "nav"
COLUMN_DRAWDOWN: str = "drawdown"
COLUMN_TURNOVER: str = "turnover"

STRATEGY_BENCHMARK_NAME: str = "Strategy 0 (Benchmark)"
STRATEGY_RAW_NAME: str = "Strategy 1 (Raw Model)"
STRATEGY_XAI_NAME: str = "Strategy 2 (XAI-Gated)"
COLUMN_DELTA_AUDIT: str = "XAI Delta (vs Raw)"

METRIC_TOTAL_RETURN: str = "Total Return (%)"
METRIC_CAGR: str = "CAGR (%)"
METRIC_ANNUAL_VOLATILITY: str = "Annualized Vol (%)"
METRIC_DOWNSIDE_DEV: str = "Downside Deviation (%)"
METRIC_SHARPE_RATIO: str = "Sharpe Ratio"
METRIC_SORTINO_RATIO: str = "Sortino Ratio"
METRIC_MAX_DRAWDOWN: str = "Maximum Drawdown (%)"
METRIC_CALMAR_RATIO: str = "Calmar Ratio"
METRIC_ANNUAL_TURNOVER: str = "Annual Turnover (x)"
METRIC_HAC_T_STAT: str = "Newey-West t-stat"
METRIC_HAC_P_VALUE: str = "Newey-West p-val"


# ==============================================================================
# Public API Functions
# ==============================================================================
def calculate_strategy_metrics(
    simulation_ledger: pd.DataFrame,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    newey_west_lag: int = DEFAULT_NEWEY_WEST_LAG,
) -> Dict[str, float]:
    """단일 전략의 시뮬레이션 원장으로부터 금융 퀀트 표준 위험조정 성과 지표를 산출합니다."""
    _validate_simulation_ledger(simulation_ledger)
    
    daily_returns: pd.Series = simulation_ledger[COLUMN_STRATEGY_RETURN]
    nav_series: pd.Series = simulation_ledger[COLUMN_NAV]
    drawdown_series: pd.Series = simulation_ledger[COLUMN_DRAWDOWN]
    turnover_series: pd.Series = simulation_ledger[COLUMN_TURNOVER]
    
    total_periods: int = len(daily_returns)
    daily_risk_free_rate: float = risk_free_rate / TRADING_DAYS_PER_YEAR

    total_return: float = _calculate_total_return(nav_series)
    cagr: float = _calculate_cagr(nav_series, total_periods)
    annualized_volatility: float = _calculate_annualized_volatility(daily_returns)
    downside_deviation: float = _calculate_downside_deviation(daily_returns, daily_risk_free_rate)
    sharpe_ratio: float = _calculate_sharpe_ratio(daily_returns, daily_risk_free_rate, annualized_volatility)
    sortino_ratio: float = _calculate_sortino_ratio(daily_returns, daily_risk_free_rate, downside_deviation)
    maximum_drawdown: float = _calculate_maximum_drawdown(drawdown_series)
    calmar_ratio: float = _calculate_calmar_ratio(cagr, maximum_drawdown)
    annual_turnover: float = _calculate_annual_turnover(turnover_series, total_periods)
    hac_t_stat, hac_p_val = _calculate_newey_west_hac_inference(daily_returns, newey_west_lag)

    return _assemble_metrics_dictionary(
        total_return=total_return,
        cagr=cagr,
        annualized_volatility=annualized_volatility,
        downside_deviation=downside_deviation,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        maximum_drawdown=maximum_drawdown,
        calmar_ratio=calmar_ratio,
        annual_turnover=annual_turnover,
        hac_t_stat=hac_t_stat,
        hac_p_val=hac_p_val,
    )


def evaluate_ablation_performance(
    simulation_ledgers: Dict[str, pd.DataFrame],
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    newey_west_lag: int = DEFAULT_NEWEY_WEST_LAG,
    include_delta_audit: bool = True,
) -> pd.DataFrame:
    """Ablation Study 3대 전략군의 성과를 일괄 평가하고 비교 감사표를 생성합니다."""
    _validate_ledgers_dictionary(simulation_ledgers)
    
    metrics_summary_table: Dict[str, Dict[str, float]] = {}
    for strategy_name, ledger in simulation_ledgers.items():
        metrics_summary_table[strategy_name] = calculate_strategy_metrics(
            simulation_ledger=ledger,
            risk_free_rate=risk_free_rate,
            newey_west_lag=newey_west_lag,
        )
        
    base_comparison_df: pd.DataFrame = _format_ablation_comparison_dataframe(metrics_summary_table)
    if include_delta_audit:
        return _append_ablation_delta_audit(base_comparison_df)
    return base_comparison_df


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_simulation_ledger(
    ledger: pd.DataFrame,
) -> None:
    """원장 데이터프레임의 결손 및 필수 회계 컬럼 존재 여부를 검증합니다."""
    if ledger is None or ledger.empty:
        raise ValueError("입력된 시뮬레이션 원장 데이터프레임이 비어 있습니다.")
    required_columns: List[str] = [
        COLUMN_STRATEGY_RETURN,
        COLUMN_NAV,
        COLUMN_DRAWDOWN,
        COLUMN_TURNOVER,
    ]
    missing_columns: List[str] = [col for col in required_columns if col not in ledger.columns]
    if missing_columns:
        raise ValueError(f"시뮬레이션 원장에 필수 컬럼이 누락되었습니다: {missing_columns}")


def _validate_ledgers_dictionary(
    ledgers_dict: Dict[str, pd.DataFrame],
) -> None:
    """Ablation 원장 딕셔너리의 유효성을 검증합니다."""
    if not ledgers_dict:
        raise ValueError("평가 대상 전략 원장 딕셔너리가 비어 있습니다.")


def _calculate_total_return(
    nav_series: pd.Series,
) -> float:
    """전체 운용 기간의 단순 누적 총수익률(%)을 산출합니다 (Base NAV = 1.0 기준)."""
    final_nav: float = float(nav_series.iloc[-1])
    return (final_nav - 1.0) * 100.0


def _calculate_cagr(
    nav_series: pd.Series,
    total_periods: int,
) -> float:
    """연율화 복리 수익률(CAGR, %)을 기하평균 방식으로 산출합니다 (Base NAV = 1.0 기준)."""
    if total_periods <= 0:
        return 0.0
    final_nav: float = float(nav_series.iloc[-1])
    wealth_ratio: float = max(final_nav, EPSILON_NUMERICAL_STABILITY)
    annualization_factor: float = TRADING_DAYS_PER_YEAR / total_periods
    return (float(wealth_ratio ** annualization_factor) - 1.0) * 100.0


def _calculate_annualized_volatility(
    daily_returns: pd.Series,
) -> float:
    """일간 수익률의 표본 표준편차를 연간 252영업일 기준으로 연율화(%)합니다."""
    daily_volatility: float = float(daily_returns.std(ddof=1))
    return daily_volatility * np.sqrt(TRADING_DAYS_PER_YEAR) * 100.0


def _calculate_downside_deviation(
    daily_returns: pd.Series,
    daily_risk_free_rate: float,
) -> float:
    """무위험 수익률을 하회하는 음의 편차만을 집계하여 연율화 하방 위험 변동성(%)을 산출합니다."""
    downside_excess: np.ndarray = np.minimum(0.0, daily_returns.to_numpy() - daily_risk_free_rate)
    downside_variance: float = float(np.mean(downside_excess ** 2))
    return np.sqrt(downside_variance) * np.sqrt(TRADING_DAYS_PER_YEAR) * 100.0


def _calculate_sharpe_ratio(
    daily_returns: pd.Series,
    daily_risk_free_rate: float,
    annualized_volatility_pct: float,
) -> float:
    """총 변동성 대비 연율화 초과수익 비율(Sharpe Ratio)을 산출합니다."""
    annualized_excess_return: float = (float(daily_returns.mean()) - daily_risk_free_rate) * TRADING_DAYS_PER_YEAR * 100.0
    denominator: float = max(annualized_volatility_pct, EPSILON_NUMERICAL_STABILITY)
    return annualized_excess_return / denominator


def _calculate_sortino_ratio(
    daily_returns: pd.Series,
    daily_risk_free_rate: float,
    downside_deviation_pct: float,
) -> float:
    """하방 변동성 대비 연율화 초과수익 비율(Sortino Ratio)을 산출합니다."""
    annualized_excess_return: float = (float(daily_returns.mean()) - daily_risk_free_rate) * TRADING_DAYS_PER_YEAR * 100.0
    denominator: float = max(downside_deviation_pct, EPSILON_NUMERICAL_STABILITY)
    return annualized_excess_return / denominator


def _calculate_maximum_drawdown(
    drawdown_series: pd.Series,
) -> float:
    """고점 대비 최대 자산 손실률(MDD, %)의 절댓값을 산출합니다."""
    min_drawdown: float = float(drawdown_series.min())
    return abs(min(0.0, min_drawdown)) * 100.0


def _calculate_calmar_ratio(
    cagr_pct: float,
    maximum_drawdown_pct: float,
) -> float:
    """최대 낙폭 대비 연율화 복리 수익률(Calmar Ratio)을 산출합니다."""
    denominator: float = max(maximum_drawdown_pct, EPSILON_NUMERICAL_STABILITY)
    return cagr_pct / denominator


def _calculate_annual_turnover(
    turnover_series: pd.Series,
    total_periods: int,
) -> float:
    """전체 포지션 전이량을 연간 단위로 환산한 연간 회전율(x)을 산출합니다."""
    if total_periods <= 0:
        return 0.0
    total_turnover: float = float(turnover_series.sum())
    annualization_factor: float = TRADING_DAYS_PER_YEAR / total_periods
    return total_turnover * annualization_factor


def _calculate_newey_west_hac_inference(
    daily_returns: pd.Series,
    max_lag: int,
) -> Tuple[float, float]:
    """Newey-West HAC 추정기를 활용하여 t-통계량과 p-value를 산출합니다."""
    return_values: np.ndarray = daily_returns.to_numpy(dtype=np.float64)
    sample_size: int = len(return_values)
    if sample_size <= max_lag + 1:
        return 0.0, 1.0

    mean_return: float = float(np.mean(return_values))
    demeaned_returns: np.ndarray = return_values - mean_return

    gamma_zero: float = float(np.sum(demeaned_returns ** 2) / sample_size)

    weighted_covariance_sum: float = 0.0
    for lag in range(1, max_lag + 1):
        bartlett_kernel_weight: float = 1.0 - (lag / (max_lag + 1))
        lagged_covariance: float = float(np.sum(demeaned_returns[lag:] * demeaned_returns[:-lag]) / sample_size)
        weighted_covariance_sum += 2.0 * bartlett_kernel_weight * lagged_covariance

    hac_variance: float = max(gamma_zero + weighted_covariance_sum, EPSILON_NUMERICAL_STABILITY)
    standard_error: float = np.sqrt(hac_variance / sample_size)

    t_statistic: float = mean_return / max(standard_error, EPSILON_NUMERICAL_STABILITY)
    degrees_of_freedom: int = sample_size - 1
    p_value: float = float(2.0 * (1.0 - stats.t.cdf(abs(t_statistic), df=degrees_of_freedom)))

    return t_statistic, p_value


def _assemble_metrics_dictionary(
    total_return: float,
    cagr: float,
    annualized_volatility: float,
    downside_deviation: float,
    sharpe_ratio: float,
    sortino_ratio: float,
    maximum_drawdown: float,
    calmar_ratio: float,
    annual_turnover: float,
    hac_t_stat: float,
    hac_p_val: float,
) -> Dict[str, float]:
    """산출된 메트릭 스칼라 값들을 표준 키-값 딕셔너리로 조립합니다."""
    return {
        METRIC_TOTAL_RETURN: round(total_return, 2),
        METRIC_CAGR: round(cagr, 2),
        METRIC_ANNUAL_VOLATILITY: round(annualized_volatility, 2),
        METRIC_DOWNSIDE_DEV: round(downside_deviation, 2),
        METRIC_SHARPE_RATIO: round(sharpe_ratio, 3),
        METRIC_SORTINO_RATIO: round(sortino_ratio, 3),
        METRIC_MAX_DRAWDOWN: round(maximum_drawdown, 2),
        METRIC_CALMAR_RATIO: round(calmar_ratio, 3),
        METRIC_ANNUAL_TURNOVER: round(annual_turnover, 2),
        METRIC_HAC_T_STAT: round(hac_t_stat, 3),
        METRIC_HAC_P_VALUE: float(f"{hac_p_val:.4e}"),
    }


def _format_ablation_comparison_dataframe(
    summary_dict: Dict[str, Dict[str, float]],
) -> pd.DataFrame:
    """개별 전략의 성과 딕셔너리를 감사용 비교 데이터프레임으로 변환합니다."""
    comparison_dataframe: pd.DataFrame = pd.DataFrame(summary_dict)
    comparison_dataframe.index.name = "Ablation Audit Metric"
    return comparison_dataframe


def _append_ablation_delta_audit(
    comparison_df: pd.DataFrame,
) -> pd.DataFrame:
    """Strategy 1(Raw ML) 대비 Strategy 2(XAI-Gated)의 개선폭(Delta)을 감사용으로 결합합니다."""
    augmented_df = comparison_df.copy()
    if STRATEGY_RAW_NAME in augmented_df.columns and STRATEGY_XAI_NAME in augmented_df.columns:
        raw_series = augmented_df[STRATEGY_RAW_NAME]
        xai_series = augmented_df[STRATEGY_XAI_NAME]
        
        delta_records: Dict[str, str] = {}
        for metric_name in augmented_df.index:
            raw_val = raw_series[metric_name]
            xai_val = xai_series[metric_name]
            diff = xai_val - raw_val
            
            # [수정] MDD 부호 역표기 및 오라벨 교정: 낙폭 축소 시 (방어), 확대 시 (확대)
            if "MDD" in metric_name or "Drawdown" in metric_name:
                if diff < 0:
                    delta_records[metric_name] = f"{diff:+.2f}%p (방어)"
                elif diff > 0:
                    delta_records[metric_name] = f"{diff:+.2f}%p (확대)"
                else:
                    delta_records[metric_name] = f"{diff:+.2f}%p"
            elif "Turnover" in metric_name:
                delta_records[metric_name] = f"{diff:+.2f}x (절감)" if diff < 0 else f"{diff:+.2f}x"
            elif "p-val" in metric_name:
                delta_records[metric_name] = "유의성 유지" if xai_val < 0.05 else "주의"
            elif "Ratio" in metric_name or "t-stat" in metric_name:
                delta_records[metric_name] = f"{diff:+.3f}"
            else:
                delta_records[metric_name] = f"{diff:+.2f}%p"
                
        augmented_df[COLUMN_DELTA_AUDIT] = pd.Series(delta_records)
    return augmented_df