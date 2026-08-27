
from typing import Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats


def _to_numpy_array(data: Union[np.ndarray, pd.Series, list]) -> np.ndarray:
    """입력 데이터를 1차원 float64 NumPy 배열로 안전하게 변환합니다."""
    if isinstance(data, (pd.Series, pd.DataFrame)):
        return data.to_numpy(dtype=np.float64).flatten()
    elif isinstance(data, list):
        return np.array(data, dtype=np.float64).flatten()
    elif isinstance(data, np.ndarray):
        return data.astype(np.float64).flatten()
    else:
        raise TypeError(f"지원하지 않는 데이터 타입입니다: {type(data)}")


def _align_and_clean_arrays(
    y_true: Union[np.ndarray, pd.Series, list],
    y_pred: Union[np.ndarray, pd.Series, list]
) -> Tuple[np.ndarray, np.ndarray]:
    """두 시계열을 1차원 변환 후 동일한 인덱스의 유한값(Finite)만 공통 마스킹 추출합니다."""
    y_t = _to_numpy_array(y_true)
    y_p = _to_numpy_array(y_pred)

    if len(y_t) == 0:
        return np.empty(0, dtype=np.float64), np.empty(0, dtype=np.float64)

    valid_mask = np.isfinite(y_t) & np.isfinite(y_p)
    return y_t[valid_mask], y_p[valid_mask]


# =================================================================================================
# Layer 1. 기계학습 기본 예측 오차 (Statistical Forecast Error)
# =================================================================================================

def mda(
    y_true: Union[np.ndarray, pd.Series], 
    y_pred: Union[np.ndarray, pd.Series]
) -> float:
    """평균 방향성 적중률(Mean Directional Accuracy)을 산출합니다."""
    y_t = _to_numpy_array(y_true)
    y_p = _to_numpy_array(y_pred)
    
    if len(y_t) == 0:
        return 0.0
    
    sign_true = np.sign(y_t)
    sign_pred = np.sign(y_p)
    
    return float(np.mean(np.equal(sign_true, sign_pred)))


def rmse(
    y_true: Union[np.ndarray, pd.Series], 
    y_pred: Union[np.ndarray, pd.Series]
) -> float:
    """평균 제곱근 오차(Root Mean Squared Error)를 산출합니다."""
    y_t = _to_numpy_array(y_true)
    y_p = _to_numpy_array(y_pred)
    
    if len(y_t) == 0:
        return 0.0
    
    return float(np.sqrt(np.mean((y_t - y_p) ** 2)))


def mae(
    y_true: Union[np.ndarray, pd.Series], 
    y_pred: Union[np.ndarray, pd.Series]
) -> float:
    """평균 절대 오차(Mean Absolute Error)를 산출합니다."""
    y_t = _to_numpy_array(y_true)
    y_p = _to_numpy_array(y_pred)
    
    if len(y_t) == 0:
        return 0.0
    
    return float(np.mean(np.abs(y_t - y_p)))


# =================================================================================================
# Layer 2. 퀀트 팩터 신호 품질 (Quant Factor Signal Quality)
# =================================================================================================

def rank_ic(
    y_true: Union[np.ndarray, pd.Series], 
    y_pred: Union[np.ndarray, pd.Series]
) -> float:
    """스피어만 순위 상관계수(Spearman Rank Information Coefficient)를 산출합니다."""
    y_t = _to_numpy_array(y_true)
    y_p = _to_numpy_array(y_pred)
    
    if len(y_t) != len(y_p) or len(y_t) < 3:
        return 0.0
    
    rank_true = stats.rankdata(y_t)
    rank_pred = stats.rankdata(y_p)
    
    if np.std(rank_true) == 0 or np.std(rank_pred) == 0:
        return 0.0
        
    correlation, _ = stats.pearsonr(rank_true, rank_pred)
    return float(correlation) if not np.isnan(correlation) else 0.0


