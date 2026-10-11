from typing import Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# Layer 1. 기계학습 기본 예측 오차 (Statistical Forecast Error)
# ==============================================================================

def mda(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
) -> float:
    """평균 방향성 적중률(Mean Directional Accuracy)을 산출합니다.

    Args:
        y_true: 실제 수익률/타겟 시계열.
        y_pred: 모델 예측 수익률 시계열.

    Returns:
        float: [0.0, 1.0] 범위의 방향성 일치 비율 (50%가 동전 던지기 베이스라인).
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) == 0:
        return 0.0

    # 부호 일치 여부(sign(y_t) == sign(y_p))를 벡터 연산으로 고속 집계
    return float(np.mean(np.sign(y_t) == np.sign(y_p)))


def rmse(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
) -> float:
    """평균 제곱근 오차(Root Mean Squared Error)를 산출합니다.

    Args:
        y_true: 실제 타겟 시계열.
        y_pred: 모델 예측값 시계열.

    Returns:
        float: 평균 제곱근 오차 수치 (0에 가까울수록 우수).
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) == 0:
        return 0.0

    return float(np.sqrt(np.mean((y_t - y_p) ** 2)))


def mae(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
) -> float:
    """평균 절대 오차(Mean Absolute Error)를 산출합니다.

    Args:
        y_true: 실제 타겟 시계열.
        y_pred: 모델 예측값 시계열.

    Returns:
        float: 평균 절대 오차 수치 (0에 가까울수록 우수).
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) == 0:
        return 0.0

    return float(np.mean(np.abs(y_t - y_p)))


# ==============================================================================
# Layer 2. 퀀트 팩터 신호 품질 (Quant Factor Signal Quality)
# ==============================================================================

def rank_ic(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
) -> float:
    """20일 중첩 시계열의 자기상관 왜곡을 보정한 위상 평균 스피어만 순위 정보 계수(Rank IC)를 산출합니다.

    Args:
        y_true: 실제 타겟 시계열.
        y_pred: 모델 예측값 시계열.
        holding_period: 타겟 예측 호라이즌 및 비중첩 위상 보폭 (기본값: 20영업일).

    Returns:
        float: [-1.0, 1.0] 범위의 비중첩 위상 평균 순위 상관계수.
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    total_samples = len(y_t)
    effective_stride = max(1, holding_period)

    # [설계 의도] 표본 수가 비중첩 3개 미만인 극소 표본 구간에서는 0.0을 반환하여 수치 불안정성 방어
    if total_samples < effective_stride * 2:
        return 0.0

    # [설계 의도] 20일 중첩(Overlapping Horizon)으로 인한 인위적 추세 동조화(Spurious Autocorrelation)를
    # 차단하기 위해, k=0..holding_period-1 개의 비중첩(Non-overlapping) 위상 서브샘플들의 Rank IC를 평균 집계
    phase_correlations: list[float] = []

    for phase_offset in range(effective_stride):
        sub_true = y_t[phase_offset::effective_stride]
        sub_pred = y_p[phase_offset::effective_stride]

        if len(sub_true) < 3:
            continue

        rank_true = stats.rankdata(sub_true)
        rank_pred = stats.rankdata(sub_pred)

        std_true = float(np.std(rank_true))
        std_pred = float(np.std(rank_pred))

        if std_true > 0.0 and std_pred > 0.0:
            correlation, _ = stats.pearsonr(rank_true, rank_pred)
            if np.isfinite(correlation):
                phase_correlations.append(float(correlation))

    if not phase_correlations:
        return 0.0

    return float(np.mean(phase_correlations))


