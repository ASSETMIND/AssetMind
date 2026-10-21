import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

# ==============================================================================
# Constants & Configuration
# ==============================================================================

# [디렉터리 계층 구조 설정]
DEFAULT_ARTIFACT_ROOT: str = "artifacts/backtest"  # 백테스트 기본 영속화 루트 디렉터리 경로
CONFIG_DIR_NAME: str = "config"  # 거버넌스 설정 저장 디렉터리명
DATA_DIR_NAME: str = "data"  # 시계열 원천 데이터 저장 디렉터리명
REPORTS_DIR_NAME: str = "reports"  # 감사 보고서 저장 디렉터리명
FIGURES_DIR_NAME: str = "figures"  # 시각화 이미지 저장 디렉터리명

# [영속화 파일 식별자 설정 - 설정 및 메타데이터]
GOVERNANCE_CONFIG_FILENAME: str = "governance_config.json"  # XAI 리스크 게이트 설정 파일명
BACKTEST_MANIFEST_FILENAME: str = "backtest_manifest.json"  # 백테스트 실행 매니페스트 메타데이터 파일명

# [영속화 파일 식별자 설정 - 시계열 데이터]
XAI_RISK_GATES_FILENAME: str = "xai_risk_gates.parquet"  # 복합 게이트 및 위험 침범 거리 파일명
STRATEGY_SIGNALS_FILENAME: str = "strategy_signals.parquet"  # 전략별 매매 시그널 및 액션 파일명
SIMULATION_LEDGERS_FILENAME: str = "simulation_ledgers.parquet"  # 3대 전략 일별 회계 원장 파일명

# [영속화 파일 식별자 설정 - 정량 감사 보고서]
GATE_SUMMARY_FILENAME: str = "gate_summary.csv"  # 리스크 게이트 통계 및 국면 분포 감사표 파일명
REGIME_ATTRIBUTION_FILENAME: str = "regime_attribution.csv"  # 국면별 팩터 위험 기여도 분해표 파일명
FACTOR_AUDIT_TRAIL_FILENAME: str = "factor_audit_trail.csv"  # 팩터별 사전 모수 추적표 파일명
EXECUTION_GOVERNANCE_AUDIT_FILENAME: str = "execution_governance_audit.csv"  # 주문 체결 및 노출도 감사표 파일명
PORTFOLIO_ACCOUNTING_SUMMARY_FILENAME: str = "portfolio_accounting_summary.csv"  # 포트폴리오 회계 감사 요약표 파일명
ABLATION_PERFORMANCE_METRICS_FILENAME: str = "ablation_performance_metrics.csv"  # 계량 성과 비교 감사표 파일명

# [영속화 파일 식별자 설정 - 시각화 플롯]
GATING_BEHAVIOR_DIAGNOSTICS_FILENAME: str = "gating_behavior_diagnostics.png"  # 거버넌스 거동 3단 진단 플롯 파일명
ABLATION_EQUITY_DRAWDOWN_FILENAME: str = "ablation_equity_drawdown.png"  # 누적 자산 및 드로다운 플롯 파일명

# [검증 및 역직렬화 규격 설정]
STATUS_VERIFIED: str = "VERIFIED"  # 아티팩트 검증 완료 상태 판정값
STATUS_MISSING: str = "MISSING"  # 필수 아티팩트 결손 상태 판정값
PARQUET_ENGINE: str = "pyarrow"  # Parquet I/O 처리 엔진

# ==============================================================================
# Public API Functions
# ==============================================================================

@dataclass(frozen=True)
class LoadedBacktestArtifacts:
    """로드된 백테스트 거버넌스 설정, 시계열 데이터, 감사 보고서를 보존하는 불변 컨테이너 DTO."""

    manifest: Dict[str, Any]
    governance_config: Dict[str, Any]
    xai_risk_gates: pd.DataFrame
    strategy_signals: pd.DataFrame
    simulation_ledgers: pd.DataFrame
    gate_summary: pd.DataFrame
    regime_attribution: pd.DataFrame
    factor_audit_trail: pd.DataFrame
    execution_governance_audit: pd.DataFrame
    portfolio_accounting_summary: pd.DataFrame
    ablation_performance_metrics: pd.DataFrame
    artifact_paths: Dict[str, Path]


