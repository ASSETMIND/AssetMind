from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.dataset.benchmark_provider import fetch_kospi_benchmark_series

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_INITIAL_CAPITAL: float = 100_000_000.0  # 기본 초기 투자 원금 (1억 원)
DEFAULT_ROUND_TRIP_COST: float = 0.0025         # 편도 비용 분할 적용을 위한 기준 왕복 거래비용 비율 (25 bps)
DEFAULT_RETURN_HORIZON_DAYS: int = 20           # 타깃 수익률의 기본 만기 기간 (20영업일)

POSITION_LONG: float = 1.0                      # 주식 100% 보유 상태
POSITION_FLAT: float = 0.0                      # 현금 100% 보유 상태 (포지션 비보유)

ACTION_BUY: str = "BUY"                         # 매수 진입 주문 액션
ACTION_HOLD: str = "HOLD"                       # 기존 상태 유지 액션
ACTION_SELL: str = "SELL"                       # 매도 청산 주문 액션

STRATEGY_BENCHMARK: str = "Strategy 0 (Benchmark)"    # KOSPI 단순 보유 기준선
STRATEGY_RAW_MODEL: str = "Strategy 1 (Raw Model)"    # 순수 ML 원시 예측 전략
STRATEGY_XAI_GATED: str = "Strategy 2 (XAI-Gated)"    # XAI 리스크 거버넌스 탑재 전략


