from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.dataset.screener import batch_screen_datasets
from src.dataset.walk_forward_splitter import WalkForwardSplitter

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_SPLITS: int = 5                     # Walk-Forward CV 기본 폴드 수 (5-Fold)
DEFAULT_FORECAST_HORIZON: int = 20          # 타겟 예측 호라이즌 및 Purged Embargo Gap 일수 (20영업일)
DEFAULT_MIN_TRAIN_RATIO: float = 0.5        # 시계열 Expanding 윈도우 최소 초기 학습 구간 비율
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05    # 통계적 가설 검정 유의수준 (alpha)

# 노트북 화면 보고서 출력용 기본 정렬 컬럼 시퀀스 (식별자 전진 배치 및 계층형 가독성 최적화)
DISPLAY_COLUMNS: Tuple[str, ...] = (
    "Dataset Bucket ID",
    "Impute",
    "Detect",
    "Refine",
    "Demsar Mean Rank",
    "Composite Score",
    "Score Sharpe",
    "Avg MDA",
    "Avg RMSE",
    "Equivalence",
    "p-adj (Abs)",
    "p-val (vs R1)",
    "Power (1-Beta)",
    "Beta (Type-2)",
    "Best Model",
    "Selected Features",
    "Min Score",
    "Avg MAE",
    "Elapsed Time"
)


# ==============================================================================
# Public API Functions
# ==============================================================================

