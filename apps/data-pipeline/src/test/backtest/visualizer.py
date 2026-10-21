"""
================================================================================
Project: AssetMind Quantitative Backtesting & Decision Governance Pipeline
Module: src/backtest/visualizer.py
Description: Backtest visualization and gating behavior diagnostics.
Author: Senior Software Engineer / Quantitative Researcher
================================================================================
"""

from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ==============================================================================
# Constants & Configuration
# ==============================================================================
COLOR_BENCHMARK: str = "#7F8C8D"            # Strategy 0 (Benchmark): 슬레이트 그레이
COLOR_RAW_MODEL: str = "#3498DB"            # Strategy 1 (Raw Model): 블루
COLOR_XAI_GATED: str = "#E74C3C"            # Strategy 2 (XAI-Gated): 레드
COLOR_SAFE_BOUNDARY: str = "#27AE60"        # 세이프존 기준선: 에메랄드 그린
COLOR_DANGER_BOUNDARY: str = "#C0392B"      # 시스템 테일 리스크 위험 한계선: 크림슨 레드

LINE_STYLE_SOLID: str = "-"                 # 실선 스타일
LINE_STYLE_DASHED: str = "--"               # 점선 스타일
LINE_WIDTH_PRIMARY: float = 1.8             # 주요 전략 곡선 두께
LINE_WIDTH_SECONDARY: float = 1.5           # 보조 곡선 두께
LINE_WIDTH_BOUNDARY: float = 1.0            # 리스크 임계 기준선 두께
ALPHA_SHADING: float = 0.15                 # 낙폭 및 게이트 위험 영역 음영 투명도

DEFAULT_FIGURE_DPI: int = 300               # 출판용 DPI
DEFAULT_GRID_ALPHA: float = 0.5             # 그리드 선 투명도
TITLE_FONT_SIZE: int = 12                   # 서브플롯 타이틀 폰트 크기
LABEL_FONT_SIZE: int = 11                   # 축 라벨 폰트 크기
TICK_FONT_SIZE: int = 9                     # 축 눈금 폰트 크기


# ==============================================================================
# Public API Functions
# ==============================================================================
def plot_ablation_performance(
    simulation_ledgers: Dict[str, pd.DataFrame],
    figure_size: Tuple[int, int] = (14, 9),
    dpi: int = DEFAULT_FIGURE_DPI,
) -> Tuple[plt.Figure, np.ndarray]:
    """3대 전략 누적 자산 성장 궤적(NAV)과 언더워터 낙폭을 상/하 2단으로 렌더링하여 Figure 객체를 반환합니다."""
    _validate_ledgers_for_plotting(simulation_ledgers)

    figure, axes = plt.subplots(
        2, 1, figsize=figure_size, dpi=dpi, sharex=True, gridspec_kw={"height_ratios": [2.5, 1.5]}
    )

    palette = {
        "benchmark": COLOR_BENCHMARK,
        "raw_model": COLOR_RAW_MODEL,
        "xai_gated": COLOR_XAI_GATED,
    }
    labels = {
        "benchmark": "Strategy 0: Benchmark (Buy & Hold)",
        "raw_model": "Strategy 1: Raw ML Model",
        "xai_gated": "Strategy 2: XAI-Gated Governance",
    }

    for key, ledger in simulation_ledgers.items():
        if not isinstance(ledger, pd.DataFrame):
            continue

        matched_key = next((k for k in palette if k in key.lower()), None)
        color = palette.get(matched_key, None)
        label = labels.get(matched_key, key)

        nav_col = next(
            (c for c in ["nav", "equity", "cumulative_return", "cum_return"] if c in ledger.columns),
            None,
        )
        if nav_col is not None:
            axes[0].plot(ledger.index, ledger[nav_col], label=label, color=color, linewidth=LINE_WIDTH_PRIMARY)

        dd_col = next((c for c in ["drawdown", "dd", "mdd_curve"] if c in ledger.columns), None)
        if dd_col is not None:
            axes[1].plot(ledger.index, ledger[dd_col], label=label, color=color, linewidth=LINE_WIDTH_SECONDARY)
            axes[1].fill_between(ledger.index, ledger[dd_col], 0.0, alpha=ALPHA_SHADING, color=color)

    axes[0].set_title("Ablation Study: Cumulative NAV Performance Comparison", fontsize=13, fontweight="bold", pad=10)
    axes[0].set_ylabel("Portfolio NAV (Base = 1.0)", fontsize=LABEL_FONT_SIZE)
    axes[0].grid(True, linestyle=LINE_STYLE_DASHED, alpha=DEFAULT_GRID_ALPHA)
    axes[0].legend(loc="upper left", frameon=True)

    axes[1].set_title("Underwater Drawdown Profile (Tail Risk Defense)", fontsize=TITLE_FONT_SIZE, fontweight="bold", pad=8)
    axes[1].set_ylabel("Drawdown Rate", fontsize=LABEL_FONT_SIZE)
    axes[1].set_xlabel("Date", fontsize=LABEL_FONT_SIZE)
    axes[1].grid(True, linestyle=LINE_STYLE_DASHED, alpha=DEFAULT_GRID_ALPHA)

    figure.tight_layout()
    return figure, axes


