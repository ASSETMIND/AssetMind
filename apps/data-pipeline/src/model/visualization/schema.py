from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 1. 모델 대표 색상 팔레트 (Model Color Codes)
DEFAULT_XGBOOST_COLOR: str = "#1F77B4"                        # XGBoost 기본 시각화 색상
DEFAULT_RANDOM_FOREST_COLOR: str = "#2CA02C"                  # RandomForest 기본 시각화 색상
DEFAULT_ELASTIC_NET_COLOR: str = "#FF7F0E"                    # ElasticNet 기본 시각화 색상
DEFAULT_CATBOOST_COLOR: str = "#9467BD"                       # CatBoost 기본 시각화 색상
DEFAULT_TABULAR_RESNET_COLOR: str = "#8C564B"                 # TabularResNet 기본 시각화 색상
DEFAULT_DCN_V2_COLOR: str = "#E377C2"                         # DCNv2 기본 시각화 색상
DEFAULT_FT_TRANSFORMER_COLOR: str = "#17BECF"                 # FTTransformer 기본 시각화 색상
DEFAULT_TCN_COLOR: str = "#BCBD22"                            # TCN 기본 시각화 색상
FALLBACK_MODEL_COLOR: str = "#4A90E2"                         # 미등록 모델 대체 기본 색상
DEFAULT_ROLLING_LINE_COLORS: Tuple[str, ...] = (
    "#1F77B4",                                                # 1순위 피처 추적 라인 색상 (파랑)
    "#FF7F0E",                                                # 2순위 피처 추적 라인 색상 (주황)
    "#2CA02C",                                                # 3순위 피처 추적 라인 색상 (초록)
    "#D62728",                                                # 4순위 피처 추적 라인 색상 (빨강)
    "#9467BD",                                                # 5순위 피처 추적 라인 색상 (보라)
    "#8C564B",                                                # 6순위 피처 추적 라인 색상 (갈색)
)

# 2. 상태 및 기준선 색상 (Status & Reference Line Colors)
BASELINE_LINE_COLOR: str = "#7F7F7F"                          # 제로 라인 및 기준선 색상
BENCHMARK_LINE_COLOR: str = "#2C3E50"                         # 벤치마크 지표(KOSPI) 시계열 라인 색상
RISK_LINE_COLOR: str = "#D0021B"                              # 리스크 임계선/게이트/컷오프 라인 색상
SAFE_LINE_COLOR: str = "#F5A623"                              # 안전 구역 경계선 색상
SAFE_ZONE_BG_COLOR: str = "#2CA02C"                           # 정상 운용(Normal) 구간 배경 하이라이트 색상
RISK_ZONE_BG_COLOR: str = "#D0021B"                           # 디리스킹(Cut-off) 구간 배경 하이라이트 색상
OPTIMUM_STAR_COLOR: str = "#F5A623"                           # 최적해 마커 별 색상
OPTIMUM_EDGE_COLOR: str = "#222222"                           # 최적해 마커 테두리 색상
CV_POINT_COLOR: str = "#2B5B84"                               # 교차검증(CV) 기준 포인트 색상
TEST_POINT_COLOR: str = "#D9534F"                             # Holdout Test 실측 포인트 색상
POSITIVE_GAP_COLOR: str = "#2CA02C"                           # 양(+)의 유지율 갭 강조 색상
NEGATIVE_GAP_COLOR: str = "#D0021B"                           # 음(-)의 유지율 갭 강조 색상
HISTOGRAM_BAR_COLOR: str = "#D3D3D3"                          # 외삽 방어용 주변분포 히스토그램 막대 색상
INTERACTION_BOX_COLOR: str = "#D0021B"                        # 1위 교호작용 페어 하이라이트 테두리 박스 색상
INTERACTION_HEATMAP_COLORMAP: str = "YlOrRd"                  # 교호작용 에너지 강도 히트맵 컬러맵
TEXT_DARK_COLOR: str = "#333333"                              # 차트 내부 주요 수치 라벨 색상
TEXT_MUTED_COLOR: str = "#777777"                             # 빈 패널 및 보조 안내 문구 색상

