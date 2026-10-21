from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 거래 액션 표준 명칭 규격
ACTION_BUY: str = "BUY"                         # 매수 진입 주문 액션
ACTION_HOLD: str = "HOLD"                       # 기존 상태 유지 및 추세 관망 액션
ACTION_SELL: str = "SELL"                       # 매도 청산 및 현금화 액션

# 포지션 상태 상수 (롱온리 현물 주식 계좌)
POSITION_LONG: float = 1.0                      # 주식 100% 보유 상태
POSITION_FLAT: float = 0.0                      # 현금 100% 보유 상태

# 전략 식별자 표준 명칭 (Ablation Study 연동)
STRATEGY_RAW_NAME: str = "Strategy 1 (Raw Model)"    # 순수 ML 원시 예측치 기반 전략
STRATEGY_XAI_NAME: str = "Strategy 2 (XAI-Gated)"    # XAI 거버넌스 게이팅 탑재 전략

# 동적 불감대 산출 기본 파라미터
DEFAULT_ROUND_TRIP_COST: float = 0.0025         # 왕복 거래 제반 비용 (25 bps)
DEFAULT_VOLATILITY_MULTIPLIER_K: float = 0.10   # [설계 의도] 20영업일 타깃 노이즈를 적정 수준(약 2.0% 내외)으로 완충하는 표준 승수
DEFAULT_ROLLING_WINDOW: int = 20                # 단기 롤링 변동성 추정 윈도우 크기
DEFAULT_RETURN_HORIZON_DAYS: int = 20           # [설계 의도] 20영업일 누적 타깃 스케일과 변동성 척도를 일치시키기 위한 보유 지평 기간
DEFAULT_TRAILING_HOLD_RATIO: float = 1.5        # [설계 의도] 거시 리스크 안정 국면에서 단기 노이즈로 인한 조기 매도를 방어하는 매도선 완충 확장 승수
DEFAULT_REGIME_STABILITY_THRESHOLD: float = 0.80  # [설계 의도] 추세 지속 지연 청산을 적용할 거시 리스크 안정 국면 하한 게이트 임계치 (G_t >= 0.80)


# ==============================================================================
# Public API Functions
# ==============================================================================
def calculate_dynamic_deadband(
    rolling_volatility_20d: Optional[pd.Series] = None,
    round_trip_cost: float = DEFAULT_ROUND_TRIP_COST,
    volatility_multiplier_k: float = DEFAULT_VOLATILITY_MULTIPLIER_K,
    reference_predictions: Optional[pd.Series] = None,
    return_horizon_days: int = DEFAULT_RETURN_HORIZON_DAYS,
) -> pd.Series:
    """거래비용과 20영업일 시간 스케일링 롤링 변동성을 결합하여 실시간 동적 중립 불감대(tau)를 산출합니다.

    Args:
        rolling_volatility_20d: 기초자산의 20영업일 롤링 변동성 시계열 (선택적).
        round_trip_cost: 왕복 거래 제반 비용 비율.
        volatility_multiplier_k: 단기 노이즈 완충 승수 (k 계수).
        reference_predictions: 변동성 시계열 부재 시 대체 추정을 위한 참조 예측치.
        return_horizon_days: 타깃 누적 수익률 보유 지평 기간 (기본값: 20영업일).

    Returns:
        pd.Series: 시점별 동적 불감대 임계치(tau_t) 시계열.

    Raises:
        ValueError: 파라미터가 음수이거나 참조 가능한 변동성 시계열이 전무한 경우.
    """
    _validate_non_negative_scalar(round_trip_cost, "round_trip_cost")
    _validate_non_negative_scalar(volatility_multiplier_k, "volatility_multiplier_k")
    if return_horizon_days <= 0:
        raise ValueError(f"return_horizon_days 값({return_horizon_days})은 0보다 커야 합니다.")

    volatility_series: pd.Series = _resolve_rolling_volatility(
        rolling_volatility=rolling_volatility_20d,
        reference_predictions=reference_predictions,
    )
    return _compute_deadband_series(
        rolling_volatility=volatility_series,
        round_trip_cost=round_trip_cost,
        volatility_multiplier_k=volatility_multiplier_k,
        return_horizon_days=return_horizon_days,
    )


