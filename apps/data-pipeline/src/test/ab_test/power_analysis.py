from typing import Dict, Optional, Tuple, Union, Any
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


# ==============================================================================
# Public API Functions
# ==============================================================================
def run_ex_ante_power_analysis(
    loaded_artifacts: Optional[Any] = None,
    simulation_ledgers: Optional[pd.DataFrame] = None,
    holding_period: Optional[int] = None,
    total_trading_days: Optional[int] = None,
    cv_trading_days: Optional[int] = None,
    alpha: float = DEFAULT_ALPHA,
    target_power: float = DEFAULT_TARGET_POWER,
    target_cohen_d: float = DEFAULT_MIN_COHEN_D,
    one_sided: bool = True,
) -> pd.DataFrame:
    """Phase 0 사전 실험계획에 따른 유효 표본 크기 및 통계적 검정력 감사 판정표를 산출합니다.

    입력된 백테스트 아티팩트 또는 시뮬레이션 원장으로부터 전체 관측 거래일 수, CV 관측창, 보유 호라이즌을
    동적으로 추출하고, 보유 호라이즌으로 인한 자기상관 왜곡을 방어하기 위해 비중첩 유효 표본 크기(N_eff)를
    환산한 뒤 Test 및 CV 관측창의 통계적 검정력(1 - Beta) 충족 여부를 정밀 검정합니다.

    Args:
        loaded_artifacts (Optional[Any]): 사전 로드된 백테스트 아티팩트 컨테이너 (기본값: None).
        simulation_ledgers (Optional[pd.DataFrame]): 일별 시뮬레이션 장부 데이터프레임 (기본값: None).
        holding_period (Optional[int]): 보유 호라이즌 및 비중첩 보폭 (기본값: None, 메타데이터 자동 추출).
        total_trading_days (Optional[int]): 명시적 전체 평가 거래일 수 (기본값: None, 데이터 기반 동적 추출).
        cv_trading_days (Optional[int]): 명시적 CV 관측창 거래일 수 (기본값: None, 메타데이터 자동 추출).
        alpha (float): 유의수준 (기본값: 0.05).
        target_power (float): 목표 사전 검정력 기준 (기본값: 0.80).
        target_cohen_d (float): 최소 탐지 가능 효과 크기 MDE (기본값: 0.25).
        one_sided (bool): 단측 검정 여부 (기본값: True).

    Returns:
        pd.DataFrame: 관측 구간별 유효 표본 수, 달성 검정력, 필요 표본 수, 판정 결과 감사표.

    Raises:
        ValueError: 거래일 수나 보유 호라이즌을 특정할 수 없거나 입력 인자가 유효 범위를 벗어난 경우.
    """
    resolved_holding_period = _resolve_holding_period(
        loaded_artifacts=loaded_artifacts,
        explicit_period=holding_period,
    )
    resolved_total_days = _resolve_total_trading_days(
        loaded_artifacts=loaded_artifacts,
        simulation_ledgers=simulation_ledgers,
        explicit_days=total_trading_days,
    )
    resolved_cv_days = _resolve_cv_trading_days(
        loaded_artifacts=loaded_artifacts,
        explicit_days=cv_trading_days,
    )

    _validate_power_analysis_inputs(
        resolved_total_days, resolved_cv_days, resolved_holding_period, alpha, target_power, target_cohen_d
    )

    n_eff_test = _compute_effective_sample_size(resolved_total_days, resolved_holding_period)
    n_eff_cv = _compute_effective_sample_size(resolved_cv_days, resolved_holding_period)

    power_test = calculate_power(n_eff_test, target_cohen_d, alpha, one_sided)
    power_cv = calculate_power(n_eff_cv, target_cohen_d, alpha, one_sided)

    n_required = calculate_required_sample_size(target_cohen_d, target_power, alpha, one_sided)
    mde_test = calculate_mde(n_eff_test, target_power, alpha, one_sided)
    mde_cv = calculate_mde(n_eff_cv, target_power, alpha, one_sided)

    return _create_power_audit_table(
        resolved_total_days,
        resolved_cv_days,
        resolved_holding_period,
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


def _resolve_holding_period(
    loaded_artifacts: Optional[Any],
    explicit_period: Optional[int],
) -> int:
    """명시적 인자 또는 아티팩트 메타데이터로부터 보유 호라이즌을 동적으로 추출합니다."""
    if explicit_period is not None:
        return explicit_period
    if loaded_artifacts is not None:
        manifest = getattr(loaded_artifacts, "manifest", None)
        if manifest is None and isinstance(loaded_artifacts, dict):
            manifest = loaded_artifacts.get("manifest")
        if isinstance(manifest, dict) and "holding_period" in manifest:
            return int(manifest["holding_period"])

        governance_config = getattr(loaded_artifacts, "governance_config", None)
        if governance_config is None and isinstance(loaded_artifacts, dict):
            governance_config = loaded_artifacts.get("governance_config")
        if isinstance(governance_config, dict) and "holding_period" in governance_config:
            return int(governance_config["holding_period"])

    raise ValueError(
        "보유 호라이즌(holding_period)을 특정할 수 없습니다. "
        "명시적 인자(holding_period=...)를 전달하거나 아티팩트 메타데이터에 등록해야 합니다."
    )


def _resolve_total_trading_days(
    loaded_artifacts: Optional[Any],
    simulation_ledgers: Optional[pd.DataFrame],
    explicit_days: Optional[int],
) -> int:
    """입력 아티팩트 또는 명시적 인자로부터 전체 관측 거래일 수를 동적으로 추출합니다."""
    if explicit_days is not None:
        return explicit_days
    if simulation_ledgers is not None and not simulation_ledgers.empty:
        return len(simulation_ledgers)
    if loaded_artifacts is not None:
        ledgers = getattr(loaded_artifacts, "simulation_ledgers", None)
        if ledgers is None and isinstance(loaded_artifacts, dict):
            ledgers = loaded_artifacts.get("simulation_ledgers")
        if isinstance(ledgers, pd.DataFrame) and not ledgers.empty:
            return len(ledgers)

        manifest = getattr(loaded_artifacts, "manifest", None)
        if manifest is None and isinstance(loaded_artifacts, dict):
            manifest = loaded_artifacts.get("manifest")
        if isinstance(manifest, dict):
            trading_days = manifest.get("evaluation_period", {}).get("trading_days")
            if trading_days:
                return int(trading_days)

    raise ValueError(
        "전체 평가 거래일 수(total_trading_days)를 특정할 수 없습니다. "
        "명시적 인자 또는 데이터(simulation_ledgers / loaded_artifacts)를 주입해야 합니다."
    )


def _resolve_cv_trading_days(
    loaded_artifacts: Optional[Any],
    explicit_days: Optional[int],
) -> int:
    """아티팩트 메타데이터 또는 명시적 인자로부터 CV 관측창 거래일 수를 동적으로 추출합니다."""
    if explicit_days is not None:
        return explicit_days
    if loaded_artifacts is not None:
        manifest = getattr(loaded_artifacts, "manifest", None)
        if manifest is None and isinstance(loaded_artifacts, dict):
            manifest = loaded_artifacts.get("manifest")
        if isinstance(manifest, dict):
            if "cv_window_days" in manifest:
                return int(manifest["cv_window_days"])
            cv_days = manifest.get("evaluation_period", {}).get("cv_trading_days")
            if cv_days:
                return int(cv_days)

    raise ValueError(
        "CV 관측창 거래일 수(cv_trading_days)를 특정할 수 없습니다. "
        "명시적 인자(cv_trading_days=...)를 전달하거나 아티팩트 메타데이터에 등록해야 합니다."
    )