# 3. 캔버스 규격 (Canvas Dimension Specifications)
DEFAULT_DUMBBELL_FIGSIZE: Tuple[float, float] = (16.0, 5.0)   # 덤벨 차트 기본 캔버스 규격
DEFAULT_UNDERWATER_FIGSIZE: Tuple[float, float] = (16.0, 8.0) # 언더워터 2단 패널 기본 캔버스 규격
DEFAULT_HPO_DASHBOARD_FIGSIZE: Tuple[float, float] = (16.0, 4.8) # HPO 감사 대시보드 1x3 패널 기본 규격
DEFAULT_GLOBAL_SUMMARY_FIGSIZE: Tuple[float, float] = (16.0, 6.0) # 글로벌 중요도 듀얼 패널 기본 캔버스 규격
DEFAULT_DEPENDENCE_FIGSIZE: Tuple[float, float] = (16.5, 6.0) # 1x2 교호작용 패널 기본 캔버스 규격
DEFAULT_SINGLE_WATERFALL_FIGSIZE: Tuple[float, float] = (12.0, 5.5) # 단일 Waterfall 기본 캔버스 규격
DEFAULT_MULTI_WATERFALL_FIGSIZE: Tuple[float, float] = (13.0, 14.0) # 다중 Waterfall 기본 캔버스 규격
DEFAULT_SINGLE_ROLLING_FIGSIZE: Tuple[float, float] = (16.0, 6.0) # 단일 롤링 시계열 패널 기본 규격
DEFAULT_DUAL_ROLLING_FIGSIZE: Tuple[float, float] = (16.0, 8.5) # 벤치마크 결합 상하 2단 롤링 패널 규격
DEFAULT_SINGLE_INFLECTION_FIGSIZE: Tuple[float, float] = (11.0, 5.5) # 단일 변곡점 기본 패널 규격
DEFAULT_MULTI_INFLECTION_FIGSIZE: Tuple[float, float] = (18.0, 5.5) # 다중 변곡점 그리드 대시보드 기본 규격

# 4. 타이포그래피 (Typography Specifications)
SUPER_TITLE_FONT_SIZE: float = 12.0                           # 캔버스 메인 슈퍼 타이틀 폰트 크기
PANEL_TITLE_FONT_SIZE: float = 10.5                           # 개별 서브플롯 타이틀 폰트 크기
AXIS_LABEL_FONT_SIZE: float = 9.0                             # 축 라벨 폰트 크기
TICK_LABEL_FONT_SIZE: float = 8.5                             # 축 눈금 라벨 폰트 크기
LEGEND_FONT_SIZE: float = 8.5                                 # 범례 폰트 크기
ANNOTATION_FONT_SIZE: float = 8.5                             # 데이터 수치 주석 텍스트 폰트 크기

# 5. 그래픽 서식 및 투명도 (Styling & Transparency Specifications)
GRID_LINE_STYLE: str = "--"                                   # 공통 그리드 라인 점선 스타일
GRID_LINE_ALPHA: float = 0.45                                 # 공통 그리드 라인 투명도
BASELINE_LINE_STYLE: str = ":"                                # 기준선 라인 점선 스타일
BASELINE_LINE_ALPHA: float = 0.80                             # 기준선 라인 투명도
SAFE_ZONE_BG_ALPHA: float = 0.08                              # 안전 구역 배경 음영 투명도
RISK_ZONE_BG_ALPHA: float = 0.08                              # 위험 구역 배경 음영 투명도
CHAMPION_FILL_ALPHA: float = 0.15                             # 챔피언 자산 곡선 음영 투명도
HISTOGRAM_BAR_ALPHA: float = 0.50                             # 주변분포 히스토그램 투명도
HISTOGRAM_MAXIMUM_RATIO: float = 5.0                          # 산점도 하단 히스토그램 높이 통제 승수
INTERACTION_BOX_LINE_WIDTH: float = 2.0                       # 1위 교호작용 페어 하이라이트 박스 선 두께

