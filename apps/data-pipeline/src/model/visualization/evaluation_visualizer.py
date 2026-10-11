from typing import Any, Dict, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.model.evaluation import metrics
from src.model.evaluation.schema import EvaluationMetric, EvaluationResult
from src.model.visualization.schema import (
    DEFAULT_DUMBBELL_FIGSIZE,
    DEFAULT_THEME,
    DEFAULT_UNDERWATER_FIGSIZE,
    VisualizationTheme,
    resolve_model_color,
)
from src.model.visualization.utils import (
    add_unified_legend,
    apply_axis_grid,
    create_horizontal_subplots,
    create_vertical_subplots,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 1. 수리 모델 및 리스크 감사 임계치 (Evaluation Math & Risk Thresholds)
DEFAULT_HARD_GATE_MDD: float = 0.30                           # Tier 3 최대 허용 낙폭 한계선 (30%)
DEFAULT_SAFE_ZONE_MDD: float = 0.15                           # 안전선 낙폭 기준 (15%)
DEFAULT_BASE_TARGET_STD: float = 0.04                         # 타겟 변동성 기준 표준편차
STD_THRESHOLD_FOR_SCALING: float = 0.20                       # 타겟 스케일링 판별 임계 표준편차
HOLDING_PERIOD_DAYS: int = 20                                 # 보유 호라이즌 일수
UNDERWATER_Y_LIMITS: Tuple[float, float] = (-35.0, 2.0)       # 언더워터 차트 y축 표시 범위

# 2. 덤벨 차트 축 및 차원 규격 (Dumbbell Chart Dimensions & Coordinates)
CV_BASELINE_RETENTION_PCT: float = 100.0                      # CV 기준선 유지율 백분율
DUMBBELL_RETENTION_AXIS_LIMITS: Tuple[float, float] = (-5.0, 145.0) # 덤벨 차트 x축 표시 범위
DUMBBELL_TEXT_X_POSITION: float = 106.0                       # 수치 주석 표기 시작 x 좌표
DUMBBELL_DIMENSIONS: Tuple[Tuple[str, str], ...] = (
    ("Composite Score", "composite_score"),                   # 복합 점수 차원
    ("L1: MDA", EvaluationMetric.MDA.value),                  # 방향 정확도 차원
    ("L2: Rank IC", EvaluationMetric.RANK_IC.value),          # 순위 상관계수 차원
    ("L3: Signal Sharpe", EvaluationMetric.SIGNAL_SHARPE.value), # 신호 샤프 비율 차원
    ("L4: Factor t-stat", EvaluationMetric.FACTOR_T_STAT.value), # 팩터 t-통계량 차원
)


# ==============================================================================
# Public API Functions
# ==============================================================================
def plot_cv_vs_test_dumbbell(
    optimization_results: Dict[str, Any],
    evaluation_results: Dict[str, EvaluationResult],
    figsize: Tuple[float, float] = DEFAULT_DUMBBELL_FIGSIZE,
    theme: Optional[VisualizationTheme] = None,
) -> plt.Figure:
    """CV 기준선(100%) 대비 Test 실측치의 5대 차원 일반화 유지율(Retention Rate %) 덤벨 차트를 렌더링합니다.

    Args:
        optimization_results (Dict[str, Any]): 모델명을 키로 하고 CV 최적화 메타데이터를 값으로 갖는 딕셔너리.
        evaluation_results (Dict[str, EvaluationResult]): 모델명을 키로 하고 Holdout EvaluationResult DTO를 값으로 갖는 딕셔너리.
        figsize (Tuple[float, float]): 캔버스 규격 (width, height). Defaults to DEFAULT_DUMBBELL_FIGSIZE.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체 (None 시 시스템 기본 테마 사용). Defaults to None.

    Returns:
        plt.Figure: 지표별 실제 유지율 갭이 가시화된 Figure 객체.

    Raises:
        ValueError: evaluation_results가 비어 있거나 유효한 평가 결과가 없을 경우 발생.
    """
    if not evaluation_results:
        raise ValueError("[plot_cv_vs_test_dumbbell] evaluation_results가 비어 있습니다.")

    resolved_theme = theme or DEFAULT_THEME

    # 1. 모델별 5대 차원 원시 지표 및 CV 대비 유지율(Retention Rate) 레코드 추출
    model_gap_records = _extract_all_model_gap_records(
        optimization_results=optimization_results,
        evaluation_results=evaluation_results,
    )

    # 2. 1xN 서브플롯 캔버스 생성 및 패널별 렌더링
    fig, axes_list = create_horizontal_subplots(
        panel_count=len(model_gap_records),
        figsize=figsize,
        sharey=True,
    )

    for ax, record in zip(axes_list, model_gap_records):
        _render_dumbbell_panel(
            ax=ax,
            record=record,
            theme=resolved_theme,
        )

    # 3. 레이아웃을 선제 정돈하여 상단 마진 공간(상단 12%) 확보
    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.88])

    # 4. 확보된 상단 마진 공간에 단일 공통 범례 및 메인 타이틀 배치
    add_unified_legend(
        figure=fig,
        ax=axes_list[0],
        ncol=2,
        bbox_to_anchor=(0.5, 0.98),
        loc="upper center",
        theme=resolved_theme,
    )

    fig.suptitle(
        "Model Generalization Retention Audit: Test Retention Relative to CV Baseline (100%)",
        fontsize=resolved_theme.typography.super_title_size,
        fontweight="bold",
        y=1.04,
    )
    return fig