def icir(
    y_true: Union[np.ndarray, pd.Series, list],
    y_pred: Optional[Union[np.ndarray, pd.Series, list]] = None,
    window_size: int = 20,
    step_size: Optional[int] = None
) -> float:
    """시계열을 슬라이싱하여 산출된 Rank IC 시계열의 정보 비율(ICIR)을 계산합니다.
    
    y_pred가 None일 경우 y_true를 이미 계산된 Rank IC 배열로 간주하여 처리합니다.
    """
    # 1. 이미 계산된 Rank IC 시계열이 단독 인입된 경우
    if y_pred is None:
        ic_arr = _to_numpy_array(y_true)
        ic_arr = ic_arr[np.isfinite(ic_arr)]
        if len(ic_arr) < 2:
            return 0.0
        ic_std = float(np.std(ic_arr, ddof=1))
        return float(np.mean(ic_arr) / ic_std) if ic_std > 0.0 and not np.isnan(ic_std) else 0.0

    # 2. y_true, y_pred가 인입된 경우 내부 슬라이싱 연산 집행
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    n_samples = len(y_t)
    if n_samples < window_size * 2:
        return rank_ic(y_t, y_p)

    step = step_size if step_size is not None else max(1, window_size // 2)
    rolling_rank_ics: list[float] = []

    for start_idx in range(0, n_samples - window_size + 1, step):
        end_idx = start_idx + window_size
        sub_ic = rank_ic(y_t[start_idx:end_idx], y_p[start_idx:end_idx])
        rolling_rank_ics.append(sub_ic)

    ic_arr = np.array(rolling_rank_ics, dtype=np.float64)
    ic_arr = ic_arr[np.isfinite(ic_arr)]
    if len(ic_arr) < 2:
        return 0.0

    ic_std = float(np.std(ic_arr, ddof=1))
    return float(np.mean(ic_arr) / ic_std) if ic_std > 0.0 and not np.isnan(ic_std) else 0.0


# =================================================================================================
# Layer 3. 금융 시뮬레이션 성과 (Financial Strategy Simulation)
# =================================================================================================

def signal_sharpe(
    y_true: Union[np.ndarray, pd.Series], 
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
    annual_days: float = 252.0,
    risk_free_rate: float = 0.0
) -> float:
    """20일 보유 주기를 반영한 위험조정 샤프 지수를 산출합니다."""
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) < 2:
        return 0.0
        
    annual_factor = annual_days / max(1, holding_period)
    strategy_returns = np.sign(y_p) * y_t
    mean_ret = np.mean(strategy_returns) - (risk_free_rate / annual_factor)
    std_ret = np.std(strategy_returns, ddof=1)
    
    if std_ret <= 0.0 or np.isnan(std_ret):
        return 0.0
        
    return float(np.sqrt(annual_factor) * (mean_ret / std_ret))


def sortino_ratio(
    y_true: Union[np.ndarray, pd.Series], 
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20,
    annual_days: float = 252.0,
    target_return: float = 0.0
) -> float:
    """하방 위험만을 반영한 연율화 소르티노 지수를 산출합니다."""
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) < 2:
        return 0.0
        
    annual_factor = annual_days / max(1, holding_period)
    strategy_returns = np.sign(y_p) * y_t
    mean_ret = np.mean(strategy_returns) - (target_return / annual_factor)
    
    downside_diff = np.minimum(0.0, strategy_returns - (target_return / annual_factor))
    downside_dev = np.sqrt(np.mean(downside_diff ** 2))
    
    if downside_dev <= 0.0 or np.isnan(downside_dev):
        return 0.0
        
    return float(np.sqrt(annual_factor) * (mean_ret / downside_dev))


def mdd(
    y_true: Union[np.ndarray, pd.Series], 
    y_pred: Union[np.ndarray, pd.Series],
    holding_period: int = 20
) -> float:
    """로그 수익률 지수 누적 기반으로 최대 낙폭(MDD)을 [0.0, 1.0] 범위로 산출합니다."""
    y_t, y_p = _align_and_clean_arrays(y_true, y_pred)
    if len(y_t) == 0:
        return 0.0
        
    # 20일 중첩 수익률을 단일 스텝 수익률로 정규화 후 연속 복리 자산 곡선 형성
    step_returns = (np.sign(y_p) * y_t) / max(1, holding_period)
    log_wealth = np.cumsum(step_returns)
    wealth_index = np.exp(log_wealth)
    
    running_max = np.maximum.accumulate(wealth_index)
    drawdowns = (running_max - wealth_index) / np.maximum(running_max, 1e-8)
    
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    return min(1.0, max(0.0, max_dd))


