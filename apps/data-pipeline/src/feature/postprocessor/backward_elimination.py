import copy
from typing import Any, Dict, List, Optional, Sequence, Tuple
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet

from src.feature.postprocessor.scaler import standard_scale
from src.statistics.distance.covariate_drift import calculate_psi
from src.statistics.correlation import spearman_correlation
from src.statistics.non_parametric.ks_test import two_sample_ks_test
from src.statistics.parametric.one_t_test import one_sample_t_test
from src.statistics.parametric.paired_t_test import paired_t_test

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [파이프라인 기본 제약 및 공통 설정]
DEFAULT_FEATURE_BOUNDS: Tuple[int, int] = (7, 12)    # 최종 정예 피처 수용 범위 (최소 7개 ~ 최대 12개)
TARGET_COLUMN_NAME: str = "target_return_20d"        # 기준 타깃 수익률 컬럼명
RANDOM_STATE_SEED: int = 42                          # 머신러닝 모델 및 순열 생성 시드
ZERO_DIVISION_EPSILON: float = 1e-12                 # 분모 제로 나눗셈 방지 임계치

# [Filter 8] 단변량 IC 신호 유의성 및 거시 레짐 불변성 임계치
IC_SIGNIFICANCE_ALPHA: float = 0.05                  # 단일표본 t-검정 유의수준 (양측 p < 0.05)
MIN_OOF_SIGN_RATIO: float = 0.80                     # 5-Fold 중 4개 이상 일치 (80% 부호 일관성)
REQUIRE_REGIME_INVARIANCE: bool = True               # Bull/Bear 외생 레짐 부호 불변성 강제 플래그
REGIME_TREND_WINDOW: int = 60                        # [설계 의도] 버크슨 역설 방지를 위한 거시 시장 국면 판정 롤링 윈도우 (60영업일 중기 추세)
MIN_REGIME_OBSERVATIONS: int = 20                    # 국면별 상관계수 연산 안정성을 위한 최소 유효 표본 수
IC_T_TEST_METHOD: str = "johnson"                    # 단일표본 t-검정 알고리즘 ("johnson" 왜도 보정 또는 "student")

# [Filter 9] 다변량 2-Pillar PFI 순열 중요도 유의성 임계치
PFI_SIGNIFICANCE_ALPHA: float = 0.10                 # 5-Fold(df=4) 극소표본 분산 보정 유의수준 (제2종 오류 방어 및 검정력 확보)
MAX_ALLOWED_NEGATIVE_FOLDS: int = 1                  # Fold별 순열 중요도 음수 드롭 허용 개수 (최대 1개 허용)
DEFAULT_PFI_REPEATS: int = 5                         # PFI 셔플 반복 횟수
ELASTIC_NET_MAX_ITER: int = 2000                     # ElasticNet 수렴 최대 반복 횟수
PFI_T_TEST_METHOD: str = "student"                   # PFI 대응표본 t-검정 알고리즘 식별자 ("student" 또는 "nadeau_bengio")

# [Filter 10] 공변량 표류(Covariate Drift) 방어 임계치
PSI_STABLE_THRESHOLD: float = 0.10                   # 안정(Stable) 분포 상한 임계치
PSI_WARNING_THRESHOLD: float = 0.20                  # 경미한 표류(Moderate Drift) 허용 상한 임계치 (고위험 차단선)
KS_SIGNIFICANCE_ALPHA: float = 0.01                  # 2-Sample KS 적합도 검정 유의수준 (대표본 과민반응 보정)
PSI_CRITICAL_BOUND: float = 0.25                     # PSI 점수 정규화 기준 상한선