def plot_gating_behavior_diagnostics(
    signal_dataframe: pd.DataFrame,
    composite_gating_scores: pd.Series,
    figure_size: Tuple[int, int] = (14, 9),
    dpi: int = DEFAULT_FIGURE_DPI,
) -> Tuple[plt.Figure, np.ndarray]:
    """XAI 종합 게이트(G_t) 동적 거동과 알파 정류 및 3-Action 판정 타임라인을 3단 시각화하여 반환합니다."""
    _validate_signal_frame_for_plotting(signal_dataframe, composite_gating_scores)

    figure, axes = plt.subplots(nrows=3, ncols=1, figsize=figure_size, dpi=dpi, sharex=True)

    _render_gating_timeline(axes[0], composite_gating_scores)
    _render_signal_rectification(axes[1], signal_dataframe)
    _render_action_distribution(axes[2], signal_dataframe)

    figure.tight_layout()
    return figure, axes


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_ledgers_for_plotting(
    simulation_ledgers: Dict[str, pd.DataFrame],
) -> None:
    if not simulation_ledgers:
        raise ValueError("시각화 대상 시뮬레이션 원장 딕셔너리가 비어 있습니다.")
    required_columns: List[str] = ["nav", "drawdown"]
    for strategy_name, ledger in simulation_ledgers.items():
        if ledger is None or ledger.empty:
            raise ValueError(f"전략 '{strategy_name}'의 회계 원장이 비어 있습니다.")
        for col in required_columns:
            if col not in ledger.columns:
                raise ValueError(f"전략 '{strategy_name}' 원장에 필수 컬럼 '{col}'이 누락되었습니다.")


def _validate_signal_frame_for_plotting(
    signal_dataframe: pd.DataFrame,
    composite_gating_scores: pd.Series,
) -> None:
    if signal_dataframe is None or signal_dataframe.empty:
        raise ValueError("시각화 대상 시그널 데이터프레임이 비어 있습니다.")
    if composite_gating_scores is None or composite_gating_scores.empty:
        raise ValueError("복합 리스크 게이트 시계열이 비어 있습니다.")
    required_columns: List[str] = ["raw_prediction", "effective_prediction", "dynamic_deadband", "action"]
    for col in required_columns:
        if col not in signal_dataframe.columns:
            raise ValueError(f"시그널 데이터프레임에 필수 컬럼 '{col}'이 누락되었습니다.")


def _render_gating_timeline(
    axis: plt.Axes,
    composite_gating_scores: pd.Series,
) -> None:
    axis.plot(composite_gating_scores.index, composite_gating_scores, color=COLOR_XAI_GATED, linewidth=LINE_WIDTH_PRIMARY, label="Composite Risk Gate (G_t)")
    axis.axhline(1.0, color=COLOR_SAFE_BOUNDARY, linestyle=LINE_STYLE_DASHED, linewidth=LINE_WIDTH_BOUNDARY)
    axis.fill_between(
        composite_gating_scores.index, composite_gating_scores, 1.0,
        where=(composite_gating_scores < 1.0), color=COLOR_DANGER_BOUNDARY, alpha=ALPHA_SHADING, label="De-risking Attenuation Area"
    )
    _apply_axis_styling(axis, "[XAI Governance] Continuous Risk Gate Survival Score (G_t)", "Gate Value (0.0 ~ 1.0)")
    axis.legend(loc="lower left", frameon=True, fontsize=TICK_FONT_SIZE)


def _render_signal_rectification(
    axis: plt.Axes,
    signal_dataframe: pd.DataFrame,
) -> None:
    index = signal_dataframe.index
    axis.plot(index, signal_dataframe["raw_prediction"], color=COLOR_RAW_MODEL, linewidth=LINE_WIDTH_SECONDARY, alpha=0.7, label="Raw Alpha (y_pred)")
    axis.plot(index, signal_dataframe["effective_prediction"], color=COLOR_XAI_GATED, linewidth=LINE_WIDTH_PRIMARY, label="Effective Alpha (y_eff)")

    deadband = signal_dataframe["dynamic_deadband"]
    axis.plot(index, deadband, color=COLOR_BENCHMARK, linestyle=LINE_STYLE_DASHED, linewidth=LINE_WIDTH_BOUNDARY, label="+Deadband (tau)")
    axis.plot(index, -deadband, color=COLOR_BENCHMARK, linestyle=LINE_STYLE_DASHED, linewidth=LINE_WIDTH_BOUNDARY, label="-Deadband (-tau)")
    axis.fill_between(index, -deadband, deadband, color=COLOR_BENCHMARK, alpha=0.1, label="Neutral Zone (HOLD)")

    _apply_axis_styling(axis, "[Signal Rectification] Alpha Shrinkage & Dynamic Dead-band Filter", "Expected Return")
    axis.legend(loc="upper left", frameon=True, fontsize=TICK_FONT_SIZE)


def _render_action_distribution(
    axis: plt.Axes,
    signal_dataframe: pd.DataFrame,
) -> None:
    action_mapping = {"SELL": 0.0, "HOLD": 0.5, "BUY": 1.0}
    numeric_actions = signal_dataframe["action"].map(action_mapping).fillna(0.5)

    axis.step(signal_dataframe.index, numeric_actions, color=COLOR_XAI_GATED, linewidth=LINE_WIDTH_PRIMARY, where="post")
    axis.set_yticks([0.0, 0.5, 1.0])
    axis.set_yticklabels(["SELL (0.0)", "HOLD (0.5)", "BUY (1.0)"])
    _apply_axis_styling(axis, "[Execution Governance] Deterministic 3-Action State Transition", "Trading Action")


def _apply_axis_styling(axis: plt.Axes, title: str, ylabel: str) -> None:
    axis.set_title(title, fontsize=TITLE_FONT_SIZE, fontweight="bold", pad=8)
    axis.set_ylabel(ylabel, fontsize=LABEL_FONT_SIZE, fontweight="bold")
    axis.grid(True, linestyle=LINE_STYLE_DASHED, alpha=DEFAULT_GRID_ALPHA)
    axis.tick_params(axis="both", labelsize=TICK_FONT_SIZE)