# =================================================================================================
# Layer 4. 단일 신호 통계적 유의성 (Single-Model Signal Significance)
# =================================================================================================

def newey_west_tstat(
    y_true: Union[np.ndarray, pd.Series], 
    y_pred: Union[np.ndarray, pd.Series],
    max_lags: Optional[int] = None
) -> Tuple[float, float]:
    """
    시계열 자기상관 및 이분산성을 보정한 Newey-West Factor t-통계량과 p-value를 산출합니다.
    
    Returns:
        Tuple[float, float]: (t_statistic, p_value)
    """
    y_t = _to_numpy_array(y_true)
    y_p = _to_numpy_array(y_pred)
    T = len(y_t)
    
    if T != len(y_p) or T < 5:
        return 0.0, 1.0
        
    strategy_returns = np.sign(y_p) * y_t
    mean_ret = np.mean(strategy_returns)
    residuals = strategy_returns - mean_ret
    
    if max_lags is None:
        max_lags = max(1, int(np.floor(4.0 * (T / 100.0) ** (2.0 / 9.0))))
        
    gamma_0 = np.mean(residuals ** 2)
    hac_variance = gamma_0
    for lag in range(1, max_lags + 1):
        weight = 1.0 - (lag / (max_lags + 1.0))
        autocov = np.mean(residuals[lag:] * residuals[:-lag])
        hac_variance += 2.0 * weight * autocov
        
    if hac_variance <= 0.0 or np.isnan(hac_variance):
        return 0.0, 1.0
        
    standard_error = np.sqrt(hac_variance / T)
    if standard_error == 0.0:
        return 0.0, 1.0
        
    t_stat = mean_ret / standard_error
    p_value = 2.0 * (1.0 - stats.norm.cdf(np.abs(t_stat)))
    
    return float(t_stat), float(p_value)


# =================================================================================================
# Layer 5. Champion-Challenger A/B 비교 검정 (Pairwise Predictive Superiority)
# =================================================================================================

def diebold_mariano_test(
    y_true: Union[np.ndarray, pd.Series],
    y_pred_champion: Union[np.ndarray, pd.Series],
    y_pred_challenger: Union[np.ndarray, pd.Series],
    loss_metric: str = "squared",
    max_lags: Optional[int] = None
) -> Tuple[float, float]:
    """
    Champion vs Challenger 예측 손실 차이에 대한 Diebold-Mariano 검정을 수행합니다.
    
    Returns:
        Tuple[float, float]: (DM_statistic, p_value_one_sided_challenger_superior)
    """
    y_t = _to_numpy_array(y_true)
    y_champ = _to_numpy_array(y_pred_champion)
    y_chall = _to_numpy_array(y_pred_challenger)
    T = len(y_t)
    
    if not (T == len(y_champ) == len(y_chall)) or T < 5:
        return 0.0, 1.0
        
    if loss_metric == "squared":
        loss_diff = ((y_t - y_champ) ** 2) - ((y_t - y_chall) ** 2)
    elif loss_metric == "absolute":
        loss_diff = np.abs(y_t - y_champ) - np.abs(y_t - y_chall)
    else:
        raise ValueError(f"지원하지 않는 loss_metric 입니다: {loss_metric}")
        
    mean_diff = np.mean(loss_diff)
    diff_centered = loss_diff - mean_diff
    
    if max_lags is None:
        max_lags = max(1, int(np.floor(4.0 * (T / 100.0) ** (2.0 / 9.0))))
        
    gamma_0 = np.mean(diff_centered ** 2)
    hac_variance = gamma_0
    for lag in range(1, max_lags + 1):
        weight = 1.0 - (lag / (max_lags + 1.0))
        autocov = np.mean(diff_centered[lag:] * diff_centered[:-lag])
        hac_variance += 2.0 * weight * autocov
        
    if hac_variance <= 0.0 or np.isnan(hac_variance):
        return 0.0, 1.0
        
    dm_stat = mean_diff / np.sqrt(hac_variance / T)
    p_value = 1.0 - stats.norm.cdf(dm_stat)
    
    return float(dm_stat), float(p_value)