# ==============================================================================
# Public API Functions
# ==============================================================================
def refine_champion_features(
    champion_partitions: Dict[str, pd.DataFrame],
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]],
    target_column: str = TARGET_COLUMN_NAME,
    feature_bounds: Tuple[int, int] = DEFAULT_FEATURE_BOUNDS
) -> Dict[str, Any]:
    """1위 챔피언 데이터셋의 후보 피처 풀에 대해 4단계 원자적 후진 소거 및 정예화를 수행합니다.

    Args:
        champion_partitions: 챔피언 데이터셋의 분할 파티션 딕셔너리 (X_train, y_train, X_val, X_test 등).
        cv_splits: 시계열 교차검증 인덱스 쌍 시퀀스 (train_indices, val_indices).
        target_column: 타깃 변수명 (기본값: 'target_return_20d').
        feature_bounds: 최종 선별 피처 수 범위 튜플 (기본값: (7, 12)).

    Returns:
        Dict[str, Any]:
            - refined_partitions: 최종 정예 피처로 슬라이싱된 불변 복제 파티션 딕셔너리.
            - survived_features: 최종 7~12개 정예 피처 컬럼 리스트.
            - audit_trail: 4단계 게이트 전수 통계량 및 생존 여부 감사 DataFrame.
            - stage_survivor_counts: 각 필터 단계별 생존 피처 수 집계 딕셔너리.

    Raises:
        ValueError: 필수 파티션 결손 또는 피처 풀이 비어있는 경우 발생.
    """
    # 1. 입력 파티션 규격 및 시계열 교차검증 분할 유효성 검증
    _validate_refinement_inputs(
        champion_partitions=champion_partitions,
        cv_splits=cv_splits,
        target_column=target_column,
        feature_bounds=feature_bounds
    )

    # 2. 분석용 학습 데이터셋 및 초기 후보 피처 풀 추출
    train_features_df: pd.DataFrame = champion_partitions["X_train"]
    target_series: pd.Series = champion_partitions["y_train"]
    initial_features: List[str] = list(train_features_df.columns)

    # 3. [Filter 8] 단변량 팩터 신호 유의성 및 레짐 불변성 검증 게이트 집행
    f8_survivors, f8_records = _execute_ic_gate(
        features=initial_features,
        features_df=train_features_df,
        target_series=target_series,
        cv_splits=cv_splits
    )

    # 4. [Filter 9] 다변량 2-Pillar 순열 중요도 유의성 및 역효과 배제 게이트 집행
    f9_survivors, f9_records = _execute_pfi_gate(
        candidate_features=f8_survivors,
        features_df=train_features_df,
        target_series=target_series,
        cv_splits=cv_splits
    )

    # 5. [Filter 10] 공변량 표류(Covariate Drift) 및 비정상성 분포 방어 게이트 집행
    f10_survivors, f10_records = _execute_drift_gate(
        candidate_features=f9_survivors,
        features_df=train_features_df
    )

    # 6. [Filter 11 삭제 완료] 3중 가설검정(Filter 8~10) 통과 피처 전량을 최종 정예군으로 확정
    final_features: List[str] = f10_survivors.copy()

    # 7. 원본 메모리 오염 방지를 위한 파티션 복제 및 최종 피처셋 슬라이싱
    refined_partitions: Dict[str, pd.DataFrame] = _slice_partitions(
        champion_partitions=champion_partitions,
        survived_features=final_features
    )

    # 8. 3단계 가설검정 전수 감사 DataFrame 및 메타데이터 종합 조립
    audit_trail: pd.DataFrame = _build_audit_record(
        initial_features=initial_features,
        f8_records=f8_records,
        f9_records=f9_records,
        f10_records=f10_records,
        final_features=final_features
    )

    stage_survivor_counts: Dict[str, int] = {
        "Initial_Pool": len(initial_features),
        "Filter_8_IC_Gate": len(f8_survivors),
        "Filter_9_PFI_Gate": len(f9_survivors),
        "Filter_10_Drift_Gate": len(f10_survivors),
        "Final_Selected_Pool": len(final_features)
    }

    return _build_refinement_result(
        refined_partitions=refined_partitions,
        survived_features=final_features,
        audit_trail=audit_trail,
        stage_survivor_counts=stage_survivor_counts
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_refinement_inputs(
    champion_partitions: Dict[str, pd.DataFrame],
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]],
    target_column: str,
    feature_bounds: Tuple[int, int]
) -> None:
    """정예화 파이프라인 구동을 위한 입력 데이터 규격을 엄격히 검증합니다."""
    # 1. 필수 학습 파티션 존재 여부 확인
    if "X_train" not in champion_partitions or "y_train" not in champion_partitions:
        raise ValueError("champion_partitions 내에 'X_train' 및 'y_train' 파티션이 반드시 포함되어야 합니다.")

    # 2. X_train의 피처 존재 여부 검증
    if champion_partitions["X_train"].empty or champion_partitions["X_train"].shape[1] == 0:
        raise ValueError("X_train 피처 행렬이 비어 있어 정예화를 수행할 수 없습니다.")

    # 3. 교차검증 분할 유효성 검증
    if not cv_splits or len(cv_splits) < 2:
        raise ValueError(f"시계열 교차검증(CV) 분할 수가 부족합니다: {len(cv_splits)} (최소 2-Fold 이상 필요)")

    # 4. 정예화 수용 범위 유효성 검증
    min_bound, max_bound = feature_bounds
    if min_bound <= 0 or min_bound > max_bound:
        raise ValueError(f"유효하지 않은 feature_bounds 범위입니다: {feature_bounds}")


