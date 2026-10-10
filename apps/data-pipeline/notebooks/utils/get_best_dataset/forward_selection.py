from typing import Any, Dict, List, Tuple, Union
import pandas as pd

from src.dataset.dataset_selector import select_features_batch

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_MAX_MISSING_RATIO: float = 0.2      # 고결측치 피처 감지 및 배제를 위한 최대 결측 비율 상한선 (20% 초과)
DEFAULT_MAX_ZERO_RATIO: float = 0.8         # 희소(Sparse) 피처 감지 및 배제를 위한 최대 0.0 수치 비율 상한선 (80% 이상)
DEFAULT_PEARSON_THRESHOLD: float = 0.85     # 피어슨 선형 공선성 감지 및 타깃 설명력 우선 보존 상관계수 임계치 (|r| >= 0.85)
DEFAULT_DISTANCE_THRESHOLD: float = 0.40    # HFC 계층 군집화 상관거리 절단 임계치 (Distance <= 0.40)
DEFAULT_MIN_FEATURES_BOUND: int = 10        # 2-Pillar 변곡점 선별 시 최소 확보 피처 하한선
DEFAULT_MAX_FEATURES_BOUND: int = 100       # 2-Pillar 변곡점 선별 시 최대 허용 피처 상한선
AUDIT_STEP_INDEX_NAME: str = ""             # 세부 감사표(Audit Table)의 인덱스 기준 컬럼명


# ==============================================================================
# Public API Functions
# ==============================================================================