# ==============================================================================
# Public API Functions
# ==============================================================================
class BacktestSimulationEngine:
    """롱온리 현물 주식 포트폴리오의 상태 전이 및 거래비용 정산 회계를 총괄하는 시뮬레이션 엔진 클래스입니다."""

    def __init__(
        self,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        round_trip_cost: float = DEFAULT_ROUND_TRIP_COST,
        return_horizon_days: int = DEFAULT_RETURN_HORIZON_DAYS,
    ) -> None:
        """시뮬레이션 엔진 인스턴스를 초기화합니다."""
        _validate_positive_scalar(initial_capital, "initial_capital")
        _validate_non_negative_scalar(round_trip_cost, "round_trip_cost")
        self.initial_capital: float = initial_capital
        self.round_trip_cost: float = round_trip_cost
        self.return_horizon_days: int = return_horizon_days

    def simulate(
        self,
        action_series: pd.Series,
        price_series: Optional[pd.Series] = None,
        target_returns: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """단일 거래 전략의 액션 시퀀스에 대해 포트폴리오 시뮬레이션을 수행합니다."""
        prices, asset_returns = _resolve_asset_series(
            action_index=action_series.index,
            price_series=price_series,
            target_returns=target_returns,
            return_horizon_days=self.return_horizon_days,
            initial_capital=self.initial_capital,
        )
        return _run_single_simulation_pipeline(
            prices=prices,
            asset_returns=asset_returns,
            action_series=action_series,
            round_trip_cost=self.round_trip_cost,
            initial_capital=self.initial_capital,
        )

    def simulate_benchmark(
        self,
        reference_index: pd.Index,
        price_series: Optional[pd.Series] = None,
        target_returns: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """기초자산 전 구간 단순 보유(Buy & Hold) 벤치마크 시뮬레이션을 수행합니다."""
        benchmark_actions: pd.Series = _generate_benchmark_action_sequence(reference_index)
        return self.simulate(
            action_series=benchmark_actions,
            price_series=price_series,
            target_returns=target_returns,
        )

    def simulate_ablation_study(
        self,
        raw_model_actions: pd.Series,
        xai_gated_actions: pd.Series,
        price_series: Optional[pd.Series] = None,
        target_returns: Optional[pd.Series] = None,
    ) -> Dict[str, pd.DataFrame]:
        """소거 연구(Ablation Study) 3대 전략군(BM, Raw ML, XAI-Gated)을 일괄 시뮬레이션합니다."""
        _validate_input_series_alignment(raw_model_actions, xai_gated_actions, "xai_gated_actions")
        reference_index: pd.Index = raw_model_actions.index

        benchmark_ledger: pd.DataFrame = self.simulate_benchmark(
            reference_index=reference_index,
            price_series=price_series,
            target_returns=target_returns,
        )
        raw_model_ledger: pd.DataFrame = self.simulate(
            action_series=raw_model_actions,
            price_series=price_series,
            target_returns=target_returns,
        )
        xai_gated_ledger: pd.DataFrame = self.simulate(
            action_series=xai_gated_actions,
            price_series=price_series,
            target_returns=target_returns,
        )

        return {
            STRATEGY_BENCHMARK: benchmark_ledger,
            STRATEGY_RAW_MODEL: raw_model_ledger,
            STRATEGY_XAI_GATED: xai_gated_ledger,
        }


def summarize_simulation_ledgers(
    simulation_ledgers: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """3대 전략의 시뮬레이션 회계 원장으로부터 주요 성과 요약 비교표를 도출합니다."""
    if not simulation_ledgers:
        raise ValueError("요약 대상 시뮬레이션 원장 딕셔너리가 비어 있습니다.")
    return _format_simulation_summary_table(simulation_ledgers)


def run_ablation_simulation(
    raw_model_actions: pd.Series,
    xai_gated_actions: pd.Series,
    price_series: Optional[pd.Series] = None,
    target_returns: Optional[pd.Series] = None,
    round_trip_cost: float = DEFAULT_ROUND_TRIP_COST,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    return_horizon_days: int = DEFAULT_RETURN_HORIZON_DAYS,
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """3대 전략 시뮬레이션과 요약 감사표 생성을 일괄 완결하는 파사드 함수입니다."""
    engine = BacktestSimulationEngine(
        initial_capital=initial_capital,
        round_trip_cost=round_trip_cost,
        return_horizon_days=return_horizon_days,
    )
    ledgers: Dict[str, pd.DataFrame] = engine.simulate_ablation_study(
        raw_model_actions=raw_model_actions,
        xai_gated_actions=xai_gated_actions,
        price_series=price_series,
        target_returns=target_returns,
    )
    summary_table: pd.DataFrame = summarize_simulation_ledgers(ledgers)
    return ledgers, summary_table


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_positive_scalar(
    scalar_value: float,
    variable_name: str,
) -> None:
    """실수형 파라미터의 양수 여부를 검증합니다."""
    if scalar_value <= 0.0:
        raise ValueError(f"{variable_name} 값({scalar_value})은 0보다 커야 합니다.")


def _validate_non_negative_scalar(
    scalar_value: float,
    variable_name: str,
) -> None:
    """실수형 파라미터의 음수 여부를 검증합니다."""
    if scalar_value < 0.0:
        raise ValueError(f"{variable_name} 값({scalar_value})은 0 이상이어야 합니다.")


def _validate_series_not_empty(
    series: pd.Series,
    variable_name: str,
) -> None:
    """시계열 객체의 공백 및 결손 여부를 검증합니다."""
    if series is None or series.empty:
        raise ValueError(f"입력된 {variable_name} 시계열이 비어 있습니다.")


def _validate_input_series_alignment(
    primary_series: pd.Series,
    secondary_series: pd.Series,
    secondary_name: str,
) -> None:
    """두 시계열의 인덱스 일치 여부를 검증합니다."""
    _validate_series_not_empty(primary_series, "primary_series")
    _validate_series_not_empty(secondary_series, secondary_name)
    if not primary_series.index.equals(secondary_series.index):
        raise ValueError(f"입력 시계열과 {secondary_name} 간의 날짜 인덱스가 일치하지 않습니다.")


def _resolve_asset_series(
    action_index: pd.Index,
    price_series: Optional[pd.Series],
    target_returns: Optional[pd.Series],
    return_horizon_days: int,
    initial_capital: float,
) -> Tuple[pd.Series, pd.Series]:
    """종가 시계열 또는 타깃 수익률로부터 일간 자산 수익률과 가격 시계열을 도출합니다."""
    # 1. 외부에서 직접 주입된 가격 시계열이 있는 경우 우선 정렬
    if price_series is not None and not price_series.empty:
        prices = price_series.reindex(action_index).ffill().bfill()
        asset_returns = prices.pct_change().fillna(0.0)
        return prices.rename("price"), asset_returns.rename("asset_return")

    # 2. 가격 시계열 부재 시 benchmark_provider를 호출하여 실제 KOSPI 수집
    try:
        kospi_benchmark_series = fetch_kospi_benchmark_series(evaluation_index=action_index)
        if kospi_benchmark_series is not None and not kospi_benchmark_series.empty:
            prices = kospi_benchmark_series.reindex(action_index).ffill().bfill()
            asset_returns = prices.pct_change().fillna(0.0)
            return prices.rename("price"), asset_returns.rename("asset_return")
    except Exception:
        pass

    # 3. 실측 타깃 수익률 기반 복원 (수정: % 스케일 정규화 및 20일 복리 분해)
    if target_returns is not None and not target_returns.empty:
        aligned_returns = target_returns.reindex(action_index).fillna(0.0)
        
        # [설계 의도] 타깃 수익률이 % 단위(평균 절댓값 0.05 초과)인 경우 소수점 비율(decimal)로 정규화
        is_percentage_scale: bool = float(aligned_returns.abs().mean()) > 0.05 or float(aligned_returns.abs().max()) > 1.0
        normalized_returns: pd.Series = aligned_returns / 100.0 if is_percentage_scale else aligned_returns.copy()
        
        # 20영업일 누적 수익률인 경우 일간 복리 등가 수익률로 정밀 분해: (1 + R)^(1/N) - 1
        if "20" in str(aligned_returns.name) or return_horizon_days > 1:
            clamped_returns = np.maximum(-0.999, normalized_returns.to_numpy())
            daily_return_values = np.sign(clamped_returns) * (np.abs(1.0 + clamped_returns) ** (1.0 / float(return_horizon_days)) - 1.0)
            daily_returns = pd.Series(daily_return_values, index=action_index, name="asset_return")
        else:
            daily_returns = normalized_returns.rename("asset_return")
            
        reconstructed_prices = (1.0 + daily_returns).cumprod() * initial_capital
        return reconstructed_prices.rename("price"), daily_returns.rename("asset_return")

    raise ValueError("KOSPI 가격 데이터를 수집할 수 없으며 대체 타깃 수익률도 제공되지 않았습니다.")


def _generate_benchmark_action_sequence(
    date_index: pd.Index,
) -> pd.Series:
    """초기 진입 후 전 구간 보유를 유지하는 벤치마크 액션 시퀀스를 생성합니다."""
    total_periods: int = len(date_index)
    action_array: np.ndarray = np.full(total_periods, fill_value=ACTION_HOLD, dtype=object)
    if total_periods > 0:
        action_array[0] = ACTION_BUY
    return pd.Series(action_array, index=date_index, name="benchmark_action")


def _derive_position_sequence(
    action_series: pd.Series,
) -> pd.Series:
    """3-Action 시퀀스로부터 결정론적 상태 머신을 거쳐 포지션 시계열을 도출합니다."""
    action_values: np.ndarray = action_series.to_numpy()
    total_steps: int = len(action_values)
    position_values: np.ndarray = np.zeros(total_steps, dtype=np.float64)

    current_state: float = POSITION_FLAT
    for step_index in range(total_steps):
        action: str = action_values[step_index]
        if action == ACTION_BUY:
            current_state = POSITION_LONG
        elif action == ACTION_SELL:
            current_state = POSITION_FLAT
        elif action == ACTION_HOLD:
            pass
        else:
            raise ValueError(f"정의되지 않은 비정상 액션이 감지되었습니다: '{action}'")
        position_values[step_index] = current_state

    return pd.Series(position_values, index=action_series.index, name="position")


def _calculate_transaction_costs(
    position_series: pd.Series,
    round_trip_cost: float,
) -> Tuple[pd.Series, pd.Series]:
    """포지션 전이에 따른 회전율(Turnover)과 편도 분할 적용 거래비용을 산출합니다."""
    lagged_positions: pd.Series = position_series.shift(1).fillna(POSITION_FLAT)
    turnover_series: pd.Series = (position_series - lagged_positions).abs()
    half_turn_cost_rate: float = round_trip_cost / 2.0
    cost_series: pd.Series = turnover_series * half_turn_cost_rate
    return turnover_series.rename("turnover"), cost_series.rename("transaction_cost")


def _assemble_accounting_ledger(
    prices: pd.Series,
    asset_returns: pd.Series,
    action_series: pd.Series,
    position_series: pd.Series,
    turnover_series: pd.Series,
    cost_series: pd.Series,
    initial_capital: float,
) -> pd.DataFrame:
    """일별 포지션 및 비용을 반영하여 전략의 순자산가치 및 고점 대비 낙폭 원장을 조립합니다."""
    # [설계 의도] t 시점 종가에 체결된 포지션 S_t는 t+1 시점의 자산 가격 변동에 노출되므로 1일 시차(Lag 1) 적용
    effective_exposure: pd.Series = position_series.shift(1).fillna(POSITION_FLAT)
    gross_returns: pd.Series = effective_exposure * asset_returns
    net_returns: pd.Series = gross_returns - cost_series

    cumulative_wealth_index: pd.Series = (1.0 + net_returns).cumprod()
    portfolio_nav_series: pd.Series = initial_capital * cumulative_wealth_index
    rolling_peak_series: pd.Series = cumulative_wealth_index.cummax()
    drawdown_series: pd.Series = (cumulative_wealth_index - rolling_peak_series) / rolling_peak_series

    return pd.DataFrame(
        {
            "price": prices,
            "action": action_series,
            "position": position_series,
            "turnover": turnover_series,
            "transaction_cost": cost_series,
            "asset_return": asset_returns,
            "strategy_return": net_returns,
            "nav": cumulative_wealth_index,
            "portfolio_value": portfolio_nav_series,
            "drawdown": drawdown_series,
        },
        index=prices.index,
    )


def _run_single_simulation_pipeline(
    prices: pd.Series,
    asset_returns: pd.Series,
    action_series: pd.Series,
    round_trip_cost: float,
    initial_capital: float,
) -> pd.DataFrame:
    """단일 전략에 대해 상태 전이부터 회계 원장 생성까지의 전 과정을 파이프라인으로 일괄 실행합니다."""
    positions: pd.Series = _derive_position_sequence(action_series)
    turnovers, costs = _calculate_transaction_costs(positions, round_trip_cost)
    return _assemble_accounting_ledger(
        prices=prices,
        asset_returns=asset_returns,
        action_series=action_series,
        position_series=positions,
        turnover_series=turnovers,
        cost_series=costs,
        initial_capital=initial_capital,
    )


def _extract_single_ledger_summary(
    ledger: pd.DataFrame,
) -> Dict[str, Any]:
    """개별 회계 원장에서 핵심 진단 지표를 요약 추출합니다."""
    final_nav = float(ledger["nav"].iloc[-1])
    total_return_pct = (final_nav - 1.0) * 100.0
    mdd_pct = abs(float(ledger["drawdown"].min())) * 100.0
    total_turnover = float(ledger["turnover"].sum())
    total_costs_pct = float(ledger["transaction_cost"].sum()) * 100.0
    exposure_ratio_pct = float((ledger["position"] == POSITION_LONG).mean()) * 100.0
    buy_count = int((ledger["action"] == ACTION_BUY).sum())
    sell_count = int((ledger["action"] == ACTION_SELL).sum())

    return {
        "Final NAV": f"{final_nav:.4f}",
        "Cumulative Return (%)": f"{total_return_pct:+.2f}%",
        "Max Drawdown (MDD %)": f"-{mdd_pct:.2f}%",
        "Total Turnover (x)": f"{total_turnover:.2f}x",
        "Transaction Cost (%)": f"-{total_costs_pct:.2f}%",
        "Market Exposure Ratio (%)": f"{exposure_ratio_pct:.1f}%",
        "Executed Trades (BUY / SELL)": f"{buy_count}회 / {sell_count}회",
    }


def _format_simulation_summary_table(
    simulation_ledgers: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """3대 전략의 요약 지표를 단일 감사 데이터프레임으로 조립합니다."""
    summary_records: Dict[str, Dict[str, Any]] = {}
    for strategy_name, ledger in simulation_ledgers.items():
        summary_records[strategy_name] = _extract_single_ledger_summary(ledger)
    summary_df = pd.DataFrame(summary_records)
    summary_df.index.name = "Portfolio Accounting Audit"
    return summary_df