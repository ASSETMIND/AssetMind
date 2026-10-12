import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ==============================================================================
# Constants & Configuration
# ==============================================================================

# [디렉터리 계층 구조 설정]
DEFAULT_ARTIFACT_ROOT: str = "artifacts/backtest"  # 백테스트 산출물 영속화 기본 루트 디렉터리 경로
CONFIG_DIR_NAME: str = "config"  # XAI 리스크 거버넌스 설정 적재 경로
DATA_DIR_NAME: str = "data"  # 시계열 원천 및 시뮬레이션 데이터 적재 경로
REPORTS_DIR_NAME: str = "reports"  # 정량 성과 및 감사 리포트 적재 경로
FIGURES_DIR_NAME: str = "figures"  # 진단 및 성과 시각화 이미지 적재 경로

# [영속화 파일 식별자 설정 - 설정 및 메타데이터]
GOVERNANCE_CONFIG_FILENAME: str = "governance_config.json"  # XAI 리스크 게이트 설정 파일명
BACKTEST_MANIFEST_FILENAME: str = "backtest_manifest.json"  # 백테스트 실행 매니페스트 메타데이터 파일명

# [영속화 파일 식별자 설정 - 시계열 데이터]
XAI_RISK_GATES_FILENAME: str = "xai_risk_gates.parquet"  # 시계열 복합 게이트 및 위험 침범 거리 파일명
STRATEGY_SIGNALS_FILENAME: str = "strategy_signals.parquet"  # 전략별 매매 시그널 및 액션 시계열 파일명
SIMULATION_LEDGERS_FILENAME: str = "simulation_ledgers.parquet"  # 전략별 일별 포트폴리오 회계 장부 파일명

# [영속화 파일 식별자 설정 - 정량 감사 보고서]
GATE_SUMMARY_FILENAME: str = "gate_summary.csv"  # 리스크 게이트 통계 및 국면 분포 감사표 파일명
REGIME_ATTRIBUTION_FILENAME: str = "regime_attribution.csv"  # 국면별 팩터 영향도 및 위험 기여도 분해표 파일명
FACTOR_AUDIT_TRAIL_FILENAME: str = "factor_audit_trail.csv"  # 팩터별 사전 모수 및 추적 감사표 파일명
EXECUTION_GOVERNANCE_AUDIT_FILENAME: str = "execution_governance_audit.csv"  # 주문 체결 및 노출도 감사표 파일명
PORTFOLIO_ACCOUNTING_SUMMARY_FILENAME: str = "portfolio_accounting_summary.csv"  # 포트폴리오 회계 감사 요약표 파일명
ABLATION_PERFORMANCE_METRICS_FILENAME: str = "ablation_performance_metrics.csv"  # 3대 전략 계량 성과 비교 감사표 파일명

# [영속화 파일 식별자 설정 - 시각화 플롯]
GATING_BEHAVIOR_DIAGNOSTICS_FILENAME: str = "gating_behavior_diagnostics.png"  # 거버넌스 거동 3단 진단 플롯 파일명
ABLATION_EQUITY_DRAWDOWN_FILENAME: str = "ablation_equity_drawdown.png"  # 누적 자산 및 낙폭 비교 플롯 파일명

# [I/O 및 직렬화 규격 설정]
IMAGE_DPI: int = 300  # 시각화 이미지 저장 해상도
IMAGE_BBOX_INCHES: str = "tight"  # 여백 최소화 바운딩 박스 옵션
JSON_INDENT: int = 4  # JSON 직렬화 들여쓰기 공백 수
PARQUET_ENGINE: str = "pyarrow"  # Parquet I/O 처리 엔진

# ==============================================================================
# Public API Functions
# ==============================================================================