def _execute_ic_gate(
    features: List[str],
    features_df: pd.DataFrame,
    target_series: pd.Series,
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]]
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """[Filter 8] 5-Fold Walk-Forward Spearman IC 유의성 및 거시 레짐 불변성을 종합 검증합니다.

    Args:
        features: 평가 대상 후보 피처 컬럼명 리스트.
        features_df: 학습 피처 데이터프레임 (X_train).
        target_series: 타깃 수익률 시계열 (y_train).
        cv_splits: 시계열 교차검증 분할 인덱스 쌍.

    Returns:
        Tuple[List[str], Dict[str, Dict[str, Any]]]: 생존 피처 리스트 및 감사 메타데이터 딕셔너리.
    """
    survivors: List[str] = []
    records: Dict[str, Dict[str, Any]] = {}

    # 1. 거시 시계열 추세 기반 Bull/Bear 외생 레짐 마스크 생성 (버크슨 역설 차단)
    bull_mask, bear_mask = _resolve_macro_regime_masks(
        target_series=target_series,
        trend_window=REGIME_TREND_WINDOW
    )

    target_values: np.ndarray = target_series.values

    # 2. 피처별 단변량 신호 검증 파이프라인 순회
    for feature_name in features:
        feature_values: np.ndarray = features_df[feature_name].values

        # 2-1. 시계열 5-Fold Walk-Forward OOF Rank IC 산출
        fold_ics_array = _calculate_oof_rank_ics(
            feature_values=feature_values,
            target_values=target_values,
            cv_splits=cv_splits
        )
        mean_ic: float = float(np.mean(fold_ics_array))

        # 2-2. 통계적 유의성 단일표본 t-검정 수행 (H0: mean(IC) == 0.0)
        t_stat, p_val, is_statistically_significant = _test_ic_significance(
            fold_ics_array=fold_ics_array,
            method=IC_T_TEST_METHOD,
            alpha=IC_SIGNIFICANCE_ALPHA
        )

        # 2-3. 시계열 교차검증 부호 일관성 검증 (최소 80% 일치)
        is_sign_consistent = _check_sign_consistency(
            fold_ics_array=fold_ics_array,
            min_ratio=MIN_OOF_SIGN_RATIO
        )

        # 2-4. 거시 레짐 불변성 검증 (Bull/Bear 부호 일치 여부)
        is_regime_invariant = _test_regime_invariance(
            feature_values=feature_values,
            target_values=target_values,
            bull_mask=bull_mask,
            bear_mask=bear_mask,
            min_observations=MIN_REGIME_OBSERVATIONS
        )

        # 2-5. Filter 8 최종 통과 여부 통합 판정
        passed: bool = is_statistically_significant and is_sign_consistent
        if REQUIRE_REGIME_INVARIANCE:
            passed = passed and is_regime_invariant

        records[feature_name] = {
            "mean_ic": mean_ic,
            "ic_t_stat": t_stat,
            "ic_p_val": p_val,
            "is_sign_consistent": is_sign_consistent,
            "is_regime_invariant": is_regime_invariant,
            "f8_passed": passed
        }

        if passed:
            survivors.append(feature_name)

    return survivors, records


def _resolve_macro_regime_masks(
    target_series: pd.Series,
    trend_window: int = REGIME_TREND_WINDOW
) -> Tuple[np.ndarray, np.ndarray]:
    """[방안 A] 타깃의 중기 롤링 평균 추세를 기반으로 외생적 Bull/Bear 국면 마스크를 분할합니다.

    Args:
        target_series: 원시 타깃 수익률 시계열.
        trend_window: 거시 추세 형성을 위한 이동평균 윈도우 크기 (기본값: 60영업일).

    Returns:
        Tuple[np.ndarray, np.ndarray]: (bull_mask, bear_mask) 불리언 마스크 배열 쌍.
    """
    # [설계 의도] y_t의 단기 부호 절단으로 인한 버크슨 역설(Berkson's Bias)을 방어하기 위해,
    # 시점별 개별 라벨이 아닌 시장의 중기 거시 추세선(Rolling MA)을 기준으로 시장 국면을 외생 분할함
    macro_trend: pd.Series = target_series.rolling(window=trend_window, min_periods=1).mean()
    bull_mask: np.ndarray = (macro_trend > 0.0).values
    bear_mask: np.ndarray = (macro_trend <= 0.0).values

    return bull_mask, bear_mask


def _calculate_oof_rank_ics(
    feature_values: np.ndarray,
    target_values: np.ndarray,
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]]
) -> np.ndarray:
    """시계열 교차검증 분할을 순회하며 검증셋(OOF) 기준 Spearman Rank IC 배열을 산출합니다."""
    fold_ics: List[float] = []

    for _, val_indices in cv_splits:
        val_x = feature_values[val_indices]
        val_y = target_values[val_indices]
        ic_result = spearman_correlation(x_values=val_x, y_values=val_y, alternative="two-sided")
        fold_ics.append(float(ic_result["correlation"]))

    return np.array(fold_ics, dtype=np.float64)


