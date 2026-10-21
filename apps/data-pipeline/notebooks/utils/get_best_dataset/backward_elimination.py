from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

from src.feature.postprocessor.backward_elimination import (
    DEFAULT_FEATURE_BOUNDS,
    TARGET_COLUMN_NAME,
    refine_champion_features,
)

# ==============================================================================
# Constants & Configuration
# ==============================================================================
NEAR_MISS_DISPLAY_LIMIT: int = 15                                               # 진단용 상위 탈락 후보 피처 추출 개수
STAGE_DEFINITIONS: Tuple[Tuple[str, str, str], ...] = (                         # 단계 레이블, 집계 키, 탈락 접두사 매핑 튜플
    ("초기 후보 풀 (Candidate Pool)", "Initial_Pool", ""),
    ("Filter 8: IC 유의성 및 레짐 불변성", "Filter_8_IC_Gate", "Filter 8"),
    ("Filter 9: 2-Pillar PFI 유의성", "Filter_9_PFI_Gate", "Filter 9"),
    ("Filter 10: 공변량 표류(PSI/KS) 방어", "Filter_10_Drift_Gate", "Filter 10"),
)


# ==============================================================================
# Public API Functions
# ==============================================================================
def run_champion_feature_refinement(
    champion_partitions: Dict[str, pd.DataFrame],
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]],
    target_column: str = TARGET_COLUMN_NAME,
    feature_bounds: Tuple[int, int] = DEFAULT_FEATURE_BOUNDS
) -> Dict[str, Any]:
    """1위 챔피언 데이터셋 피처 정예화를 실행하고 3종의 통합 진단 및 요약 DataFrame을 패키징하여 반환합니다.

    Args:
        champion_partitions: 챔피언 데이터셋 분할 파티션 딕셔너리.
        cv_splits: 시계열 교차검증 분할 인덱스 쌍 시퀀스.
        target_column: 타깃 수익률 컬럼명.
        feature_bounds: 최종 정예 피처 수용 범위 (최소, 최대).

    Returns:
        Dict[str, Any]:
            - refined_partitions: 최종 정예 피처셋으로 슬라이싱된 불변 파티션 딕셔너리.
            - survived_features: 최종 선별된 정예 피처 리스트.
            - audit_trail: 전수 감사 원천 DataFrame.
            - funnel_audit_table: 단계별 생존 수율 및 세부 탈락 원인이 행 단위로 통합된 깔때기 감사 DataFrame.
            - near_miss_table: 임계치 인접 탈락 후보 상위 N개 정밀 진단 DataFrame.
            - summary_table: 최종 선별된 최정예 팩터 성과 통계 요약 DataFrame.

    Raises:
        ValueError: 입력 파티션 결손 또는 교차검증 분할 정보 부족 시 발생.
    """
    # 1. 파사드 진입부 입력 데이터 무결성 검증
    _validate_facade_inputs(
        champion_partitions=champion_partitions,
        cv_splits=cv_splits
    )

    # 2. 4단계 후진 소거 정예화 코어 파이프라인 단일 실행
    refinement_output: Dict[str, Any] = _execute_refinement_pipeline(
        champion_partitions=champion_partitions,
        cv_splits=cv_splits,
        target_column=target_column,
        feature_bounds=feature_bounds
    )

    # 3. 단계별 수율과 세부 탈락 원인을 단일 행(Row)으로 1:1 결합한 통합 깔때기 감사표 조립
    funnel_audit_table: pd.DataFrame = _build_funnel_audit_table(
        stage_survivor_counts=refinement_output["stage_survivor_counts"],
        audit_trail=refinement_output["audit_trail"]
    )

    # 4. 임계치 인접 상위 탈락 후보 정밀 진단 DataFrame 조립
    near_miss_table: pd.DataFrame = _build_near_miss_table(
        audit_trail=refinement_output["audit_trail"]
    )

    # 5. 최종 선별된 최정예 팩터 성과 요약 DataFrame 조립
    summary_table: pd.DataFrame = _build_summary_table(
        audit_trail=refinement_output["audit_trail"],
        survived_features=refinement_output["survived_features"]
    )

    # 6. 정예 파티션 및 3종 DataFrame 번들 패키징 및 순수 반환
    return _build_facade_output(
        refinement_output=refinement_output,
        funnel_audit_table=funnel_audit_table,
        near_miss_table=near_miss_table,
        summary_table=summary_table
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_facade_inputs(
    champion_partitions: Dict[str, pd.DataFrame],
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]]
) -> None:
    """파사드 계층 진입부에서 데이터 무결성을 검증합니다."""
    # [설계 의도] 필수 학습 파티션 존재 여부 및 시계열 교차검증 분할 최소 조건 방어
    if not champion_partitions or "X_train" not in champion_partitions:
        raise ValueError("champion_partitions가 비어 있거나 'X_train'이 누락되었습니다.")

    if not cv_splits or len(cv_splits) < 2:
        raise ValueError("시계열 교차검증(CV) 분할 정보가 올바르지 않습니다.")