def deploy_backtest_artifacts(
    governance_config: Dict[str, Any],
    risk_gates_data: Union[pd.DataFrame, Dict[str, Any]],
    strategy_signals: pd.DataFrame,
    simulation_ledgers: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    reports: Dict[str, pd.DataFrame],
    figures: Optional[Dict[str, plt.Figure]] = None,
    manifest_metadata: Optional[Dict[str, Any]] = None,
    artifact_root: Union[str, Path] = DEFAULT_ARTIFACT_ROOT,
) -> Dict[str, Path]:
    """백테스트 거버넌스 설정, 시계열 데이터, 감사 보고서 및 시각화 아티팩트를 프로덕션 규격으로 일괄 영속화합니다.

    Args:
        governance_config (Dict[str, Any]): XAI 리스크 거버넌스 동결 파라미터 설정 딕셔너리.
        risk_gates_data (Union[pd.DataFrame, Dict[str, Any]]): 복합 리스크 게이트 및 개별 침범 거리 시계열 데이터.
        strategy_signals (pd.DataFrame): 전략별 매매 시그널 및 액션 상태 전이 시계열 데이터프레임.
        simulation_ledgers (Union[pd.DataFrame, Dict[str, pd.DataFrame]]): 3대 전략의 일별 포트폴리오 회계 원장.
        reports (Dict[str, pd.DataFrame]): 감사 및 계량 성과 분석 보고서 데이터프레임 딕셔너리.
        figures (Optional[Dict[str, plt.Figure]]): 거동 진단 및 성과 비교 Matplotlib Figure 딕셔너리. Defaults to None.
        manifest_metadata (Optional[Dict[str, Any]]): 백테스트 실행 환경 및 종합 성과 요약 메타데이터. Defaults to None.
        artifact_root (Union[str, Path]): 최상위 영속화 디렉터리 경로. Defaults to DEFAULT_ARTIFACT_ROOT.

    Returns:
        Dict[str, Path]: 계층별로 생성된 아티팩트 물리 디렉터리 경로 매핑 딕셔너리.

    Raises:
        ValueError: 입력 시그널 또는 감사 보고서가 비어 있거나 DatetimeIndex가 결손된 경우 발생.
    """
    _validate_backtest_inputs(
        strategy_signals=strategy_signals,
        reports=reports,
    )

    target_directories: Dict[str, Path] = _prepare_artifact_directories(
        base_path=Path(artifact_root)
    )

    _persist_config_layer(
        governance_config=governance_config,
        destination_directory=target_directories[CONFIG_DIR_NAME],
    )

    _persist_data_layer(
        risk_gates_data=risk_gates_data,
        strategy_signals=strategy_signals,
        simulation_ledgers=simulation_ledgers,
        destination_directory=target_directories[DATA_DIR_NAME],
    )

    _persist_reports_layer(
        reports=reports,
        destination_directory=target_directories[REPORTS_DIR_NAME],
    )

    if figures:
        _persist_figures_layer(
            figures=figures,
            destination_directory=target_directories[FIGURES_DIR_NAME],
        )

    _persist_manifest_metadata(
        manifest_metadata=manifest_metadata,
        simulation_ledgers=simulation_ledgers,
        destination_path=Path(artifact_root) / BACKTEST_MANIFEST_FILENAME,
    )

    return target_directories

# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _convert_to_serializable(value: Any) -> Any:
    """JSON 직렬화가 불가능한 객체를 표준 파이썬 기본형 타입으로 재귀 변환합니다."""
    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    if isinstance(value, (np.ndarray, pd.Series)):
        return value.tolist()
    if isinstance(value, (pd.Timestamp, pd.DatetimeIndex)):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _save_json(payload: Dict[str, Any], destination_path: Path) -> None:
    """딕셔너리 구조체를 JSON 파일로 안전하게 직렬화하여 저장합니다."""
    with open(destination_path, "w", encoding="utf-8") as file_buffer:
        json.dump(
            payload,
            file_buffer,
            ensure_ascii=False,
            indent=JSON_INDENT,
            default=_convert_to_serializable,
        )


def _save_parquet(dataframe: pd.DataFrame, destination_path: Path) -> None:
    """데이터프레임을 인덱스를 보존한 상태로 Parquet 포맷으로 디스크에 영속화합니다."""
    dataframe.to_parquet(destination_path, engine=PARQUET_ENGINE, index=True)


def _save_csv(dataframe: pd.DataFrame, destination_path: Path) -> None:
    """데이터프레임을 인덱스를 보존한 상태로 CSV 포맷으로 디스크에 영속화합니다."""
    dataframe.to_csv(destination_path, index=True, encoding="utf-8-sig")