def rectify_alpha_signal(
    raw_predictions: pd.Series,
    composite_gating_scores: Optional[pd.Series] = None,
    dynamic_deadbands: Optional[pd.Series] = None,
) -> pd.Series:
    """1차 머신러닝 예측값에 XAI 거버넌스 감산형 리스크 페널티를 반영하여 유효 기대수익률을 산출합니다.

    Args:
        raw_predictions: 1차 ML 모델이 산출한 20영업일 원시 기대수익률 시계열.
        composite_gating_scores: XAI 복합 리스크 게이트 시계열 (None일 경우 원시 신호 보존).
        dynamic_deadbands: 거래비용 및 노이즈가 반영된 동적 불감대 시계열 (선택적).

    Returns:
        pd.Series: 리스크 오버레이가 반영된 유효 기대수익률(y_eff) 시계열.

    Raises:
        ValueError: 원시 예측 시계열이 비어 있거나 인덱스가 불일치하는 경우.
    """
    _validate_series_not_empty(raw_predictions, "raw_predictions")
    if composite_gating_scores is None:
        return raw_predictions.copy().rename("effective_prediction")

    _validate_aligned_series(raw_predictions, composite_gating_scores, "composite_gating_scores")
    return _apply_alpha_gating_multiplication(
        raw_predictions=raw_predictions,
        composite_gating_scores=composite_gating_scores,
        dynamic_deadbands=dynamic_deadbands,
    )


def determine_trading_action(
    effective_predictions: pd.Series,
    dynamic_deadbands: pd.Series,
    raw_predictions: Optional[pd.Series] = None,
    composite_gating_scores: Optional[pd.Series] = None,
    trailing_hold_ratio: float = DEFAULT_TRAILING_HOLD_RATIO,
    regime_stability_threshold: float = DEFAULT_REGIME_STABILITY_THRESHOLD,
) -> pd.Series:
    """비대칭 거버넌스 히스테리시스를 적용하여 휩소 채터링 억제 및 테일 리스크 탈출을 동시에 달성합니다.

    Args:
        effective_predictions: 리스크가 보정된 유효 기대수익률(y_eff) 시계열.
        dynamic_deadbands: 시점별 동적 중립 불감대(tau) 시계열.
        raw_predictions: 원시 기대수익률 시계열 (호환성 유지용).
        composite_gating_scores: XAI 복합 리스크 게이트 시계열 (선택적).
        trailing_hold_ratio: 거시 안정 국면 매도선 완충 확장 승수.
        regime_stability_threshold: 추세 지속 지연 청산 적용 하한 게이트 임계치.

    Returns:
        pd.Series: 시점별 최종 집행 액션(BUY / HOLD / SELL) 시계열.

    Raises:
        ValueError: 입력 시계열 간 인덱스 불일치가 존재하는 경우.
    """
    _validate_aligned_series(effective_predictions, dynamic_deadbands, "dynamic_deadbands")
    return _classify_stateful_hysteresis_actions(
        effective_predictions=effective_predictions,
        dynamic_deadbands=dynamic_deadbands,
        composite_gating_scores=composite_gating_scores,
        trailing_hold_ratio=trailing_hold_ratio,
        regime_stability_threshold=regime_stability_threshold,
    )

