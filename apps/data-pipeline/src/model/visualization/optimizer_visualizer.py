from typing import Any, Dict, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd

from src.model.optimization.walk_forward_optimizer import SingleOptimizationResult
from src.model.visualization.schema import (
    DEFAULT_HPO_DASHBOARD_FIGSIZE,
    DEFAULT_THEME,
    VisualizationTheme,
    resolve_model_color,
)
from src.model.visualization.utils import (
    apply_axis_grid,
    create_horizontal_subplots,
    format_parameter_value,
    render_empty_panel,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 1. 반응면 추세 적합 및 스케일 임계치 (Response Surface & Scaling Thresholds)
LOG_SCALE_RATIO_THRESHOLD: float = 50.0                       # 로그 스케일 전환 판별 파라미터 탐색 범위 비율 임계치
POLYNOMIAL_TREND_GRID_POINTS: int = 100                       # 다항 회귀 추세선 보간 그리드 포인트 수
MAX_POLYNOMIAL_DEGREE: int = 2                                # 과적합 방지용 다항식 최대 차수

# 2. 중요도 랭킹 및 이력 테이블 규격 (Importance Ranking & Table Specifications)
DEFAULT_TOP_IMPORTANCE_COUNT: int = 5                         # fANOVA 수평 바차트에 표시할 최대 핵심 파라미터 수
TRIAL_SCORE_ROUND_DECIMALS: int = 4                           # Trial 이력 복합 스코어 반올림 자릿수
TRIAL_DURATION_ROUND_DECIMALS: int = 2                        # Trial 이력 소요 시간 반올림 자릿수


# ==============================================================================
# Public API Functions
# ==============================================================================
def plot_model_hpo_dashboard(
    result_or_study: Union[SingleOptimizationResult, optuna.Study],
    model_name: Optional[str] = None,
    figsize: Tuple[float, float] = DEFAULT_HPO_DASHBOARD_FIGSIZE,
    theme: Optional[VisualizationTheme] = None,
) -> plt.Figure:
    """단일 모델의 fANOVA 중요도 및 Top-1, Top-2 반응면 슬라이스를 1x3 Panel로 렌더링합니다.

    Args:
        result_or_study (Union[SingleOptimizationResult, optuna.Study]): 튜닝 결과 DTO 또는 Optuna Study.
        model_name (Optional[str]): 모델 식별 명칭 (기본값: None, 스터디 메타데이터에서 자동 추론).
        figsize (Tuple[float, float]): 대시보드 캔버스 크기 (기본값: DEFAULT_HPO_DASHBOARD_FIGSIZE).
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체 (기본값: None, 시스템 기본 테마 사용).

    Returns:
        plt.Figure: 1x3 서브플롯으로 조립된 HPO 감사 대시보드 Figure 객체.

    Raises:
        TypeError: 지원하지 않는 형식의 입력 객체가 전달되었을 경우 발생.
    """
    resolved_theme = theme or DEFAULT_THEME

    # 1. 스터디 객체 및 최적 파라미터/점수 메타데이터 정규화 추출
    study, resolved_name, default_score, best_params, best_score = _resolve_study_metadata(
        result_or_study=result_or_study,
        model_name=model_name,
    )

    # 2. fANOVA 기반 파라미터 주효과 분산 비율 산출 및 Top-2 파라미터 식별
    param_importances = _extract_fanova_importances(study=study)
    top_param_names = list(param_importances.keys())[:2]

    # 3. 1x3 가로 서브플롯 캔버스 생성
    fig, axes = create_horizontal_subplots(
        panel_count=3,
        figsize=figsize,
    )
    model_color = resolve_model_color(model_name=resolved_name, theme=resolved_theme)

    # 4. Panel 1: 거시 감사 (Macro fANOVA Importance)
    _render_fanova_panel(
        ax=axes[0],
        model_name=resolved_name,
        param_importances=param_importances,
        best_params=best_params,
        model_color=model_color,
        theme=resolved_theme,
    )

    # 5. Panel 2: 미시 감사 (Micro Top-1 Slice Response Surface)
    if len(top_param_names) >= 1:
        _render_slice_panel(
            ax=axes[1],
            study=study,
            model_name=resolved_name,
            param_name=top_param_names[0],
            param_rank=1,
            importance_ratio=param_importances[top_param_names[0]],
            best_params=best_params,
            best_score=best_score,
            model_color=model_color,
            theme=resolved_theme,
        )
    else:
        render_empty_panel(ax=axes[1], message="No Top-1 Parameter Found", theme=resolved_theme)

    # 6. Panel 3: 미시 감사 (Micro Top-2 Slice Response Surface)
    if len(top_param_names) >= 2:
        _render_slice_panel(
            ax=axes[2],
            study=study,
            model_name=resolved_name,
            param_name=top_param_names[1],
            param_rank=2,
            importance_ratio=param_importances[top_param_names[1]],
            best_params=best_params,
            best_score=best_score,
            model_color=model_color,
            theme=resolved_theme,
        )
    else:
        render_empty_panel(ax=axes[2], message="No Top-2 Parameter Available", theme=resolved_theme)

    # 7. 대시보드 메인 슈퍼 타이틀 배치 및 레이아웃 정돈
    fig.suptitle(
        f"[{resolved_name}] HPO Optimization Audit: fANOVA Variance & Top-2 Slice Response Surfaces",
        fontsize=resolved_theme.typography.super_title_size,
        fontweight="bold",
        y=1.02,
    )
    plt.tight_layout()
    return fig


def get_trial_history_table(
    result_or_study: Union[SingleOptimizationResult, optuna.Study],
    top_k: Optional[int] = None,
) -> pd.DataFrame:
    """Optuna Study의 완료된 전체 Trial 이력을 복합 스코어 기준 내림차순 랭킹표로 추출합니다.

    Args:
        result_or_study (Union[SingleOptimizationResult, optuna.Study]): 튜닝 결과 DTO 또는 Optuna Study.
        top_k (Optional[int]): 상위 추출 개수 (기본값: None, 전체 이력 반환).

    Returns:
        pd.DataFrame: 랭킹 정렬된 Trial 정형화 데이터프레임.

    Raises:
        TypeError: 지원하지 않는 형식의 입력 객체가 전달되었을 경우 발생.
    """
    return _build_trial_history_dataframe(
        result_or_study=result_or_study,
        top_k=top_k,
    )


class OptimizerVisualizer:
    """HPO 최적화 감사, fANOVA 중요도 및 반응면 시각화 파사드 클래스."""

    plot_model_hpo_dashboard = staticmethod(plot_model_hpo_dashboard)
    get_trial_history_table = staticmethod(get_trial_history_table)


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _resolve_study_metadata(
    result_or_study: Union[SingleOptimizationResult, optuna.Study],
    model_name: Optional[str],
) -> Tuple[optuna.Study, str, Optional[float], Dict[str, Any], Optional[float]]:
    """입력 객체의 타입을 판별하여 Optuna Study 및 핵심 최적화 메타데이터를 정규화 추출합니다."""
    # [설계 의도] SingleOptimizationResult DTO 객체와 순수 optuna.Study 객체를 모두 수용하는 다형성 정규화
    is_dto = (
        isinstance(result_or_study, SingleOptimizationResult)
        or type(result_or_study).__name__ == "SingleOptimizationResult"
        or (hasattr(result_or_study, "study") and hasattr(result_or_study, "best_params"))
    )

    if is_dto:
        return (
            result_or_study.study,
            getattr(result_or_study, "model_name", model_name or "Model"),
            getattr(result_or_study, "default_score", None),
            getattr(result_or_study, "best_params", {}),
            getattr(result_or_study, "best_score", None),
        )

    resolved_name = model_name or getattr(result_or_study, "study_name", "Model")
    completed_trials = [t for t in result_or_study.trials if t.value is not None]
    best_score_val = float(result_or_study.best_value) if completed_trials else None
    best_params_map = result_or_study.best_params if completed_trials else {}

    return (
        result_or_study,
        resolved_name,
        None,
        best_params_map,
        best_score_val,
    )


def _extract_fanova_importances(study: optuna.Study) -> Dict[str, float]:
    """fANOVA 알고리즘을 적용하여 파라미터별 주효과 분산 설명 비율을 추출합니다."""
    # [설계 의도] 파라미터 수가 단일이거나 튜닝 표본 부족 시 fANOVA 예외를 방어하고 균등 분할로 안전 폴백
    try:
        importances = optuna.importance.get_param_importances(study)
        if not importances:
            raise ValueError("No importance returned")
        return importances
    except Exception:
        completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        if completed_trials:
            param_names = list(completed_trials[0].params.keys())
            equal_ratio = 1.0 / max(1, len(param_names))
            return {p: equal_ratio for p in param_names}
        return {}


def _fit_response_surface_trend(
    param_values: np.ndarray,
    score_values: np.ndarray,
    grid_points: int = POLYNOMIAL_TREND_GRID_POINTS,
) -> Tuple[np.ndarray, np.ndarray]:
    """파라미터 값에 따른 목적함수 조건부 기댓값 E[Y|θ] 추세선을 적합합니다."""
    unique_x = np.unique(param_values)
    if len(unique_x) < 2:
        return param_values, score_values

    # [설계 의도] 과적합(Overfitting)을 억제하고 대역적 곡률을 관찰하기 위해 최대 2차 다항식으로 강제 제한
    degree = min(MAX_POLYNOMIAL_DEGREE, len(unique_x) - 1)
    coefficients = np.polyfit(param_values, score_values, deg=degree)
    poly_func = np.poly1d(coefficients)

    x_grid = np.linspace(param_values.min(), param_values.max(), grid_points)
    y_trend = poly_func(x_grid)
    return x_grid, y_trend


def _check_log_scale_suitability(
    param_values: np.ndarray,
    ratio_threshold: float = LOG_SCALE_RATIO_THRESHOLD,
) -> bool:
    """파라미터 탐색 범위의 차수가 극단적인 경우(50배 초과) 로그 스케일 적용 여부를 판별합니다."""
    min_val = float(np.min(param_values))
    max_val = float(np.max(param_values))
    if min_val <= 0.0:
        return False
    return (max_val / max(1e-12, min_val)) >= ratio_threshold


def _resolve_slice_parameter_encoding(
    raw_values: List[Any],
    raw_opt_val: Any,
) -> Tuple[np.ndarray, float, Optional[List[str]], bool]:
    """슬라이스 패널 렌더링을 위해 수치형 및 비수치형(Tuple/Categorical) 파라미터 값을 X축 수치 좌표로 정규화합니다."""
    try:
        if any(isinstance(v, bool) for v in raw_values):
            raise TypeError("Boolean parameter is treated as categorical")
        numeric_values = np.array([float(v) for v in raw_values], dtype=float)
        opt_x = float(raw_opt_val)
        return numeric_values, opt_x, None, True
    except (TypeError, ValueError):
        try:
            unique_categories = sorted(set(raw_values))
        except TypeError:
            unique_categories = list(dict.fromkeys(str(v) for v in raw_values))
            raw_values = [str(v) for v in raw_values]
            raw_opt_val = str(raw_opt_val)

        if raw_opt_val not in unique_categories:
            unique_categories.append(raw_opt_val)

        category_to_idx = {cat: float(idx) for idx, cat in enumerate(unique_categories)}
        encoded_values = np.array([category_to_idx[v] for v in raw_values], dtype=float)
        opt_x = category_to_idx[raw_opt_val]
        tick_labels = [format_parameter_value(cat) for cat in unique_categories]
        return encoded_values, opt_x, tick_labels, False


def _render_fanova_panel(
    ax: plt.Axes,
    model_name: str,
    param_importances: Dict[str, float],
    best_params: Dict[str, Any],
    model_color: str,
    theme: VisualizationTheme,
) -> None:
    """fANOVA 파라미터 중요도 수평 바차트를 단일 Axes에 렌더링합니다."""
    if not param_importances:
        render_empty_panel(ax=ax, message="fANOVA Calculation Unavailable", theme=theme)
        return

    # [설계 의도] 상위 N개 중요 파라미터를 역순 배치하여 시각적 위계(Top-1이 최상단) 형성
    items = list(param_importances.items())[:DEFAULT_TOP_IMPORTANCE_COUNT][::-1]
    param_names = [k for k, _ in items]
    scores = [v for _, v in items]

    display_labels = [
        f"{p_name}\n(opt={format_parameter_value(best_params.get(p_name, '-'))})"
        for p_name in param_names
    ]

    y_positions = np.arange(len(param_names))
    bars = ax.barh(
        y_positions,
        scores,
        color=model_color,
        alpha=0.85,
        edgecolor=theme.status_palette.optimum_edge,
        height=0.55,
    )
    ax.set_yticks(y_positions)
    ax.set_yticklabels(display_labels, fontsize=theme.typography.tick_label_size)

    max_score = max(scores) if scores else 1.0
    ax.set_xlim(0.0, max(0.1, max_score * 1.25))

    for bar, score in zip(bars, scores):
        ax.text(
            bar.get_width() + (max_score * 0.02),
            bar.get_y() + bar.get_height() / 2.0,
            f"{score * 100.0:.1f}%",
            ha="left",
            va="center",
            fontsize=theme.typography.annotation_size,
            fontweight="bold",
            color=theme.status_palette.text_dark,
        )

    ax.set_title(f"[{model_name}] Parameter Importance (fANOVA)", fontsize=theme.typography.panel_title_size, fontweight="bold")
    ax.set_xlabel("fANOVA Variance Ratio", fontsize=theme.typography.axis_label_size)
    apply_axis_grid(ax=ax, theme=theme)


def _render_slice_panel(
    ax: plt.Axes,
    study: optuna.Study,
    model_name: str,
    param_name: str,
    param_rank: int,
    importance_ratio: float,
    best_params: Dict[str, Any],
    best_score: Optional[float],
    model_color: str,
    theme: VisualizationTheme,
) -> None:
    """선별된 핵심 파라미터의 1차원 슬라이스 반응면(Slice Surface)을 렌더링합니다."""
    # 1. 해당 파라미터가 포함된 완료 Trial 수집 및 좌표 인코딩
    completed = [t for t in study.trials if t.value is not None and param_name in t.params]
    if not completed:
        render_empty_panel(ax=ax, message=f"No Completed Trials for {param_name}", theme=theme)
        return

    raw_values = [t.params[param_name] for t in completed]
    raw_opt_val = best_params.get(param_name, raw_values[0])
    param_values, opt_x, category_labels, is_numeric = _resolve_slice_parameter_encoding(
        raw_values=raw_values,
        raw_opt_val=raw_opt_val,
    )
    score_values = np.array([float(t.value) for t in completed])

    # 2. 산점도 플로팅 (Trial 관측 점)
    ax.scatter(
        param_values,
        score_values,
        color=model_color,
        alpha=0.45,
        s=36,
        edgecolors="none",
        label="Trial Internal Score",
    )

    # 3. 2차 다항식 반응면 추세선 적합 및 플로팅
    x_grid, y_trend = _fit_response_surface_trend(
        param_values=param_values,
        score_values=score_values,
    )
    if len(x_grid) > 1:
        ax.plot(
            x_grid,
            y_trend,
            color=theme.status_palette.risk_line,
            linewidth=2.0,
            label="Expected Response E[Y|θ]",
        )

    # 4. 최적해(Optimum) 마커 강조 표시
    opt_score = float(best_score) if best_score is not None else float(np.max(score_values))
    ax.scatter(
        [opt_x],
        [opt_score],
        marker="*",
        s=180,
        color=theme.status_palette.optimum_star,
        edgecolor=theme.status_palette.optimum_edge,
        linewidth=1.2,
        zorder=6,
        label=f"Optimum: {format_parameter_value(raw_opt_val)}",
    )

    # 5. 수치형 극단 스케일 로그 변환 또는 범주형(Tuple/Str) X축 틱 라벨 바인딩
    if is_numeric and _check_log_scale_suitability(param_values=param_values):
        ax.set_xscale("log")
    elif category_labels is not None:
        ax.set_xticks(np.arange(len(category_labels)))
        ax.set_xticklabels(category_labels, fontsize=theme.typography.tick_label_size)

    # 6. 축 라벨, 그리드 및 범례 바인딩
    ax.set_title(
        f"[{model_name}] Top-{param_rank} Slice: {param_name} ({importance_ratio * 100.0:.1f}%)",
        fontsize=theme.typography.panel_title_size,
        fontweight="bold",
    )
    ax.set_xlabel(f"Parameter Value: {param_name}", fontsize=theme.typography.axis_label_size)
    ax.set_ylabel("Composite Score", fontsize=theme.typography.axis_label_size)
    apply_axis_grid(ax=ax, theme=theme)
    ax.legend(loc="lower right", fontsize=theme.typography.legend_size, framealpha=0.9)


def _build_trial_history_dataframe(
    result_or_study: Union[SingleOptimizationResult, optuna.Study],
    top_k: Optional[int],
) -> pd.DataFrame:
    """Study 또는 DTO로부터 완료된 Trial 이력 데이터프레임을 구성합니다."""
    # [설계 의도] DTO 내부에 이미 정형화된 DataFrame이 유효하게 존재하는 경우 안전 재활용 (DRY 준수)
    existing_df = getattr(result_or_study, "trial_history_df", None)
    if isinstance(existing_df, pd.DataFrame):
        history_df = existing_df.copy()
    elif isinstance(result_or_study, optuna.Study) or type(result_or_study).__name__ == "Study":
        records: List[Dict[str, Any]] = []
        for trial in result_or_study.trials:
            if trial.state != optuna.trial.TrialState.COMPLETE:
                continue
            row = {
                "Trial No": trial.number,
                "Composite Score": round(float(trial.value), TRIAL_SCORE_ROUND_DECIMALS),
            }
            row.update(trial.params)
            duration_sec = trial.duration.total_seconds() if trial.duration else 0.0
            row["Duration (s)"] = round(duration_sec, TRIAL_DURATION_ROUND_DECIMALS)
            records.append(row)
        history_df = pd.DataFrame(records)
        if not history_df.empty:
            history_df.sort_values(by="Composite Score", ascending=False, inplace=True)
            history_df.reset_index(drop=True, inplace=True)
            history_df.index += 1
            history_df.index.name = "Rank"
    else:
        raise TypeError(f"[_build_trial_history_dataframe] 지원하지 않는 입력 객체 타입입니다: {type(result_or_study)}")

    if top_k is not None and top_k > 0:
        history_df = history_df.head(top_k)

    return history_df