def icir(
    y_true: Union[np.ndarray, pd.Series, list],
    y_pred: Optional[Union[np.ndarray, pd.Series, list]] = None,
    window_size: int = 60,
    step_size: Optional[int] = None,
    holding_period: int = 20,
) -> float:
    """시계열 슬라이싱 기반 Rank IC 시계열의 평균 대 변동성 비율(ICIR)을 산출합니다.

    Args:
        y_true: 실제 타겟 시계열 (y_pred가 None일 경우 이미 산출된 Rank IC 배열로 간주).
        y_pred: 모델 예측값 시계열 (None일 경우 y_true 단독 평가).
        window_size: 롤링 Rank IC 윈도우 크기 (기본값: 60 거래일).
        step_size: 롤링 이동 보폭 (기본값: None 시 holding_period 단위).
        holding_period: 타겟 예측 호라이즌 (기본값: 20영업일).

    Returns:
        float: Rank IC 평균 / 표본 표준편차 비율.
    """
    # 1. 기 산출된 Rank IC 1차원 시계열이 단독 인입된 경우
    if y_pred is None:
        ic_arr = _to_numpy_array(y_true)
        ic_arr = ic_arr[np.isfinite(ic_arr)]
        if len(ic_arr) < 2:
            return 0.0
        ic_std = float(np.std(ic_arr, ddof=1))
        return float(np.mean(ic_arr) / ic_std) if ic_std > 0.0 and np.isfinite(ic_std) else 0.0

    # 2. y_true, y_pred 동시 인입 시 롤링 윈도우 순회 집계
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    total_samples = len(y_t)
    # [설계 의도] 최소 유효 윈도우 크기를 5영업일로 방어하여 슬라이스 크기 미달로 인한 조기 탈락 방지
    effective_window = max(window_size, 5)

    if total_samples < effective_window:
        return 0.0

    step = step_size if step_size is not None else max(1, window_size // 2)
    rolling_rank_ics: list[float] = []

    for start_idx in range(0, total_samples - effective_window + 1, step):
        end_idx = start_idx + effective_window
        # 20일 중첩 타겟의 자기상관 왜곡을 방지하기 위해 롤링 윈도우 내에서도 holding_period 비중첩 위상 분할 적용
        sub_ic = rank_ic(
            y_true=y_t[start_idx:end_idx],
            y_pred=y_p[start_idx:end_idx],
            holding_period=holding_period,
        )
        if np.isfinite(sub_ic):
            rolling_rank_ics.append(sub_ic)

    ic_arr = np.array(rolling_rank_ics, dtype=np.float64)
    ic_arr = ic_arr[np.isfinite(ic_arr)]
    if len(ic_arr) < 2:
        return 0.0

    ic_std = float(np.std(ic_arr, ddof=1))
    return float(np.mean(ic_arr) / ic_std) if ic_std > 0.0 and np.isfinite(ic_std) else 0.0


def rank_ic_tstat(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
) -> Tuple[float, float]:
    """예측 신호의 팩터 순위 상관계수(Rank IC)에 대한 통계적 유의성(t-stat, p-value)을 산출합니다.

    스피어만 순위 상관계수의 귀무가설(H0: rho == 0)에 대한 점근적 Student-t 분포 검정을 수행합니다.

    Args:
        y_true (Union[np.ndarray, pd.Series]): 실제 타겟 시계열.
        y_pred (Union[np.ndarray, pd.Series]): 모델 예측값 시계열.
        holding_period (int): 타겟 예측 호라이즌 (기본값: 20영업일).

    Returns:
        Tuple[float, float]: (factor_t_statistic, factor_p_value_two_sided)

    Raises:
        ValueError: 유효 표본 수가 3개 미만인 경우 0.0, 1.0을 기본 반환하여 크래시 방지.
    """
    # [설계 의도] 도메인 계층 분리 원칙에 따라 결측치 정제 및 1차원 ndarray 변환 수행
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    total_samples = len(y_t)

    if total_samples < 3:
        return 0.0, 1.0

    ic_value = rank_ic(y_true=y_t, y_pred=y_p, holding_period=holding_period)

    # [수리적 연산] Pearson/Spearman 순위 상관계수 통계 검정: t = rho * sqrt(N - 2) / sqrt(1 - rho^2)
    # 극단치(-1.0, 1.0)에 의한 분모 0 나눗셈(Zero-Division) 방어 클리핑
    bounded_ic = float(np.clip(ic_value, -0.999999, 0.999999))
    degrees_of_freedom = total_samples - 2
    t_stat = float(bounded_ic * np.sqrt(degrees_of_freedom / (1.0 - bounded_ic**2)))

    # Student-t 양측 검정 (Two-sided p-value)
    p_value = float(2.0 * stats.t.sf(np.abs(t_stat), df=degrees_of_freedom))

    return t_stat, p_value


# ==============================================================================
# Layer 3. 금융 시뮬레이션 성과 (Financial Strategy Simulation)
# ==============================================================================

def signal_sharpe(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
    annual_days: float = 252.0,
    risk_free_rate: float = 0.0,
    pred_std: Optional[float] = None,
) -> float:
    """예측 신호 부호(Long/Short) 기반 20일 보유 전략의 연율화 샤프 지수를 산출합니다.

    Args:
        y_true: 실제 자산 수익률 시계열.
        y_pred: 모델 예측 수익률 시계열.
        holding_period: 포지션 리밸런싱/보유 주기 (기본값: 20일).
        annual_days: 연간 영업일 수 (기본값: 252일).
        risk_free_rate: 무위험 이자율 (기본값: 0.0).

    Returns:
        float: 연율화된 샤프 지수.
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) < 2:
        return 0.0

    total_samples = len(y_t)
    effective_stride = max(1, holding_period)
    if total_samples < effective_stride * 2:
        return 0.0

    annual_factor = annual_days / effective_stride
    phase_sharpes: list[float] = []

    # 20영업일 중첩 보유에 따른 MA(19) 분산 왜곡을 차단하기 위해 비중첩 위상별 샤프 지수 평균 산출
    for phase_offset in range(effective_stride):
        sub_true = y_t[phase_offset::effective_stride]
        sub_pred = y_p[phase_offset::effective_stride]
        if len(sub_true) < 2:
            continue

        sub_weights = _to_position_weights(sub_pred, pred_std=pred_std)
        sub_returns = sub_weights * sub_true
        mean_ret = float(np.mean(sub_returns)) - (risk_free_rate / annual_factor)
        std_ret = float(np.std(sub_returns, ddof=1))

        if std_ret > 0.0 and np.isfinite(std_ret):
            phase_sharpes.append(float(np.sqrt(annual_factor) * (mean_ret / std_ret)))

    if not phase_sharpes:
        return 0.0

    return float(np.mean(phase_sharpes))


def sortino_ratio(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
    annual_days: float = 252.0,
    target_return: float = 0.0,
    pred_std: Optional[float] = None,
) -> float:
    """하방 위험(Downside Deviation)만을 통제한 연율화 소르티노 지수를 안정적으로 산출합니다.

    Args:
        y_true: 실제 자산 수익률 시계열.
        y_pred: 모델 예측 수익률 시계열.
        holding_period: 포지션 리밸런싱/보유 주기 (기본값: 20일).
        annual_days: 연간 영업일 수 (기본값: 252일).
        target_return: 최소 요구 목표 수익률 (기본값: 0.0).

    Returns:
        float: 연율화된 소르티노 지수.
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) < 2:
        return 0.0

    total_samples = len(y_t)
    effective_stride = max(1, holding_period)
    if total_samples < effective_stride * 2:
        return 0.0

    annual_factor = annual_days / effective_stride
    target_threshold = target_return / annual_factor
    phase_sortinos: list[float] = []

    # 20영업일 중첩에 의한 하방 리스크 과소추정을 방지하는 비중첩 위상 평균 소르티노 지수 산출
    for phase_offset in range(effective_stride):
        sub_true = y_t[phase_offset::effective_stride]
        sub_pred = y_p[phase_offset::effective_stride]
        if len(sub_true) < 2:
            continue

        sub_weights = _to_position_weights(sub_pred, pred_std=pred_std)
        sub_returns = sub_weights * sub_true
        excess_returns = sub_returns - target_threshold
        mean_ret = float(np.mean(excess_returns))
        sub_std = float(np.std(sub_returns, ddof=1))
        downside_returns = np.minimum(0.0, excess_returns)
        raw_downside_dev = float(np.sqrt(np.mean(downside_returns ** 2)))

        # [수리적 보정] 하방 변동성 붕괴 방어(Floor): 전체 변동성의 25% 및 최소 1e-4 하한선 강제
        effective_downside_dev = max(raw_downside_dev, 0.25 * sub_std, 1e-4)

        if np.isfinite(effective_downside_dev):
            raw_sortino = float(np.sqrt(annual_factor) * (mean_ret / effective_downside_dev))
            # 소표본 단일 위상 수치 폭발 방어: 실무 상한선 [-5.0, 5.0] 클리핑
            phase_sortinos.append(float(np.clip(raw_sortino, -5.0, 5.0)))

    if not phase_sortinos:
        return 0.0

    return float(np.mean(phase_sortinos))