def _execute_refinement_pipeline(
    champion_partitions: Dict[str, pd.DataFrame],
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]],
    target_column: str,
    feature_bounds: Tuple[int, int]
) -> Dict[str, Any]:
    """피처 태스크 모듈을 호출하여 원자적 정예화를 집행합니다."""
    return refine_champion_features(
        champion_partitions=champion_partitions,
        cv_splits=cv_splits,
        target_column=target_column,
        feature_bounds=feature_bounds
    )


def _build_funnel_audit_table(
    stage_survivor_counts: Dict[str, int],
    audit_trail: pd.DataFrame,
    stage_definitions: Optional[Tuple[Tuple[str, str, str], ...]] = None
) -> pd.DataFrame:
    """단계별 생존 수율과 해당 단계의 세부 탈락 원인을 1:1로 결합한 단일 감사표를 조립합니다."""
    # [설계 의도] 암묵적 전역 스코프 참조로 인한 NameError 방어 및 순수 함수 의존성 주입 원칙 준수
    active_definitions = stage_definitions if stage_definitions is not None else STAGE_DEFINITIONS
    initial_count: int = stage_survivor_counts.get("Initial_Pool", 0)
    audit_rows: List[Dict[str, Any]] = []

    prev_count = initial_count
    for label, stage_key, filter_prefix in active_definitions:
        current_count = stage_survivor_counts.get(stage_key, 0)
        dropped_count = max(0, prev_count - current_count) if prev_count > 0 else 0
        retention_rate = (current_count / prev_count * 100.0) if prev_count > 0 else 0.0
        cumulative_rate = (current_count / initial_count * 100.0) if initial_count > 0 else 0.0

        # [설계 의도] 해당 필터 단계에 속한 탈락 원인들을 전수 감사 데이터에서 동적으로 집계하여 매핑
        if filter_prefix:
            stage_drops = audit_trail[audit_trail["drop_reason"].str.startswith(filter_prefix)]
            if not stage_drops.empty:
                reason_counts = stage_drops["drop_reason"].value_counts()
                breakdown_parts = [
                    f"{reason.replace(f'{filter_prefix}: ', '')} ({count}개)"
                    for reason, count in reason_counts.items()
                ]
                drop_breakdown = ", ".join(breakdown_parts)
            else:
                drop_breakdown = "-"
        else:
            drop_breakdown = "-"

        audit_rows.append({
            "필터 단계 (Filter Stage)": label,
            "생존 피처 수": f"{current_count} 개",
            "탈락 피처 수": f"{dropped_count} 개" if filter_prefix else "-",
            "직전 대비 생존율 (%)": f"{retention_rate:.1f}%",
            "누적 생존율 (%)": f"{cumulative_rate:.1f}%",
            "해당 단계 세부 탈락 원인 (Breakdown)": drop_breakdown,
        })
        prev_count = current_count

    return pd.DataFrame(audit_rows).set_index("필터 단계 (Filter Stage)")