# 6. 테마 불변 데이터 계약 클래스 정의 (Data Contract Classes)
@dataclass(frozen=True)
class ModelColorPalette:
    """머신러닝 모델별 시각화 색상 불변 데이터 계약."""

    xgboost: str = DEFAULT_XGBOOST_COLOR                       # XGBoost 색상
    random_forest: str = DEFAULT_RANDOM_FOREST_COLOR           # RandomForest 색상
    elastic_net: str = DEFAULT_ELASTIC_NET_COLOR               # ElasticNet 색상
    catboost: str = DEFAULT_CATBOOST_COLOR                     # CatBoost 색상
    tabular_resnet: str = DEFAULT_TABULAR_RESNET_COLOR         # TabularResNet 색상
    dcn_v2: str = DEFAULT_DCN_V2_COLOR                         # DCNv2 색상
    ft_transformer: str = DEFAULT_FT_TRANSFORMER_COLOR         # FTTransformer 색상
    tcn: str = DEFAULT_TCN_COLOR                               # TCN 색상
    fallback: str = FALLBACK_MODEL_COLOR                       # 미등록 모델 대체 색상
    custom_models: Dict[str, str] = field(default_factory=dict) # 사용자 정의 추가 모델 색상 맵
    rolling_sequence: Tuple[str, ...] = DEFAULT_ROLLING_LINE_COLORS # 시계열 순환 색상 튜플

    def as_dict(self) -> Dict[str, str]:
        """모델명 키와 색상 값 매핑 딕셔너리를 반환합니다."""
        color_map: Dict[str, str] = {
            "XGBoost": self.xgboost,
            "RandomForest": self.random_forest,
            "ElasticNet": self.elastic_net,
            "CatBoost": self.catboost,
            "TabularResNet": self.tabular_resnet,
            "DCNv2": self.dcn_v2,
            "FTTransformer": self.ft_transformer,
            "TCN": self.tcn,
        }
        color_map.update(self.custom_models)
        return color_map


@dataclass(frozen=True)
class StatusColorPalette:
    """시스템 상태 표시 및 가이드라인 색상 불변 데이터 계약."""

    baseline: str = BASELINE_LINE_COLOR                         # 기준선 색상
    benchmark: str = BENCHMARK_LINE_COLOR                       # 벤치마크 라인 색상
    risk_line: str = RISK_LINE_COLOR                           # 리스크 임계선/게이트 색상
    safe_line: str = SAFE_LINE_COLOR                           # 안전 구역 경계선 색상
    safe_zone_bg: str = SAFE_ZONE_BG_COLOR                     # 안전 구역 배경색
    risk_zone_bg: str = RISK_ZONE_BG_COLOR                     # 위험 구역 배경색
    optimum_star: str = OPTIMUM_STAR_COLOR                     # 최적해 마커 색상
    optimum_edge: str = OPTIMUM_EDGE_COLOR                     # 최적해 테두리 색상
    cv_point: str = CV_POINT_COLOR                             # CV 포인트 색상
    test_point: str = TEST_POINT_COLOR                         # Test 포인트 색상
    positive_gap: str = POSITIVE_GAP_COLOR                     # 양(+)의 유지율 갭 색상
    negative_gap: str = NEGATIVE_GAP_COLOR                     # 음(-)의 유지율 갭 색상
    histogram_bar: str = HISTOGRAM_BAR_COLOR                   # 히스토그램 막대 색상
    interaction_box: str = INTERACTION_BOX_COLOR               # 교호작용 강조 박스 색상
    heatmap_colormap: str = INTERACTION_HEATMAP_COLORMAP       # 교호작용 히트맵 컬러맵
    text_dark: str = TEXT_DARK_COLOR                           # 수치 강조 텍스트 색상
    text_muted: str = TEXT_MUTED_COLOR                         # 안내 문구 텍스트 색상