def _test_ic_significance(
    fold_ics_array: np.ndarray,
    method: str = IC_T_TEST_METHOD,
    alpha: float = IC_SIGNIFICANCE_ALPHA
) -> Tuple[float, float, bool]:
    """Fold별 IC 배열에 대해 단일표본 t-검정(H0: mean(IC) == 0.0)을 수행합니다."""
    # [설계 의도] 수리통계 모듈과의 결합도를 낮추고 모수 검정 알고리즘 변경(Student <-> Johnson)을 캡슐화함
    t_test_result = one_sample_t_test(
        sample_values=fold_ics_array,
        method=method,
        alternative="two-sided"
    )
    t_stat: float = float(t_test_result["statistic"])
    p_val: float = float(t_test_result["p_value"])
    is_significant: bool = bool(p_val < alpha)

    return t_stat, p_val, is_significant


def _check_sign_consistency(
    fold_ics_array: np.ndarray,
    min_ratio: float = MIN_OOF_SIGN_RATIO
) -> bool:
    """Walk-Forward CV 구간 동안 IC 신호의 부호가 안정적으로 유지되는지 검증합니다."""
    signs: np.ndarray = np.sign(fold_ics_array)
    positive_ratio: float = float(np.mean(signs > 0))
    negative_ratio: float = float(np.mean(signs < 0))
    max_consistency_ratio: float = max(positive_ratio, negative_ratio)

    return bool(max_consistency_ratio >= min_ratio)


def _test_regime_invariance(
    feature_values: np.ndarray,
    target_values: np.ndarray,
    bull_mask: np.ndarray,
    bear_mask: np.ndarray,
    min_observations: int = MIN_REGIME_OBSERVATIONS
) -> bool:
    """외생적 Bull/Bear 시장 국면별로 신호 방향(부호)이 역전되지 않고 유지되는지 검증합니다."""
    # [설계 의도] 특정 국면의 관측치가 유효 표본 크기 미만일 경우 표본 부족으로 인한 왜곡 판정을 방지
    if np.sum(bull_mask) < min_observations or np.sum(bear_mask) < min_observations:
        return True

    bull_ic_result = spearman_correlation(
        x_values=feature_values[bull_mask],
        y_values=target_values[bull_mask],
        alternative="two-sided"
    )
    bear_ic_result = spearman_correlation(
        x_values=feature_values[bear_mask],
        y_values=target_values[bear_mask],
        alternative="two-sided"
    )

    bull_ic: float = float(bull_ic_result["correlation"])
    bear_ic: float = float(bear_ic_result["correlation"])

    # 상승장과 하락장에서 신호 부호가 일치하며 0이 아닌 경우에만 레짐 불변으로 판정
    return bool(np.sign(bull_ic) == np.sign(bear_ic) and np.sign(bull_ic) != 0)


def _execute_pfi_gate(
    candidate_features: List[str],
    features_df: pd.DataFrame,
    target_series: pd.Series,
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]]
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """[Filter 9] 2-Pillar OOF 순열 중요도(PFI) 유의성 검정 및 역효과 피처를 배제합니다."""
    survivors: List[str] = []
    records: Dict[str, Dict[str, Any]] = {}

    if not candidate_features:
        return survivors, records

    # 1. 2-Pillar 결합 모델 기반 Walk-Forward OOF Baseline 예측 및 Fold별 원천 Rank IC 산출
    baseline_oof_preds, baseline_fold_ics = _predict_to_oof(
        features_df=features_df[candidate_features],
        target_series=target_series,
        cv_splits=cv_splits
    )

    # 2. 각 후보 피처별 순열 셔플 후 Fold별 Rank IC Drop 산출
    pfi_drops_by_feature = _compute_pfi_drops(
        candidate_features=candidate_features,
        features_df=features_df[candidate_features],
        target_series=target_series,
        cv_splits=cv_splits,
        baseline_fold_ics=baseline_fold_ics
    )

    for feature_name in candidate_features:
        fold_drops: np.ndarray = pfi_drops_by_feature[feature_name]
        mean_drop: float = float(np.mean(fold_drops))

        # 3. 대응표본 t-검정 통계량 및 p-value 유의성 산출 (H0: mean(Drop) <= 0.0)
        pfi_t_stat, pfi_p_val, is_statistically_significant = _test_pfi_significance(
            baseline_fold_ics=baseline_fold_ics,
            fold_drops=fold_drops,
            method=PFI_T_TEST_METHOD,
            alpha=PFI_SIGNIFICANCE_ALPHA
        )

        # 4. 다변량 순열 기여도 검증 (Mean Drop > 0.0 & Negative Folds <= 1)
        negative_fold_count: int = int(np.sum(fold_drops <= 0.0))
        is_positive_contribution: bool = bool(mean_drop > 0.0 and negative_fold_count <= MAX_ALLOWED_NEGATIVE_FOLDS)

        # 5. Filter 9 최종 통과 여부 판정 (실질 기여도와 통계적 유의성 p < 0.10 완전 결합)
        passed: bool = is_positive_contribution and is_statistically_significant

        records[feature_name] = {
            "pfi_mean_drop": mean_drop,
            "pfi_t_stat": pfi_t_stat,
            "pfi_p_val": pfi_p_val,
            "negative_folds": negative_fold_count,
            "f9_passed": passed
        }

        if passed:
            survivors.append(feature_name)

    return survivors, records


