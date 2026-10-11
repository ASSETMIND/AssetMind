from typing import Any, Dict, List, Optional, Tuple, Union
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from src.model.visualization.schema import (
    DEFAULT_DEPENDENCE_FIGSIZE,
    DEFAULT_DUAL_ROLLING_FIGSIZE,
    DEFAULT_GLOBAL_SUMMARY_FIGSIZE,
    DEFAULT_MULTI_WATERFALL_FIGSIZE,
    DEFAULT_SINGLE_INFLECTION_FIGSIZE,
    DEFAULT_SINGLE_ROLLING_FIGSIZE,
    DEFAULT_SINGLE_WATERFALL_FIGSIZE,
    DEFAULT_THEME,
    VisualizationTheme,
    resolve_model_color,
)
from src.model.visualization.utils import (
    add_unified_legend,
    apply_axis_grid,
    create_grid_subplots,
    create_horizontal_subplots,
    create_vertical_subplots,
)
from src.model.xai.shap_schema import (
    InflectionPolicyResult,
    RegimeCohortResult,
    ShapResult,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 1. 패널 배치 및 여백 비율 (Layout Spacing & Margin Ratios)
DEFAULT_INTERACTION_HORIZONTAL_SPACE: float = 0.28            # 교호작용 패널 간 수평 여백 비율
DEFAULT_MULTI_WATERFALL_VERTICAL_SPACE: float = 0.35          # 다중 Waterfall 패널 간 수직 간격 비율
DEFAULT_WATERFALL_PANEL_HEIGHT: float = 4.2                   # 다중 Waterfall 패널당 적응형 높이 승수
DEFAULT_WATERFALL_TOP_RECTANGLE: float = 0.92                 # Waterfall 전체 타이틀 상단 여백 비율
DEFAULT_WATERFALL_TITLE_VERTICAL_POSITION: float = 0.980      # Waterfall 메인 타이틀 y축 렌더링 위치
DEFAULT_SUBPLOT_TOP_RECTANGLE: float = 0.90                   # 전체 타이틀과 서브플롯 간 겹침 방지 여백 비율
DEFAULT_ROLLING_HEIGHT_RATIOS: Tuple[float, float] = (1.0, 2.2) # 벤치마크 패널과 롤링 SHAP 패널 간 높이 비율
DEFAULT_INFLECTION_GRID_COLUMNS: int = 3                      # 다중 피처 변곡점 대시보드 기본 열 개수
DEFAULT_INFLECTION_ROW_HEIGHT: float = 4.8                    # 변곡점 대시보드 행당 적응형 높이 승수

# 2. 피처 표시 및 시각화 기본 수치 (Display Counts & Thresholds)
DEFAULT_MAXIMUM_DISPLAY: int = 8                              # 차트 패널에 표시할 기본 최대 피처 수
DEFAULT_TOP_K_ROLLING: int = 4                                # 시계열 추적할 기본 최상위 피처 수
HISTOGRAM_DEFAULT_BINS: int = 30                              # 산점도 주변분포 히스토그램 빈 수


# ==============================================================================
# Public API Functions
# ==============================================================================
def plot_global_summary(
    shap_result: ShapResult,
    maximum_display: int = DEFAULT_MAXIMUM_DISPLAY,
    figure_size: Optional[Tuple[float, float]] = None,
    max_display: Optional[int] = None,
    figsize: Optional[Tuple[float, float]] = None,
    theme: Optional[VisualizationTheme] = None,
) -> plt.Figure:
    """글로벌 피처 중요도(Bar) 및 다변량 신호 방향성(Beeswarm)을 1x2 듀얼 패널로 렌더링합니다.

    Args:
        shap_result (ShapResult): 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
        maximum_display (int): 패널에 표시할 최대 피처 개수. Defaults to 8.
        figure_size (Optional[Tuple[float, float]]): 캔버스 크기. Defaults to None.
        max_display (Optional[int]): 하위 호환용 최대 피처 개수. Defaults to None.
        figsize (Optional[Tuple[float, float]]): 하위 호환용 캔버스 크기. Defaults to None.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체. Defaults to None.

    Returns:
        plt.Figure: 좌측 Beeswarm 및 우측 Mean |SHAP| Bar 차트로 구성된 Figure 객체.

    Raises:
        ValueError: shap_result 내부 데이터가 비어 있거나 유효하지 않을 경우 발생.
    """
    _validate_shap_result(shap_result=shap_result)
    resolved_theme = theme or DEFAULT_THEME
    effective_display: int = max_display or maximum_display
    effective_figure_size: Tuple[float, float] = figsize or figure_size or DEFAULT_GLOBAL_SUMMARY_FIGSIZE

    # 1. 1x2 가로 서브플롯 캔버스 생성
    figure, (axis_beeswarm, axis_bar) = create_horizontal_subplots(
        panel_count=2,
        figsize=effective_figure_size,
        wspace=0.20,
    )

    # 2. Panel 1: Beeswarm 다변량 신호 분포 렌더링
    _render_beeswarm_panel(
        axis=axis_beeswarm,
        shap_result=shap_result,
        maximum_display=effective_display,
        theme=resolved_theme,
    )

    # 3. Panel 2: Mean |SHAP| 피처 랭킹 수평 바차트 렌더링
    _render_global_bar_panel(
        axis=axis_bar,
        shap_result=shap_result,
        maximum_display=effective_display,
        theme=resolved_theme,
    )

    # 4. 전체 슈퍼 타이틀 및 레이아웃 정돈
    figure.suptitle(
        f"[{shap_result.model_name}] Global Feature Importance",
        fontsize=resolved_theme.typography.super_title_size,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout()
    return figure


def plot_dependence_interaction(
    shap_result: ShapResult,
    target_feature: Optional[str] = None,
    interaction_feature: Optional[str] = None,
    figure_size: Optional[Tuple[float, float]] = None,
    figsize: Optional[Tuple[float, float]] = None,
    theme: Optional[VisualizationTheme] = None,
) -> plt.Figure:
    """2차 교호작용 전수 감사 히트맵과 최상위 비선형 반응 곡선을 1x2 대시보드로 렌더링합니다.

    Args:
        shap_result (ShapResult): 2차 교호작용 텐서가 포함된 SHAP 결과 불변 DTO.
        target_feature (Optional[str]): 주 분석 대상 피처 (None 시 최상위 피처 자동 선정).
        interaction_feature (Optional[str]): 컬러맵 결합 피처 (None 시 최적 파트너 자동 선정).
        figure_size (Optional[Tuple[float, float]]): 캔버스 크기. Defaults to None.
        figsize (Optional[Tuple[float, float]]): 하위 호환용 캔버스 크기. Defaults to None.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체. Defaults to None.

    Returns:
        plt.Figure: 좌측 히트맵 및 우측 비선형 반응 산점도로 구성된 Figure 객체.

    Raises:
        ValueError: shap_result가 유효하지 않거나 interaction_values가 부재할 경우 발생.
    """
    _validate_shap_result(shap_result=shap_result)
    _validate_interaction_values(shap_result=shap_result)
    resolved_theme = theme or DEFAULT_THEME
    effective_figure_size: Tuple[float, float] = figsize or figure_size or DEFAULT_DEPENDENCE_FIGSIZE

    # 1. 평균 절대 상호작용 행렬 연산 및 최적 교호작용 피처 쌍 탐색
    interaction_matrix = _calculate_interaction_matrix(interaction_values=shap_result.interaction_values)
    primary_feature, secondary_feature = _resolve_top_interaction_pair(
        interaction_matrix=interaction_matrix,
        feature_names=shap_result.feature_names,
        target_feature=target_feature,
        interaction_feature=interaction_feature,
    )

    # 2. 1x2 가로 서브플롯 캔버스 생성
    figure, (axis_heatmap, axis_dependence) = create_horizontal_subplots(
        panel_count=2,
        figsize=effective_figure_size,
        wspace=DEFAULT_INTERACTION_HORIZONTAL_SPACE,
    )

    # 3. Panel 1: 2차 교호작용 에너지 강도 히트맵
    _render_interaction_heatmap_panel(
        axis=axis_heatmap,
        interaction_matrix=interaction_matrix,
        feature_names=shap_result.feature_names,
        highlighted_pair=(primary_feature, secondary_feature),
        theme=resolved_theme,
    )

    # 4. Panel 2: 최상위 비선형 반응 의존성 산점도
    _render_dependence_panel(
        axis=axis_dependence,
        shap_result=shap_result,
        target_feature=primary_feature,
        interaction_feature=secondary_feature,
        theme=resolved_theme,
    )

    figure.suptitle(
        f"[{shap_result.model_name}] Feature Interaction & Non-linear Dependence Dashboard",
        fontsize=resolved_theme.typography.super_title_size,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout()
    return figure


def plot_regime_waterfall(
    shap_result: ShapResult,
    sample_targets: Optional[Union[Union[int, Any], List[Union[int, Any]], List[Tuple[Union[int, Any], str]]]] = None,
    regime_targets: Optional[List[str]] = None,
    title: Optional[str] = None,
    title_suffix: str = "",
    maximum_display: int = DEFAULT_MAXIMUM_DISPLAY,
    figure_size: Optional[Tuple[float, float]] = None,
    max_display: Optional[int] = None,
    figsize: Optional[Tuple[float, float]] = None,
    theme: Optional[VisualizationTheme] = None,
) -> plt.Figure:
    """5대 시장 국면 코호트 평균 또는 Holdout Test 대표 국면의 예측 형성 경로 Waterfall을 렌더링합니다.

    Args:
        shap_result (ShapResult): 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
        sample_targets: 평가 데이터 단일 인덱스 또는 (인덱스, 국면명칭) 튜플 시퀀스.
        regime_targets (Optional[List[str]]): 코호트 감사 결과 중 시각화할 국면 명칭 리스트.
        title (Optional[str]): 대시보드 메인 제목. Defaults to None.
        title_suffix (str): 국면 식별 부제. Defaults to "".
        maximum_display (int): 표시할 최대 주요 피처 수. Defaults to 8.
        figure_size (Optional[Tuple[float, float]]): 캔버스 크기. Defaults to None.
        max_display (Optional[int]): 하위 호환용 최대 피처 수. Defaults to None.
        figsize (Optional[Tuple[float, float]]): 하위 호환용 캔버스 크기. Defaults to None.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체. Defaults to None.

    Returns:
        plt.Figure: 폭포수 차트로 구성된 Figure 객체.

    Raises:
        ValueError: shap_result가 비어 있거나 유효한 국면/타깃 데이터가 부재한 경우 발생.
        KeyError: 지정한 시계열 인덱스가 데이터셋에 부재할 경우 발생.
    """
    _validate_shap_result(shap_result=shap_result)
    resolved_theme = theme or DEFAULT_THEME
    effective_display: int = max_display or maximum_display

    # [설계 의도] sample_targets 미지정 시 5대 시장 국면 코호트 평균 모드로 자동 분기
    if sample_targets is None and shap_result.regime_cohort_result is not None:
        return _render_regime_cohort_waterfall_dashboard(
            shap_result=shap_result,
            cohort_result=shap_result.regime_cohort_result,
            regime_targets=regime_targets,
            title=title,
            maximum_display=effective_display,
            figure_size=figsize or figure_size,
            theme=resolved_theme,
        )

    effective_targets = sample_targets if sample_targets is not None else shap_result.stress_events
    if not effective_targets:
        raise ValueError("[plot_regime_waterfall] sample_targets가 지정되지 않았으며 유효한 국면 정보가 없습니다.")

    normalized_targets = _normalize_waterfall_targets(
        sample_targets=effective_targets,
        title_suffix=title_suffix,
    )
    effective_figure_size = figsize or figure_size or _resolve_waterfall_figure_size(target_count=len(normalized_targets))

    # 1. Nx1 세로 서브플롯 캔버스 생성
    figure, axes = create_vertical_subplots(
        panel_count=len(normalized_targets),
        figsize=effective_figure_size,
        hspace=DEFAULT_MULTI_WATERFALL_VERTICAL_SPACE,
    )

    # 2. 타깃별 Waterfall 패널 순회 렌더링
    for axis, (target_item, label_suffix) in zip(axes, normalized_targets):
        sample_location_index = _resolve_sample_integer_index(
            evaluation_index=shap_result.evaluation_index,
            target=target_item,
        )
        _render_waterfall_panel(
            axis=axis,
            shap_result=shap_result,
            sample_location_index=sample_location_index,
            maximum_display=effective_display,
            theme=resolved_theme,
        )
        date_label = str(shap_result.evaluation_index[sample_location_index])[:10]
        header_text = (
            f"[{shap_result.model_name}] {date_label} ({label_suffix})"
            if label_suffix
            else f"[{shap_result.model_name}] {date_label}"
        )
        axis.set_title(header_text, fontsize=resolved_theme.typography.panel_title_size, fontweight="bold")

    # [설계 의도] shap.plots.waterfall 내부의 자동 리사이즈 부작용을 방지하고 본래 규격 강제 복원
    figure.set_size_inches(effective_figure_size)

    main_title = title or _resolve_waterfall_title(
        model_name=shap_result.model_name,
        is_multi_panel=(len(normalized_targets) > 1),
        title_suffix=title_suffix,
    )
    figure.suptitle(
        main_title,
        fontsize=resolved_theme.typography.super_title_size,
        fontweight="bold",
        y=DEFAULT_WATERFALL_TITLE_VERTICAL_POSITION,
    )
    figure.subplots_adjust(top=DEFAULT_WATERFALL_TOP_RECTANGLE)
    return figure


def plot_dynamic_rolling_shap(
    shap_result: ShapResult,
    top_k_features: int = DEFAULT_TOP_K_ROLLING,
    kospi_series: Optional[pd.Series] = None,
    event_benchmarks: Optional[List[Tuple[Union[int, Any], str]]] = None,
    figure_size: Optional[Tuple[float, float]] = None,
    top_k: Optional[int] = None,
    figsize: Optional[Tuple[float, float]] = None,
    theme: Optional[VisualizationTheme] = None,
) -> plt.Figure:
    """시계열 타임라인에 따른 최상위 핵심 팩터의 SHAP 기여도 전이 및 시장 지표를 동기화 렌더링합니다.

    Args:
        shap_result (ShapResult): 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
        top_k_features (int): 시계열 추적할 최상위 기여 팩터 수. Defaults to 4.
        kospi_series (Optional[pd.Series]): 상단 패널에 매핑할 시장 지표 시계열. Defaults to None.
        event_benchmarks (Optional[List[Tuple[Union[int, Any], str]]]): 주요 스트레스 이벤트 시퀀스.
        figure_size (Optional[Tuple[float, float]]): 대시보드 캔버스 크기. Defaults to None.
        top_k (Optional[int]): 하위 호환용 최상위 피처 수. Defaults to None.
        figsize (Optional[Tuple[float, float]]): 하위 호환용 캔버스 크기. Defaults to None.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체. Defaults to None.

    Returns:
        plt.Figure: 시장 벤치마크 및 팩터별 기여도 전이가 동기화된 Figure 객체.

    Raises:
        ValueError: rolling_shap_dataframe이 DTO 내부에 부재할 경우 발생.
    """
    _validate_shap_result(shap_result=shap_result)
    if shap_result.rolling_shap_dataframe is None:
        raise ValueError("[plot_dynamic_rolling_shap] DTO 내부에 rolling_shap_dataframe 데이터가 없습니다.")

    resolved_theme = theme or DEFAULT_THEME
    effective_top_k: int = top_k or top_k_features
    effective_benchmark_series: Optional[pd.Series] = (
        kospi_series if kospi_series is not None else shap_result.benchmark_series
    )
    effective_events: Optional[List[Tuple[Union[int, Any], str]]] = (
        event_benchmarks if event_benchmarks is not None else shap_result.stress_events
    )

    has_benchmark: bool = effective_benchmark_series is not None
    effective_figure_size = figsize or figure_size or (
        DEFAULT_DUAL_ROLLING_FIGSIZE if has_benchmark else DEFAULT_SINGLE_ROLLING_FIGSIZE
    )

    # 1. 시장 벤치마크 유무에 따른 서브플롯 분기 생성
    if has_benchmark:
        figure, axes = create_vertical_subplots(
            panel_count=2,
            figsize=effective_figure_size,
            sharex=True,
            height_ratios=DEFAULT_ROLLING_HEIGHT_RATIOS,
            hspace=0.12,
        )
        axis_benchmark, axis_rolling = axes[0], axes[1]
        _render_benchmark_panel(
            axis=axis_benchmark,
            benchmark_series=effective_benchmark_series,
            evaluation_index=shap_result.evaluation_index,
            theme=resolved_theme,
        )
    else:
        figure, axes = create_vertical_subplots(panel_count=1, figsize=effective_figure_size)
        axis_rolling = axes[0]

    # 2. 하단 롤링 SHAP 팩터 기여도 전이 패널 렌더링
    _render_rolling_shap_panel(
        axis=axis_rolling,
        shap_result=shap_result,
        top_k_features=effective_top_k,
        theme=resolved_theme,
    )

    title_suffix = " with Market Benchmark" if has_benchmark else " (20D Window)"
    figure.suptitle(
        f"[{shap_result.model_name}] Dynamic Rolling SHAP{title_suffix}",
        fontsize=resolved_theme.typography.super_title_size,
        fontweight="bold",
        y=0.985,
    )
    plt.tight_layout()
    return figure


def plot_inflection_sizing(
    shap_result: ShapResult,
    inflection_targets: Optional[
        Union[
            str,
            Tuple[str, Dict[str, float]],
            List[Tuple[str, Dict[str, float]]],
            Dict[str, Dict[str, float]],
            InflectionPolicyResult,
        ]
    ] = None,
    evaluation_features: Optional[pd.DataFrame] = None,
    inflection_info: Optional[Dict[str, float]] = None,
    figure_size: Optional[Tuple[float, float]] = None,
    X_eval: Optional[pd.DataFrame] = None,
    figsize: Optional[Tuple[float, float]] = None,
    theme: Optional[VisualizationTheme] = None,
) -> plt.Figure:
    """리스크 팩터의 SHAP 변곡점 및 동적 리스크 통제/포지션 사이징 영역을 렌더링합니다.

    Args:
        shap_result (ShapResult): 수리통계적 검증이 완료된 SHAP 결과 불변 DTO.
        inflection_targets: 단일 피처명, 튜플, 리스트, 딕셔너리 또는 InflectionPolicyResult 객체.
        evaluation_features (Optional[pd.DataFrame]): 평가 데이터셋 원시 피처 행렬.
        inflection_info (Optional[Dict[str, float]]): 단일 피처명 지정 시 사용할 변곡점 정보.
        figure_size (Optional[Tuple[float, float]]): 캔버스 크기. Defaults to None.
        X_eval (Optional[pd.DataFrame]): 하위 호환용 평가 피처 행렬. Defaults to None.
        figsize (Optional[Tuple[float, float]]): 하위 호환용 캔버스 크기. Defaults to None.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체. Defaults to None.

    Returns:
        plt.Figure: 변곡점 컷오프 및 정책 영역 분할 Figure 객체.

    Raises:
        ValueError: 대상 피처명이 유효하지 않거나 피처 데이터가 비어 있을 경우 발생.
    """
    _validate_shap_result(shap_result=shap_result)
    resolved_theme = theme or DEFAULT_THEME
    resolved_features = evaluation_features if evaluation_features is not None else X_eval
    if resolved_features is None:
        raise ValueError("[plot_inflection_sizing] evaluation_features 또는 X_eval은 필수 입력입니다.")

    effective_targets = inflection_targets if inflection_targets is not None else shap_result.inflection_policy_result
    if effective_targets is None:
        raise ValueError("[plot_inflection_sizing] inflection_targets가 지정되지 않았으며 유효한 결과가 없습니다.")

    normalized_targets = _normalize_inflection_targets(
        targets=effective_targets,
        fallback_info=inflection_info,
        valid_feature_names=shap_result.feature_names,
    )
    is_multi_panel = len(normalized_targets) > 1
    effective_figure_size = figsize or figure_size or _resolve_inflection_figure_size(target_count=len(normalized_targets))

    # 1. 패널 수에 따른 가로 1xN 또는 2차원 그리드 서브플롯 생성
    if len(normalized_targets) <= 3:
        figure, axes = create_horizontal_subplots(
            panel_count=len(normalized_targets),
            figsize=effective_figure_size,
        )
    else:
        figure, axes = create_grid_subplots(
            total_panels=len(normalized_targets),
            n_cols=DEFAULT_INFLECTION_GRID_COLUMNS,
            figsize=effective_figure_size,
            hspace=0.35,
            wspace=0.22,
        )

    column_count = min(len(normalized_targets), DEFAULT_INFLECTION_GRID_COLUMNS)
    for index, (axis, (target_feature_name, info_dictionary)) in enumerate(zip(axes, normalized_targets)):
        _render_inflection_panel(
            axis=axis,
            shap_result=shap_result,
            feature_name=target_feature_name,
            inflection_info=info_dictionary,
            evaluation_features=resolved_features,
            show_ylabel=(index % column_count == 0),
            show_legend=(not is_multi_panel),
            theme=resolved_theme,
        )

    # 2. 다중 패널 시 최상단 단일 통합 공통 범례 배치
    if is_multi_panel:
        add_unified_legend(
            figure=figure,
            ax=axes[0],
            ncol=4,
            bbox_to_anchor=(0.5, 0.95),
            theme=resolved_theme,
        )

    figure.suptitle(
        f"[{shap_result.model_name}] Risk Inflection & Policy Boundary Dashboard",
        fontsize=resolved_theme.typography.super_title_size,
        fontweight="bold",
        y=0.985,
    )
    top_rectangle = 0.93 if len(normalized_targets) > 3 else DEFAULT_SUBPLOT_TOP_RECTANGLE
    plt.tight_layout(rect=[0.0, 0.0, 1.0, top_rectangle])
    return figure


class ShapVisualizer:
    """SHAP 기반 설명 가능성 분석, 국면 부검 및 동적 리스크 시각화 파사드 클래스."""

    plot_global_summary = staticmethod(plot_global_summary)
    plot_dependence_interaction = staticmethod(plot_dependence_interaction)
    plot_regime_waterfall = staticmethod(plot_regime_waterfall)
    plot_dynamic_rolling_shap = staticmethod(plot_dynamic_rolling_shap)
    plot_inflection_sizing = staticmethod(plot_inflection_sizing)


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_shap_result(shap_result: ShapResult) -> None:
    """ShapResult DTO의 유효성과 데이터 존재 여부를 검증합니다."""
    if shap_result is None or shap_result.shap_values.size == 0:
        raise ValueError("[_validate_shap_result] shap_result가 비어 있거나 유효하지 않습니다.")


def _validate_interaction_values(shap_result: ShapResult) -> None:
    """ShapResult DTO 내부에 2차 교호작용 텐서가 존재하는지 검증합니다."""
    if shap_result.interaction_values is None:
        raise ValueError(
            "[_validate_interaction_values] DTO 내에 interaction_values가 없습니다. "
            "ShapExplainer.explain(compute_interaction=True) 옵션을 확인하십시오."
        )


def _resolve_sample_integer_index(evaluation_index: pd.Index, target: Union[int, Any]) -> int:
    """타임스탬프 또는 정수 인덱스로부터 0-based 정수 위치를 도출합니다."""
    if isinstance(target, (int, np.integer)):
        if 0 <= target < len(evaluation_index):
            return int(target)
        raise IndexError(f"[_resolve_sample_integer_index] 정수 인덱스 범위 초과: {target}")

    if target in evaluation_index:
        return int(evaluation_index.get_loc(target))

    raise KeyError(f"[_resolve_sample_integer_index] 지정한 타임스탬프 '{target}'가 평가 인덱스에 없습니다.")


def _render_beeswarm_panel(
    axis: plt.Axes,
    shap_result: ShapResult,
    maximum_display: int,
    theme: VisualizationTheme,
) -> None:
    """Beeswarm 신호 분포 패널을 렌더링합니다."""
    plt.sca(axis)
    shap.plots.beeswarm(shap_result.shap_explanation, max_display=maximum_display, show=False)
    axis.set_title("Beeswarm Distribution", fontsize=theme.typography.panel_title_size, fontweight="bold")
    apply_axis_grid(ax=axis, theme=theme)


def _render_global_bar_panel(
    axis: plt.Axes,
    shap_result: ShapResult,
    maximum_display: int,
    theme: VisualizationTheme,
) -> None:
    """피처별 Mean |SHAP| 절대 기여도 및 비중 수평 막대그래프를 렌더링합니다."""
    top_importance_dataframe = shap_result.global_importance_dataframe.head(maximum_display).iloc[::-1]
    y_positions = np.arange(len(top_importance_dataframe))
    importance_values = top_importance_dataframe["mean_abs_shap"].to_numpy()
    ratio_values = top_importance_dataframe["importance_ratio_pct"].to_numpy()

    model_color = resolve_model_color(model_name=shap_result.model_name, theme=theme)
    axis.barh(y_positions, importance_values, color=model_color, alpha=0.85, edgecolor="none", height=0.6)

    maximum_value = np.max(importance_values) if len(importance_values) > 0 else 1.0
    for index, (value, ratio) in enumerate(zip(importance_values, ratio_values)):
        axis.text(
            value + (maximum_value * 0.02),
            index,
            f"{value:.4f} ({ratio:.1f}%)",
            va="center",
            ha="left",
            fontsize=theme.typography.annotation_size,
            fontweight="bold",
            color=theme.status_palette.text_dark,
        )

    axis.set_yticks(y_positions)
    axis.set_yticklabels([])
    axis.tick_params(axis="y", left=False)
    axis.set_xlabel("Mean |SHAP| (E[|ϕ|])", fontsize=theme.typography.axis_label_size)
    axis.set_xlim(0.0, maximum_value * 1.32)
    axis.set_title("Mean |SHAP| Ranking", fontsize=theme.typography.panel_title_size, fontweight="bold")
    apply_axis_grid(ax=axis, theme=theme)


def _calculate_interaction_matrix(interaction_values: np.ndarray) -> np.ndarray:
    """2차 교호작용 텐서로부터 피처 간 평균 절대 상호작용 행렬을 연산합니다."""
    matrix: np.ndarray = np.mean(np.abs(interaction_values), axis=0)
    np.fill_diagonal(matrix, 0.0)
    return matrix


def _resolve_top_interaction_pair(
    interaction_matrix: np.ndarray,
    feature_names: List[str],
    target_feature: Optional[str] = None,
    interaction_feature: Optional[str] = None,
) -> Tuple[str, str]:
    """상호작용 강도 행렬에서 최대 시너지를 갖는 최적 피처 쌍을 도출합니다."""
    if target_feature and interaction_feature:
        if target_feature not in feature_names or interaction_feature not in feature_names:
            raise ValueError("[_resolve_top_interaction_pair] 지정된 피처가 결과 피처 풀에 없습니다.")
        return target_feature, interaction_feature

    if target_feature:
        if target_feature not in feature_names:
            raise ValueError(f"[_resolve_top_interaction_pair] '{target_feature}'이(가) 피처 풀에 없습니다.")
        target_index = feature_names.index(target_feature)
        partner_index = int(np.argmax(interaction_matrix[target_index]))
        return target_feature, feature_names[partner_index]

    upper_indices = np.triu_indices_from(interaction_matrix, k=1)
    if len(upper_indices[0]) == 0:
        return feature_names[0], feature_names[1]

    maximum_index = int(np.argmax(interaction_matrix[upper_indices]))
    row_index = int(upper_indices[0][maximum_index])
    column_index = int(upper_indices[1][maximum_index])

    return feature_names[row_index], feature_names[column_index]


def _render_interaction_heatmap_panel(
    axis: plt.Axes,
    interaction_matrix: np.ndarray,
    feature_names: List[str],
    highlighted_pair: Tuple[str, str],
    theme: VisualizationTheme,
) -> None:
    """피처 간 2차 교호작용 강도 히트맵 및 1위 시너지 셀을 렌더링합니다."""
    image_plot = axis.imshow(interaction_matrix, cmap=theme.status_palette.heatmap_colormap, aspect="auto")
    feature_count = len(feature_names)

    maximum_value = float(np.max(interaction_matrix)) if np.max(interaction_matrix) > 0.0 else 1.0
    for row in range(feature_count):
        for column in range(feature_count):
            value = float(interaction_matrix[row, column])
            if row != column and value > 0.0:
                text_color = "white" if value > (maximum_value * 0.60) else "black"
                axis.text(column, row, f"{value:.3f}", ha="center", va="center", fontsize=7.5, color=text_color)

    # [설계 의도] 1위 교호작용 페어 셀 테두리 하이라이트 박스 표시
    primary_feature, secondary_feature = highlighted_pair
    if primary_feature in feature_names and secondary_feature in feature_names:
        row_position = feature_names.index(primary_feature)
        column_position = feature_names.index(secondary_feature)
        for target_row, target_col in [(row_position, column_position), (column_position, row_position)]:
            rectangle_patch = plt.Rectangle(
                (target_col - 0.5, target_row - 0.5),
                1.0,
                1.0,
                fill=False,
                edgecolor=theme.status_palette.interaction_box,
                linewidth=theme.styles.interaction_box_width,
            )
            axis.add_patch(rectangle_patch)

    tick_positions = np.arange(feature_count)
    axis.set_xticks(tick_positions)
    axis.set_yticks(tick_positions)
    axis.set_xticklabels(feature_names, rotation=45, ha="right", fontsize=theme.typography.tick_label_size)
    axis.set_yticklabels(feature_names, fontsize=theme.typography.tick_label_size)
    axis.set_title(f"SHAP Interaction Strength ({feature_count}x{feature_count})", fontsize=theme.typography.panel_title_size, fontweight="bold")

    color_bar = plt.colorbar(image_plot, ax=axis, fraction=0.046, pad=0.04)
    color_bar.ax.tick_params(labelsize=theme.typography.tick_label_size)
    color_bar.set_label("Mean |SHAP Interaction|", fontsize=theme.typography.axis_label_size)


def _render_dependence_panel(
    axis: plt.Axes,
    shap_result: ShapResult,
    target_feature: str,
    interaction_feature: Optional[str],
    theme: VisualizationTheme,
) -> None:
    """비선형 의존성 산점도, 상호작용 컬러맵 및 하단 주변분포 히스토그램을 렌더링합니다."""
    plt.sca(axis)
    target_index = shap_result.feature_names.index(target_feature)
    interaction_index = (
        shap_result.feature_names.index(interaction_feature)
        if interaction_feature and interaction_feature in shap_result.feature_names
        else "auto"
    )

    # 1. SHAP 의존성 산점도 및 컬러바를 우선 렌더링하여 기본 Axes의 크기 및 축 정렬 확정
    shap.plots.scatter(
        shap_result.shap_explanation[:, target_index],
        color=shap_result.shap_explanation[:, interaction_index] if interaction_index != "auto" else None,
        ax=axis,
        show=False,
    )

    # 2. [설계 의도] 컬러바 생성으로 리사이즈된 축에 동기화하여 하단 주변분포 히스토그램 오버레이 (외삽 감지)
    feature_raw_values = shap_result.shap_explanation[:, target_index].data
    axis_histogram = axis.twinx()
    counts, _, _ = axis_histogram.hist(
        feature_raw_values,
        bins=HISTOGRAM_DEFAULT_BINS,
        color=theme.status_palette.histogram_bar,
        alpha=theme.styles.histogram_alpha,
        zorder=0,
    )
    maximum_count = float(np.max(counts)) if len(counts) > 0 and np.max(counts) > 0 else 1.0
    axis_histogram.set_ylim(0.0, maximum_count * theme.styles.histogram_max_ratio)
    axis_histogram.set_yticks([])
    axis_histogram.axis("off")

    # 히스토그램이 산점도 클릭/호버 및 배경 투명도에 간섭하지 않도록 레이어 우선순위 정돈
    axis.set_zorder(axis_histogram.get_zorder() + 1)
    axis.patch.set_visible(False)
    axis.axhline(0.0, color=theme.status_palette.baseline, linestyle="--", linewidth=1.0, alpha=0.7)
    axis.set_ylabel(f"SHAP Value for {target_feature}", fontsize=theme.typography.axis_label_size)
    axis.set_xlabel(target_feature, fontsize=theme.typography.axis_label_size)
    axis.set_title(f"Empirical Dependence (x {interaction_feature})", fontsize=theme.typography.panel_title_size, fontweight="bold")
    apply_axis_grid(ax=axis, theme=theme)


def _render_waterfall_panel(
    axis: plt.Axes,
    shap_result: ShapResult,
    sample_location_index: int,
    maximum_display: int,
    theme: VisualizationTheme,
) -> None:
    """단일 관측치 로컬 Waterfall 기여 분해 패널을 렌더링합니다."""
    plt.sca(axis)
    shap.plots.waterfall(shap_result.shap_explanation[sample_location_index], max_display=maximum_display, show=False)
    apply_axis_grid(ax=axis, theme=theme)


def _render_cohort_waterfall_panel(
    axis: plt.Axes,
    cohort_explanation: shap.Explanation,
    maximum_display: int,
    theme: VisualizationTheme,
) -> None:
    """단일 시장 국면 코호트 평균 Explanation 객체의 Waterfall 패널을 렌더링합니다."""
    plt.sca(axis)
    shap.plots.waterfall(cohort_explanation, max_display=maximum_display, show=False)
    apply_axis_grid(ax=axis, theme=theme)


def _create_cohort_explanation(
    mean_shap_vector: np.ndarray,
    base_value: float,
    feature_names: List[str],
) -> shap.Explanation:
    """국면별 평균 SHAP 벡터로부터 waterfall 플롯 렌더링용 Explanation 객체를 조립합니다."""
    return shap.Explanation(
        values=mean_shap_vector,
        base_values=base_value,
        feature_names=feature_names,
    )


def _render_regime_cohort_waterfall_dashboard(
    shap_result: ShapResult,
    cohort_result: RegimeCohortResult,
    regime_targets: Optional[List[str]],
    title: Optional[str],
    maximum_display: int,
    figure_size: Optional[Tuple[float, float]],
    theme: VisualizationTheme,
) -> plt.Figure:
    """5대 시장 국면 코호트의 평균 기여도 워터폴 패널들을 일괄 렌더링합니다."""
    available_regimes = cohort_result.regime_mean_shap_dataframe.index.tolist()
    target_regimes = [r for r in regime_targets if r in available_regimes] if regime_targets else available_regimes

    if not target_regimes:
        raise ValueError("[_render_regime_cohort_waterfall_dashboard] 렌더링 대상 유효 시장 국면이 존재하지 않습니다.")

    effective_figure_size = figure_size or _resolve_waterfall_figure_size(target_count=len(target_regimes))
    figure, axes = create_vertical_subplots(
        panel_count=len(target_regimes),
        figsize=effective_figure_size,
        hspace=DEFAULT_MULTI_WATERFALL_VERTICAL_SPACE,
    )

    for axis, regime_name in zip(axes, target_regimes):
        mean_shap_vector = cohort_result.regime_mean_shap_dataframe.loc[regime_name].to_numpy(dtype=np.float64)
        sample_count = cohort_result.regime_sample_counts.get(regime_name, 0)
        cohort_explanation = _create_cohort_explanation(
            mean_shap_vector=mean_shap_vector,
            base_value=shap_result.base_value,
            feature_names=shap_result.feature_names,
        )

        _render_cohort_waterfall_panel(
            axis=axis,
            cohort_explanation=cohort_explanation,
            maximum_display=maximum_display,
            theme=theme,
        )
        axis.set_title(
            f"[{shap_result.model_name}] {regime_name} (Cohort Mean, N={sample_count})",
            fontsize=theme.typography.panel_title_size,
            fontweight="bold",
        )

    figure.set_size_inches(effective_figure_size)
    main_title = title or f"[{shap_result.model_name}] Robust Regime-Cohort Waterfall Breakdown (Cohort Mean)"
    figure.suptitle(
        main_title,
        fontsize=theme.typography.super_title_size,
        fontweight="bold",
        y=DEFAULT_WATERFALL_TITLE_VERTICAL_POSITION,
    )
    figure.subplots_adjust(top=DEFAULT_WATERFALL_TOP_RECTANGLE)
    return figure


def _render_benchmark_panel(
    axis: plt.Axes,
    benchmark_series: pd.Series,
    evaluation_index: pd.Index,
    theme: VisualizationTheme,
) -> None:
    """상단 시장 지표 벤치마크 시계열 패널을 렌더링합니다."""
    aligned_series = benchmark_series.reindex(evaluation_index).ffill().bfill()
    axis.plot(
        aligned_series.index,
        aligned_series.values,
        color=theme.status_palette.benchmark,
        linewidth=1.6,
        label="Market Benchmark",
    )

    axis.set_ylabel("Index Level", fontsize=theme.typography.axis_label_size, fontweight="bold")
    axis.set_title("Market Ground Truth Benchmark", fontsize=theme.typography.panel_title_size, fontweight="bold")
    apply_axis_grid(ax=axis, theme=theme)
    axis.legend(loc="upper left", frameon=True, fontsize=theme.typography.legend_size)


def _render_rolling_shap_panel(
    axis: plt.Axes,
    shap_result: ShapResult,
    top_k_features: int,
    theme: VisualizationTheme,
) -> None:
    """상위 핵심 피처의 시계열 롤링 평균 SHAP 기여도 전이 궤적을 렌더링합니다."""
    rolling_dataframe = shap_result.rolling_shap_dataframe
    top_features = shap_result.top_features[:top_k_features]
    color_sequence = theme.model_palette.rolling_sequence

    for index, feature in enumerate(top_features):
        line_color = color_sequence[index % len(color_sequence)]
        axis.plot(
            rolling_dataframe.index,
            rolling_dataframe[feature],
            label=f"{feature}",
            color=line_color,
            linewidth=1.8,
            alpha=0.9,
        )

    axis.axhline(0.0, color=theme.status_palette.baseline, linestyle="--", linewidth=1.2, alpha=0.8)
    axis.set_ylabel("Rolling SHAP (Mean)", fontsize=theme.typography.axis_label_size, fontweight="bold")
    axis.set_xlabel("Horizon Timeline", fontsize=theme.typography.axis_label_size, fontweight="bold")
    axis.set_title("Factor Attribution Shifts", fontsize=theme.typography.panel_title_size, fontweight="bold")
    apply_axis_grid(ax=axis, theme=theme)
    axis.legend(loc="upper left", frameon=True, fontsize=theme.typography.legend_size, ncol=2)


def _render_inflection_panel(
    axis: plt.Axes,
    shap_result: ShapResult,
    feature_name: str,
    inflection_info: Dict[str, float],
    evaluation_features: pd.DataFrame,
    show_ylabel: bool,
    show_legend: bool,
    theme: VisualizationTheme,
) -> None:
    """변곡점 임계치 기준 리스크 분할 및 포지션 사이징 가이드 패널을 렌더링합니다."""
    feature_values = evaluation_features[feature_name].to_numpy(dtype=np.float64)
    feature_index = shap_result.feature_names.index(feature_name)
    shap_values = shap_result.shap_values[:, feature_index]

    threshold = inflection_info["inflection_threshold"]
    delta_impact = inflection_info["delta_impact"]

    model_fallback_color = theme.model_palette.fallback
    axis.scatter(feature_values, shap_values, color=model_fallback_color, alpha=0.45, s=25, label="Holdout Samples")
    axis.axvline(
        threshold,
        color=theme.status_palette.risk_line,
        linestyle="-.",
        linewidth=2.0,
        label=f"Inflection Threshold ({threshold:.4f})",
    )
    axis.axhline(0.0, color=theme.status_palette.baseline, linestyle="--", linewidth=1.0, alpha=0.7)

    minimum_value, maximum_value = float(np.min(feature_values)), float(np.max(feature_values))

    # [설계 의도] 팩터별 위험 방향 부호(risk_direction_sign: +1 초과 시 위험, -1 하회 시 위험)에 따른 정상/위험 구역 동적 분기
    # 메타데이터 부재 시 delta_impact 부호(음수 시 좌측 위험)를 폴백으로 활용하여 코스피 건설업 첨도 등의 역방향 팩터 지원
    risk_direction_sign = inflection_info.get(
        "risk_direction_sign",
        inflection_info.get("risk_sign", -1 if delta_impact < 0 else 1),
    )

    if risk_direction_sign == -1:
        # [역방향 팩터] 임계치 하회 시 위험 (좌: De-risking Zone, 우: Normal Operation Zone)
        axis.axvspan(
            minimum_value,
            threshold,
            color=theme.status_palette.risk_zone_bg,
            alpha=theme.styles.risk_zone_alpha,
            label="De-risking / Cut-off Zone",
        )
        axis.axvspan(
            threshold,
            maximum_value,
            color=theme.status_palette.safe_zone_bg,
            alpha=theme.styles.safe_zone_alpha,
            label="Normal Operation Zone",
        )
        text_x_pos = threshold - (threshold - minimum_value) * 0.04
        text_ha = "right"
        shift_desc = "De-risking on Drop" if delta_impact < 0 else "Normal on Rise"
    else:
        # [순방향 팩터] 임계치 초과 시 위험 (좌: Normal Operation Zone, 우: De-risking Zone)
        axis.axvspan(
            minimum_value,
            threshold,
            color=theme.status_palette.safe_zone_bg,
            alpha=theme.styles.safe_zone_alpha,
            label="Normal Operation Zone",
        )
        axis.axvspan(
            threshold,
            maximum_value,
            color=theme.status_palette.risk_zone_bg,
            alpha=theme.styles.risk_zone_alpha,
            label="De-risking / Cut-off Zone",
        )
        text_x_pos = threshold + (maximum_value - threshold) * 0.04
        text_ha = "left"
        shift_desc = "Shift to Downside" if delta_impact < 0 else "Shift to High Risk"

    axis.text(
        text_x_pos,
        float(np.max(shap_values)) * 0.85,
        f"Δ Impact: {delta_impact:+.4f}\n({shift_desc})",
        color=theme.status_palette.risk_line,
        fontsize=theme.typography.axis_label_size,
        fontweight="bold",
        ha=text_ha,
    )

    axis.set_xlabel(f"Factor Value: {feature_name}", fontsize=theme.typography.axis_label_size, fontweight="bold")
    if show_ylabel:
        axis.set_ylabel("SHAP Marginal Impact", fontsize=theme.typography.axis_label_size, fontweight="bold")
    axis.set_title(feature_name, fontsize=theme.typography.panel_title_size, fontweight="bold")
    apply_axis_grid(ax=axis, theme=theme)

    if show_legend:
        axis.legend(loc="upper right", frameon=True, fontsize=theme.typography.legend_size)


def _resolve_waterfall_figure_size(target_count: int) -> Tuple[float, float]:
    """Waterfall 패널 수에 따른 적응형 캔버스 크기를 산출합니다."""
    if target_count == 1:
        return DEFAULT_SINGLE_WATERFALL_FIGSIZE
    computed_height = max(DEFAULT_MULTI_WATERFALL_FIGSIZE[1], DEFAULT_WATERFALL_PANEL_HEIGHT * target_count)
    return (DEFAULT_MULTI_WATERFALL_FIGSIZE[0], computed_height)


def _normalize_waterfall_targets(
    sample_targets: Union[Union[int, Any], List[Union[int, Any]], List[Tuple[Union[int, Any], str]]],
    title_suffix: str,
) -> List[Tuple[Union[int, Any], str]]:
    """입력된 Waterfall 타겟을 (인덱스, 국면명칭) 튜플 리스트로 표준화합니다."""
    if not isinstance(sample_targets, list):
        return [(sample_targets, title_suffix)]

    normalized_list: List[Tuple[Union[int, Any], str]] = []
    for item in sample_targets:
        if isinstance(item, tuple) and len(item) == 2:
            normalized_list.append((item[0], str(item[1])))
        else:
            normalized_list.append((item, ""))
    return normalized_list


def _resolve_inflection_figure_size(target_count: int) -> Tuple[float, float]:
    """변곡점 패널 수에 따른 적응형 캔버스 규격을 산출합니다."""
    if target_count == 1:
        return DEFAULT_SINGLE_INFLECTION_FIGSIZE
    if target_count <= 3:
        return (6.0 * target_count, 5.5)
    row_count = int(np.ceil(target_count / DEFAULT_INFLECTION_GRID_COLUMNS))
    return (18.0, DEFAULT_INFLECTION_ROW_HEIGHT * row_count)


def _normalize_inflection_targets(
    targets: Union[
        str,
        Tuple[str, Dict[str, float]],
        List[Tuple[str, Dict[str, float]]],
        Dict[str, Dict[str, float]],
        InflectionPolicyResult,
    ],
    fallback_info: Optional[Dict[str, float]],
    valid_feature_names: List[str],
) -> List[Tuple[str, Dict[str, float]]]:
    """입력된 변곡점 타겟을 [(피처명, 정보딕셔너리), ...] 형태로 표준화합니다."""
    normalized_list: List[Tuple[str, Dict[str, float]]] = []

    if isinstance(targets, InflectionPolicyResult):
        for feature_name, record in targets.policy_records.items():
            normalized_list.append((feature_name, record.as_dictionary))
    elif isinstance(targets, str):
        if fallback_info is None:
            raise ValueError("[_normalize_inflection_targets] 단일 피처명 지정 시 inflection_info가 필수입니다.")
        normalized_list.append((targets, fallback_info))
    elif isinstance(targets, dict):
        normalized_list = list(targets.items())
    elif isinstance(targets, list):
        normalized_list = targets
    elif isinstance(targets, tuple) and len(targets) == 2 and isinstance(targets[0], str):
        normalized_list = [targets]
    else:
        raise ValueError("[_normalize_inflection_targets] 지원하지 않는 inflection_targets 형식입니다.")

    for feature_name, _ in normalized_list:
        if feature_name not in valid_feature_names:
            raise ValueError(f"[_normalize_inflection_targets] '{feature_name}'이(가) 결과 피처 풀에 없습니다.")

    return normalized_list


def _resolve_waterfall_title(
    model_name: str,
    is_multi_panel: bool,
    title_suffix: str = "",
) -> str:
    """Waterfall 대시보드의 단일/다중 국면에 따른 상단 메인 타이틀 문자열을 산출합니다."""
    if is_multi_panel:
        return f"[{model_name}] Regime-Specific Waterfall Breakdown"
    suffix = f" ({title_suffix})" if title_suffix else ""
    return f"[{model_name}] Local Waterfall Breakdown{suffix}"