def plot_underwater_drawdown(
    y_test: Union[pd.Series, np.ndarray],
    evaluation_results: Dict[str, EvaluationResult],
    hard_gate_mdd: float = DEFAULT_HARD_GATE_MDD,
    safe_zone_mdd: float = DEFAULT_SAFE_ZONE_MDD,
    figsize: Tuple[float, float] = DEFAULT_UNDERWATER_FIGSIZE,
    theme: Optional[VisualizationTheme] = None,
) -> plt.Figure:
    """Holdout Test 구간의 실현 자본 곡선(PnL) 및 MDD Hard Gate 위반 감사 언더워터 플롯을 2x1 Panel로 렌더링합니다.

    Args:
        y_test (Union[pd.Series, np.ndarray]): Out-of-Sample 테스트 정답 타겟 시계열.
        evaluation_results (Dict[str, EvaluationResult]): 후보 모델별 EvaluationResult DTO 딕셔너리.
        hard_gate_mdd (float): Tier 3 최대 허용 낙폭 한계선. Defaults to DEFAULT_HARD_GATE_MDD (0.30).
        safe_zone_mdd (float): 절대 저위험 안전선 낙폭 기준. Defaults to DEFAULT_SAFE_ZONE_MDD (0.15).
        figsize (Tuple[float, float]): 대시보드 캔버스 규격. Defaults to DEFAULT_UNDERWATER_FIGSIZE.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체 (None 시 시스템 기본 테마 사용). Defaults to None.

    Returns:
        plt.Figure: 실현 자본 곡선(상단) 및 언더워터 낙폭 궤적(하단)으로 구성된 Figure 객체.

    Raises:
        ValueError: y_test 시계열 또는 evaluation_results가 비어 있을 경우 발생.
    """
    if len(y_test) == 0 or not evaluation_results:
        raise ValueError("[plot_underwater_drawdown] y_test 또는 evaluation_results가 비어 있습니다.")

    resolved_theme = theme or DEFAULT_THEME

    # 1. 시계열 타임라인 인덱스 정규화 및 전 후보 모델 자본/드로다운 궤적 일괄 연산
    timeline = y_test.index if isinstance(y_test, (pd.Series, pd.DataFrame)) else np.arange(len(y_test))
    model_trajectories = _compute_all_model_trajectories(
        y_test=y_test,
        evaluation_results=evaluation_results,
    )

    # 2. 복합 점수 기준 1위 챔피언 모델 식별
    champion_name = max(model_trajectories.keys(), key=lambda k: model_trajectories[k]["composite_score"])

    # 3. 상하 2단(2x1) 서브플롯 캔버스 생성
    fig, axes_list = create_vertical_subplots(
        panel_count=2,
        figsize=figsize,
        sharex=True,
        height_ratios=(1.2, 1.0),
    )
    ax_wealth, ax_dd = axes_list[0], axes_list[1]

    # 4. Panel 1: 실현 자본 누적 성장률 (Realized Equity Trajectory)
    _render_equity_panel(
        ax=ax_wealth,
        timeline=timeline,
        model_trajectories=model_trajectories,
        champion_name=champion_name,
        theme=resolved_theme,
    )

    # 5. Panel 2: 언더워터 드로다운 및 게이트 감사 (Underwater Drawdown Audit)
    _render_drawdown_panel(
        ax=ax_dd,
        timeline=timeline,
        model_trajectories=model_trajectories,
        champion_name=champion_name,
        hard_gate_mdd=hard_gate_mdd,
        safe_zone_mdd=safe_zone_mdd,
        theme=resolved_theme,
    )

    # 6. 대시보드 메인 타이틀 및 레이아웃 조정
    fig.suptitle(
        "Holdout Test Performance Simulation & Systemic Tail Risk Defense Verification",
        fontsize=resolved_theme.typography.super_title_size,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout()
    return fig


class EvaluationVisualizer:
    """Holdout Test 종합 평가, 챔피언 감사 및 리스크 시계열 시각화 파사드 클래스."""

    plot_cv_vs_test_dumbbell = staticmethod(plot_cv_vs_test_dumbbell)
    plot_underwater_drawdown = staticmethod(plot_underwater_drawdown)


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _extract_all_model_gap_records(
    optimization_results: Optional[Dict[str, Any]],
    evaluation_results: Dict[str, EvaluationResult],
) -> List[Dict[str, Any]]:
    """후보 모델들을 순회하여 5대 평가 차원의 CV vs Test 수치 및 유지율을 추출합니다."""
    # [설계 의도] 복합 점수(composite_score) 내림차순 정렬을 통해 챔피언 및 순위 부여
    sorted_candidates: List[Tuple[str, EvaluationResult]] = sorted(
        evaluation_results.items(),
        key=lambda item: item[1].composite_score,
        reverse=True,
    )

    all_records: List[Dict[str, Any]] = []
    opt_dict = optimization_results or {}

    for rank, (model_name, eval_result) in enumerate(sorted_candidates, start=1):
        opt_res = opt_dict.get(model_name)
        dimension_data: List[Dict[str, Any]] = []

        for dim_display, metric_key in DUMBBELL_DIMENSIONS:
            cv_val = _extract_cv_dimension_value(opt_res=opt_res, metric_key=metric_key)
            test_val = _extract_test_dimension_value(eval_result=eval_result, metric_key=metric_key)
            gap = test_val - cv_val

            # [수리적 보정] CV 표본 기준 유지율 산출: (Test / CV) * 100% (분모 0 나눗셈 예외 방어)
            retention_pct = (test_val / cv_val * 100.0) if abs(cv_val) > 1e-8 else 0.0

            dimension_data.append({
                "dimension": dim_display,
                "metric_key": metric_key,
                "cv_value": cv_val,
                "test_value": test_val,
                "gap": gap,
                "retention_pct": retention_pct,
            })

        all_records.append({
            "model_name": model_name,
            "rank": rank,
            "dimensions": dimension_data,
        })

    return all_records


def _extract_cv_dimension_value(opt_res: Any, metric_key: str) -> float:
    """Optimization 메타데이터 객체로부터 해당 차원의 CV 점수를 안전하게 추출합니다."""
    # [설계 의도] 최적화 결과 메타데이터가 미제공된 경우 기본 0.0으로 안전 폴백
    if opt_res is None:
        return 0.0

    if metric_key == "composite_score":
        best_score = getattr(opt_res, "best_score", None)
        return float(best_score) if best_score is not None and np.isfinite(best_score) else 0.0

    cv_metrics = getattr(opt_res, "tuned_metrics", {})
    if isinstance(cv_metrics, dict):
        candidates = [metric_key]
        try:
            candidates.append(EvaluationMetric(metric_key))
        except (ValueError, KeyError):
            pass

        for candidate_key in candidates:
            if candidate_key in cv_metrics:
                val = cv_metrics[candidate_key]
                return float(val) if np.isfinite(val) else 0.0

    return 0.0


def _extract_test_dimension_value(eval_result: EvaluationResult, metric_key: str) -> float:
    """EvaluationResult DTO로부터 해당 차원의 Test 실측 점수를 안전하게 추출합니다."""
    if metric_key == "composite_score":
        return float(eval_result.composite_score)

    # [설계 의도] EvaluationMetric Enum 키를 통한 동적 조회 및 키 부재 예외 방어
    try:
        enum_key = EvaluationMetric(metric_key)
        return float(eval_result.get_metric(enum_key))
    except (ValueError, KeyError):
        return 0.0


def _compute_all_model_trajectories(
    y_test: Union[pd.Series, np.ndarray],
    evaluation_results: Dict[str, EvaluationResult],
) -> Dict[str, Dict[str, Any]]:
    """전 후보 모델의 누적 자본 성장률 및 언더워터 낙폭 시계열을 일괄 연산합니다."""
    # [설계 의도] Pandas Series/DataFrame 또는 NumPy 입력을 1차원 부동소수점 배열로 정규화
    y_true_arr = (
        y_test.to_numpy(dtype=np.float64).flatten()
        if isinstance(y_test, (pd.Series, pd.DataFrame))
        else np.asarray(y_test, dtype=np.float64).flatten()
    )

    trajectories: Dict[str, Dict[str, Any]] = {}
    for model_name, eval_res in evaluation_results.items():
        y_pred_arr = eval_res.predictions.to_numpy(dtype=np.float64).flatten()
        cum_ret_pct, drawdown_pct, max_dd_pct = _compute_trajectory_arrays(
            y_true=y_true_arr,
            y_pred=y_pred_arr,
        )

        # [수리적 일원화] 콘솔 리더보드의 공식 감사 MDD(7.67%)를 SSOT로 직접 바인딩
        audited_mdd_pct = float(eval_res.get_metric(EvaluationMetric.MDD)) * 100.0

        trajectories[model_name] = {
            "cum_return_pct": cum_ret_pct,
            "drawdown_pct": drawdown_pct,
            "max_dd_pct": max_dd_pct,
            "audited_mdd_pct": audited_mdd_pct,
            "sharpe": eval_res.get_metric(EvaluationMetric.SIGNAL_SHARPE),
            "composite_score": eval_res.composite_score,
        }

    return trajectories


def _compute_trajectory_arrays(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """도메인 수식을 재활용하여 실현 누적 자본 및 드로다운 시계열을 산출합니다."""
    # [설계 의도] metrics.py의 핵심 내부 함수(_to_position_weights)를 직접 호출하여 도메인 수식 재구현 배제 (DRY 준수)
    pred_std = float(np.std(y_pred, ddof=1)) if len(y_pred) > 1 else 1.0
    effective_pred_std = pred_std if (pred_std > 1e-8 and np.isfinite(pred_std)) else 1.0
    weights = metrics._to_position_weights(y_pred, pred_std=effective_pred_std)

    # [수리적 보정] 타겟 이분산성 표준화 척도 역스케일링
    true_std = float(np.std(y_true, ddof=1)) if len(y_true) > 1 else 1.0
    scale_factor = DEFAULT_BASE_TARGET_STD if true_std > STD_THRESHOLD_FOR_SCALING else 1.0

    # [설계 의도] 20일 보유 호라이즌의 중첩 복리 왜곡을 제거하는 일별 균등 기여분 분할
    daily_returns = (weights * (y_true * scale_factor)) / float(HOLDING_PERIOD_DAYS)
    log_wealth = np.cumsum(daily_returns)
    cum_returns_pct = (np.exp(log_wealth) - 1.0) * 100.0

    # [수리적 연산] 누적 최고점(Running Max) 기반 언더워터 드로다운 산출
    wealth_index = np.r_[1.0, np.exp(log_wealth)]
    running_max = np.maximum.accumulate(wealth_index)
    drawdowns_pct = ((wealth_index[1:] - running_max[1:]) / np.maximum(running_max[1:], 1e-8)) * 100.0
    max_dd_pct = float(np.abs(np.min(drawdowns_pct))) if len(drawdowns_pct) > 0 else 0.0

    return cum_returns_pct, drawdowns_pct, max_dd_pct


def _render_dumbbell_panel(
    ax: plt.Axes,
    record: Dict[str, Any],
    theme: VisualizationTheme,
) -> None:
    """단일 모델의 5대 평가 차원 유지율을 공통 백분율 축에 렌더링합니다."""
    model_name = record["model_name"]
    rank = record["rank"]
    dims = record["dimensions"]
    y_positions = np.arange(len(dims))
    dimension_labels = [d["dimension"] for d in dims]

    # 1. CV 기준선(100%) 수직 가이드라인 표시
    ax.axvline(
        CV_BASELINE_RETENTION_PCT,
        color=theme.status_palette.baseline,
        linestyle=theme.styles.baseline_linestyle,
        linewidth=1.2,
        alpha=theme.styles.baseline_alpha,
        zorder=1,
    )

    for idx, d_info in enumerate(dims):
        te_v = d_info["test_value"]
        gap = d_info["gap"]
        retention = d_info["retention_pct"]

        # 2. 점수 이동 경로 연결선: 100%(CV) -> retention%(Test)
        ax.plot(
            [CV_BASELINE_RETENTION_PCT, retention],
            [idx, idx],
            color=theme.status_palette.baseline,
            linewidth=2.0,
            alpha=0.6,
            zorder=2,
        )

        # 3. CV 좌표 점 (100% 기준선 고정)
        ax.scatter(
            CV_BASELINE_RETENTION_PCT,
            idx,
            color=theme.status_palette.cv_point,
            s=80,
            zorder=3,
            label="CV Baseline (100%)" if (rank == 1 and idx == 0) else "",
        )

        # 4. Test 좌표 점 (실제 유지율 위치)
        ax.scatter(
            retention,
            idx,
            color=theme.status_palette.test_point,
            s=70,
            marker="D",
            zorder=4,
            label="Test Retention (%)" if (rank == 1 and idx == 0) else "",
        )

        # 5. 우측 고정 열 주석: 원시 수치 및 유지율 동시 표기
        gap_color = theme.status_palette.positive_gap if gap >= 0.0 else theme.status_palette.negative_gap
        ax.text(
            DUMBBELL_TEXT_X_POSITION,
            idx,
            f"T: {te_v:.2f} ({retention:.1f}%)",
            va="center",
            ha="left",
            fontsize=theme.typography.annotation_size,
            fontweight="bold",
            color=gap_color,
        )

    # 6. 축 라벨, 범위, 서브플롯 타이틀 및 표준 그리드 적용
    model_color = resolve_model_color(model_name=model_name, theme=theme)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(dimension_labels, fontsize=theme.typography.axis_label_size)
    ax.set_xlabel("Generalization Retention Rate (%) [CV Baseline = 100%]", fontsize=theme.typography.axis_label_size)
    ax.set_xlim(DUMBBELL_RETENTION_AXIS_LIMITS)
    ax.set_title(
        f"{'★ ' if rank == 1 else ''}[{model_name}] Generalization Retention (Rank {rank})",
        fontsize=theme.typography.panel_title_size,
        fontweight="bold",
        color=model_color,
    )
    apply_axis_grid(ax=ax, theme=theme)
    ax.invert_yaxis()


def _render_equity_panel(
    ax: plt.Axes,
    timeline: Any,
    model_trajectories: Dict[str, Dict[str, Any]],
    champion_name: str,
    theme: VisualizationTheme,
) -> None:
    """실현 자본 누적 성장률 곡선 패널을 렌더링합니다."""
    # 1. 모델별 누적 자본 곡선 순회 플로팅 (챔피언 모델 하이라이트)
    for model_name, data in model_trajectories.items():
        is_champion = model_name == champion_name
        model_color = resolve_model_color(model_name=model_name, theme=theme)
        linewidth = 2.2 if is_champion else 1.3
        alpha = 1.0 if is_champion else 0.7

        # [수리적 일원화] 차트 범례에 콘솔 실측치 MDD를 직접 매핑하여 Lie Factor 1.0 확립
        model_label = (
            f"★ [{model_name}] (Champ, Sharpe: {data['sharpe']:.2f}, MDD: {data['audited_mdd_pct']:.2f}%)"
            if is_champion
            else f"[{model_name}] (Sharpe: {data['sharpe']:.2f}, MDD: {data['audited_mdd_pct']:.2f}%)"
        )

        ax.plot(
            timeline,
            data["cum_return_pct"],
            label=model_label,
            color=model_color,
            linewidth=linewidth,
            alpha=alpha,
        )

    # 2. 제로 기준선 및 표준 축 서식/그리드/범례 적용
    ax.axhline(0.0, color=theme.status_palette.baseline, linestyle="--", linewidth=1.0, alpha=0.7)
    ax.set_ylabel("Cumulative PnL (%)", fontsize=theme.typography.axis_label_size, fontweight="bold")
    ax.set_title("Holdout Test Realized Equity Trajectory (Cumulative Return)", fontsize=theme.typography.panel_title_size, fontweight="bold")
    apply_axis_grid(ax=ax, theme=theme)
    ax.legend(loc="upper left", frameon=True, fontsize=theme.typography.legend_size)


def _render_drawdown_panel(
    ax: plt.Axes,
    timeline: Any,
    model_trajectories: Dict[str, Dict[str, Any]],
    champion_name: str,
    hard_gate_mdd: float,
    safe_zone_mdd: float,
    theme: VisualizationTheme,
) -> None:
    """언더워터 낙폭 궤적 및 Hard Gate 가이드라인 패널을 렌더링합니다."""
    # 1. 모델별 언더워터 드로다운 궤적 플로팅 (챔피언 음영 영역 하이라이트)
    for model_name, data in model_trajectories.items():
        is_champion = model_name == champion_name
        model_color = resolve_model_color(model_name=model_name, theme=theme)
        linewidth = 2.2 if is_champion else 1.3
        alpha = 1.0 if is_champion else 0.7

        ax.plot(
            timeline,
            data["drawdown_pct"],
            label=f"[{model_name}] Drawdown",
            color=model_color,
            linewidth=linewidth,
            alpha=alpha,
        )

        if is_champion:
            ax.fill_between(
                timeline,
                data["drawdown_pct"],
                0.0,
                color=model_color,
                alpha=theme.styles.champion_fill_alpha,
                label=f"[{model_name}] Drawdown Area",
            )

    # 2. 리스크 게이트 감사 가이드라인 배치 (Tier 3 Hard Limit & Safe Zone)
    hard_limit_pct = -hard_gate_mdd * 100.0
    safe_limit_pct = -safe_zone_mdd * 100.0

    ax.axhline(
        hard_limit_pct,
        color=theme.status_palette.risk_line,
        linestyle="-.",
        linewidth=1.8,
        label=f"Tier 3 Hard Gate Limit ({hard_limit_pct:.0f}%)",
    )
    ax.axhline(
        safe_limit_pct,
        color=theme.status_palette.safe_line,
        linestyle=":",
        linewidth=1.5,
        label=f"Safe Zone Boundary ({safe_limit_pct:.0f}%)",
    )
    ax.axhline(0.0, color=theme.status_palette.baseline, linestyle="-", linewidth=0.8)

    # 3. 표준 축 서식, 한계 범위, 그리드 및 하단 범례 적용
    ax.set_ylabel("Underwater Drawdown (%)", fontsize=theme.typography.axis_label_size, fontweight="bold")
    ax.set_xlabel("Holdout Test Horizon Timeline", fontsize=theme.typography.axis_label_size, fontweight="bold")
    ax.set_title("Dynamic Downside Risk Audit & Maximum Drawdown Hard Gate Defense", fontsize=theme.typography.panel_title_size, fontweight="bold")
    ax.set_ylim(UNDERWATER_Y_LIMITS)
    apply_axis_grid(ax=ax, theme=theme)
    ax.legend(loc="lower left", frameon=True, fontsize=theme.typography.legend_size, ncol=2)