def _predict_to_oof(
    features_df: pd.DataFrame,
    target_series: pd.Series,
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]]
) -> Tuple[np.ndarray, np.ndarray]:
    """2-Pillar(ElasticNet + LightGBM) 모델을 순회 학습하여 OOF 예측치 및 Fold별 Rank IC를 산출합니다."""
    oof_predictions: np.ndarray = np.full(len(features_df), np.nan, dtype=np.float64)
    fold_ics: List[float] = []

    for train_indices, val_indices in cv_splits:
        train_fold_df = features_df.iloc[train_indices]
        val_fold_df = features_df.iloc[val_indices]
        y_tr = target_series.iloc[train_indices].values
        y_va = target_series.iloc[val_indices].values

        # [설계 의도] 단위 차이에 민감한 선형 모델의 왜곡을 방지하기 위해 scaler.py를 재사용하여 Fold 내 격리 표준화 수행
        train_scaled_df, val_scaled_df, _ = standard_scale(X_train=train_fold_df, X_test=val_fold_df)

        # Pillar 1: 선형 정규화 모델 (ElasticNet) - 스케일링 행렬 주입
        enet = ElasticNet(l1_ratio=0.5, alpha=0.01, random_state=RANDOM_STATE_SEED, max_iter=ELASTIC_NET_MAX_ITER)
        enet.fit(train_scaled_df.values, y_tr)
        pred_enet = enet.predict(val_scaled_df.values)

        # Pillar 2: 비선형 트리 앙상블 (LightGBM) - 단조 변환 불변성 유지 위해 원본 행렬 주입
        lgbm = lgb.LGBMRegressor(
            n_estimators=100,
            learning_rate=0.03,
            max_depth=4,
            num_leaves=15,
            random_state=RANDOM_STATE_SEED,
            verbosity=-1
        )
        lgbm.fit(train_fold_df.values, y_tr)
        pred_lgb = lgbm.predict(val_fold_df.values)

        # 2-Pillar 50:50 단순 평균 앙상블
        blended_preds: np.ndarray = 0.5 * pred_enet + 0.5 * pred_lgb
        oof_predictions[val_indices] = blended_preds

        # Fold 검증셋 기준 Rank IC 계산
        fold_ic = float(spearman_correlation(x_values=blended_preds, y_values=y_va, alternative="two-sided")["correlation"])
        fold_ics.append(fold_ic)

    return oof_predictions, np.array(fold_ics, dtype=np.float64)


def _compute_pfi_drops(
    candidate_features: List[str],
    features_df: pd.DataFrame,
    target_series: pd.Series,
    cv_splits: Sequence[Tuple[np.ndarray, np.ndarray]],
    baseline_fold_ics: np.ndarray
) -> Dict[str, np.ndarray]:
    """각 피처를 개별 셔플한 후 Fold별 OOF Rank IC 감소분(Drop)을 계산합니다."""
    pfi_drops: Dict[str, np.ndarray] = {feat: np.zeros(len(cv_splits), dtype=np.float64) for feat in candidate_features}
    rng = np.random.default_rng(RANDOM_STATE_SEED)

    for fold_idx, (train_indices, val_indices) in enumerate(cv_splits):
        train_fold_df = features_df.iloc[train_indices]
        val_fold_df = features_df.iloc[val_indices]
        y_tr = target_series.iloc[train_indices].values
        y_va = target_series.iloc[val_indices].values
        baseline_ic: float = baseline_fold_ics[fold_idx]

        # [설계 의도] Fold 격리 표준화 적용 후 스케일링 및 원본 검증 행렬 복제
        train_scaled_df, val_scaled_df, _ = standard_scale(X_train=train_fold_df, X_test=val_fold_df)
        va_scaled_orig = val_scaled_df.values.copy()
        va_raw_orig = val_fold_df.values.copy()

        # 기본 모델 적합
        enet = ElasticNet(l1_ratio=0.5, alpha=0.01, random_state=RANDOM_STATE_SEED, max_iter=ELASTIC_NET_MAX_ITER)
        enet.fit(train_scaled_df.values, y_tr)
        lgbm = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.03, max_depth=4, num_leaves=15, random_state=RANDOM_STATE_SEED, verbosity=-1)
        lgbm.fit(train_fold_df.values, y_tr)

        for feat_idx, feat_name in enumerate(candidate_features):
            perm_indices = rng.permutation(len(y_va))

            # Scaled 및 Raw 행렬 각각 동일한 순열 인덱스로 해당 피처 컬럼 셔플
            va_scaled_perm = va_scaled_orig.copy()
            va_scaled_perm[:, feat_idx] = va_scaled_orig[perm_indices, feat_idx]

            va_raw_perm = va_raw_orig.copy()
            va_raw_perm[:, feat_idx] = va_raw_orig[perm_indices, feat_idx]

            pred_perm = 0.5 * enet.predict(va_scaled_perm) + 0.5 * lgbm.predict(va_raw_perm)
            perm_ic = float(spearman_correlation(x_values=pred_perm, y_values=y_va, alternative="two-sided")["correlation"])

            # Drop = Baseline IC - Shuffled IC
            pfi_drops[feat_name][fold_idx] = baseline_ic - perm_ic

    return pfi_drops


