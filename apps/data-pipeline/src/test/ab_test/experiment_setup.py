from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd

from src.test.backtest.backtest_loader import (
    LoadedBacktestArtifacts,
    load_backtest_artifacts,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_ARTIFACT_ROOT: str = "artifacts/backtest"  # 백테스트 아티팩트 기본 루트 디렉터리 경로
STRATEGY_RAW_PREFIX: str = "Strategy_1_Raw_Model"  # 미적용 원시 모델(Raw Baseline) 컬럼 접두사
STRATEGY_GATED_PREFIX: str = "Strategy_2_XAI-Gated"  # XAI 방어 거버넌스 모델(Treatment) 컬럼 접두사
BENCHMARK_PREFIX: str = "Strategy_0_Benchmark"  # 벤치마크(KOSPI) 컬럼 접두사


# ==============================================================================
# State Container (Class + Functional Lifecycle)
# ==============================================================================
@dataclass(frozen=True)
class ExperimentContext:
    """축 3(거버넌스 정책 축) A/B 테스트 집행에 필요한 데이터 컨텍스트를 보존하는 불변 컨테이너."""

    total_trading_days: int  # 전체 평가 기간 총 거래일 수
    cv_trading_days: int  # CV 윈도우 동결 관측 기간 (거래일)
    holding_period: int  # 포지션 보유 호라이즌 (거래일)
    trade_dates: np.ndarray  # 정렬된 거래일자 1차원 벡터 (T,)
    raw_returns: np.ndarray  # 미적용 모델 일별 실현 수익률 벡터 (T,)
    gated_returns: np.ndarray  # 방어 거버넌스 일별 실현 수익률 벡터 (T,)
    raw_drawdowns: np.ndarray  # 미적용 모델 일별 낙폭(Drawdown) 벡터 (T,)
    gated_drawdowns: np.ndarray  # 방어 거버넌스 일별 낙폭(Drawdown) 벡터 (T,)
    raw_nav: np.ndarray  # 미적용 모델 일별 기준가(NAV) 벡터 (T,)
    gated_nav: np.ndarray  # 방어 거버넌스 일별 기준가(NAV) 벡터 (T,)
    raw_positions: np.ndarray  # 미적용 모델 일별 포지션 비중 벡터 (T,)
    gated_positions: np.ndarray  # 방어 거버넌스 일별 포지션 비중 벡터 (T,)
    predictions_raw: np.ndarray  # 모델 원시 예측값 시계열 벡터 (T,)
    composite_risk_gates: np.ndarray  # 복합 리스크 게이트 G_t 시계열 벡터 (T,)
    summary_table: pd.DataFrame  # 실험 환경 동결 및 정렬 무결성 검증 요약표
    manifest: Dict[str, Any]  # 백테스트 실행 매니페스트 메타데이터


# ==============================================================================
# Public API Functions
# ==============================================================================
def setup_experiment_environment(
    total_trading_days: int,
    cv_trading_days: int,
    holding_period: int,
    artifact_root: str = DEFAULT_ARTIFACT_ROOT,
    loaded_artifacts: Optional[LoadedBacktestArtifacts] = None,
) -> ExperimentContext:
    """백테스트 산출물을 로드하고 평가 관측창 동결 및 무결성을 검증하여 실험 컨텍스트를 바인딩합니다.

    Args:
        total_trading_days (int): 전체 평가 기간 기대 거래일 수.
        cv_trading_days (int): CV 관측창 동결 거래일 수.
        holding_period (int): 포지션 보유 호라이즌(일).
        artifact_root (str): 아티팩트 루트 디렉터리 경로 (기본값: 'artifacts/backtest').
        loaded_artifacts (Optional[LoadedBacktestArtifacts]): 사전 로드된 아티팩트 객체 (None 시 자동 로드).

    Returns:
        ExperimentContext: A/B 테스트 검정에 즉시 투입 가능한 정렬된 벡터 및 검증 요약 컨테이너.

    Raises:
        ValueError: 거래일 수가 기대치와 불일치하거나 필수 컬럼 결손, 시계열 불일치가 발생한 경우.
    """
    artifacts = _resolve_artifacts(artifact_root, loaded_artifacts)
    _validate_artifacts_integrity(artifacts, total_trading_days)

    extracted_arrays = _extract_aligned_vectors(artifacts)
    summary_df = _build_integrity_summary_table(
        artifacts=artifacts,
        arrays=extracted_arrays,
        total_trading_days=total_trading_days,
        cv_trading_days=cv_trading_days,
        holding_period=holding_period,
    )

    return _create_experiment_context(
        total_trading_days=total_trading_days,
        cv_trading_days=cv_trading_days,
        holding_period=holding_period,
        arrays=extracted_arrays,
        summary_df=summary_df,
        manifest=artifacts.manifest,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _resolve_artifacts(
    artifact_root: str,
    loaded_artifacts: Optional[LoadedBacktestArtifacts],
) -> LoadedBacktestArtifacts:
    """입력 인자로부터 아티팩트 객체를 확보하거나 디스크에서 로드합니다."""
    if loaded_artifacts is not None:
        return loaded_artifacts
    return load_backtest_artifacts(artifact_root=artifact_root)


def _validate_artifacts_integrity(
    artifacts: LoadedBacktestArtifacts,
    total_trading_days: int,
) -> None:
    """시계열 원장, 시그널 테이블의 거래일 일치 및 필수 컬럼 존재 여부를 검증합니다."""
    ledgers = artifacts.simulation_ledgers
    signals = artifacts.strategy_signals

    if len(ledgers) != total_trading_days:
        raise ValueError(
            f"시뮬레이션 원장 거래일 수가 기대치와 다릅니다: {len(ledgers)} != {total_trading_days}"
        )
    if len(signals) != total_trading_days:
        raise ValueError(
            f"전략 시그널 거래일 수가 기대치와 다릅니다: {len(signals)} != {total_trading_days}"
        )

    # 날짜 인덱스 상호 일치 검증
    dates_ledgers = (
        ledgers.index.to_numpy()
        if isinstance(ledgers.index, pd.DatetimeIndex)
        else pd.to_datetime(ledgers["trade_date"]).to_numpy()
    )
    dates_signals = (
        signals.index.to_numpy()
        if isinstance(signals.index, pd.DatetimeIndex)
        else pd.to_datetime(signals["trade_date"]).to_numpy()
    )
    if not np.array_equal(dates_ledgers, dates_signals):
        raise ValueError("시뮬레이션 원장과 전략 시그널 간의 거래일자(trade_date) 정렬이 불일치합니다.")

    required_ledger_cols = [
        f"{STRATEGY_RAW_PREFIX}__strategy_return",
        f"{STRATEGY_RAW_PREFIX}__drawdown",
        f"{STRATEGY_RAW_PREFIX}__nav",
        f"{STRATEGY_GATED_PREFIX}__strategy_return",
        f"{STRATEGY_GATED_PREFIX}__drawdown",
        f"{STRATEGY_GATED_PREFIX}__nav",
    ]
    for col in required_ledger_cols:
        if col not in ledgers.columns:
            raise ValueError(f"시뮬레이션 원장에 필수 컬럼이 결손되었습니다: {col}")

    required_signal_cols = [
        "prediction_raw",
        "position_raw",
        "position_gated",
        "composite_risk_gate",
    ]
    for col in required_signal_cols:
        if col not in signals.columns:
            raise ValueError(f"전략 시그널에 필수 컬럼이 결손되었습니다: {col}")


def _extract_aligned_vectors(artifacts: LoadedBacktestArtifacts) -> Dict[str, np.ndarray]:
    """DataFrame으로부터 A/B 테스트에 투입할 1차원 NumPy 배열을 정렬 추출합니다."""
    ledgers = artifacts.simulation_ledgers
    signals = artifacts.strategy_signals

    trade_dates = (
        ledgers.index.to_numpy()
        if isinstance(ledgers.index, pd.DatetimeIndex)
        else pd.to_datetime(ledgers["trade_date"]).to_numpy()
    )

    return {
        "trade_dates": trade_dates,
        "raw_returns": ledgers[f"{STRATEGY_RAW_PREFIX}__strategy_return"].to_numpy(dtype=np.float64),
        "gated_returns": ledgers[f"{STRATEGY_GATED_PREFIX}__strategy_return"].to_numpy(dtype=np.float64),
        "raw_drawdowns": ledgers[f"{STRATEGY_RAW_PREFIX}__drawdown"].to_numpy(dtype=np.float64),
        "gated_drawdowns": ledgers[f"{STRATEGY_GATED_PREFIX}__drawdown"].to_numpy(dtype=np.float64),
        "raw_nav": ledgers[f"{STRATEGY_RAW_PREFIX}__nav"].to_numpy(dtype=np.float64),
        "gated_nav": ledgers[f"{STRATEGY_GATED_PREFIX}__nav"].to_numpy(dtype=np.float64),
        "raw_positions": signals["position_raw"].to_numpy(dtype=np.float64),
        "gated_positions": signals["position_gated"].to_numpy(dtype=np.float64),
        "predictions_raw": signals["prediction_raw"].to_numpy(dtype=np.float64),
        "composite_risk_gates": signals["composite_risk_gate"].to_numpy(dtype=np.float64),
    }


def _build_integrity_summary_table(
    artifacts: LoadedBacktestArtifacts,
    arrays: Dict[str, np.ndarray],
    total_trading_days: int,
    cv_trading_days: int,
    holding_period: int,
) -> pd.DataFrame:
    """평가 윈도우 동결 및 시계열 정렬 무결성을 요약한 데이터프레임을 생성합니다."""
    manifest_period = artifacts.manifest.get("evaluation_period", {})
    start_date = manifest_period.get("start", "N/A")
    end_date = manifest_period.get("end", "N/A")

    n_samples = len(arrays["trade_dates"])
    n_eff = n_samples // holding_period
    min_eff_threshold = cv_trading_days // holding_period
    nan_count = int(
        np.isnan(arrays["raw_returns"]).sum()
        + np.isnan(arrays["gated_returns"]).sum()
        + np.isnan(arrays["predictions_raw"]).sum()
    )

    rows = [
        {
            "Audit Metric": "Evaluation Period",
            "Observed Value": f"{start_date} ~ {end_date}",
            "Reference Baseline": f"Test Horizon (Target {total_trading_days}d)",
            "Integrity Status": "VERIFIED",
        },
        {
            "Audit Metric": "Total Trading Days (T)",
            "Observed Value": f"{n_samples} days",
            "Reference Baseline": f"{total_trading_days} days",
            "Integrity Status": "MATCH" if n_samples == total_trading_days else "MISMATCH",
        },
        {
            "Audit Metric": "Effective Sample Size (N_eff)",
            "Observed Value": f"{n_eff} blocks",
            "Reference Baseline": f">= {min_eff_threshold} blocks (CV Frozen)",
            "Integrity Status": "POWER_SATISFIED" if n_eff >= min_eff_threshold else "UNDERPOWERED",
        },
        {
            "Audit Metric": "Series Alignment & NaN Count",
            "Observed Value": f"{nan_count} NaNs",
            "Reference Baseline": "0 NaNs Required",
            "Integrity Status": "CLEAN" if nan_count == 0 else "CORRUPTED",
        },
        {
            "Audit Metric": "Target Comparison Group",
            "Observed Value": f"{STRATEGY_RAW_PREFIX} vs {STRATEGY_GATED_PREFIX}",
            "Reference Baseline": "Axis 3 (Raw Baseline vs Risk-Gated)",
            "Integrity Status": "BOUND",
        },
    ]
    return pd.DataFrame(rows)


def _create_experiment_context(
    total_trading_days: int,
    cv_trading_days: int,
    holding_period: int,
    arrays: Dict[str, np.ndarray],
    summary_df: pd.DataFrame,
    manifest: Dict[str, Any],
) -> ExperimentContext:
    """추출된 배열과 요약표를 불변 ExperimentContext 객체로 조립합니다."""
    return ExperimentContext(
        total_trading_days=total_trading_days,
        cv_trading_days=cv_trading_days,
        holding_period=holding_period,
        trade_dates=arrays["trade_dates"],
        raw_returns=arrays["raw_returns"],
        gated_returns=arrays["gated_returns"],
        raw_drawdowns=arrays["raw_drawdowns"],
        gated_drawdowns=arrays["gated_drawdowns"],
        raw_nav=arrays["raw_nav"],
        gated_nav=arrays["gated_nav"],
        raw_positions=arrays["raw_positions"],
        gated_positions=arrays["gated_positions"],
        predictions_raw=arrays["predictions_raw"],
        composite_risk_gates=arrays["composite_risk_gates"],
        summary_table=summary_df,
        manifest=manifest,
    )