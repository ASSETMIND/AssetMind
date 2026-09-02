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
) -> float:
    """스피어만 순위 정보 계수(Spearman Rank Information Coefficient)를 산출합니다.

    Args:
        y_true: 실제 타겟 시계열.
        y_pred: 모델 예측값 시계열.

    Returns:
        float: [-1.0, 1.0] 범위의 순위 상관계수.
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) < 3:
        return 0.0

    # 동순위(Ties)를 정밀 보정하는 scipy.stats.rankdata(average) 사용
    rank_true = stats.rankdata(y_t)
    rank_pred = stats.rankdata(y_p)

    std_true = float(np.std(rank_true))
    std_pred = float(np.std(rank_pred))

    if std_true == 0.0 or std_pred == 0.0:
        return 0.0

    correlation, _ = stats.pearsonr(rank_true, rank_pred)
    return float(correlation) if np.isfinite(correlation) else 0.0


def icir(
    y_true: Union[np.ndarray, pd.Series, list],
    y_pred: Optional[Union[np.ndarray, pd.Series, list]] = None,
    window_size: int = 20,
    step_size: Optional[int] = None,
) -> float:
    """시계열을 슬라이싱하여 산출된 Rank IC 시계열의 정보 비율(ICIR)을 산출합니다.

    Args:
        y_true: 실제 타겟 시계열 (y_pred가 None일 경우 이미 산출된 Rank IC 배열로 간주).
        y_pred: 모델 예측값 시계열 (None일 경우 y_true 단독 평가).
        window_size: 롤링 Rank IC 윈도우 크기 (기본값: 20 거래일).
        step_size: 롤링 이동 보폭 (기본값: None 시 window_size // 2).

    Returns:
        float: Rank IC의 평균 / 표준편차 비율 (0.5 이상 우수).
    """
    # 1. 이미 산출된 Rank IC 시계열이 단독 인입된 경우
    if y_pred is None:
        ic_arr = _to_numpy_array(y_true)
        ic_arr = ic_arr[np.isfinite(ic_arr)]
        if len(ic_arr) < 2:
            return 0.0
        ic_std = float(np.std(ic_arr, ddof=1))
        return float(np.mean(ic_arr) / ic_std) if ic_std > 0.0 and np.isfinite(ic_std) else 0.0

    # 2. y_true, y_pred가 인입된 경우 롤링 Rank IC 계산 후 집계
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    total_samples = len(y_t)

    if total_samples < window_size * 2:
        return rank_ic(y_t, y_p)

    step = step_size if step_size is not None else max(1, window_size // 2)
    rolling_rank_ics: list[float] = []

    for start_idx in range(0, total_samples - window_size + 1, step):
        end_idx = start_idx + window_size
        sub_ic = rank_ic(y_t[start_idx:end_idx], y_p[start_idx:end_idx])
        rolling_rank_ics.append(sub_ic)

    ic_arr = np.array(rolling_rank_ics, dtype=np.float64)
    ic_arr = ic_arr[np.isfinite(ic_arr)]
    if len(ic_arr) < 2:
        return 0.0

    ic_std = float(np.std(ic_arr, ddof=1))
    return float(np.mean(ic_arr) / ic_std) if ic_std > 0.0 and np.isfinite(ic_std) else 0.0


# ==============================================================================
# Layer 3. 금융 시뮬레이션 성과 (Financial Strategy Simulation)
# ==============================================================================

def signal_sharpe(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
    annual_days: float = 252.0,
    risk_free_rate: float = 0.0,
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

    annual_factor = annual_days / max(1, holding_period)
    strategy_returns = np.sign(y_p) * y_t
    mean_return = float(np.mean(strategy_returns)) - (risk_free_rate / annual_factor)
    std_return = float(np.std(strategy_returns, ddof=1))

    if std_return <= 0.0 or not np.isfinite(std_return):
        return 0.0

    return float(np.sqrt(annual_factor) * (mean_return / std_return))


def sortino_ratio(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
    annual_days: float = 252.0,
    target_return: float = 0.0,
) -> float:
    """하방 위험(Downside Deviation)만을 통제한 연율화 소르티노 지수를 산출합니다.

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

    annual_factor = annual_days / max(1, holding_period)
    strategy_returns = np.sign(y_p) * y_t
    target_threshold = target_return / annual_factor
    mean_return = float(np.mean(strategy_returns)) - target_threshold

    # 목표치 이하의 손실 구간(Downside Risk)만 제곱 평균하여 위험 분모 산출
    downside_diff = np.minimum(0.0, strategy_returns - target_threshold)
    downside_dev = float(np.sqrt(np.mean(downside_diff ** 2)))

    if downside_dev <= 0.0 or not np.isfinite(downside_dev):
        return 0.0

    return float(np.sqrt(annual_factor) * (mean_return / downside_dev))


def mdd(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
) -> float:
    """로그 수익률 지수 누적 자산 곡선을 기반으로 최대 낙폭(MDD) 비율을 산출합니다.

    Args:
        y_true: 실제 자산 수익률 시계열.
        y_pred: 모델 예측 수익률 시계열.
        holding_period: 포지션 보유 기간 (기본값: 20일).

    Returns:
        float: [0.0, 1.0] 범위의 최대 낙폭 비율.
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) == 0:
        return 0.0

    # 20일 중첩 수익률을 1거래일 단위 스텝 수익률로 정규화 후 연속 복리 자산 곡선 산출
    step_returns = (np.sign(y_p) * y_t) / max(1, holding_period)
    log_wealth = np.cumsum(step_returns)
    wealth_index = np.exp(log_wealth)

    running_max = np.maximum.accumulate(wealth_index)
    drawdowns = (running_max - wealth_index) / np.maximum(running_max, 1e-8)

    max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    return min(1.0, max(0.0, max_drawdown))


# ==============================================================================
# Layer 4. 단일 신호 통계적 유의성 (Single-Model Signal Significance)
# ==============================================================================

def newey_west_tstat(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    max_lags: Optional[int] = None,
) -> Tuple[float, float]:
    """시계열 자기상관 및 이분산성을 보정한 Newey-West Factor t-통계량과 p-value를 산출합니다.

    Args:
        y_true: 실제 자산 수익률 시계열.
        y_pred: 모델 예측 수익률 시계열.
        max_lags: HAC 보정 최대 시차 (None 시 자동 산출).

    Returns:
        Tuple[float, float]: (t_statistic, p_value_two_sided)
    """
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    total_samples = len(y_t)

    if total_samples < 5:
        return 0.0, 1.0

    strategy_returns = np.sign(y_p) * y_t
    mean_return = float(np.mean(strategy_returns))
    residuals = strategy_returns - mean_return

    hac_variance = _calculate_hac_variance(residuals, max_lags=max_lags)
    if hac_variance <= 0.0 or not np.isfinite(hac_variance):
        return 0.0, 1.0

    standard_error = float(np.sqrt(hac_variance / total_samples))
    if standard_error == 0.0:
        return 0.0, 1.0

    t_stat = mean_return / standard_error
    p_value = float(2.0 * (1.0 - stats.norm.cdf(np.abs(t_stat))))

    return float(t_stat), float(p_value)


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


def _calculate_hac_variance(residuals: np.ndarray, max_lags: Optional[int] = None) -> float:
    """시계열 자기상관(Autocorrelation) 및 이분산성을 보정하는 Newey-West HAC 분산을 산출합니다.

    Args:
        residuals: 평균이 0으로 중심화된 잔차 시계열 (T,).
        max_lags: Newey-West 커널 대역폭 (None일 경우 $4(T/100)^{2/9}$ 공식 적용).

    Returns:
        float: 장기 점근 분산(Long-run Variance) 추정치.
    """
    total_samples = len(residuals)
    if total_samples < 2:
        return 0.0

    # Stock & Watson 권장 최적 시차(Bandwidth) 휴리스틱 자동 산출
    if max_lags is None:
        max_lags = max(1, int(np.floor(4.0 * (total_samples / 100.0) ** (2.0 / 9.0))))

    gamma_0 = float(np.mean(residuals ** 2))
    hac_variance = gamma_0

    # Bartlett Kernel 선형 가중치를 적용한 자기공분산 누적 합산
    for lag in range(1, max_lags + 1):
        weight = 1.0 - (lag / (max_lags + 1.0))
        autocovariance = float(np.mean(residuals[lag:] * residuals[:-lag]))
        hac_variance += 2.0 * weight * autocovariance

    return float(max(0.0, hac_variance))