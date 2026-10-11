from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import matplotlib.pyplot as plt
import numpy as np

from src.model.visualization.schema import (
    DEFAULT_THEME,
    VisualizationTheme,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_EMPTY_TEXT_X: float = 0.5                              # 빈 패널 안내 텍스트 중앙 x 좌표
DEFAULT_EMPTY_TEXT_Y: float = 0.5                              # 빈 패널 안내 텍스트 중앙 y 좌표
DEFAULT_LEGEND_LOC: str = "upper center"                       # 공통 상단 범례 기본 앵커 위치
DEFAULT_LEGEND_NCOL: int = 2                                   # 공통 범례 기본 열 개수
DEFAULT_LEGEND_BBOX_Y: float = 1.05                            # 공통 범례 기본 y축 상단 앵커 위치
DEFAULT_FLOAT_PRECISION: int = 4                               # 부동소수점 포맷팅 기본 자릿수


# ==============================================================================
# Public API Functions
# ==============================================================================
def create_horizontal_subplots(
    panel_count: int,
    figsize: Tuple[float, float],
    wspace: Optional[float] = None,
    sharey: bool = False,
) -> Tuple[plt.Figure, List[plt.Axes]]:
    """가로 1xN 서브플롯 캔버스와 Axes 1차원 리스트를 생성합니다.

    Args:
        panel_count (int): 가로로 배치할 패널 서브플롯 개수.
        figsize (Tuple[float, float]): 캔버스 규격 (width, height).
        wspace (Optional[float]): 서브플롯 간 수평 여백 비율 (기본값: None).
        sharey (bool): y축 공유 여부 (기본값: False).

    Returns:
        Tuple[plt.Figure, List[plt.Axes]]: 생성된 Figure와 1차원 Axes 리스트.

    Raises:
        ValueError: panel_count가 1 미만일 경우 발생.
    """
    _validate_panel_count(panel_count=panel_count)
    return _build_horizontal_subplots(
        panel_count=panel_count,
        figsize=figsize,
        wspace=wspace,
        sharey=sharey,
    )


def create_vertical_subplots(
    panel_count: int,
    figsize: Tuple[float, float],
    hspace: Optional[float] = None,
    sharex: bool = False,
    height_ratios: Optional[Sequence[float]] = None,
) -> Tuple[plt.Figure, List[plt.Axes]]:
    """세로 Nx1 서브플롯 캔버스와 Axes 1차원 리스트를 생성합니다.

    Args:
        panel_count (int): 세로로 배치할 패널 서브플롯 개수.
        figsize (Tuple[float, float]): 캔버스 규격 (width, height).
        hspace (Optional[float]): 서브플롯 간 수직 여백 비율 (기본값: None).
        sharex (bool): x축 공유 여부 (기본값: False).
        height_ratios (Optional[Sequence[float]]): 패널 간 높이 비율 시퀀스 (기본값: None).

    Returns:
        Tuple[plt.Figure, List[plt.Axes]]: 생성된 Figure와 1차원 Axes 리스트.

    Raises:
        ValueError: panel_count가 1 미만일 경우 발생.
    """
    _validate_panel_count(panel_count=panel_count)
    return _build_vertical_subplots(
        panel_count=panel_count,
        figsize=figsize,
        hspace=hspace,
        sharex=sharex,
        height_ratios=height_ratios,
    )


def create_grid_subplots(
    total_panels: int,
    n_cols: int,
    figsize: Tuple[float, float],
    hspace: Optional[float] = None,
    wspace: Optional[float] = None,
) -> Tuple[plt.Figure, List[plt.Axes]]:
    """2차원 그리드 서브플롯을 생성하고 잔여 빈 서브플롯을 비활성화하여 반환합니다.

    Args:
        total_panels (int): 렌더링에 필요한 총 유효 패널 수.
        n_cols (int): 그리드의 열 개수.
        figsize (Tuple[float, float]): 캔버스 규격 (width, height).
        hspace (Optional[float]): 서브플롯 간 수직 여백 비율 (기본값: None).
        wspace (Optional[float]): 서브플롯 간 수평 여백 비율 (기본값: None).

    Returns:
        Tuple[plt.Figure, List[plt.Axes]]: 생성된 Figure와 유효 Axes 1차원 리스트.

    Raises:
        ValueError: total_panels 또는 n_cols가 1 미만일 경우 발생.
    """
    _validate_grid_dimensions(total_panels=total_panels, n_cols=n_cols)
    return _build_grid_subplots(
        total_panels=total_panels,
        n_cols=n_cols,
        figsize=figsize,
        hspace=hspace,
        wspace=wspace,
    )


def apply_axis_grid(
    ax: plt.Axes,
    theme: Optional[VisualizationTheme] = None,
) -> None:
    """테마에 정의된 표준 점선 및 투명도 서식으로 그리드를 적용합니다.

    Args:
        ax (plt.Axes): 그리드를 적용할 Matplotlib Axes 객체.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 (None 시 기본 테마).
    """
    resolved_theme = _resolve_theme(theme=theme)
    _configure_grid(ax=ax, theme=resolved_theme)


def apply_axis_labels(
    ax: plt.Axes,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    theme: Optional[VisualizationTheme] = None,
) -> None:
    """테마 규격 타이포그래피를 적용하여 패널 타이틀 및 축 라벨을 일괄 바인딩합니다.

    Args:
        ax (plt.Axes): 라벨을 바인딩할 Matplotlib Axes 객체.
        title (Optional[str]): 서브플롯 타이틀 문자열.
        xlabel (Optional[str]): x축 라벨 문자열.
        ylabel (Optional[str]): y축 라벨 문자열.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 (None 시 기본 테마).
    """
    resolved_theme = _resolve_theme(theme=theme)
    _bind_axis_labels(
        ax=ax,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        theme=resolved_theme,
    )


def render_empty_panel(
    ax: plt.Axes,
    message: str,
    theme: Optional[VisualizationTheme] = None,
) -> None:
    """데이터 결손 또는 시각화 불가 패널에 안내 문구를 출력하고 축을 숨깁니다.

    Args:
        ax (plt.Axes): 안내 문구를 출력할 Matplotlib Axes 객체.
        message (str): 캔버스 중앙에 출력할 알림 메시지.
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 (None 시 기본 테마).
    """
    resolved_theme = _resolve_theme(theme=theme)
    _display_empty_notice(ax=ax, message=message, theme=resolved_theme)


def add_unified_legend(
    figure: plt.Figure,
    ax: plt.Axes,
    ncol: int = DEFAULT_LEGEND_NCOL,
    bbox_to_anchor: Tuple[float, float] = (0.5, DEFAULT_LEGEND_BBOX_Y),
    loc: str = DEFAULT_LEGEND_LOC,
    theme: Optional[VisualizationTheme] = None,
) -> None:
    """Axes로부터 중복이 제거된 핸들과 라벨을 추출하여 Figure 상단에 단일 공통 범례를 배치합니다.

    Args:
        figure (plt.Figure): 범례를 배치할 대상 Figure 객체.
        ax (plt.Axes): 범례 정보를 추출할 참조 Axes 객체.
        ncol (int): 범례 열 개수 (기본값: 2).
        bbox_to_anchor (Tuple[float, float]): 범례 기준점 배치 좌표 (기본값: (0.5, 1.05)).
        loc (str): 범례 앵커 위치 (기본값: 'upper center').
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 (None 시 기본 테마).
    """
    handles, labels = _extract_unique_legend_handles_labels(ax=ax)
    if not handles:
        return
    resolved_theme = _resolve_theme(theme=theme)
    _render_figure_legend(
        figure=figure,
        handles=handles,
        labels=labels,
        ncol=ncol,
        bbox_to_anchor=bbox_to_anchor,
        loc=loc,
        theme=resolved_theme,
    )


def format_parameter_value(
    value: Any,
    precision: int = DEFAULT_FLOAT_PRECISION,
) -> str:
    """수치형 파라미터 값을 불필요한 후행 0을 제거한 차트 레이블용 문자열로 변환합니다.

    Args:
        value (Any): 변환 대상 수치형 또는 문자열 값.
        precision (int): 부동소수점 포맷팅 소수점 자릿수 (기본값: 4).

    Returns:
        str: 정돈된 문자열 표현식.
    """
    return _convert_number_to_clean_string(value=value, precision=precision)


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _resolve_theme(theme: Optional[VisualizationTheme]) -> VisualizationTheme:
    """전달된 테마 객체 또는 기본 테마 싱글톤을 반환합니다."""
    return theme if theme is not None else DEFAULT_THEME


def _validate_panel_count(panel_count: int) -> None:
    """패널 개수가 최소 1개 이상인지 검증합니다."""
    if panel_count < 1:
        raise ValueError(f"[_validate_panel_count] 패널 수는 최소 1 이상이어야 합니다. 입력값: {panel_count}")


def _validate_grid_dimensions(total_panels: int, n_cols: int) -> None:
    """그리드 패널 수와 열 개수의 유효성을 검증합니다."""
    if total_panels < 1:
        raise ValueError(f"[_validate_grid_dimensions] 유효 패널 수는 최소 1 이상이어야 합니다. 입력값: {total_panels}")
    if n_cols < 1:
        raise ValueError(f"[_validate_grid_dimensions] 열 개수는 최소 1 이상이어야 합니다. 입력값: {n_cols}")


def _build_horizontal_subplots(
    panel_count: int,
    figsize: Tuple[float, float],
    wspace: Optional[float],
    sharey: bool,
) -> Tuple[plt.Figure, List[plt.Axes]]:
    """1xN 가로 서브플롯을 생성하고 Axes 리스트를 정규화하여 반환합니다."""
    gridspec_kw = {"wspace": wspace} if wspace is not None else None
    fig, axes = plt.subplots(
        nrows=1,
        ncols=panel_count,
        figsize=figsize,
        sharey=sharey,
        gridspec_kw=gridspec_kw,
    )
    axes_list = [axes] if panel_count == 1 else list(axes)
    return fig, axes_list


def _build_vertical_subplots(
    panel_count: int,
    figsize: Tuple[float, float],
    hspace: Optional[float],
    sharex: bool,
    height_ratios: Optional[Sequence[float]],
) -> Tuple[plt.Figure, List[plt.Axes]]:
    """Nx1 세로 서브플롯을 생성하고 Axes 리스트를 정규화하여 반환합니다."""
    gridspec_kw: Dict[str, Any] = {}
    if hspace is not None:
        gridspec_kw["hspace"] = hspace
    if height_ratios is not None:
        gridspec_kw["height_ratios"] = list(height_ratios)

    effective_gridspec = gridspec_kw if gridspec_kw else None
    fig, axes = plt.subplots(
        nrows=panel_count,
        ncols=1,
        figsize=figsize,
        sharex=sharex,
        gridspec_kw=effective_gridspec,
    )
    axes_list = [axes] if panel_count == 1 else list(axes)
    return fig, axes_list


def _build_grid_subplots(
    total_panels: int,
    n_cols: int,
    figsize: Tuple[float, float],
    hspace: Optional[float],
    wspace: Optional[float],
) -> Tuple[plt.Figure, List[plt.Axes]]:
    """그리드 레이아웃을 생성하고 초과 서브플롯을 비활성화한 뒤 유효 Axes만 반환합니다."""
    n_rows = int(np.ceil(total_panels / n_cols))
    gridspec_kw: Dict[str, Any] = {}
    if hspace is not None:
        gridspec_kw["hspace"] = hspace
    if wspace is not None:
        gridspec_kw["wspace"] = wspace

    effective_gridspec = gridspec_kw if gridspec_kw else None
    fig, axes_array = plt.subplots(
        nrows=n_rows,
        ncols=n_cols,
        figsize=figsize,
        gridspec_kw=effective_gridspec,
    )

    flat_axes: List[plt.Axes] = (
        [axes_array]
        if (n_rows == 1 and n_cols == 1)
        else list(axes_array.flatten())
    )

    for unused_axis in flat_axes[total_panels:]:
        unused_axis.axis("off")

    return fig, flat_axes[:total_panels]


def _configure_grid(ax: plt.Axes, theme: VisualizationTheme) -> None:
    """Axes 객체에 테마 스타일의 그리드 속성을 적용합니다."""
    ax.grid(
        True,
        linestyle=theme.styles.grid_linestyle,
        alpha=theme.styles.grid_alpha,
    )


def _bind_axis_labels(
    ax: plt.Axes,
    title: Optional[str],
    xlabel: Optional[str],
    ylabel: Optional[str],
    theme: VisualizationTheme,
) -> None:
    """타이틀 및 라벨 텍스트와 폰트 크기, 두께를 설정합니다."""
    if title:
        ax.set_title(
            title,
            fontsize=theme.typography.panel_title_size,
            fontweight="bold",
        )
    if xlabel:
        ax.set_xlabel(
            xlabel,
            fontsize=theme.typography.axis_label_size,
        )
    if ylabel:
        ax.set_ylabel(
            ylabel,
            fontsize=theme.typography.axis_label_size,
        )


def _display_empty_notice(
    ax: plt.Axes,
    message: str,
    theme: VisualizationTheme,
) -> None:
    """축을 비활성화하고 중앙에 알림 텍스트를 배치합니다."""
    ax.text(
        DEFAULT_EMPTY_TEXT_X,
        DEFAULT_EMPTY_TEXT_Y,
        message,
        ha="center",
        va="center",
        fontsize=theme.typography.axis_label_size,
        color=theme.status_palette.text_muted,
    )
    ax.set_axis_off()


def _extract_unique_legend_handles_labels(
    ax: plt.Axes,
) -> Tuple[List[Any], List[str]]:
    """Axes로부터 범례 핸들과 라벨을 순서를 보존하며 중복 제거하여 반환합니다."""
    raw_handles, raw_labels = ax.get_legend_handles_labels()
    unique_handles: List[Any] = []
    unique_labels: List[str] = []
    seen: set = set()

    for handle, label in zip(raw_handles, raw_labels):
        if label and label not in seen and not label.startswith("_"):
            seen.add(label)
            unique_handles.append(handle)
            unique_labels.append(label)

    return unique_handles, unique_labels


def _render_figure_legend(
    figure: plt.Figure,
    handles: List[Any],
    labels: List[str],
    ncol: int,
    bbox_to_anchor: Tuple[float, float],
    loc: str,
    theme: VisualizationTheme,
) -> None:
    """Figure 객체에 스타일이 적용된 단일 통합 범례를 배치합니다."""
    figure.legend(
        handles,
        labels,
        loc=loc,
        bbox_to_anchor=bbox_to_anchor,
        ncol=ncol,
        frameon=True,
        fontsize=theme.typography.legend_size,
    )


def _convert_number_to_clean_string(value: Any, precision: int) -> str:
    """부동소수점 값의 후행 0 및 마침표를 제거하여 문자열로 변환합니다."""
    if isinstance(value, (float, np.floating)):
        formatted = f"{value:.{precision}f}"
        return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted
    return str(value)