@dataclass(frozen=True)
class FigureDimensionConfig:
    """차트 종류별 기본 캔버스 규격 불변 데이터 계약."""

    dumbbell: Tuple[float, float] = DEFAULT_DUMBBELL_FIGSIZE
    underwater: Tuple[float, float] = DEFAULT_UNDERWATER_FIGSIZE
    hpo_dashboard: Tuple[float, float] = DEFAULT_HPO_DASHBOARD_FIGSIZE
    global_summary: Tuple[float, float] = DEFAULT_GLOBAL_SUMMARY_FIGSIZE
    dependence: Tuple[float, float] = DEFAULT_DEPENDENCE_FIGSIZE
    single_waterfall: Tuple[float, float] = DEFAULT_SINGLE_WATERFALL_FIGSIZE
    multi_waterfall: Tuple[float, float] = DEFAULT_MULTI_WATERFALL_FIGSIZE
    single_rolling: Tuple[float, float] = DEFAULT_SINGLE_ROLLING_FIGSIZE
    dual_rolling: Tuple[float, float] = DEFAULT_DUAL_ROLLING_FIGSIZE
    single_inflection: Tuple[float, float] = DEFAULT_SINGLE_INFLECTION_FIGSIZE
    multi_inflection: Tuple[float, float] = DEFAULT_MULTI_INFLECTION_FIGSIZE


@dataclass(frozen=True)
class TypographyConfig:
    """타이포그래피 및 계층별 폰트 규격 불변 데이터 계약."""

    super_title_size: float = SUPER_TITLE_FONT_SIZE
    panel_title_size: float = PANEL_TITLE_FONT_SIZE
    axis_label_size: float = AXIS_LABEL_FONT_SIZE
    tick_label_size: float = TICK_LABEL_FONT_SIZE
    legend_size: float = LEGEND_FONT_SIZE
    annotation_size: float = ANNOTATION_FONT_SIZE


@dataclass(frozen=True)
class ChartStyleConfig:
    """그래픽 프리미티브 서식 및 투명도 불변 데이터 계약."""

    grid_linestyle: str = GRID_LINE_STYLE
    grid_alpha: float = GRID_LINE_ALPHA
    baseline_linestyle: str = BASELINE_LINE_STYLE
    baseline_alpha: float = BASELINE_LINE_ALPHA
    safe_zone_alpha: float = SAFE_ZONE_BG_ALPHA
    risk_zone_alpha: float = RISK_ZONE_BG_ALPHA
    champion_fill_alpha: float = CHAMPION_FILL_ALPHA
    histogram_alpha: float = HISTOGRAM_BAR_ALPHA
    histogram_max_ratio: float = HISTOGRAM_MAXIMUM_RATIO
    interaction_box_width: float = INTERACTION_BOX_LINE_WIDTH


@dataclass(frozen=True)
class VisualizationTheme:
    """시각화 시스템 전체 디자인 테마 통합 데이터 계약."""

    model_palette: ModelColorPalette = field(default_factory=ModelColorPalette)
    status_palette: StatusColorPalette = field(default_factory=StatusColorPalette)
    dimensions: FigureDimensionConfig = field(default_factory=FigureDimensionConfig)
    typography: TypographyConfig = field(default_factory=TypographyConfig)
    styles: ChartStyleConfig = field(default_factory=ChartStyleConfig)


DEFAULT_THEME: VisualizationTheme = VisualizationTheme()       # 시스템 전역 기본 테마 불변 인스턴스