def run_batch_cv_screening(
    model_ready_repository: Dict[str, Dict[str, pd.DataFrame]],
    n_splits: int = DEFAULT_SPLITS,
    forecast_horizon: int = DEFAULT_FORECAST_HORIZON,
    min_train_ratio: float = DEFAULT_MIN_TRAIN_RATIO,
    model_factories: Optional[Dict[str, Callable[[], Any]]] = None,
    significance_level: float = DEFAULT_SIGNIFICANCE_LEVEL
) -> Tuple[pd.DataFrame, str, Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """18종 데이터셋에 대해 시계열 교차검증과 4대 역할 게이트를 일괄 집행하고 프레젠테이션 리포트를 사출합니다.

    Args:
        model_ready_repository: 18종 분할 데이터셋 저장소.
        n_splits: 시계열 교차검증 폴드 수 (기본값: 5).
        forecast_horizon: 타겟 예측 호라이즌 일수 (기본값: 20).
        min_train_ratio: 최소 초기 학습 구간 비율 (기본값: 0.5).
        model_factories: 확장 평가 모델 팩토리 딕셔너리 (None인 경우 기본 모델 레지스트리 자동 바인딩).
        significance_level: 가설 검정 유의수준 (기본값: 0.05).

    Returns:
        Tuple[pd.DataFrame, str, Dict[str, Any], pd.DataFrame, pd.DataFrame]:
            - raw_ranking_report: 원시 수치 랭킹 데이터프레임.
            - champion_dataset_id: 최종 1위 챔피언 데이터셋 ID.
            - champion_meta: 챔피언 성능 요약 메타데이터.
            - display_ranking_report: 화면 출력용 포맷팅 완료 데이터프레임.
            - block_anova_report: 화면 출력용 포맷팅 완료 분산분석표 데이터프레임.
    """
    # 1. 시계열 교차검증 분할기 생성
    cv_splitter: WalkForwardSplitter = _create_walk_forward_splitter(
        n_splits=n_splits,
        forecast_horizon=forecast_horizon,
        min_train_ratio=min_train_ratio
    )

    # 2. 하위 도메인 오케스트레이션 엔진을 호출하여 18종 벤치마크 및 4대 게이트 집행
    raw_ranking_df, champion_id, champion_meta, raw_anova_table = _execute_screening_pipeline(
        model_ready_repository=model_ready_repository,
        splitter=cv_splitter,
        model_factories=model_factories,
        significance_level=significance_level
    )

    # 3. 노트북 가독성을 위한 수치 포맷팅 및 백분율 변환 적용
    formatted_ranking_df: pd.DataFrame = _format_display_ranking_report(
        raw_ranking_df=raw_ranking_df
    )

    # 4. 분산분석표(ANOVA)의 유의확률 및 F-통계량 문자열 정규화 포맷팅
    formatted_anova_df: pd.DataFrame = _format_block_anova_report(
        block_anova_table=raw_anova_table
    )

    # 5. 최종 보고서 표시 컬럼 정렬 및 슬라이싱
    display_ranking_report: pd.DataFrame = _filter_display_columns(
        display_df=formatted_ranking_df
    )

    # 6. [셀 6] 호환 5대 결과 객체 패키징 반환
    return raw_ranking_df, champion_id, champion_meta, display_ranking_report, formatted_anova_df


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _create_walk_forward_splitter(
    n_splits: int,
    forecast_horizon: int,
    min_train_ratio: float
) -> WalkForwardSplitter:
    """시계열 교차검증 분할기(WalkForwardSplitter) 인스턴스를 조립합니다."""
    # 1. 파라미터를 바인딩하여 WalkForwardSplitter 인스턴스 반환
    return WalkForwardSplitter(
        n_splits=n_splits,
        forecast_horizon=forecast_horizon,
        min_train_ratio=min_train_ratio
    )


def _execute_screening_pipeline(
    model_ready_repository: Dict[str, Dict[str, pd.DataFrame]],
    splitter: WalkForwardSplitter,
    model_factories: Optional[Dict[str, Callable[[], Any]]],
    significance_level: float
) -> Tuple[pd.DataFrame, str, Dict[str, Any], pd.DataFrame]:
    """하위 데이터셋 스크리닝 비즈니스 엔진을 실행하고 원천 결과를 수집합니다."""
    # 1. src.dataset.screener의 배치 스크리닝 엔트리포인트 실행
    return batch_screen_datasets(
        model_ready_repository=model_ready_repository,
        splitter=splitter,
        model_factories=model_factories,
        significance_level=significance_level
    )


def _format_display_ranking_report(raw_ranking_df: pd.DataFrame) -> pd.DataFrame:
    """원시 랭킹 데이터프레임의 수치들을 백분율, 유효 소수점 자리수로 포맷팅합니다."""
    # 1. 원본 수치 보존을 위한 깊은 복제 수행
    display_df: pd.DataFrame = raw_ranking_df.copy()

    # 2. Demšar 평균 순위, 복합점수, 최저점, Score Sharpe 소수점 2~4자리 포맷팅
    if "Demsar Mean Rank" in display_df.columns:
        display_df["Demsar Mean Rank"] = display_df["Demsar Mean Rank"].map(lambda val: f"{val:.2f}")
    if "Composite Score" in display_df.columns:
        display_df["Composite Score"] = display_df["Composite Score"].map(lambda val: f"{val:.4f}")
    if "Min Score" in display_df.columns:
        display_df["Min Score"] = display_df["Min Score"].map(lambda val: f"{val:.4f}")
    if "Score Sharpe" in display_df.columns:
        display_df["Score Sharpe"] = display_df["Score Sharpe"].map(lambda val: f"{val:.4f}")

    # 3. 모델 성능 메트릭(Avg MDA, Avg RMSE, Avg MAE) 정밀 포맷팅
    if "Avg MDA" in display_df.columns:
        display_df["Avg MDA"] = display_df["Avg MDA"].map(lambda val: f"{val * 100.0:.2f}%")
    if "Avg RMSE" in display_df.columns:
        display_df["Avg RMSE"] = display_df["Avg RMSE"].map(lambda val: f"{val:.6f}")
    if "Avg MAE" in display_df.columns:
        display_df["Avg MAE"] = display_df["Avg MAE"].map(lambda val: f"{val:.6f}")

    # 4. 제1종/제2종 오류 통계 지표 포맷팅
    if "p-val (Abs)" in display_df.columns:
        display_df["p-val (Abs)"] = display_df["p-val (Abs)"].map(lambda val: f"{val:.4f}")
    if "Beta (Type-2)" in display_df.columns:
        display_df["Beta (Type-2)"] = display_df["Beta (Type-2)"].map(lambda val: f"{val:.4f}")
    if "Power (1-Beta)" in display_df.columns:
        display_df["Power (1-Beta)"] = display_df["Power (1-Beta)"].map(lambda val: f"{val * 100.0:.1f}%")

    # 5. 최고점 Baseline 대비 상대 비교 p-value 및 동등성 판정 문자열 포맷팅
    if "p-val (vs R1)" in display_df.columns and "Equivalence" in display_df.columns:
        display_df["p-val (vs R1)"] = [
            f"{pval:.4f}" if str(eq) != "BASELINE" else "BASELINE"
            for pval, eq in zip(raw_ranking_df["p-val (vs R1)"], raw_ranking_df["Equivalence"])
        ]

    if "p-adj (Abs)" in display_df.columns:
        display_df["p-adj (Abs)"] = display_df["p-adj (Abs)"].map(lambda val: f"{val:.4f}")

    # 6. 타이브레이커 기준 명시: Clipping(표본 보존율 100%) vs Masking(결측 손실)
    if "Refine" in display_df.columns:
        display_df["Refine"] = display_df["Refine"].map(
            lambda val: f"{val} (Loss 0.0%)" if "clip" in str(val).lower() else f"{val} (NaN Lost)"
        )

    return display_df


def _format_block_anova_report(block_anova_table: pd.DataFrame) -> pd.DataFrame:
    """ANOVA 분산분석표에 요인별 국문 명칭, 유의성 판정 및 검정 대상 귀무가설(H0)을 결합하여 정돈합니다."""
    # 1. 원시 수치 보존을 위한 깊은 복제 수행
    formatted_anova: pd.DataFrame = block_anova_table.copy()

    # 2. 통계 검정 판정 및 검정 대상 귀무가설(H0) 정의 (수치 포맷팅 이전 원형 p-value 기반)
    verdicts: List[str] = []
    null_hypotheses: List[str] = []

    for row_name, p_val in zip(formatted_anova.index, formatted_anova["PR(>F)"]):
        row_str = str(row_name)
        if pd.isna(p_val):
            verdicts.append("-")
            null_hypotheses.append("오차항은 독립이고 동일한 정규분포를 따른다")
        elif "Block" in row_str:
            is_significant: bool = p_val < 0.05
            verdicts.append("기각 (p < 0.05)" if is_significant else "채택 (p >= 0.05)")
            null_hypotheses.append("H0: 시장 국면(Fold) 간 모평균에 차이가 없다")
        elif "Impute" in row_str:
            is_significant = p_val < 0.05
            verdicts.append("기각 (p < 0.05)" if is_significant else "채택 (p >= 0.05)")
            null_hypotheses.append("H0: 결측 대치 방식 간 모평균에 차이가 없다")
        elif "Detect" in row_str:
            is_significant = p_val < 0.05
            verdicts.append("기각 (p < 0.05)" if is_significant else "채택 (p >= 0.05)")
            null_hypotheses.append("H0: 이상치 감지 방식 간 모평균에 차이가 없다")
        elif "Refine" in row_str:
            is_significant = p_val < 0.05
            verdicts.append("기각 (p < 0.05)" if is_significant else "채택 (p >= 0.05)")
            null_hypotheses.append("H0: 정제 기법(Clip vs Mask) 간 모평균에 차이가 없다")
        else:
            is_significant = p_val < 0.05
            verdicts.append("기각 (p < 0.05)" if is_significant else "채택 (p >= 0.05)")
            null_hypotheses.append("H0: 전처리 요인 주효과 간 모평균에 차이가 없다")

    formatted_anova["판정 (alpha=0.05)"] = verdicts
    formatted_anova["검정 대상 귀무가설 (Null Hypothesis: H0)"] = null_hypotheses

    # 3. 요인 인덱스를 직관적인 표준 국문 명칭으로 리네이밍
    factor_name_map = {
        "C(Block_Factor)": "시장 국면 블록 (Fold)",
        "C(Factor_0_Impute)": "결측 대치 (Impute)",
        "C(Factor_1_Detect)": "이상치 감지 (Detect)",
        "C(Factor_2_Refine)": "이상치 정제 (Refine)",
        "Residual": "잔차 오차 (Residual)"
    }
    formatted_anova.rename(index=factor_name_map, inplace=True)
    formatted_anova.index.name = "요인 구분 (Source)"

    # 4. 제곱합(sum_sq), F-통계량 및 p-value 표기 포맷팅
    if "sum_sq" in formatted_anova.columns:
        formatted_anova["sum_sq"] = formatted_anova["sum_sq"].map(lambda val: f"{val:.6e}" if pd.notna(val) else "-")
    if "df" in formatted_anova.columns:
        formatted_anova["df"] = formatted_anova["df"].map(lambda val: f"{int(val)}" if pd.notna(val) else "-")
    if "F" in formatted_anova.columns:
        formatted_anova["F"] = formatted_anova["F"].map(lambda val: f"{val:.4f}" if pd.notna(val) else "-")
    if "PR(>F)" in formatted_anova.columns:
        formatted_anova["PR(>F)"] = formatted_anova["PR(>F)"].map(
            lambda val: f"{val:.4e}" if pd.notna(val) and val < 0.001 else (f"{val:.4f}" if pd.notna(val) else "-")
        )

    # 5. 분산분석표 컬럼 국문 정규화
    formatted_anova.rename(
        columns={
            "sum_sq": "제곱합 (SS)",
            "df": "자유도 (df)",
            "F": "F-통계량 (F-val)",
            "PR(>F)": "유의확률 (p-val)"
        },
        inplace=True
    )

    return formatted_anova


def _filter_display_columns(display_df: pd.DataFrame) -> pd.DataFrame:
    """설정된 보고서 컬럼 시퀀스 중 유효한 컬럼만 선택하여 순서를 재배치합니다."""
    # 1. 데이터프레임에 실재하는 대상 컬럼들만 필터링하여 순서 확정
    valid_columns: List[str] = [col for col in DISPLAY_COLUMNS if col in display_df.columns]

    return display_df[valid_columns]