def generate_execution_signals(
    raw_predictions: pd.Series,
    composite_gating_scores: Optional[pd.Series] = None,
    rolling_volatility_20d: Optional[pd.Series] = None,
    round_trip_cost: float = DEFAULT_ROUND_TRIP_COST,
    volatility_multiplier_k: float = DEFAULT_VOLATILITY_MULTIPLIER_K,
    return_horizon_days: int = DEFAULT_RETURN_HORIZON_DAYS,
    trailing_hold_ratio: float = DEFAULT_TRAILING_HOLD_RATIO,
    regime_stability_threshold: float = DEFAULT_REGIME_STABILITY_THRESHOLD,
) -> pd.DataFrame:
    """원시 예측치와 XAI 게이트, 시장 변동성을 종합하여 최종 의사결정 시그널 프레임을 생성합니다.

    Args:
        raw_predictions: 1차 머신러닝 예측값 시계열.
        composite_gating_scores: XAI 복합 리스크 게이트 시계열 (선택적).
        rolling_volatility_20d: 20영업일 롤링 변동성 시계열 (선택적).
        round_trip_cost: 왕복 거래비용 비율.
        volatility_multiplier_k: 변동성 완충 승수.
        return_horizon_days: 타깃 누적 수익률 보유 지평 기간.
        trailing_hold_ratio: 거시 안정 국면 매도선 완충 확장 승수.
        regime_stability_threshold: 추세 지속 지연 청산 적용 하한 게이트 임계치.

    Returns:
        pd.DataFrame: raw_prediction, effective_prediction, dynamic_deadband, action, position을 포함하는 프레임.
    """
    dynamic_deadbands: pd.Series = calculate_dynamic_deadband(
        rolling_volatility_20d=rolling_volatility_20d,
        round_trip_cost=round_trip_cost,
        volatility_multiplier_k=volatility_multiplier_k,
        reference_predictions=raw_predictions,
        return_horizon_days=return_horizon_days,
    )
    effective_predictions: pd.Series = rectify_alpha_signal(
        raw_predictions=raw_predictions,
        composite_gating_scores=composite_gating_scores,
        dynamic_deadbands=dynamic_deadbands,
    )
    actions: pd.Series = determine_trading_action(
        effective_predictions=effective_predictions,
        dynamic_deadbands=dynamic_deadbands,
        raw_predictions=raw_predictions,
        composite_gating_scores=composite_gating_scores,
        trailing_hold_ratio=trailing_hold_ratio,
        regime_stability_threshold=regime_stability_threshold,
    )
    positions: pd.Series = _derive_position_series_from_actions(actions)

    return _assemble_signal_dataframe(
        raw_predictions=raw_predictions,
        effective_predictions=effective_predictions,
        dynamic_deadbands=dynamic_deadbands,
        actions=actions,
        positions=positions,
    )