def batch_select_features(
    split_repository: Dict[str, Dict[str, Union[pd.DataFrame, pd.Series]]],
    max_missing_ratio: float = DEFAULT_MAX_MISSING_RATIO,
    max_zero_ratio: float = DEFAULT_MAX_ZERO_RATIO,
    pearson_threshold: float = DEFAULT_PEARSON_THRESHOLD,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
    min_features: int = DEFAULT_MIN_FEATURES_BOUND,
    max_features: int = DEFAULT_MAX_FEATURES_BOUND
) -> Tuple[Dict[str, Dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    """18종 분할 데이터셋의 일괄 피처 선별을 총괄 실행하고, 노트북 출력용 요약 및 감사 보고서 DataFrame을 사출합니다.

    Args:
        split_repository: 18종 분할 데이터셋 딕셔너리.
        max_missing_ratio: 결측치 허용 상한 비율 (기본값: 0.20).
        max_zero_ratio: 0값 허용 상한 비율 (기본값: 0.80).
        pearson_threshold: 피어슨 상관계수 임계치 (기본값: 0.85).
        distance_threshold: HFC 거리 임계치 (기본값: 0.40).
        min_features: 최소 선별 피처 수 (기본값: 10).
        max_features: 최대 선별 피처 수 (기본값: 100).

    Returns:
        Tuple[Dict[str, Dict[str, Any]], pd.DataFrame, pd.DataFrame]:
            - model_ready_repository: 후행 전처리 및 선별이 완료된 18종 데이터셋 저장소.
            - selection_summary_report: 18종 데이터셋 일괄 정산 대시보드 DataFrame.
            - representative_audit_report: 대표 데이터셋 6단계 세부 감사표 DataFrame.
    """
    # 1. 18종 분할 데이터셋 대상 피처 선별 오케스트레이션 엔진 일괄 호출
    model_ready_repository, summary_records, audit_meta = select_features_batch(
        split_repository=split_repository,
        max_missing_ratio=max_missing_ratio,
        max_zero_ratio=max_zero_ratio,
        pearson_threshold=pearson_threshold,
        distance_threshold=distance_threshold,
        min_features=min_features,
        max_features=max_features
    )

    # 2. 반환된 18종 배치 요약 레코드를 정산 대시보드 DataFrame으로 렌더링
    selection_summary_report: pd.DataFrame = _build_selection_summary_report(
        batch_summary_records=summary_records
    )

    # 3. 대표 데이터셋(첫 번째 버킷)의 6단계 전처리 메타데이터를 세부 감사표 DataFrame으로 렌더링
    representative_audit_report: pd.DataFrame = _build_representative_audit_report(
        audit_meta=audit_meta
    )

    # 4. 선별 완료 데이터셋 리포지토리 및 두 리포트 DataFrame 반환
    return model_ready_repository, selection_summary_report, representative_audit_report


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _build_selection_summary_report(
    batch_summary_records: List[Dict[str, Any]]
) -> pd.DataFrame:
    """18종 데이터셋 일괄 피처 선별 메타데이터를 정산 대시보드 DataFrame으로 변환합니다."""
    report_rows: List[Dict[str, Any]] = []

    for record in batch_summary_records:
        report_rows.append({
            "Dataset Bucket ID": record["bucket_job_id"],
            "Initial Features": record["initial_feature_count"],
            "After Noise Filter": record["after_noise_count"],
            "After Collinear Filter": record["collinear_filtered_count"],
            "Selected Features": record["selected_features_count"],
            "Cumulative Coverage": f"{record['achieved_cumulative_ratio'] * 100:.1f}%",
            "Elapsed Time": f"{record['elapsed_seconds']:.2f}s"
        })

    return pd.DataFrame(report_rows)


def _build_representative_audit_report(
    audit_meta: Dict[str, Any]
) -> pd.DataFrame:
    """대표 데이터셋의 6단계 후행 전처리 및 선별 메타데이터를 세부 감사표 DataFrame으로 조립합니다."""
    if not audit_meta:
        return pd.DataFrame(columns=[
            "잔여 피처 수 (Features)",
            "변동 내역 (Changes)",
            "적용 기준 (Fit Strategy)"
        ])

    init_count: int = audit_meta.get("initial_feature_count", 0)
    noise_count: int = audit_meta.get("noise_removed_count", 0)
    after_noise_count: int = audit_meta.get("after_noise_count", init_count - noise_count)

    dropped_constants_count: int = len(audit_meta.get("dropped_constants", []))
    dropped_missings_count: int = len(audit_meta.get("dropped_missings", []))
    dropped_zeros_count: int = len(audit_meta.get("dropped_zeros", []))

    dropped_pearson_count: int = len(audit_meta.get("dropped_pearson", []))
    collinear_count: int = audit_meta.get("collinear_filtered_count", 0)
    dropped_hierarchical_count: int = len(audit_meta.get("dropped_hierarchical", []))

    stability_count: int = audit_meta.get("stability_filtered_count", 0)
    dropped_unstable_count: int = len(audit_meta.get("dropped_unstable", []))

    selected_count: int = audit_meta.get("selected_features_count", 0)
    cum_ratio: float = audit_meta.get("achieved_cumulative_ratio", 0.0)

    max_missing: float = audit_meta.get("max_missing_ratio", DEFAULT_MAX_MISSING_RATIO)
    max_zero: float = audit_meta.get("max_zero_ratio", DEFAULT_MAX_ZERO_RATIO)
    pearson_th: float = audit_meta.get("pearson_threshold", DEFAULT_PEARSON_THRESHOLD)
    dist_th: float = audit_meta.get("distance_threshold", DEFAULT_DISTANCE_THRESHOLD)
    min_feat: int = audit_meta.get("min_features", DEFAULT_MIN_FEATURES_BOUND)
    max_feat: int = audit_meta.get("max_features", DEFAULT_MAX_FEATURES_BOUND)

    # 6단계 전처리 워터폴 흐름을 감사표 행 데이터로 구성
    audit_records: List[Dict[str, str]] = [
        {
            AUDIT_STEP_INDEX_NAME: "1. Noise Filter (Constant & Missing & Zero)",
            "잔여 피처 수 (Features)": f"{after_noise_count:,}",
            "변동 내역 (Changes)": (
                f"-{noise_count} Features (Constant: {dropped_constants_count}, "
                f"Missing: {dropped_missings_count}, Zero: {dropped_zeros_count})"
            ),
            "적용 기준 (Fit Strategy)": f"상수 및 결측률(> {max_missing * 100:.0f}%), 0값(≥ {max_zero * 100:.0f}%)"
        },
        {
            AUDIT_STEP_INDEX_NAME: "2. Pearson Collinearity",
            "잔여 피처 수 (Features)": f"{after_noise_count - dropped_pearson_count:,}",
            "변동 내역 (Changes)": f"-{dropped_pearson_count} Features",
            "적용 기준 (Fit Strategy)": f"피어슨 선형 상관계수(|r| ≥ {pearson_th})"
        },
        {
            AUDIT_STEP_INDEX_NAME: "3. Hierarchical Feature Clustering (HFC)",
            "잔여 피처 수 (Features)": f"{collinear_count:,}",
            "변동 내역 (Changes)": f"-{dropped_hierarchical_count} Features",
            "적용 기준 (Fit Strategy)": f"상관거리 계층 군집화 (Distance ≤ {dist_th})"
        },
        {
            AUDIT_STEP_INDEX_NAME: "4. Walk-Forward Sign Consistency Gate",
            "잔여 피처 수 (Features)": f"{stability_count:,}",
            "변동 내역 (Changes)": f"-{dropped_unstable_count} Unstable Features",
            "적용 기준 (Fit Strategy)": "5-Fold OOF 부호 일치율(≥ 80%) 및 1-Sample t-검정 유의성(p < 0.05)"
        },
        {
            AUDIT_STEP_INDEX_NAME: "5. Rolling Adaptive Standardization",
            "잔여 피처 수 (Features)": f"{stability_count:,}",
            "변동 내역 (Changes)": "Extrapolation 0% & PSI Normalized (Rolling 60d Adaptive)",
            "적용 기준 (Fit Strategy)": "최근 60영업일 롤링 평균/표준편차 및 ±3σ 유계화"
        },
        {
            AUDIT_STEP_INDEX_NAME: f"6. Dynamic 2-Pillar Selection (Top {selected_count})",
            "잔여 피처 수 (Features)": f"{selected_count:,}",
            "변동 내역 (Changes)": f"Selected {selected_count} Features (Coverage: {cum_ratio * 100:.1f}%)",
            "적용 기준 (Fit Strategy)": f"2-Pillar Kneedle Elbow + Dynamic (Bounds: [{min_feat}, {max_feat}])"
        }
    ]

    return pd.DataFrame(audit_records).set_index(AUDIT_STEP_INDEX_NAME)