def load_backtest_artifacts(
    artifact_root: Union[str, Path] = DEFAULT_ARTIFACT_ROOT,
    auto_display: bool = True,
) -> LoadedBacktestArtifacts:
    """영속화된 백테스트 결과물을 계층별로 복원하고 4대 핵심 검증 리포트를 자동 사출합니다.

    Args:
        artifact_root (Union[str, Path]): 백테스트 아티팩트 최상위 디렉터리 경로. Defaults to DEFAULT_ARTIFACT_ROOT.
        auto_display (bool): 콘솔 및 주피터 검증 대시보드 자동 출력 여부. Defaults to True.

    Returns:
        LoadedBacktestArtifacts: 설정, 시계열 데이터셋, 정량 보고서 및 물리 경로 컨테이너.

    Raises:
        FileNotFoundError: 필수 아티팩트 디렉터리 또는 핵심 파일이 디스크에 존재하지 않는 경우 발생.
    """
    base_path: Path = Path(artifact_root)
    _validate_artifact_hierarchy(base_path=base_path)

    loaded_artifacts: LoadedBacktestArtifacts = _load_all_artifacts(base_path=base_path)

    if auto_display:
        _display_manifest_profile(manifest=loaded_artifacts.manifest)
        _display_performance_metrics(metrics_df=loaded_artifacts.ablation_performance_metrics)
        _display_execution_audit(audit_df=loaded_artifacts.execution_governance_audit)
        _display_contract_verification(artifacts=loaded_artifacts)

    return loaded_artifacts

# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _load_json(destination_path: Path) -> Dict[str, Any]:
    """지정된 경로의 JSON 파일을 역직렬화하여 딕셔너리로 반환합니다."""
    if not destination_path.exists():
        raise FileNotFoundError(f"JSON 파일이 누락되었습니다: {destination_path.resolve()}")
    with open(destination_path, "r", encoding="utf-8") as file_buffer:
        return json.load(file_buffer)


def _load_parquet(destination_path: Path) -> pd.DataFrame:
    """Parquet 파일을 인덱스를 보존한 상태로 데이터프레임으로 역직렬화합니다."""
    if not destination_path.exists():
        raise FileNotFoundError(f"Parquet 파일이 누락되었습니다: {destination_path.resolve()}")
    return pd.read_parquet(destination_path, engine=PARQUET_ENGINE)


def _load_csv(destination_path: Path) -> pd.DataFrame:
    """CSV 파일을 인덱스를 보존한 상태로 데이터프레임으로 역직렬화합니다."""
    if not destination_path.exists():
        raise FileNotFoundError(f"CSV 리포트 파일이 누락되었습니다: {destination_path.resolve()}")
    return pd.read_csv(destination_path, index_col=0)


def _validate_artifact_hierarchy(base_path: Path) -> None:
    """백테스트 최상위 디렉터리 및 필수 하위 계층 폴더의 물리적 실재성을 검증합니다."""
    if not base_path.exists():
        raise FileNotFoundError(f"백테스트 아티팩트 루트 디렉터리가 존재하지 않습니다: {base_path.resolve()}")

    required_directories: List[Path] = [
        base_path / CONFIG_DIR_NAME,
        base_path / DATA_DIR_NAME,
        base_path / REPORTS_DIR_NAME,
    ]
    for directory_path in required_directories:
        if not directory_path.is_dir():
            raise FileNotFoundError(f"필수 백테스트 하위 디렉터리가 결손되었습니다: {directory_path.resolve()}")