def summarize_action_distributions(
    strategy_signals_dictionary: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """전략별 3-Action 발생 빈도, 시장 노출도, 완결 매매 횟수 및 채터링 방어 비교 감사표를 생성합니다.

    Args:
        strategy_signals_dictionary: 전략 식별자를 키로 하고 시그널 데이터프레임을 값으로 하는 딕셔너리.

    Returns:
        pd.DataFrame: 전략별 액션 분포 및 채터링 억제율 요약 비교 감사표.

    Raises:
        ValueError: 대상 시그널 딕셔너리가 비어 있는 경우.
    """
    if not strategy_signals_dictionary:
        raise ValueError("액션 요약 대상 시그널 딕셔너리가 비어 있습니다.")
    return _assemble_ablation_action_summary_table(strategy_signals_dictionary)


def generate_ablation_execution_signals(
    raw_predictions: pd.Series,
    composite_gating_scores: pd.Series,
    rolling_volatility_20d: Optional[pd.Series] = None,
    round_trip_cost: float = DEFAULT_ROUND_TRIP_COST,
    volatility_multiplier_k: float = DEFAULT_VOLATILITY_MULTIPLIER_K,
    trailing_hold_ratio: float = DEFAULT_TRAILING_HOLD_RATIO,
    regime_stability_threshold: float = DEFAULT_REGIME_STABILITY_THRESHOLD,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Strategy 1(Raw ML)과 Strategy 2(XAI-Gated) 시그널을 일괄 사출하고 액션 비교표를 도출합니다.

    Args:
        raw_predictions: 1차 ML 모델 원시 예측치 시계열.
        composite_gating_scores: XAI 복합 리스크 게이트 시계열.
        rolling_volatility_20d: 시장 롤링 변동성 시계열 (선택적).
        round_trip_cost: 왕복 거래비용 비율.
        volatility_multiplier_k: 변동성 완충 계수.
        trailing_hold_ratio: 거시 안정 국면 매도선 완충 확장 승수.
        regime_stability_threshold: 추세 지속 지연 청산 적용 하한 게이트 임계치.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            - pd.DataFrame: Strategy 1 (Raw Model) 시그널 데이터프레임.
            - pd.DataFrame: Strategy 2 (XAI-Gated) 시그널 데이터프레임.
            - pd.DataFrame: 3-Action 비교 및 채터링 방어 감사 요약표.
    """
    signals_raw_model: pd.DataFrame = generate_execution_signals(
        raw_predictions=raw_predictions,
        composite_gating_scores=None,
        rolling_volatility_20d=rolling_volatility_20d,
        round_trip_cost=round_trip_cost,
        volatility_multiplier_k=volatility_multiplier_k,
        trailing_hold_ratio=trailing_hold_ratio,
        regime_stability_threshold=regime_stability_threshold,
    )
    signals_xai_gated: pd.DataFrame = generate_execution_signals(
        raw_predictions=raw_predictions,
        composite_gating_scores=composite_gating_scores,
        rolling_volatility_20d=rolling_volatility_20d,
        round_trip_cost=round_trip_cost,
        volatility_multiplier_k=volatility_multiplier_k,
        trailing_hold_ratio=trailing_hold_ratio,
        regime_stability_threshold=regime_stability_threshold,
    )

    signals_dictionary: Dict[str, pd.DataFrame] = {
        STRATEGY_RAW_NAME: signals_raw_model,
        STRATEGY_XAI_NAME: signals_xai_gated,
    }
    summary_table: pd.DataFrame = summarize_action_distributions(signals_dictionary)

    return signals_raw_model, signals_xai_gated, summary_table


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_series_not_empty(
    series: pd.Series,
    variable_name: str,
) -> None:
    """시계열 객체의 공백 및 결손 여부를 검증합니다."""
    if series is None or series.empty:
        raise ValueError(f"입력된 {variable_name} 시계열이 비어 있습니다.")


def _validate_non_negative_scalar(
    scalar_value: float,
    variable_name: str,
) -> None:
    """실수형 파라미터의 음수 여부를 검증합니다."""
    if scalar_value < 0.0:
        raise ValueError(f"{variable_name} 값({scalar_value})은 0 이상이어야 합니다.")


def _validate_aligned_series(
    primary_series: pd.Series,
    secondary_series: pd.Series,
    secondary_name: str,
) -> None:
    """두 시계열의 인덱스 일치 여부 및 결손 상태를 검증합니다."""
    _validate_series_not_empty(primary_series, "primary_series")
    _validate_series_not_empty(secondary_series, secondary_name)
    if not primary_series.index.equals(secondary_series.index):
        raise ValueError(f"입력 시계열과 {secondary_name} 시계열 간의 날짜 인덱스가 일치하지 않습니다.")


def _resolve_rolling_volatility(
    rolling_volatility: Optional[pd.Series],
    reference_predictions: Optional[pd.Series],
) -> pd.Series:
    """주입된 변동성 시계열이 없을 경우 참조 시계열로부터 롤링 변동성을 자체 추정합니다."""
    if rolling_volatility is not None and not rolling_volatility.empty:
        return rolling_volatility
    if reference_predictions is not None and not reference_predictions.empty:
        computed_standard_deviation = (
            reference_predictions.rolling(window=DEFAULT_ROLLING_WINDOW, min_periods=1)
            .std()
            .bfill()
        )
        return computed_standard_deviation.fillna(0.0)
    raise ValueError("변동성 시계열과 참조 시계열이 모두 누락되었습니다.")


def _compute_deadband_series(
    rolling_volatility: pd.Series,
    round_trip_cost: float,
    volatility_multiplier_k: float,
    return_horizon_days: int = DEFAULT_RETURN_HORIZON_DAYS,
) -> pd.Series:
    """보유 기간 시간 제곱근 스케일링(sqrt(T))을 반영하여 예측치 척도와 일치된 동적 불감대 시계열을 계산합니다."""
    # [설계 의도] 20영업일 누적 기대수익률 스케일과 일간 롤링 변동성 간의 단위를 일치시키기 위해
    # 금융공학 표준 시간 제곱근 규칙(Square Root of Time: sqrt(T))을 적용하여 불감대 밴드의 완충력을 확보함
    time_scaling_factor: float = np.sqrt(float(return_horizon_days)) if return_horizon_days > 1 else 1.0
    scaled_volatility: pd.Series = rolling_volatility * time_scaling_factor
    computed_deadband: pd.Series = round_trip_cost + (volatility_multiplier_k * scaled_volatility)
    return computed_deadband.rename("dynamic_deadband")


def _apply_alpha_gating_multiplication(
    raw_predictions: pd.Series,
    composite_gating_scores: pd.Series,
    dynamic_deadbands: Optional[pd.Series] = None,
) -> pd.Series:
    """포트폴리오 이론의 리스크 페널티 수축을 적용하여 거시 위험 시 유효 알파를 안전 구역으로 정류합니다."""
    # [설계 의도] 단순 곱연산 시 모델의 후행적 양수 알파가 유지되어 폭락장에서 매도가 마비되는 결함을 방지하기 위해,
    # 평균-분산 효용 이론에 입각하여 위험 침범도((1 - G_t) / G_t)를 불감대 척도(tau) 기반 리스크 페널티로
    # 차감하는 연속 감산 수축(Continuous Penalty Shrinkage)을 적용하여 신호 왜곡 없이 조기 탈출을 유도함
    clamped_gating: pd.Series = composite_gating_scores.clip(lower=1e-6, upper=1.0)
    raw_values: np.ndarray = raw_predictions.to_numpy(dtype=np.float64)
    gating_values: np.ndarray = clamped_gating.to_numpy(dtype=np.float64)

    if dynamic_deadbands is not None:
        deadband_values: np.ndarray = dynamic_deadbands.to_numpy(dtype=np.float64)
        risk_penalty: np.ndarray = deadband_values * ((1.0 - gating_values) / gating_values)
    else:
        risk_penalty = (1.0 - gating_values)

    rectified_values: np.ndarray = (raw_values * gating_values) - risk_penalty
    return pd.Series(rectified_values, index=raw_predictions.index, name="effective_prediction")


def _classify_stateful_hysteresis_actions(
    effective_predictions: pd.Series,
    dynamic_deadbands: pd.Series,
    composite_gating_scores: Optional[pd.Series] = None,
    trailing_hold_ratio: float = DEFAULT_TRAILING_HOLD_RATIO,
    regime_stability_threshold: float = DEFAULT_REGIME_STABILITY_THRESHOLD,
) -> pd.Series:
    """거시 리스크 연동 비대칭 청산 허들을 적용하여 정상 시 채터링 방어 및 위기 시 즉각 현금화를 집행합니다."""
    # [설계 의도] 현물 롱온리 계좌에서 정상 시(G_t=1.0)에는 -tau_t의 완전한 불감대를 유지해 회전율을 차단하고,
    # 거시 위험 급증 시(G_t -> 0)에는 청산 기준선(-tau_t * G_t)을 0 방향으로 자연 수축시켜
    # 시스템 위기 구간에서 주식을 쥐고 버티는 포지션 마비(Lock-in)를 방지함
    effective_values: np.ndarray = effective_predictions.to_numpy(dtype=np.float64)
    deadband_values: np.ndarray = dynamic_deadbands.to_numpy(dtype=np.float64)
    gating_values: Optional[np.ndarray] = (
        composite_gating_scores.clip(lower=1e-6, upper=1.0).to_numpy(dtype=np.float64)
        if composite_gating_scores is not None
        else None
    )

    total_periods: int = len(effective_values)
    action_sequence: List[str] = [ACTION_HOLD] * total_periods

    current_position: float = POSITION_FLAT

    for step_index in range(total_periods):
        effective_alpha: float = effective_values[step_index]
        deadband_tau: float = deadband_values[step_index]
        gate_multiplier: float = gating_values[step_index] if gating_values is not None else 1.0

        if current_position == POSITION_FLAT:
            # [비보유 상태] 유효 알파 신호가 불감대 상단을 명확히 돌파할 때만 매수 진입
            if effective_alpha > deadband_tau:
                action_sequence[step_index] = ACTION_BUY
                current_position = POSITION_LONG
            else:
                action_sequence[step_index] = ACTION_HOLD

        else:
            # [보유 상태] 거시 위험에 비례하여 유연하게 반응하는 비대칭 청산 임계치 적용
            # [설계 의도] 거시 리스크가 안정적인 국면(G_t >= regime_stability_threshold)에서는
            # 매도 탈출선을 trailing_hold_ratio배 하향 확장하여 단기 노이즈로 인한 섣부른 조기 청산을 억제함
            expansion_multiplier: float = (
                trailing_hold_ratio if gate_multiplier >= regime_stability_threshold else 1.0
            )
            sell_threshold: float = -deadband_tau * gate_multiplier * expansion_multiplier
            if effective_alpha < sell_threshold:
                action_sequence[step_index] = ACTION_SELL
                current_position = POSITION_FLAT
            else:
                # 불감대 내에 머무르면 기존 매수 포지션을 흔들림 없이 유지(HOLD)
                action_sequence[step_index] = ACTION_HOLD

    return pd.Series(
        action_sequence,
        index=effective_predictions.index,
        name="action",
    )


def _derive_position_series_from_actions(
    action_series: pd.Series,
) -> pd.Series:
    """액션 시계열로부터 롱온리 포지션(1.0 또는 0.0) 상태 시계열을 복원합니다."""
    # [설계 의도] 공개 API 호환성을 유지하면서 실제 포트폴리오 노출도(Market Exposure)를 정확히 감사하기 위해 복원
    total_periods: int = len(action_series)
    position_array: np.ndarray = np.zeros(total_periods, dtype=np.float64)

    current_state: float = POSITION_FLAT
    for step_index, action_value in enumerate(action_series):
        if action_value == ACTION_BUY:
            current_state = POSITION_LONG
        elif action_value == ACTION_SELL:
            current_state = POSITION_FLAT
        position_array[step_index] = current_state

    return pd.Series(position_array, index=action_series.index, name="position")


def _assemble_signal_dataframe(
    raw_predictions: pd.Series,
    effective_predictions: pd.Series,
    dynamic_deadbands: pd.Series,
    actions: pd.Series,
    positions: pd.Series,
) -> pd.DataFrame:
    """개별 산출 시계열을 통합하여 실행 진단용 시그널 데이터프레임으로 조립합니다."""
    return pd.DataFrame(
        {
            "raw_prediction": raw_predictions,
            "effective_prediction": effective_predictions,
            "dynamic_deadband": dynamic_deadbands,
            "action": actions,
            "position": positions,
        },
        index=raw_predictions.index,
    )


def _calculate_action_switch_count(
    action_series: pd.Series,
) -> int:
    """시계열 상에서 액션이 변경(포지션 전이)된 총 횟수를 집계합니다."""
    shifted_actions = action_series.shift(1)
    valid_transitions = (action_series != shifted_actions) & (shifted_actions.notna())
    return int(valid_transitions.sum())


def _assemble_ablation_action_summary_table(
    strategy_signals_dictionary: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """전략별 액션 분포 통계, 시장 노출도, 완결 매매 횟수 및 채터링 방어율을 집계하여 감사 비교표를 조립합니다."""
    summary_records: Dict[str, Dict[str, Any]] = {}

    for strategy_name, signal_dataframe in strategy_signals_dictionary.items():
        actions: pd.Series = signal_dataframe["action"]
        positions: pd.Series = (
            signal_dataframe["position"]
            if "position" in signal_dataframe.columns
            else _derive_position_series_from_actions(actions)
        )

        total_horizon_days: int = len(actions)
        buy_action_count: int = int((actions == ACTION_BUY).sum())
        hold_action_count: int = int((actions == ACTION_HOLD).sum())
        sell_action_count: int = int((actions == ACTION_SELL).sum())
        action_switch_count: int = _calculate_action_switch_count(actions)

        # 포지션 분해 통계 (Hold in Long vs Hold in Flat)
        long_exposure_days: int = int((positions == POSITION_LONG).sum())
        hold_in_long_count: int = int(((actions == ACTION_HOLD) & (positions == POSITION_LONG)).sum())
        hold_in_flat_count: int = int(((actions == ACTION_HOLD) & (positions == POSITION_FLAT)).sum())

        market_exposure_ratio: float = (long_exposure_days / max(total_horizon_days, 1)) * 100.0
        completed_trades_count: int = min(buy_action_count, sell_action_count)
        mean_holding_period: float = (
            long_exposure_days / max(completed_trades_count, 1) if completed_trades_count > 0 else 0.0
        )

        # 알파 신호 정류(수축) 비율 산출
        raw_pred_abs_mean: float = float(signal_dataframe["raw_prediction"].abs().mean())
        eff_pred_abs_mean: float = float(signal_dataframe["effective_prediction"].abs().mean())
        signal_retention_ratio: float = (
            (eff_pred_abs_mean / max(raw_pred_abs_mean, 1e-8)) * 100.0 if raw_pred_abs_mean > 0 else 100.0
        )

        summary_records[strategy_name] = {
            "Total Horizon (Days)": f"{total_horizon_days} 영업일",
            "BUY Action Count (%)": f"{buy_action_count}회 ({(buy_action_count / total_horizon_days) * 100:.1f}%)",
            "HOLD Action Count (%)": f"{hold_action_count}회 ({(hold_action_count / total_horizon_days) * 100:.1f}%)",
            "  ├─ Hold in Long Position": f"{hold_in_long_count}일 ({(hold_in_long_count / total_horizon_days) * 100:.1f}%)",
            "  └─ Hold in Cash (Flat)": f"{hold_in_flat_count}일 ({(hold_in_flat_count / total_horizon_days) * 100:.1f}%)",
            "SELL Action Count (%)": f"{sell_action_count}회 ({(sell_action_count / total_horizon_days) * 100:.1f}%)",
            "Market Exposure Ratio (%)": f"{market_exposure_ratio:.1f}%",
            "Completed Trades (Count)": f"{completed_trades_count}회",
            "Mean Holding Period (Days)": f"{mean_holding_period:.1f} 영업일",
            "Action Switch (Churn Count)": f"{action_switch_count}회",
            "Mean Dynamic Deadband (τ)": f"{float(signal_dataframe['dynamic_deadband'].mean()):.5f}",
            "Alpha Signal Retention (%)": f"{signal_retention_ratio:.1f}%",
        }

    summary_dataframe = pd.DataFrame(summary_records)

    # Strategy 1 대비 Strategy 2의 Churn 억제율 산출
    if STRATEGY_RAW_NAME in summary_dataframe.columns and STRATEGY_XAI_NAME in summary_dataframe.columns:
        raw_switches = int(
            summary_dataframe.loc["Action Switch (Churn Count)", STRATEGY_RAW_NAME].replace("회", "")
        )
        xai_switches = int(
            summary_dataframe.loc["Action Switch (Churn Count)", STRATEGY_XAI_NAME].replace("회", "")
        )
        churn_reduction_ratio = ((raw_switches - xai_switches) / max(raw_switches, 1)) * 100.0

        summary_dataframe.loc["Churn Suppression Rate (%)", STRATEGY_RAW_NAME] = "Baseline (0.0%)"
        if churn_reduction_ratio >= 0:
            summary_dataframe.loc["Churn Suppression Rate (%)", STRATEGY_XAI_NAME] = (
                f"+{churn_reduction_ratio:.1f}% 억제"
            )
        else:
            summary_dataframe.loc["Churn Suppression Rate (%)", STRATEGY_XAI_NAME] = (
                f"{churn_reduction_ratio:.1f}%"
            )

    summary_dataframe.index.name = "Execution Governance Audit"
    return summary_dataframe