def _build_near_miss_table(audit_trail: pd.DataFrame) -> pd.DataFrame:
    """임계치 경계선에서 탈락한 후보 피처들의 연속형 통계량을 조립합니다."""
    # [설계 의도] 탈락 후보의 연속 수치를 확인하여 필터 임계치와의 마진을 정량 분석할 수 있도록 지원
    dropped_df = audit_trail[audit_trail["drop_reason"] != "Survives (Champion Feature)"].copy()

    # IC 절대값 기준으로 정렬하여 신호가 강했으나 안정성/PFI/표류로 탈락한 상위 변수 우선 노출
    dropped_df["abs_ic"] = dropped_df["f8_mean_ic"].abs()
    sorted_dropped = dropped_df.sort_values(by="abs_ic", ascending=False).head(NEAR_MISS_DISPLAY_LIMIT)

    near_miss_rows: List[Dict[str, Any]] = []
    for _, row in sorted_dropped.iterrows():
        near_miss_rows.append({
            "피처명": row["feature_name"],
            "상세 탈락 사유": row["drop_reason"],
            "Mean IC": f"{row['f8_mean_ic']:.4f}" if pd.notna(row["f8_mean_ic"]) else "-",
            "IC p-val": f"{row['f8_ic_p_val']:.4e}" if pd.notna(row["f8_ic_p_val"]) else "-",
            "PFI Drop": f"{row['f9_pfi_drop']:.4f}" if pd.notna(row["f9_pfi_drop"]) else "-",
            "Negative Folds": int(row["f9_negative_folds"]) if pd.notna(row["f9_negative_folds"]) else "-",
            "PSI": f"{row['f10_psi']:.4f}" if pd.notna(row["f10_psi"]) else "-",
            "KS p-val": f"{row['f10_ks_p_val']:.4f}" if pd.notna(row["f10_ks_p_val"]) else "-",
        })

    result_df = pd.DataFrame(near_miss_rows)
    if not result_df.empty:
        result_df = result_df.set_index("피처명")
    return result_df


def _build_summary_table(
    audit_trail: pd.DataFrame,
    survived_features: List[str]
) -> pd.DataFrame:
    """최종 선별된 최정예 팩터들의 성과 통계 요약 DataFrame을 조립합니다."""
    survivors_df = audit_trail[audit_trail["feature_name"].isin(survived_features)].copy()
    survivors_df = survivors_df.sort_values(by="f9_pfi_drop", ascending=False).reset_index(drop=True)

    summary_records: List[Dict[str, Any]] = []
    for rank, (_, row) in enumerate(survivors_df.iterrows(), start=1):
        summary_records.append({
            "순위": rank,
            "피처명": row["feature_name"],
            "Mean IC": f"{row['f8_mean_ic']:.4f}",
            "IC p-val": f"{row['f8_ic_p_val']:.4e}",
            "PFI Drop": f"{row['f9_pfi_drop']:.4f}",
            "PFI p-val": f"{row['f9_pfi_p_val']:.4e}",
            "PSI": f"{row['f10_psi']:.4f}",
            "KS p-val": f"{row['f10_ks_p_val']:.4f}",
        })

    return pd.DataFrame(summary_records)


def _build_facade_output(
    refinement_output: Dict[str, Any],
    funnel_audit_table: pd.DataFrame,
    near_miss_table: pd.DataFrame,
    summary_table: pd.DataFrame
) -> Dict[str, Any]:
    """정예 파티션 및 3종의 통합 감사/요약 DataFrame을 단일 딕셔너리로 패키징합니다."""
    return {
        "refined_partitions": refinement_output["refined_partitions"],
        "survived_features": refinement_output["survived_features"],
        "audit_trail": refinement_output["audit_trail"],
        "funnel_audit_table": funnel_audit_table,
        "near_miss_table": near_miss_table,
        "summary_table": summary_table,
    }