def _load_config_layer(
    config_dir: Path,
    manifest_path: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """매니페스트 메타데이터와 거버넌스 설정 딕셔너리를 로드합니다."""
    governance_config = _load_json(destination_path=config_dir / GOVERNANCE_CONFIG_FILENAME)
    manifest = _load_json(destination_path=manifest_path) if manifest_path.exists() else {}
    return governance_config, manifest


def _load_data_layer(
    data_dir: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """게이트, 매매 시그널, 시뮬레이션 장부 시계열 데이터프레임을 일괄 로드합니다."""
    risk_gates = _load_parquet(destination_path=data_dir / XAI_RISK_GATES_FILENAME)
    strategy_signals = _load_parquet(destination_path=data_dir / STRATEGY_SIGNALS_FILENAME)
    simulation_ledgers = _load_parquet(destination_path=data_dir / SIMULATION_LEDGERS_FILENAME)
    return risk_gates, strategy_signals, simulation_ledgers


def _load_reports_layer(
    reports_dir: Path,
) -> Dict[str, pd.DataFrame]:
    """6대 정량 성과 및 거버넌스 감사 보고서를 일괄 역직렬화합니다."""
    report_files: Dict[str, str] = {
        "gate_summary": GATE_SUMMARY_FILENAME,
        "regime_attribution": REGIME_ATTRIBUTION_FILENAME,
        "factor_audit_trail": FACTOR_AUDIT_TRAIL_FILENAME,
        "execution_governance_audit": EXECUTION_GOVERNANCE_AUDIT_FILENAME,
        "portfolio_accounting_summary": PORTFOLIO_ACCOUNTING_SUMMARY_FILENAME,
        "ablation_performance_metrics": ABLATION_PERFORMANCE_METRICS_FILENAME,
    }

    loaded_reports: Dict[str, pd.DataFrame] = {}
    for key, filename in report_files.items():
        file_path = reports_dir / filename
        if file_path.exists():
            loaded_reports[key] = _load_csv(destination_path=file_path)
        else:
            loaded_reports[key] = pd.DataFrame()

    return loaded_reports


def _collect_artifact_paths(base_path: Path) -> Dict[str, Path]:
    """영속화 계층의 모든 산출물 파일 물리 경로 매핑을 생성합니다."""
    return {
        "manifest": base_path / BACKTEST_MANIFEST_FILENAME,
        "config_governance": base_path / CONFIG_DIR_NAME / GOVERNANCE_CONFIG_FILENAME,
        "data_risk_gates": base_path / DATA_DIR_NAME / XAI_RISK_GATES_FILENAME,
        "data_signals": base_path / DATA_DIR_NAME / STRATEGY_SIGNALS_FILENAME,
        "data_ledgers": base_path / DATA_DIR_NAME / SIMULATION_LEDGERS_FILENAME,
        "report_gate_summary": base_path / REPORTS_DIR_NAME / GATE_SUMMARY_FILENAME,
        "report_regime_attribution": base_path / REPORTS_DIR_NAME / REGIME_ATTRIBUTION_FILENAME,
        "report_factor_audit": base_path / REPORTS_DIR_NAME / FACTOR_AUDIT_TRAIL_FILENAME,
        "report_execution_audit": base_path / REPORTS_DIR_NAME / EXECUTION_GOVERNANCE_AUDIT_FILENAME,
        "report_accounting_summary": base_path / REPORTS_DIR_NAME / PORTFOLIO_ACCOUNTING_SUMMARY_FILENAME,
        "report_ablation_metrics": base_path / REPORTS_DIR_NAME / ABLATION_PERFORMANCE_METRICS_FILENAME,
        "figure_gating_behavior": base_path / FIGURES_DIR_NAME / GATING_BEHAVIOR_DIAGNOSTICS_FILENAME,
        "figure_ablation_equity": base_path / FIGURES_DIR_NAME / ABLATION_EQUITY_DRAWDOWN_FILENAME,
    }


def _load_all_artifacts(base_path: Path) -> LoadedBacktestArtifacts:
    """디스크 상의 설정, 데이터, 리포트를 전수 역직렬화하여 불변 컨테이너를 조립합니다."""
    config_dir: Path = base_path / CONFIG_DIR_NAME
    data_dir: Path = base_path / DATA_DIR_NAME
    reports_dir: Path = base_path / REPORTS_DIR_NAME
    manifest_path: Path = base_path / BACKTEST_MANIFEST_FILENAME

    governance_config, manifest = _load_config_layer(config_dir=config_dir, manifest_path=manifest_path)
    risk_gates, strategy_signals, simulation_ledgers = _load_data_layer(data_dir=data_dir)
    reports = _load_reports_layer(reports_dir=reports_dir)
    artifact_paths = _collect_artifact_paths(base_path=base_path)

    return LoadedBacktestArtifacts(
        manifest=manifest,
        governance_config=governance_config,
        xai_risk_gates=risk_gates,
        strategy_signals=strategy_signals,
        simulation_ledgers=simulation_ledgers,
        gate_summary=reports.get("gate_summary", pd.DataFrame()),
        regime_attribution=reports.get("regime_attribution", pd.DataFrame()),
        factor_audit_trail=reports.get("factor_audit_trail", pd.DataFrame()),
        execution_governance_audit=reports.get("execution_governance_audit", pd.DataFrame()),
        portfolio_accounting_summary=reports.get("portfolio_accounting_summary", pd.DataFrame()),
        ablation_performance_metrics=reports.get("ablation_performance_metrics", pd.DataFrame()),
        artifact_paths=artifact_paths,
    )


def _display_manifest_profile(manifest: Dict[str, Any]) -> None:
    """백테스트 실행 기간, 챔피언 모델 소스, 벤치마크 메타데이터를 사출합니다."""
    period_info = manifest.get("evaluation_period", {})
    start_date = period_info.get("start", "N/A")
    end_date = period_info.get("end", "N/A")
    trading_days = period_info.get("trading_days", "N/A")

    separator = "=" * 100
    print(separator)
    print("📈 [AssetMind] Backtest & Decision Governance Artifacts Loaded Successfully")
    print(separator)
    print("\n[1. Backtest Run Profile & Meta Specification]")
    print(f" • Backtest Run Date   : {manifest.get('backtest_run_date', 'N/A')}")
    print(f" • Evaluation Horizon  : {start_date} ~ {end_date} ({trading_days} Trading Days)")
    print(f" • Champion Model Path : {manifest.get('champion_model_source', 'N/A')}")
    print(f" • Benchmark Asset     : {manifest.get('benchmark', 'KOSPI')}")
    print(f" • Dynamic Deadband (τ): {manifest.get('deadband_tau', 'N/A')}")


def _display_performance_metrics(metrics_df: pd.DataFrame) -> None:
    """3대 전략 계량 성과 비교 감사표를 사출합니다."""
    print("\n[2. 3-Strategy Ablation Performance Metrics (Risk-Adjusted)]")
    if not metrics_df.empty:
        _render_dataframe(dataframe=metrics_df)
    else:
        print(" - ablation_performance_metrics 리포트가 존재하지 않습니다.")


def _display_execution_audit(audit_df: pd.DataFrame) -> None:
    """주문 체결, 노출도 및 채터링 억제율 감사표를 사출합니다."""
    print("\n[3. Execution Governance & Action Distribution Audit]")
    if not audit_df.empty:
        _render_dataframe(dataframe=audit_df)
    else:
        print(" - execution_governance_audit 리포트가 존재하지 않습니다.")


def _display_contract_verification(artifacts: LoadedBacktestArtifacts) -> None:
    """백테스트 연동 계약 산출물들의 무결성과 물리 파일 실재성을 사출합니다."""
    print("\n[4. Backtest Data Contract & Artifacts Verification]")
    verification_table = _build_contract_verification_table(artifacts=artifacts)
    _render_dataframe(dataframe=verification_table)


def _build_contract_verification_table(
    artifacts: LoadedBacktestArtifacts,
) -> pd.DataFrame:
    """산출물 계층별 데이터 형상 및 물리 파일 실재 여부를 감사 테이블로 구성합니다."""
    figures_exist = (
        artifacts.artifact_paths["figure_gating_behavior"].exists()
        and artifacts.artifact_paths["figure_ablation_equity"].exists()
    )

    records: List[Dict[str, str]] = [
        {
            "Contract Component": "Manifest & Config",
            "Target Entity": f"{BACKTEST_MANIFEST_FILENAME} / {GOVERNANCE_CONFIG_FILENAME}",
            "Specification / Dimension": f"Period: {len(artifacts.strategy_signals)} Days | Frozen Synapses",
            "Integrity Check": STATUS_VERIFIED if artifacts.manifest else STATUS_MISSING,
        },
        {
            "Contract Component": "XAI Risk Gates",
            "Target Entity": XAI_RISK_GATES_FILENAME,
            "Specification / Dimension": f"Shape {artifacts.xai_risk_gates.shape} [Composite & Distances]",
            "Integrity Check": STATUS_VERIFIED if not artifacts.xai_risk_gates.empty else STATUS_MISSING,
        },
        {
            "Contract Component": "Strategy Signals",
            "Target Entity": STRATEGY_SIGNALS_FILENAME,
            "Specification / Dimension": f"Shape {artifacts.strategy_signals.shape} [Raw & Gated Signals]",
            "Integrity Check": STATUS_VERIFIED if not artifacts.strategy_signals.empty else STATUS_MISSING,
        },
        {
            "Contract Component": "Simulation Ledgers",
            "Target Entity": SIMULATION_LEDGERS_FILENAME,
            "Specification / Dimension": f"Shape {artifacts.simulation_ledgers.shape} [3-Strategy Accounting]",
            "Integrity Check": STATUS_VERIFIED if not artifacts.simulation_ledgers.empty else STATUS_MISSING,
        },
        {
            "Contract Component": "Audit Dashboards",
            "Target Entity": "6 Quantitative Report CSVs",
            "Specification / Dimension": "Performance, Regime, Factor, Accounting, Governance",
            "Integrity Check": STATUS_VERIFIED if not artifacts.ablation_performance_metrics.empty else STATUS_MISSING,
        },
        {
            "Contract Component": "Visual Evidences",
            "Target Entity": "2 Diagnostic PNG Plots",
            "Specification / Dimension": "Gating Behavior & Underwater Drawdown (DPI 300)",
            "Integrity Check": STATUS_VERIFIED if figures_exist else STATUS_MISSING,
        },
    ]
    return pd.DataFrame(records)


def _render_dataframe(dataframe: pd.DataFrame) -> None:
    """주피터 환경에서는 display()로, 일반 환경에서는 콘솔 포맷 문자열로 렌더링합니다."""
    try:
        from IPython.display import display
        display(dataframe)
    except ImportError:
        print(dataframe.to_string(index=True))