def _save_figure(figure: plt.Figure, destination_path: Path) -> None:
    """Matplotlib Figure 객체를 고해상도 이미지 파일로 영속화합니다."""
    figure.savefig(destination_path, dpi=IMAGE_DPI, bbox_inches=IMAGE_BBOX_INCHES)


def _validate_backtest_inputs(
    strategy_signals: pd.DataFrame,
    reports: Dict[str, pd.DataFrame],
) -> None:
    """입력된 시그널 및 감사 보고서 데이터의 존재 여부와 무결성을 검증합니다."""
    if strategy_signals.empty:
        raise ValueError("배포 대상인 strategy_signals 데이터프레임이 비어 있습니다.")
    if not isinstance(strategy_signals.index, pd.DatetimeIndex):
        raise ValueError("strategy_signals의 인덱스가 DatetimeIndex 형식이 아닙니다.")
    if not reports:
        raise ValueError("배포 대상인 감사 보고서(reports) 딕셔너리가 비어 있습니다.")


def _prepare_artifact_directories(base_path: Path) -> Dict[str, Path]:
    """백테스트 아티팩트 계층별 물리 디렉터리를 생성하고 경로 매핑을 반환합니다."""
    directory_mapping: Dict[str, Path] = {
        CONFIG_DIR_NAME: base_path / CONFIG_DIR_NAME,
        DATA_DIR_NAME: base_path / DATA_DIR_NAME,
        REPORTS_DIR_NAME: base_path / REPORTS_DIR_NAME,
        FIGURES_DIR_NAME: base_path / FIGURES_DIR_NAME,
    }

    for target_path in directory_mapping.values():
        target_path.mkdir(parents=True, exist_ok=True)

    return directory_mapping


def _prepare_risk_gates_dataframe(
    risk_gates_data: Union[pd.DataFrame, Dict[str, Any]],
) -> pd.DataFrame:
    """입력된 리스크 게이트 데이터를 단일 통합 데이터프레임으로 변환 및 정규화합니다."""
    if isinstance(risk_gates_data, pd.DataFrame):
        return risk_gates_data

    composite_series = risk_gates_data.get("composite_risk_gate")
    if composite_series is None:
        raise ValueError("risk_gates_data에 'composite_risk_gate' 필드가 결손되었습니다.")

    integrated_dataframe = pd.DataFrame({"composite_risk_gate": composite_series})

    individual_gates = risk_gates_data.get("individual_gates")
    if isinstance(individual_gates, pd.DataFrame):
        integrated_dataframe = integrated_dataframe.join(
            individual_gates.add_prefix("gate_")
        )

    risk_distances = risk_gates_data.get("risk_distances")
    if isinstance(risk_distances, pd.DataFrame):
        integrated_dataframe = integrated_dataframe.join(
            risk_distances.add_prefix("dist_")
        )

    return integrated_dataframe


def _prepare_simulation_ledgers_dataframe(
    simulation_ledgers: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
) -> pd.DataFrame:
    """전략별 회계 장부 데이터를 단일 통합 데이터프레임으로 결합 및 정규화합니다."""
    if isinstance(simulation_ledgers, pd.DataFrame):
        return simulation_ledgers

    ledger_dataframes: List[pd.DataFrame] = []
    for strategy_name, ledger_df in simulation_ledgers.items():
        standardized_name = (
            strategy_name.replace(" ", "_").replace("(", "").replace(")", "")
        )
        prefixed_df = ledger_df.copy().add_prefix(f"{standardized_name}__")
        ledger_dataframes.append(prefixed_df)

    return pd.concat(ledger_dataframes, axis=1)


def _persist_config_layer(
    governance_config: Dict[str, Any],
    destination_directory: Path,
) -> None:
    """거버넌스 설정 딕셔너리를 지정된 디렉터리에 JSON으로 영속화합니다."""
    target_path = destination_directory / GOVERNANCE_CONFIG_FILENAME
    _save_json(payload=governance_config, destination_path=target_path)