def _execute_drift_gate(
    candidate_features: List[str],
    features_df: pd.DataFrame
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """[Filter 10] Train 시계열 50:50 동적 분할 기반 공변량 표류(PSI < 0.10 & KS p >= 0.05)를 검증합니다."""
    survivors: List[str] = []
    records: Dict[str, Dict[str, Any]] = {}

    if not candidate_features:
        return survivors, records

    # 1. Train 시계열 인덱스 기준 시간 순서 보존 동적 50:50 분할
    reference_df, target_df = _split_reference_target(features_df=features_df)

    for feature_name in candidate_features:
        ref_values = reference_df[feature_name].values
        tar_values = target_df[feature_name].values

        # 2. 모집단 안정성 지수(PSI) 산출
        psi_result = calculate_psi(
            reference_values=ref_values,
            target_values=tar_values,
            num_bins=10,
            bin_strategy="quantile"
        )
        psi_value: float = float(psi_result["psi_value"])

        # 3. 2-Sample Kolmogorov-Smirnov 비모수 형태 적합도 검정 (H0: 동일 분포)
        ks_result = two_sample_ks_test(
            sample_1_values=ref_values,
            sample_2_values=tar_values,
            method="asymptotic",
            alternative="two-sided"
        )
        ks_p_val: float = float(ks_result["p_value"])

        # 4. Filter 10 분포 안정성 평가 알고리즘 위임 판정
        passed, stability_reason = _is_distribution_stable(
            psi_value=psi_value,
            ks_p_val=ks_p_val
        )

        records[feature_name] = {
            "psi_value": psi_value,
            "ks_statistic": float(ks_result["statistic"]),
            "ks_p_val": ks_p_val,
            "stability_reason": stability_reason,
            "f10_passed": passed
        }

        if passed:
            survivors.append(feature_name)

    return survivors, records


def _split_reference_target(features_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """시간 순서를 엄격히 보존하며 Train 데이터를 50:50 Reference와 Target으로 분할합니다."""
    split_index: int = len(features_df) // 2
    reference_df: pd.DataFrame = features_df.iloc[:split_index]
    target_df: pd.DataFrame = features_df.iloc[split_index:]
    return reference_df, target_df


def _execute_parsimony_gate(
    candidate_features: List[str],
    f8_records: Dict[str, Dict[str, Any]],
    f9_records: Dict[str, Dict[str, Any]],
    f10_records: Dict[str, Dict[str, Any]],
    feature_bounds: Tuple[int, int]
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """[Filter 11] 종합 Selection Score를 산출하고 (7, 12) 제약에 맞춰 최종 정예 팩터를 확정합니다."""
    records: Dict[str, Dict[str, Any]] = {}
    min_bound, max_bound = feature_bounds

    # Filter 8~10을 정규 통과한 무결한 후보군만을 대상으로 차원 축소 집행
    eval_candidates: List[str] = candidate_features.copy()

    # 1. 다기준 가중치 결합 Selection Score 계산
    scores_dict: Dict[str, float] = _calculate_selection_scores(
        candidate_features=eval_candidates,
        f8_records=f8_records,
        f9_records=f9_records,
        f10_records=f10_records
    )

    # 2. 내림차순 정렬 후 Bounds(7, 12) 제약 슬라이싱
    final_features: List[str] = _slice_top_k(
        scores_dict=scores_dict,
        min_bound=min_bound,
        max_bound=max_bound
    )

    for feat in eval_candidates:
        records[feat] = {
            "selection_score": scores_dict.get(feat, 0.0),
            "final_selected": feat in final_features
        }

    return final_features, records


def _calculate_selection_scores(
    candidate_features: List[str],
    f8_records: Dict[str, Dict[str, Any]],
    f9_records: Dict[str, Dict[str, Any]],
    f10_records: Dict[str, Dict[str, Any]]
) -> Dict[str, float]:
    """IC(40%), PFI(40%), PSI 안정성(20%) 가중 결합 정규화 Selection Score를 계산합니다."""
    raw_ics = [abs(f8_records[f]["mean_ic"]) for f in candidate_features]
    raw_pfis = [max(0.0, f9_records[f]["pfi_mean_drop"]) for f in candidate_features]

    max_ic = max(raw_ics) if raw_ics and max(raw_ics) > 0 else 1.0
    max_pfi = max(raw_pfis) if raw_pfis and max(raw_pfis) > 0 else 1.0

    scores: Dict[str, float] = {}
    for feat in candidate_features:
        norm_ic = abs(f8_records[feat]["mean_ic"]) / max_ic
        norm_pfi = max(0.0, f9_records[feat]["pfi_mean_drop"]) / max_pfi
        psi_val = f10_records.get(feat, {}).get("psi_value", 0.0)
        norm_stability = max(0.0, 1.0 - (min(psi_val, PSI_CRITICAL_BOUND) / PSI_CRITICAL_BOUND))

        total_score = (WEIGHT_IC * norm_ic) + (WEIGHT_PFI * norm_pfi) + (WEIGHT_PSI * norm_stability)
        scores[feat] = float(total_score)

    return scores


def _slice_top_k(
    scores_dict: Dict[str, float],
    min_bound: int,
    max_bound: int
) -> List[str]:
    """점수 내림차순 정렬 후 지정된 범위 내 상위 K개 피처를 슬라이싱합니다."""
    sorted_features = sorted(scores_dict.keys(), key=lambda k: scores_dict[k], reverse=True)
    target_k = min(len(sorted_features), max_bound)
    target_k = max(target_k, min(min_bound, len(sorted_features)))
    return sorted_features[:target_k]


def _slice_partitions(
    champion_partitions: Dict[str, pd.DataFrame],
    survived_features: List[str]
) -> Dict[str, pd.DataFrame]:
    """메모리 제자리 오염(In-place Mutation)을 방지하며 4개 파티션을 정예 피처로 복제 슬라이싱합니다."""
    cloned_partitions: Dict[str, pd.DataFrame] = copy.deepcopy(champion_partitions)

    for partition_name, partition_df in cloned_partitions.items():
        if partition_name.startswith("X_"):
            cloned_partitions[partition_name] = partition_df[survived_features]

    return cloned_partitions


def _build_audit_record(
    initial_features: List[str],
    f8_records: Dict[str, Dict[str, Any]],
    f9_records: Dict[str, Dict[str, Any]],
    f10_records: Dict[str, Dict[str, Any]],
    final_features: List[str]
) -> pd.DataFrame:
    """3단계 후진 소거 전 구간의 통계량 및 탈락 사유를 포괄하는 전수 감사 DataFrame을 생성합니다."""
    audit_rows: List[Dict[str, Any]] = []

    for feature_name in initial_features:
        f8 = f8_records.get(feature_name, {})
        f9 = f9_records.get(feature_name, {})
        f10 = f10_records.get(feature_name, {})

        # 탈락 원인 특정 (Filter 8 -> Filter 9 -> Filter 10 순차 검정)
        drop_reason: str = "Survives (Champion Feature)" if feature_name in final_features else "Unknown"
        if not f8.get("f8_passed", False):
            if not f8.get("is_sign_consistent", True):
                drop_reason = f"Filter 8: OOF 부호 불안정 (일치율<{MIN_OOF_SIGN_RATIO * 100:.0f}%)"
            elif REQUIRE_REGIME_INVARIANCE and not f8.get("is_regime_invariant", True):
                drop_reason = "Filter 8: Bull/Bear 레짐 역전"
            else:
                drop_reason = f"Filter 8: IC 통계적 무의미 (p>={IC_SIGNIFICANCE_ALPHA})"
        elif not f9.get("f9_passed", False):
            if f9.get("negative_folds", 0) > MAX_ALLOWED_NEGATIVE_FOLDS:
                drop_reason = f"Filter 9: Fold 역효과 다수 발생 (Negative Drop > {MAX_ALLOWED_NEGATIVE_FOLDS})"
            elif f9.get("pfi_mean_drop", 0.0) <= 0.0:
                drop_reason = "Filter 9: 다변량 기여도 없음 (PFI Drop <= 0.0)"
            else:
                drop_reason = f"Filter 9: PFI 통계적 무의미 (p>={PFI_SIGNIFICANCE_ALPHA})"
        elif not f10.get("f10_passed", False):
            drop_reason = str(f10.get("stability_reason", "Filter 10: 공변량 표류 탈락"))

        audit_rows.append({
            "feature_name": feature_name,
            "f8_mean_ic": f8.get("mean_ic", np.nan),
            "f8_ic_p_val": f8.get("ic_p_val", np.nan),
            "f8_passed": f8.get("f8_passed", False),
            "f9_pfi_drop": f9.get("pfi_mean_drop", np.nan),
            "f9_pfi_p_val": f9.get("pfi_p_val", np.nan),
            "f9_negative_folds": f9.get("negative_folds", np.nan),
            "f9_passed": f9.get("f9_passed", False),
            "f10_psi": f10.get("psi_value", np.nan),
            "f10_ks_p_val": f10.get("ks_p_val", np.nan),
            "f10_passed": f10.get("f10_passed", False),
            "final_selected": feature_name in final_features,
            "drop_reason": drop_reason
        })

    return pd.DataFrame(audit_rows)


def _build_refinement_result(
    refined_partitions: Dict[str, pd.DataFrame],
    survived_features: List[str],
    audit_trail: pd.DataFrame,
    stage_survivor_counts: Dict[str, int]
) -> Dict[str, Any]:
    """최종 피처 정예화 산출물 및 통계 메타데이터를 정형화된 패키지로 조립합니다."""
    return {
        "refined_partitions": refined_partitions,
        "survived_features": survived_features,
        "audit_trail": audit_trail,
        "stage_survivor_counts": stage_survivor_counts
    }

def _test_pfi_significance(
    baseline_fold_ics: np.ndarray,
    fold_drops: np.ndarray,
    method: str = PFI_T_TEST_METHOD,
    alpha: float = PFI_SIGNIFICANCE_ALPHA
) -> Tuple[float, float, bool]:
    """Fold별 IC Drop에 대해 단측 대응표본 t-검정(H0: mean(Drop) <= 0.0)을 수행합니다."""
    # [설계 의도] 통계 검정 알고리즘 변경 및 통계량 추출 책임을 캡슐화하여 OCP 원칙 충족
    paired_result = paired_t_test(
        sample_a_values=baseline_fold_ics,
        sample_b_values=baseline_fold_ics - fold_drops,
        method=method,
        alternative="greater"
    )
    t_stat: float = float(paired_result["statistic"])
    p_val: float = float(paired_result["p_value"])
    is_significant: bool = bool(p_val < alpha)

    return t_stat, p_val, is_significant

def _is_distribution_stable(
    psi_value: float,
    ks_p_val: float
) -> Tuple[bool, str]:
    """PSI 효과 크기와 KS 적합도 검정을 결합하여 공변량 분포 안정성을 평가합니다.

    [설계 의도] 대규모 시계열 표본(N > 1,000)에서 발생하는 KS 검정의 대표본 과민반응을 
    효과 크기(PSI)로 통제하며, 경미한 표류 구간(0.10 <= PSI < 0.20)에 한해 KS 검정을 
    조건부 결합하여 실제 체제 붕괴가 발생한 비정상성 변수를 확실히 기각합니다.

    Args:
        psi_value: 모집단 안정성 지수(PSI) 수치.
        ks_p_val: 2-Sample Kolmogorov-Smirnov 검정 p-value.

    Returns:
        Tuple[bool, str]: 분포 안정성 통과 여부 및 상세 판정 사유.
    """
    # 1. 안정 구간 (Stable): 시계열 분포 변화가 미미하여 무조건 통과
    if psi_value < PSI_STABLE_THRESHOLD:
        return True, "Stable Distribution"

    # 2. 경미한 표류 구간 (Moderate Drift): 형태 왜곡이 유의하지 않은 경우(p >= alpha) 조건부 통과
    if psi_value < PSI_WARNING_THRESHOLD and ks_p_val >= KS_SIGNIFICANCE_ALPHA:
        return True, "Moderate Drift (KS Preserved)"

    # 3. 고위험 표류 탈락: PSI >= 0.20 체제 붕괴 위험군 차단
    if psi_value >= PSI_WARNING_THRESHOLD:
        return False, f"Filter 10: 고위험 공변량 표류 (PSI>={PSI_WARNING_THRESHOLD:.2f})"

    # 4. 형태 변형 탈락: 경미한 표류 구간 내에서 분포 형태 왜곡(p < alpha) 감지 변수 차단
    return False, f"Filter 10: 분포 형태 변형 (PSI 경고 및 KS p<{KS_SIGNIFICANCE_ALPHA:.2f})"