# ==============================================================================
# Public API Functions
# ==============================================================================
def get_default_theme() -> VisualizationTheme:
    """시각화 시스템의 기본 디자인 테마 불변 계약 객체를 반환합니다.

    Returns:
        VisualizationTheme: 표준 색상, 규격, 폰트, 스타일이 바인딩된 기본 테마 객체.
    """
    return _fetch_default_theme_instance()


def create_custom_theme(
    custom_model_colors: Optional[Dict[str, str]] = None,
    figure_size_overrides: Optional[Dict[str, Tuple[float, float]]] = None,
    super_title_size: Optional[float] = None,
    panel_title_size: Optional[float] = None,
    grid_alpha: Optional[float] = None,
) -> VisualizationTheme:
    """사용자 정의 오버라이드를 적용하여 새로운 불변 시각화 테마 객체를 생성합니다.

    Args:
        custom_model_colors (Optional[Dict[str, str]]): 모델명 매핑 색상 오버라이드 딕셔너리.
        figure_size_overrides (Optional[Dict[str, Tuple[float, float]]]): 차트 종류별 캔버스 크기 오버라이드 딕셔너리.
        super_title_size (Optional[float]): 슈퍼 타이틀 폰트 크기.
        panel_title_size (Optional[float]): 패널 타이틀 폰트 크기.
        grid_alpha (Optional[float]): 그리드 라인 투명도.

    Returns:
        VisualizationTheme: 오버라이드가 반영된 신규 불변 테마 계약 객체.
    """
    return _build_custom_theme(
        custom_model_colors=custom_model_colors,
        figure_size_overrides=figure_size_overrides,
        super_title_size=super_title_size,
        panel_title_size=panel_title_size,
        grid_alpha=grid_alpha,
    )


def resolve_model_color(
    model_name: str,
    theme: Optional[VisualizationTheme] = None,
) -> str:
    """모델 명칭에 매핑되는 대표 색상 헥스 코드를 안전하게 반환합니다.

    Args:
        model_name (str): 대상 머신러닝 모델 명칭 (예: 'XGBoost', 'RandomForest').
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체 (None 시 기본 테마 적용).

    Returns:
        str: 모델 시각화용 색상 헥스 코드 문자열.
    """
    target_theme = _resolve_effective_theme(theme=theme)
    return _lookup_model_color(
        model_name=model_name,
        palette=target_theme.model_palette,
    )