def _persist_data_layer(
    risk_gates_data: Union[pd.DataFrame, Dict[str, Any]],
    strategy_signals: pd.DataFrame,
    simulation_ledgers: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    destination_directory: Path,
) -> None:
    """게이트, 시그널, 시뮬레이션 장부 시계열 데이터를 Parquet 포맷으로 일괄 영속화합니다."""
    gates_dataframe = _prepare_risk_gates_dataframe(risk_gates_data=risk_gates_data)
    _save_parquet(
        dataframe=gates_dataframe,
        destination_path=destination_directory / XAI_RISK_GATES_FILENAME,
    )

    _save_parquet(
        dataframe=strategy_signals,
        destination_path=destination_directory / STRATEGY_SIGNALS_FILENAME,
    )

    ledgers_dataframe = _prepare_simulation_ledgers_dataframe(
        simulation_ledgers=simulation_ledgers
    )
    _save_parquet(
        dataframe=ledgers_dataframe,
        destination_path=destination_directory / SIMULATION_LEDGERS_FILENAME,
    )


def _persist_reports_layer(
    reports: Dict[str, pd.DataFrame],
    destination_directory: Path,
) -> None:
    """감사 보고서 및 계량 성과 분석 테이블을 CSV 포맷으로 일괄 영속화합니다."""
    key_mapping: Dict[str, str] = {
        "gate_summary": GATE_SUMMARY_FILENAME,
        "regime_attribution": REGIME_ATTRIBUTION_FILENAME,
        "factor_audit_trail": FACTOR_AUDIT_TRAIL_FILENAME,
        "execution_governance_audit": EXECUTION_GOVERNANCE_AUDIT_FILENAME,
        "portfolio_accounting_summary": PORTFOLIO_ACCOUNTING_SUMMARY_FILENAME,
        "ablation_performance_metrics": ABLATION_PERFORMANCE_METRICS_FILENAME,
    }

    for key, dataframe_obj in reports.items():
        if isinstance(dataframe_obj, pd.DataFrame) and not dataframe_obj.empty:
            filename: str = key_mapping.get(key, f"{key}.csv")
            _save_csv(
                dataframe=dataframe_obj,
                destination_path=destination_directory / filename,
            )


def _persist_figures_layer(
    figures: Dict[str, plt.Figure],
    destination_directory: Path,
) -> None:
    """거동 진단 및 성과 비교 시각화 차트를 고해상도 PNG 이미지로 저장합니다."""
    key_mapping: Dict[str, str] = {
        "gating_behavior": GATING_BEHAVIOR_DIAGNOSTICS_FILENAME,
        "gating_behavior_diagnostics": GATING_BEHAVIOR_DIAGNOSTICS_FILENAME,
        "ablation_equity": ABLATION_EQUITY_DRAWDOWN_FILENAME,
        "ablation_equity_drawdown": ABLATION_EQUITY_DRAWDOWN_FILENAME,
    }

    for key, figure_obj in figures.items():
        if figure_obj is not None:
            filename: str = key_mapping.get(key, f"{key}.png")
            _save_figure(
                figure=figure_obj,
                destination_path=destination_directory / filename,
            )


def _build_default_manifest(
    simulation_ledgers: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
) -> Dict[str, Any]:
    """사용자 정의 메타데이터가 부재할 경우 회계 원장으로부터 기본 매니페스트 구조를 도출합니다."""
    sample_index = (
        next(iter(simulation_ledgers.values())).index
        if isinstance(simulation_ledgers, dict)
        else simulation_ledgers.index
    )

    return {
        "backtest_run_date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "evaluation_period": {
            "start": str(sample_index.min().date()),
            "end": str(sample_index.max().date()),
            "trading_days": len(sample_index),
        },
        "status": "COMPLETED",
    }


def _persist_manifest_metadata(
    manifest_metadata: Optional[Dict[str, Any]],
    simulation_ledgers: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    destination_path: Path,
) -> None:
    """백테스트 실행 메타데이터 및 성과 스냅샷을 최상위 매니페스트 파일로 저장합니다."""
    payload: Dict[str, Any] = (
        manifest_metadata
        if manifest_metadata is not None
        else _build_default_manifest(simulation_ledgers=simulation_ledgers)
    )
    _save_json(payload=payload, destination_path=destination_path)