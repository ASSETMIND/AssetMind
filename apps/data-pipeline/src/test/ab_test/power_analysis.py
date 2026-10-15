from typing import Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.statistics.error_control.power_analysis import (
    calculate_mde,
    calculate_power,
    calculate_required_sample_size,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_ALPHA: float = 0.05  # 기본 제1종 오류 유의수준 (Type I Error Rate)
DEFAULT_TARGET_POWER: float = 0.80  # 기본 목표 통계적 검정력 (1 - Beta)
DEFAULT_MIN_COHEN_D: float = 0.25  # 사전 확정 최소 탐지 가능 효과 크기 (MDE)
DEFAULT_SHARPE_DIFF: float = 0.15  # 금융 실무 샤프 지수 차이 기준 최소 탐지 임계치
DEFAULT_HOLDING_PERIOD: int = 20  # 비중첩 위상 환산 보폭 및 보유 호라이즌 (거래일)
EVALUATION_HORIZON_CV: int = 203  # CV 윈도우 동결 기준 관측 기간 (거래일)
EVALUATION_HORIZON_TEST: int = 509  # 백테스트 전체 평가 관측 기간 (거래일)


# ==============================================================================
# Public API Functions
# ==============================================================================
def run_ex_ante_power_analysis(
    total_trading_days: int = EVALUATION_HORIZON_TEST,
    cv_trading_days: int = EVALUATION_HORIZON_CV,
    holding_period: int = DEFAULT_HOLDING_PERIOD,
    alpha: float = DEFAULT_ALPHA,
    target_power: float = DEFAULT_TARGET_POWER,
    target_cohen_d: float = DEFAULT_MIN_COHEN_D,
    one_sided: bool = True,
) -> pd.DataFrame:
    """Phase 0 사전 실험계획에 따른 유효 표본 크기 및 통계적 검정력 감사 판정표를 산출합니다.

    20영업일 보유 호라이즌으로 인한 자기상관 왜곡을 방어하기 위해 비중첩 유효 표본 크기(N_eff)를
    환산하고, Test 전체 구간(509일) 및 CV 관측창(203일)에 대한 통계적 검정력(1 - Beta) 충족 여부를
    순수 통계 계층(src/statistics/error_control/power_analysis.py)을 호출하여 정밀 검정합니다.

    Args:
        total_trading_days (int): 백테스트 전체 평가 거래일 수 (기본값: 509).
        cv_trading_days (int): CV 벤치마크 관측창 거래일 수 (기본값: 203).
        holding_period (int): 보유 호라이즌 및 비중첩 보폭 (기본값: 20).
        alpha (float): 유의수준 (기본값: 0.05).
        target_power (float): 목표 사전 검정력 기준 (기본값: 0.80).
        target_cohen_d (float): 최소 탐지 가능 효과 크기 MDE (기본값: 0.25).
        one_sided (bool): 단측 검정 여부 (기본값: True).

    Returns:
        pd.DataFrame: 관측 구간별 유효 표본 수, 달성 검정력, 필요 표본 수, 판정 결과 감사표.

    Raises:
        ValueError: 입력 거래일 수, 보유 호라이즌, 유의수준 또는 검정력이 유효하지 않은 경우.
    """
    _validate_power_analysis_inputs(
        total_trading_days, cv_trading_days, holding_period, alpha, target_power, target_cohen_d
    )

    n_eff_test = _compute_effective_sample_size(total_trading_days, holding_period)
    n_eff_cv = _compute_effective_sample_size(cv_trading_days, holding_period)

    power_test = calculate_power(n_eff_test, target_cohen_d, alpha, one_sided)
    power_cv = calculate_power(n_eff_cv, target_cohen_d, alpha, one_sided)

    n_required = calculate_required_sample_size(target_cohen_d, target_power, alpha, one_sided)
    mde_test = calculate_mde(n_eff_test, target_power, alpha, one_sided)
    mde_cv = calculate_mde(n_eff_cv, target_power, alpha, one_sided)

    return _create_power_audit_table(
        total_trading_days,
        cv_trading_days,
        holding_period,
        n_eff_test,
        n_eff_cv,
        power_test,
        power_cv,
        target_power,
        n_required,
        mde_test,
        mde_cv,
        target_cohen_d,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_power_analysis_inputs(
    total_days: int,
    cv_days: int,
    holding_period: int,
    alpha: float,
    target_power: float,
    cohen_d: float,
) -> None:
    """사전 검정력 분석 입력 인자의 유효성을 검증합니다."""
    if total_days <= 0 or cv_days <= 0 or holding_period <= 0:
        raise ValueError("거래일 수와 보유 호라이즌은 양의 정수여야 합니다.")
    if not (0.0 < alpha < 1.0) or not (0.0 < target_power < 1.0):
        raise ValueError("유의수준(alpha)과 목표 검정력은 (0, 1) 범위 내의 값이어야 합니다.")
    if cohen_d <= 0.0:
        raise ValueError("Cohen's d 효과 크기는 양수여야 합니다.")


def _compute_effective_sample_size(
    trading_days: int,
    holding_period: int,
) -> int:
    """보유 호라이즌 보폭 기반 비중첩 독립 유효 표본 크기를 산출합니다."""
    return max(1, trading_days // holding_period)


def _create_power_audit_table(
    total_days: int,
    cv_days: int,
    holding_period: int,
    n_eff_test: int,
    n_eff_cv: int,
    power_test: float,
    power_cv: float,
    target_power: float,
    n_required: int,
    mde_test: float,
    mde_cv: float,
    target_cohen_d: float,
) -> pd.DataFrame:
    """평가 윈도우별 유효 표본 크기 및 검정력 감사 판정표를 조립하여 반환합니다."""
    required_days = n_required * holding_period
    rows = [
        {
            "Evaluation Scope": f"Test Horizon (Overall {total_days}d)",
            "Observed Days": total_days,
            "Holding Period": holding_period,
            "Effective N (N_eff)": n_eff_test,
            "Target MDE (Cohen's d)": target_cohen_d,
            "Achievable MDE": mde_test,
            "Achieved Power (1-β)": round(power_test, 4),
            "Target Power": target_power,
            "Required N_eff": n_required,
            "Required Days": required_days,
            "Audit Verdict": "PASS" if power_test >= target_power else "WARNING (Underpowered)",
        },
        {
            "Evaluation Scope": f"CV Window (Frozen {cv_days}d)",
            "Observed Days": cv_days,
            "Holding Period": holding_period,
            "Effective N (N_eff)": n_eff_cv,
            "Target MDE (Cohen's d)": target_cohen_d,
            "Achievable MDE": mde_cv,
            "Achieved Power (1-β)": round(power_cv, 4),
            "Target Power": target_power,
            "Required N_eff": n_required,
            "Required Days": required_days,
            "Audit Verdict": "PASS" if power_cv >= target_power else "WARNING (Underpowered)",
        },
    ]
    return pd.DataFrame(rows)