def resolve_figure_size(
    chart_type: str,
    theme: Optional[VisualizationTheme] = None,
) -> Tuple[float, float]:
    """차트 유형 명칭에 따른 표준 캔버스 규격(width, height)을 반환합니다.

    Args:
        chart_type (str): 대상 차트 유형 식별자 (예: 'dumbbell', 'underwater', 'global_summary').
        theme (Optional[VisualizationTheme]): 적용할 시각화 테마 객체 (None 시 기본 테마 적용).

    Returns:
        Tuple[float, float]: (가로, 세로) 인치 단위 캔버스 크기 튜플.

    Raises:
        KeyError: 지원하지 않는 차트 유형 식별자가 전달된 경우 발생.
    """
    target_theme = _resolve_effective_theme(theme=theme)
    return _lookup_chart_dimension(
        chart_type=chart_type,
        dimensions=target_theme.dimensions,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _fetch_default_theme_instance() -> VisualizationTheme:
    """싱글톤 기본 테마 객체를 반환합니다."""
    return DEFAULT_THEME


def _resolve_effective_theme(theme: Optional[VisualizationTheme]) -> VisualizationTheme:
    """전달된 테마 객체 또는 기본 테마 객체를 안전하게 결정합니다."""
    return theme if theme is not None else DEFAULT_THEME


def _lookup_model_color(model_name: str, palette: ModelColorPalette) -> str:
    """팔레트 맵에서 모델 색상을 조회하고 부재 시 대체 색상을 반환합니다."""
    model_map = palette.as_dict()
    return model_map.get(model_name, palette.fallback)


def _lookup_chart_dimension(
    chart_type: str,
    dimensions: FigureDimensionConfig,
) -> Tuple[float, float]:
    """차트 유형 문자열을 기반으로 등록된 캔버스 규격을 매핑 조회합니다."""
    dimension_map: Dict[str, Tuple[float, float]] = {
        "dumbbell": dimensions.dumbbell,
        "underwater": dimensions.underwater,
        "hpo_dashboard": dimensions.hpo_dashboard,
        "global_summary": dimensions.global_summary,
        "dependence": dimensions.dependence,
        "single_waterfall": dimensions.single_waterfall,
        "multi_waterfall": dimensions.multi_waterfall,
        "single_rolling": dimensions.single_rolling,
        "dual_rolling": dimensions.dual_rolling,
        "single_inflection": dimensions.single_inflection,
        "multi_inflection": dimensions.multi_inflection,
    }
    if chart_type not in dimension_map:
        raise KeyError(
            f"[_lookup_chart_dimension] 지원하지 않는 차트 유형입니다: '{chart_type}'. "
            f"지원 유형: {list(dimension_map.keys())}"
        )
    return dimension_map[chart_type]


def _build_custom_theme(
    custom_model_colors: Optional[Dict[str, str]],
    figure_size_overrides: Optional[Dict[str, Tuple[float, float]]],
    super_title_size: Optional[float],
    panel_title_size: Optional[float],
    grid_alpha: Optional[float],
) -> VisualizationTheme:
    """오버라이드 속성들을 결합하여 새로운 테마 불변 객체를 생성합니다."""
    model_palette = (
        ModelColorPalette(custom_models=custom_model_colors)
        if custom_model_colors is not None
        else ModelColorPalette()
    )

    dimensions = (
        _override_dimensions(overrides=figure_size_overrides)
        if figure_size_overrides is not None
        else FigureDimensionConfig()
    )

    typography = TypographyConfig(
        super_title_size=super_title_size or SUPER_TITLE_FONT_SIZE,
        panel_title_size=panel_title_size or PANEL_TITLE_FONT_SIZE,
    )

    styles = ChartStyleConfig(
        grid_alpha=grid_alpha if grid_alpha is not None else GRID_LINE_ALPHA
    )

    return VisualizationTheme(
        model_palette=model_palette,
        status_palette=StatusColorPalette(),
        dimensions=dimensions,
        typography=typography,
        styles=styles,
    )


def _override_dimensions(
    overrides: Dict[str, Tuple[float, float]],
) -> FigureDimensionConfig:
    """캔버스 크기 오버라이드 딕셔너리를 반영한 규격 객체를 생성합니다."""
    return FigureDimensionConfig(
        dumbbell=overrides.get("dumbbell", DEFAULT_DUMBBELL_FIGSIZE),
        underwater=overrides.get("underwater", DEFAULT_UNDERWATER_FIGSIZE),
        hpo_dashboard=overrides.get("hpo_dashboard", DEFAULT_HPO_DASHBOARD_FIGSIZE),
        global_summary=overrides.get("global_summary", DEFAULT_GLOBAL_SUMMARY_FIGSIZE),
        dependence=overrides.get("dependence", DEFAULT_DEPENDENCE_FIGSIZE),
        single_waterfall=overrides.get("single_waterfall", DEFAULT_SINGLE_WATERFALL_FIGSIZE),
        multi_waterfall=overrides.get("multi_waterfall", DEFAULT_MULTI_WATERFALL_FIGSIZE),
        single_rolling=overrides.get("single_rolling", DEFAULT_SINGLE_ROLLING_FIGSIZE),
        dual_rolling=overrides.get("dual_rolling", DEFAULT_DUAL_ROLLING_FIGSIZE),
        single_inflection=overrides.get("single_inflection", DEFAULT_SINGLE_INFLECTION_FIGSIZE),
        multi_inflection=overrides.get("multi_inflection", DEFAULT_MULTI_INFLECTION_FIGSIZE),
    )