def mdd(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
    pred_std: Optional[float] = None,
    target_actual_std: Optional[float] = None,
    eval_horizon: Optional[int] = 203,
) -> float:
    """20일 비중첩 위상(Phase Offset) 앙상블 및 동일 관측창(203일) 롤링 기준 평균 최대 낙폭(MDD) 비율을 산출합니다.

    Args:
        y_true (Union[np.ndarray, pd.Series]): 실제 타겟 시계열 (표준화 척도 또는 실제 수익률).
        y_pred (Union[np.ndarray, pd.Series]): 모델 예측값 시계열.
        holding_period (int): 포지션 보유 기간 (기본값: 20영업일).
        pred_std (Optional[float]): Train CV에서 동결된 예측값 표준편차 (Look-ahead Bias 방지).
        target_actual_std (Optional[float]): 타겟 변수의 실제 20일 변동성 (None 시 자동 감지 적응).
        eval_horizon (Optional[int]): CV 검증창과 일원화할 기준 관측 기간 (기본값: 203영업일, None 시 단일 전체 구간).

    Returns:
        float: [0.0, 1.0] 범위의 위상 및 롤링 윈도우 평균 최대 낙폭 비율.
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) < 2:
        return 0.0

    total_samples = len(y_t)
    effective_stride = max(1, holding_period)
    if total_samples < effective_stride * 2:
        return 0.0

    # [설계 의도] Train CV 동결 pred_std가 미제공된 경우, 10개 행 단위의 소표본 분산 붕괴 방지를 위해 전체 y_p 분산으로 1회 바인딩
    safe_pred_std: float = (
        float(pred_std)
        if (pred_std is not None and pred_std > 0.0 and np.isfinite(pred_std))
        else (float(np.std(y_p, ddof=1)) if len(y_p) > 1 else 1.0)
    )

    # [설계 의도] 표준화(Z-Score, std ≈ 1.0) 타깃의 지수 누적 폭발 방어:
    # y_true의 분산이 0.2 초과(표준화 척도)일 때만 외부 주입 target_actual_std(또는 기본 0.04) 고정 배율로 역스케일링 수행
    std_y_true: float = float(np.std(y_t, ddof=1)) if len(y_t) > 1 else 1.0
    if std_y_true > 0.20:
        # Train/Test 공통 기준 변동성을 적용하여 구간별 표본 변동성 차이로 인한 역스케일링 왜곡 차단
        base_target_std: float = (
            float(target_actual_std)
            if (target_actual_std is not None and target_actual_std > 0.0 and np.isfinite(target_actual_std))
            else 0.04
        )
        scale_factor = base_target_std
    else:
        # 이미 십진 수익률(예: 0.03 = 3%) 척도인 경우 1:1 보존
        scale_factor = 1.0

    phase_mdds: list[float] = []
    sub_window: int = (
        max(2, eval_horizon // effective_stride)
        if (eval_horizon is not None and eval_horizon > 0)
        else 0
    )

    # [설계 의도] 20영업일 중첩 보유에 따른 경로 중복(Path Duplication) 복리 왜곡을 방지하고,
    # CV 203일 윈도우와 Test 500+일 장기 누적 간 관측 기간(Horizon) 불일치 왜곡을 롤링 앙상블로 일원화
    for phase_offset in range(effective_stride):
        sub_true = y_t[phase_offset::effective_stride]
        sub_pred = y_p[phase_offset::effective_stride]
        if len(sub_true) < 2:
            continue

        sub_weights = _to_position_weights(sub_pred, pred_std=safe_pred_std)
        # 역스케일링된 실제 십진 수익률 기반 포지션 실현 손익 산출
        sub_returns = sub_weights * (sub_true * scale_factor)

        # CV와 동일한 관측창(sub_window, 약 203영업일) 단위로 롤링 슬라이싱하여 기간 척도 일치화
        if sub_window > 0 and len(sub_returns) > sub_window:
            rolling_mdds: list[float] = []
            for start_idx in range(len(sub_returns) - sub_window + 1):
                window_returns = sub_returns[start_idx : start_idx + sub_window]
                log_wealth = np.cumsum(window_returns)
                wealth_index = np.r_[1.0, np.exp(log_wealth)]
                running_max = np.maximum.accumulate(wealth_index)
                drawdowns = (running_max - wealth_index) / np.maximum(running_max, 1e-8)
                rolling_mdds.append(float(np.max(drawdowns)))
            phase_mdds.append(float(np.mean(rolling_mdds)))
        else:
            # 표본 크기가 관측창 이하(CV 각 Fold 203일 구간 등)인 경우 단일 자산 곡선 산출
            log_wealth = np.cumsum(sub_returns)
            wealth_index = np.r_[1.0, np.exp(log_wealth)]
            running_max = np.maximum.accumulate(wealth_index)
            drawdowns = (running_max - wealth_index) / np.maximum(running_max, 1e-8)
            phase_mdds.append(float(np.max(drawdowns)))

    if not phase_mdds:
        return 0.0

    return float(np.clip(np.mean(phase_mdds), 0.0, 1.0))


# ==============================================================================
# Layer 4. 단일 신호 통계적 유의성 (Single-Model Signal Significance)
# ==============================================================================

def newey_west_tstat(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    max_lags: Optional[int] = None,
    holding_period: int = 20,
    pred_std: Optional[float] = None,
) -> Tuple[float, float]:
    """20일 중첩 시계열 구조를 보정한 Newey-West Factor t-통계량과 p-value를 산출합니다.

    Args:
        y_true: 실제 자산 수익률 시계열.
        y_pred: 모델 예측 수익률 시계열.
        max_lags: HAC 보정 최대 시차 (None 시 holding_period 기반 자동 산출).
        holding_period: 타겟 예측 호라이즌 (기본값: 20영업일).

    Returns:
        Tuple[float, float]: (t_statistic, p_value_two_sided)
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    total_samples = len(y_t)

    if total_samples < max(5, holding_period):
        return 0.0, 1.0

    weights = _to_position_weights(y_p, pred_std=pred_std)
    strategy_returns = weights * y_t
    mean_return = float(np.mean(strategy_returns))
    residuals = strategy_returns - mean_return

    # [설계 의도] 20일 중첩 타겟의 MA(19) 자기공분산을 온전히 커버하도록 holding_period를 대역폭 기본값으로 전달
    hac_variance = _calculate_hac_variance(
        residuals=residuals,
        max_lags=max_lags,
        holding_period=holding_period,
    )
    if hac_variance <= 0.0 or not np.isfinite(hac_variance):
        return 0.0, 1.0

    # 계량경제학 표준 Newey-West HAC 점근 표준오차(SE = sqrt(Omega_NW / T)) 산출
    standard_error = float(np.sqrt(hac_variance / total_samples))

    if standard_error <= 1e-8 or not np.isfinite(standard_error):
        return 0.0, 1.0

    t_stat = float(mean_return / standard_error)

    # [설계 의도] 20일 중첩 타겟의 유효 표본 크기(ESS)를 반영한 소표본 자유도 산출 (ADP 모수 검정 원칙)
    df_effective: int = max(2, (total_samples // max(1, holding_period)) - 1)

    # [설계 의도] 대점근 표준정규분포 가정을 폐기하고 Student-t 소표본 두터운 꼬리를 반영한 정확 양측 검정
    p_value = float(2.0 * stats.t.sf(np.abs(t_stat), df=df_effective))

    return t_stat, p_value


# ==============================================================================
# Layer 5. Champion-Challenger A/B 비교 검정 (Pairwise Predictive Superiority)
# ==============================================================================

def diebold_mariano_test(
    y_true: Union[np.ndarray, pd.Series],
    y_pred_champion: Union[np.ndarray, pd.Series],
    y_pred_challenger: Union[np.ndarray, pd.Series],
    loss_metric: str = "squared",
    max_lags: Optional[int] = None,
) -> Tuple[float, float]:
    """Champion vs Challenger 예측 손실 차이에 대한 Diebold-Mariano 검정을 수행합니다.

    Args:
        y_true: 실제 타겟 시계열.
        y_pred_champion: 기존 Champion 모델의 예측값.
        y_pred_challenger: 신규 Challenger 모델의 예측값.
        loss_metric: 손실 함수 유형 ('squared': MSE 차이, 'absolute': MAE 차이).
        max_lags: HAC 보정 시차 (None 시 자동 산출).

    Returns:
        Tuple[float, float]: (DM_statistic, p_value_one_sided_challenger_superior)
            - DM 통계량이 양수이고 p-value <= 0.05이면 Challenger가 통계적으로 우월함.
    """
    y_t = _to_numpy_array(y_true)
    y_champ = _to_numpy_array(y_pred_champion)
    y_chall = _to_numpy_array(y_pred_challenger)
    total_samples = len(y_t)

    if not (total_samples == len(y_champ) == len(y_chall)) or total_samples < 5:
        return 0.0, 1.0

    # 손실 차분 시계열 구성: d_t = Loss(Champion) - Loss(Challenger)
    if loss_metric == "squared":
        loss_diff = ((y_t - y_champ) ** 2) - ((y_t - y_chall) ** 2)
    elif loss_metric == "absolute":
        loss_diff = np.abs(y_t - y_champ) - np.abs(y_t - y_chall)
    else:
        raise ValueError(f"지원하지 않는 loss_metric 입니다: {loss_metric}")

    mean_loss_diff = float(np.mean(loss_diff))
    residuals = loss_diff - mean_loss_diff

    hac_variance = _calculate_hac_variance(residuals, max_lags=max_lags)
    if hac_variance <= 0.0 or not np.isfinite(hac_variance):
        return 0.0, 1.0

    standard_error = float(np.sqrt(hac_variance / total_samples))
    if standard_error == 0.0:
        return 0.0, 1.0

    dm_stat = mean_loss_diff / standard_error
    # Challenger 우월성에 대한 단측 검정 (Right-tailed test)
    p_value = float(1.0 - stats.norm.cdf(dm_stat))

    return float(dm_stat), float(p_value)

# ==============================================================================
# 내부 수리 정제 및 공통 커널 헬퍼 (Private Helpers)
# ==============================================================================

def _to_numpy_array(data: Union[np.ndarray, pd.Series, pd.DataFrame, list]) -> np.ndarray:
    """다양한 형태의 1차원 시계열 데이터를 1차원 float64 NumPy 배열로 안전하게 통일 변환합니다.

    Args:
        data: NumPy 배열, Pandas Series/DataFrame, 파이썬 리스트 등 입력 데이터.

    Returns:
        np.ndarray: C-contiguous 1차원 float64 NumPy 배열.

    Raises:
        TypeError: 지원하지 않는 자료형이 인입된 경우 발생.
    """
    if isinstance(data, (pd.Series, pd.DataFrame)):
        return np.ascontiguousarray(data.to_numpy(dtype=np.float64).flatten())
    elif isinstance(data, list):
        return np.ascontiguousarray(np.array(data, dtype=np.float64).flatten())
    elif isinstance(data, np.ndarray):
        return np.ascontiguousarray(data.astype(np.float64).flatten())
    else:
        raise TypeError(f"지원하지 않는 데이터 타입입니다: {type(data)}")


def _align_and_clean_arrays(
    y_true: Union[np.ndarray, pd.Series, pd.DataFrame, list],
    y_pred: Union[np.ndarray, pd.Series, pd.DataFrame, list],
) -> Tuple[np.ndarray, np.ndarray]:
    """두 시계열의 유효 구간(Finite)을 동시 필터링하여 인덱스가 정렬된 무결성 배열 쌍을 추출합니다.

    Args:
        y_true: 실제 정답 타겟 시계열.
        y_pred: 모델 예측값 시계열.

    Returns:
        Tuple[np.ndarray, np.ndarray]: 결측치 및 무한대가 제거된 (y_true_clean, y_pred_clean) 튜플.
    """
    y_t = _to_numpy_array(y_true)
    y_p = _to_numpy_array(y_pred)

    if len(y_t) == 0 or len(y_p) == 0 or len(y_t) != len(y_p):
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)

    # 단일 비트 연산으로 양쪽 배열의 NaN/Inf를 동시 마스킹하여 메모리 복제 최소화
    valid_mask = np.isfinite(y_t) & np.isfinite(y_p)
    return y_t[valid_mask], y_p[valid_mask]


def _calculate_hac_variance(
    residuals: np.ndarray,
    max_lags: Optional[int] = None,
    holding_period: int = 20,
) -> float:
    """시계열 자기상관 및 이분산성을 보정하는 Newey-West HAC 장기 분산을 산출합니다.

    Args:
        residuals: 평균이 0으로 중심화된 잔차 시계열 (T,).
        max_lags: Newey-West 커널 대역폭 (None일 경우 holding_period 이상 보장).
        holding_period: 중첩 자기상관 차수 기준 (기본값: 20영업일).

    Returns:
        float: 장기 점근 분산(Long-run Variance) 추정치.
    """
    total_samples = len(residuals)
    if total_samples < 2:
        return 0.0

    # [설계 의도] 20일 중첩 구조에서는 최소 20시차(MA(19)) 이상의 공분산 누적이 필수적이므로 하한선 강제
    if max_lags is None:
        heuristic_lags = int(np.floor(4.0 * (total_samples / 100.0) ** (2.0 / 9.0)))
        max_lags = max(holding_period, heuristic_lags)

    # [수리적 보정] Newey-West(1987) 준정정치성 보장을 위해 전 시차 분모를 동일 표본 수(T)로 정규화
    gamma_0 = float(np.sum(residuals ** 2) / total_samples)
    hac_variance = gamma_0

    # Bartlett Kernel 선형 가중치를 적용한 자기공분산 누적 합산
    for lag in range(1, max_lags + 1):
        if lag >= total_samples:
            break
        weight = 1.0 - (lag / (max_lags + 1.0))
        autocovariance = float(np.sum(residuals[lag:] * residuals[:-lag]) / total_samples)
        hac_variance += 2.0 * weight * autocovariance

    return float(max(0.0, hac_variance))

def _to_position_weights(
    y_pred: np.ndarray,
    pred_std: Optional[float] = None,
) -> np.ndarray:
    """연속형 예측 수익률을 신뢰도(Conviction) 기반의 포지션 비중 [-1.0, 1.0]으로 변환합니다.

    단순 부호(np.sign) 기반의 100% 무조건 풀 레버리지 베팅을 탈피하고,
    예측 신호의 크기(Magnitude)와 분산에 비례하여 포지션 비중을 동적 결정합니다.
    확신도가 낮은 0 부근에서는 현금 버퍼(Cash Buffer, 비중 ≈ 0)를 확보하여
    손실 복리 누적 및 궤멸적 최대 낙폭(MDD)을 원천 차단합니다.
    """
    if len(y_pred) == 0:
        return np.empty(0, dtype=np.float64)

    # [설계 의도] Train CV에서 동결된 pred_std를 주입받아 Test 전체 사후 분산 참조(Look-ahead Bias) 차단
    if pred_std is not None and pred_std > 0.0 and np.isfinite(pred_std):
        effective_std: float = float(pred_std)
    else:
        effective_std = float(np.std(y_pred, ddof=1)) if len(y_pred) > 1 else 0.0

    if effective_std <= 1e-8 or not np.isfinite(effective_std):
        return np.sign(y_pred)

    # Z-Score 정규화 후 tanh 비선형 스케일링으로 유계화
    return np.tanh(y_pred / effective_std)