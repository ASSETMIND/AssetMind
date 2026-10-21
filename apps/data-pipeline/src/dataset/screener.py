import copy
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.dataset.walk_forward_splitter import WalkForwardSplitter
from src.model.core.elasticnet_regressor import ElasticNetRegressor
from src.model.core.random_forest_regressor import RandomForestRegressor
from src.model.core.xgboost_regressor import XGBoostRegressor
from src.model.evaluation import metrics
from src.model.evaluation.composite_score import get_trial_score
from src.model.evaluation.criteria import Weights
from src.model.evaluation.schema import EvaluationMetric
from src.statistics.error_control.type1_error_control import control_type1_error
from src.statistics.error_control.type2_error_control import compute_type2_error
from src.statistics.non_parametric.friedman_test import friedman_test
from src.statistics.parametric.one_t_test import one_sample_t_test
from src.statistics.parametric.paired_t_test import paired_t_test
from src.statistics.parametric.two_way_anova import block_two_way_anova

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_SPLITS: int = 5                                  # Walk-Forward CV 기본 폴드 수 (5-Fold)
DEFAULT_FORECAST_HORIZON: int = 20                       # 타겟 예측 호라이즌 및 Purged Embargo Gap 일수 (20영업일)
DEFAULT_MIN_TRAIN_RATIO: float = 0.5                     # 시계열 Expanding 윈도우 최소 초기 학습 구간 비율
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05                 # 통계적 가설 검정 기본 유의수준 (alpha)
HALF_LIFE_DAYS: float = 504.0                            # 최근 시장 국면 적응을 위한 지수 감쇠 반감기 (2년 = 504영업일)
ZERO_VARIANCE_EPSILON: float = 1e-6                      # 분모 제로 나눗셈 방지 수치 안정성 임계치
NORM_MDA_CENTER: float = 0.50                            # Fold 방향성 지표 정규화 중심값 (무작위 예측선 50%)
NORM_SCALE_FACTOR: float = 0.15                          # Fold 원천 연속 지표 정규화 분모 스케일 계수
MDA_WEIGHT: float = 0.60                                 # Fold 복합 점수 내 방향성(MDA) 가중치
RANK_IC_WEIGHT: float = 0.40                             # Fold 복합 점수 내 순위상관(Rank IC) 가중치
COMPOSITE_LAYER1_WEIGHT: float = 0.60                    # 2-Layer 종합 평가 점수 내 Layer 1(ML) 가중치
COMPOSITE_LAYER2_WEIGHT: float = 0.40                    # 2-Layer 종합 평가 점수 내 Layer 2(Factor) 가중치

# [확장성 보장] 기본 모델 팩토리 레지스트리 (모델 자체 기본 파라미터 활용)
DEFAULT_MODEL_FACTORIES: Dict[str, Callable[[], Any]] = {
    "ElasticNet": lambda: ElasticNetRegressor(),
    "XGBoostRegressor": lambda: XGBoostRegressor(),
    "RandomForestRegressor": lambda: RandomForestRegressor()
}


# ==============================================================================
# Public API Functions
# ==============================================================================

def screen_single_dataset_cv(
    dataset_partitions: Dict[str, pd.DataFrame],
    splitter: Optional[WalkForwardSplitter] = None,
    model_factories: Optional[Dict[str, Callable[[], Any]]] = None
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """단일 데이터셋 파티션에 대해 Walk-Forward CV 및 주입된 모델 앙상블 평가를 집행합니다.

    Args:
        dataset_partitions: X_train, y_train 등을 포함하는 파티션 딕셔너리.
        splitter: 시계열 교차검증 분할기 (None인 경우 5-Fold 기본 분할기 생성).
        model_factories: 모델명과 생성 팩토리 딕셔너리 (None인 경우 기본 3대 모델 팩토리 주입).

    Returns:
        Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
            - summary_record: 데이터셋 5-Fold 평균 및 최고 모델 성능 요약 레코드.
            - model_cv_summaries: 개별 모델별 Fold 평균 세부 평가 결과 리스트.
            - fold_records: ANOVA 및 순위 집계를 위한 Fold별 원시 관측치 리스트.
    """
    # 1. 시계열 교차검증 분할기 인스턴스 검증 및 할당
    cv_splitter: WalkForwardSplitter = _resolve_cv_splitter(splitter=splitter)

    # 2. 평가 대상 피처 행렬 및 타깃 시계열 추출
    feature_matrix_train: pd.DataFrame = dataset_partitions["X_train"]
    target_series_train: pd.Series = dataset_partitions["y_train"]

    # 3. 모델 팩토리 주입 여부 확인 및 레지스트리 바인딩
    active_factories: Dict[str, Callable[[], Any]] = _resolve_model_factories(
        model_factories=model_factories
    )

    # 4. 모델별 5-Fold Walk-Forward 교차검증 실행 및 Fold별 성능 수집
    model_cv_summaries = _execute_model_cross_validations(
        feature_matrix=feature_matrix_train,
        target_series=target_series_train,
        cv_splitter=cv_splitter,
        model_factories=active_factories
    )

    # 5. 분산분석(ANOVA) 및 국면 안정성 평가를 위한 Fold별 메트릭 집계
    fold_records = _aggregate_raw_fold_records(
        model_cv_summaries=model_cv_summaries,
        fold_count=cv_splitter.n_splits,
        model_count=len(active_factories)
    )

    # 6. 하방 국면 방어력(Score Sharpe) 및 데이터셋 종합 요약 지표 산출
    summary_record = _construct_dataset_summary_record(
        feature_count=feature_matrix_train.shape[1],
        model_cv_summaries=model_cv_summaries,
        fold_records=fold_records
    )

    # 7. 단일 데이터셋 CV 평가 결과 3대 튜플 반환
    return summary_record, model_cv_summaries, fold_records


def batch_screen_datasets(
    model_ready_repository: Dict[str, Dict[str, pd.DataFrame]],
    splitter: Optional[WalkForwardSplitter] = None,
    model_factories: Optional[Dict[str, Callable[[], Any]]] = None,
    significance_level: float = DEFAULT_SIGNIFICANCE_LEVEL
) -> Tuple[pd.DataFrame, str, Dict[str, Any], pd.DataFrame]:
    """18종 데이터셋 저장소에 대해 5-Fold CV 벤치마크 및 4대 역할 중심 통계 게이트를 순차 집행합니다.

    Args:
        model_ready_repository: 18종 분할 데이터셋 저장소 딕셔너리.
        splitter: 시계열 교차검증 분할기 (기본값: 5-Fold, Horizon 20).
        model_factories: 확장 가능한 평가 모델 팩토리 딕셔너리 (기본값: 3대 모델 레지스트리).
        significance_level: 가설 검정 유의수준 (기본값: 0.05).

    Returns:
        Tuple[pd.DataFrame, str, Dict[str, Any], pd.DataFrame]:
            - raw_ranking_df: 4대 게이트 판정 결과가 수치형으로 집약된 랭킹 데이터프레임.
            - champion_dataset_id: 최종 선별된 1위 챔피언 데이터셋 버킷 ID.
            - champion_meta: 챔피언 데이터셋 주요 성능 메타데이터 딕셔너리.
            - block_anova_table: Filter 7-A 시장 국면 통제 분산분석표 (pd.DataFrame).
    """
    start_execution_time: float = time.time()

    # 1. 18종 데이터셋 전수 Walk-Forward CV 배치 평가 집행
    batch_records, all_fold_details = _execute_batch_dataset_evaluations(
        model_ready_repository=model_ready_repository,
        splitter=splitter,
        model_factories=model_factories
    )
    raw_ranking_df: pd.DataFrame = pd.DataFrame(batch_records)
    fold_details_df: pd.DataFrame = pd.DataFrame(all_fold_details)

    # 2. [Gate 7-A: 시장 국면 통제 옴니버스 분산분석] Fold 블록을 통제한 Two-Way ANOVA 수행
    block_anova_table, is_omnibus_passed = _gate_rcbd_omnibus(
        fold_details=fold_details_df,
        alpha=significance_level
    )

    # 3. [Gate 7-B1: 제1종 오류 제어 절대 성과 검정] 단일표본 t-검정 + Holm 보정으로 무정보 버킷 기각
    raw_ranking_df = _gate_type1_error(
        ranking_df=raw_ranking_df,
        fold_details=fold_details_df,
        alpha=significance_level
    )

    # 4. [Gate 7-B2: 제2종 오류 감사 상대 동등성 검정] 대응표본 t-검정 + 비중심 t-분포 소표본 검정력 감사
    raw_ranking_df, baseline_dataset_id = _gate_type2_error(
        ranking_df=raw_ranking_df,
        fold_details=fold_details_df,
        alpha=significance_level
    )

    # 5. [Gate 7-C: 학술 표준 비모수 순위 집계] Demšar (2006 JMLR) 기준 Fold별 가중 순위 집계
    raw_ranking_df = _gate_demsar_ranking(
        ranking_df=raw_ranking_df,
        fold_details=fold_details_df
    )

    # 6. [Gate 7-D: 표본 보존율 및 하방 안정성 타이브레이커] 윈저화 보존율 및 Score Sharpe 기반 챔피언 확정
    raw_ranking_df, champion_dataset_id, champion_meta = _gate_tie_breaker(
        ranking_df=raw_ranking_df,
        total_elapsed_seconds=time.time() - start_execution_time,
        is_omnibus_passed=is_omnibus_passed
    )

    # 7. 정렬 완료 원천 랭킹표, 챔피언 ID, 챔피언 메타, ANOVA 결과 테이블 반환
    return raw_ranking_df, champion_dataset_id, champion_meta, block_anova_table


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _resolve_cv_splitter(splitter: Optional[WalkForwardSplitter]) -> WalkForwardSplitter:
    """시계열 교차검증 분할기 주입 여부를 확인하고 기본 객체를 구성합니다."""
    # 1. 분할기 인스턴스가 주입되었는지 검증하고 미지정 시 기본 5-Fold 분할기 인스턴스화
    if splitter is not None:
        return splitter
    return WalkForwardSplitter(
        n_splits=DEFAULT_SPLITS,
        forecast_horizon=DEFAULT_FORECAST_HORIZON,
        min_train_ratio=DEFAULT_MIN_TRAIN_RATIO
    )


def _resolve_model_factories(
    model_factories: Optional[Dict[str, Callable[[], Any]]]
) -> Dict[str, Callable[[], Any]]:
    """평가 대상 모델 팩토리 레지스트리 주입 여부를 확인하고 확장 가능한 팩토리 맵을 반환합니다."""
    # 1. 외부에서 주입된 모델 팩토리가 존재할 경우 사용, 미지정 시 기본 3대 모델 레지스트리 반환
    if model_factories is not None and len(model_factories) > 0:
        return model_factories
    return DEFAULT_MODEL_FACTORIES


def _calculate_exponential_decay_weights(sample_count: int, half_life: float) -> np.ndarray:
    """최근 시장 국면 적응을 위한 반감기 기반 지수 시간 감쇠 가중치를 산출합니다."""
    # 1. 0부터 N-1까지의 시간 경과 인덱스 배열 생성
    time_indices: np.ndarray = np.arange(sample_count) - (sample_count - 1)

    # 2. 반감기(504일) 지수 함수 적용: w = exp((ln(2) / half_life) * (t - (N - 1)))
    decay_factors: np.ndarray = np.exp((np.log(2.0) / half_life) * time_indices)

    # 3. 평균 가중치가 1.0이 되도록 정규화하여 반환
    return decay_factors / np.mean(decay_factors)


def _execute_model_cross_validations(
    feature_matrix: pd.DataFrame,
    target_series: pd.Series,
    cv_splitter: WalkForwardSplitter,
    model_factories: Dict[str, Callable[[], Any]]
) -> List[Dict[str, Any]]:
    """등록된 모델군에 대해 시계열 교차검증을 수행하고 모델별 성능 통계량을 도출합니다."""
    target_std: float = float(target_series.std())
    screening_weights = Weights(
        layer_1_ml=COMPOSITE_LAYER1_WEIGHT,
        layer_2_factor=COMPOSITE_LAYER2_WEIGHT
    )
    model_cv_summaries: List[Dict[str, Any]] = []

    # 1. 주입된 각 모델 팩토리별로 5-Fold Walk-Forward 적합 및 평가 순회
    for model_name, factory in model_factories.items():
        fold_rmses: List[float] = []
        fold_maes: List[float] = []
        fold_mdas: List[float] = []
        fold_rank_ics: List[float] = []

        for X_tr_fold, y_tr_fold, X_val_fold, y_val_fold in cv_splitter.split_walk_forward(
            X=feature_matrix, y=target_series
        ):
            # 2. 시간 감쇠 가중치 산출 및 모델 인스턴스 학습
            decay_weights = _calculate_exponential_decay_weights(
                sample_count=len(X_tr_fold),
                half_life=HALF_LIFE_DAYS
            )
            model_instance = factory()
            model_instance.fit(X_train=X_tr_fold, y_train=y_tr_fold, sample_weight=decay_weights)

            # 3. OOF 검증 파티션 추론 및 4대 평가 지표 집계
            y_pred_val = model_instance.predict(X_test=X_val_fold)
            fold_rmses.append(metrics.rmse(y_true=y_val_fold, y_pred=y_pred_val))
            fold_maes.append(metrics.mae(y_true=y_val_fold, y_pred=y_pred_val))
            fold_mdas.append(metrics.mda(y_true=y_val_fold, y_pred=y_pred_val))
            fold_rank_ics.append(metrics.rank_ic(y_true=y_val_fold, y_pred=y_pred_val))

        # 4. Fold별 Rank IC의 평균 및 표준편차 기반 ICIR 산출
        mean_rank_ic: float = float(np.mean(fold_rank_ics))
        std_rank_ic: float = float(np.std(fold_rank_ics))
        calculated_icir: float = float(mean_rank_ic / (std_rank_ic + ZERO_VARIANCE_EPSILON))

        cv_metrics = {
            EvaluationMetric.RMSE: float(np.mean(fold_rmses)),
            EvaluationMetric.MAE: float(np.mean(fold_maes)),
            EvaluationMetric.MDA: float(np.mean(fold_mdas)),
            EvaluationMetric.RANK_IC: mean_rank_ic,
            EvaluationMetric.ICIR: calculated_icir,
        }

        # 5. Layer 1(ML)과 Layer 2(Factor) 결합 종합 복합 점수 도출
        composite_score = get_trial_score(
            metrics=cv_metrics,
            weights=screening_weights,
            target_std=target_std
        )

        model_cv_summaries.append({
            "model_name": model_name,
            "composite_score": composite_score,
            "RMSE": cv_metrics[EvaluationMetric.RMSE],
            "MAE": cv_metrics[EvaluationMetric.MAE],
            "MDA": cv_metrics[EvaluationMetric.MDA],
            "Rank_IC": cv_metrics[EvaluationMetric.RANK_IC],
            "fold_rmses": fold_rmses,
            "fold_maes": fold_maes,
            "fold_mdas": fold_mdas,
            "fold_rank_ics": fold_rank_ics
        })

    return model_cv_summaries


def _aggregate_raw_fold_records(
    model_cv_summaries: List[Dict[str, Any]],
    fold_count: int,
    model_count: int
) -> List[Dict[str, Any]]:
    """모델 앙상블 평균을 통해 Fold별 원시 관측치(RMSE, MDA, 복합점수)를 생성합니다."""
    fold_records: List[Dict[str, Any]] = []

    # 1. 5개 Fold 각각에 대해 등록된 모델들의 메트릭 산술평균 도출
    for fold_index in range(fold_count):
        f_rmses = [model_cv_summaries[m_idx]["fold_rmses"][fold_index] for m_idx in range(model_count)]
        f_maes = [model_cv_summaries[m_idx]["fold_maes"][fold_index] for m_idx in range(model_count)]
        f_mdas = [model_cv_summaries[m_idx]["fold_mdas"][fold_index] for m_idx in range(model_count)]
        f_rank_ics = [model_cv_summaries[m_idx]["fold_rank_ics"][fold_index] for m_idx in range(model_count)]

        mean_f_rmse: float = float(np.mean(f_rmses))
        mean_f_mae: float = float(np.mean(f_maes))
        mean_f_mda: float = float(np.mean(f_mdas))
        mean_f_ic: float = float(np.mean(f_rank_ics))

        # 2. 하드 클리핑을 배제하고 원천 연속 신호 보존형 단일 Fold 복합 점수 산출
        norm_f_mda: float = float((mean_f_mda - NORM_MDA_CENTER) / NORM_SCALE_FACTOR)
        norm_f_ic: float = float(mean_f_ic / NORM_SCALE_FACTOR)
        f_composite_score: float = float(MDA_WEIGHT * norm_f_mda + RANK_IC_WEIGHT * norm_f_ic)

        fold_records.append({
            "fold": fold_index + 1,
            "mda": mean_f_mda,
            "rmse": mean_f_rmse,
            "mae": mean_f_mae,
            "rank_ic": mean_f_ic,
            "composite_score": f_composite_score
        })

    return fold_records


def _construct_dataset_summary_record(
    feature_count: int,
    model_cv_summaries: List[Dict[str, Any]],
    fold_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """단일 데이터셋의 성능 평균, 최저점, 하방 국면 Score Sharpe를 정형 레코드로 조립합니다."""
    # 1. 모델들의 복합점수 및 주요 메트릭 평균 계산
    average_score: float = float(np.mean([m["composite_score"] for m in model_cv_summaries]))
    average_mda: float = float(np.mean([m["MDA"] for m in model_cv_summaries]))
    average_rmse: float = float(np.mean([m["RMSE"] for m in model_cv_summaries]))
    average_mae: float = float(np.mean([m["MAE"] for m in model_cv_summaries]))
    best_model = max(model_cv_summaries, key=lambda x: x["composite_score"])

    # 2. Fold별 복합점수 시퀀스로부터 최저점 및 하방 변동성 대비 Score Sharpe 산출
    fold_composite_scores = [record["composite_score"] for record in fold_records]
    min_score: float = float(np.min(fold_composite_scores))
    score_std: float = float(np.std(fold_composite_scores))
    score_sharpe: float = float(average_score / (score_std + ZERO_VARIANCE_EPSILON))

    # 3. 데이터셋 종합 성능 요약 딕셔너리 구성 및 반환
    return {
        "Selected Features": feature_count,
        "Composite Score": average_score,
        "Min Score": min_score,
        "Score Sharpe": score_sharpe,
        "Avg MDA": average_mda,
        "Avg RMSE": average_rmse,
        "Avg MAE": average_mae,
        "Best Model": best_model["model_name"],
        "Best Model Score": best_model["composite_score"],
        "Best Model MDA": best_model["MDA"]
    }


def _execute_batch_dataset_evaluations(
    model_ready_repository: Dict[str, Dict[str, pd.DataFrame]],
    splitter: Optional[WalkForwardSplitter],
    model_factories: Optional[Dict[str, Callable[[], Any]]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """18종 저장소의 모든 데이터셋에 대해 CV 스크리닝을 실행하고 메트릭 레코드를 수집합니다."""
    from tqdm.auto import tqdm

    cv_splitter = _resolve_cv_splitter(splitter=splitter)
    active_factories = _resolve_model_factories(model_factories=model_factories)
    batch_records: List[Dict[str, Any]] = []
    all_fold_details: List[Dict[str, Any]] = []

    progress_iterator = tqdm(
        model_ready_repository.items(),
        total=len(model_ready_repository),
        desc="🔍 [5-Fold CV Batch Screening]",
        unit="set"
    )

    # 1. 18개 전처리 버킷별로 CV 실행 및 결과 수집
    for bucket_job_id, dataset_partitions in progress_iterator:
        step_start_time = time.time()
        summary_record, _, fold_records = screen_single_dataset_cv(
            dataset_partitions=dataset_partitions,
            splitter=cv_splitter,
            model_factories=active_factories
        )
        elapsed_seconds: float = time.time() - step_start_time

        # 2. 버킷 ID에서 전처리 3대 요인(Impute, Detect, Refine) 명칭 추출
        impute_method, detect_method, refine_method = _parse_pipeline_metadata(bucket_job_id=bucket_job_id)

        # 3. 분산분석 및 순위 집계용 Fold 세부 데이터 적재
        for fold_record in fold_records:
            all_fold_details.append({
                "Dataset_ID": bucket_job_id,
                "Impute": impute_method,
                "Detect": detect_method,
                "Refine": refine_method,
                "Fold": fold_record["fold"],
                "MDA": fold_record["mda"],
                "RMSE": fold_record["rmse"],
                "MAE": fold_record["mae"],
                "Rank_IC": fold_record["rank_ic"],
                "Composite_Score": fold_record["composite_score"]
            })

        summary_record["Dataset Bucket ID"] = bucket_job_id
        summary_record["Impute"] = impute_method
        summary_record["Detect"] = detect_method
        summary_record["Refine"] = refine_method
        summary_record["Elapsed Time"] = f"{elapsed_seconds:.2f}s"
        batch_records.append(summary_record)

    return batch_records, all_fold_details


def _parse_pipeline_metadata(bucket_job_id: str) -> Tuple[str, str, str]:
    """버킷 식별자 문자열로부터 결측대치, 이상치감지, 정제 알고리즘 명칭을 파싱합니다."""
    # 1. 정규표현식을 통해 버킷 명칭 내 3대 전처리 파이프라인 명칭 추출
    impute_match = re.search(r"impute_([a-z_]+)_detect", bucket_job_id)
    detect_match = re.search(r"detect_([a-z_]+)_refine", bucket_job_id)
    refine_match = re.search(r"refine_([a-z_]+)", bucket_job_id)

    impute_name = impute_match.group(1) if impute_match else "unknown"
    detect_name = detect_match.group(1) if detect_match else "unknown"
    refine_name = refine_match.group(1) if refine_match else "unknown"

    return impute_name, detect_name, refine_name


def _gate_rcbd_omnibus(
    fold_details: pd.DataFrame,
    alpha: float
) -> Tuple[pd.DataFrame, bool]:
    """[Gate 7-A] 시장 국면 통제 옴니버스 분산분석 게이트 (Fold 블록 요인 통제 Two-Way ANOVA).

    목적 및 역할:
        18개 전처리 파이프라인 간의 성능 차이가 단순 표본 오차에 불과한지 여부를 총괄적으로 검증합니다.
        시장 국면(Fold)에 따른 분산을 블록 요인으로 사전에 통제한 Type-II OLS 분산분석을 집행하여,
        전처리 3대 주효과(Impute, Detect, Refine) 중 단 하나라도 통계적으로 유의미한 차이를 만들지 못할 경우
        (All p >= alpha) 미세한 소수점 점수 차이로 인한 자의적 줄세우기 및 과적합을 원천 차단합니다.

    Args:
        fold_details: Fold별 전처리 요인 및 성과 메트릭이 기록된 원시 관측치 데이터프레임.
        alpha: 옴니버스 가설 검정 유의수준 (기본값: 0.05).

    Returns:
        Tuple[pd.DataFrame, bool]:
            - anova_table: Fold 블록 요인과 전처리 요인 주효과가 분해된 Type-II 분산분석표.
            - is_treatment_significant: 전처리 주효과 옴니버스 게이트 통과 여부 (적어도 하나 p < alpha).
    """
    # 1. 90개 관측치(18 sets x 5 Folds)의 반응 변수, 블록 요인, 처리 요인 딕셔너리 패키징
    response_scores: np.ndarray = fold_details["Composite_Score"].to_numpy(dtype=np.float64)
    block_folds: np.ndarray = fold_details["Fold"].to_numpy()
    treatment_factors = {
        "Impute": fold_details["Impute"].to_numpy(),
        "Detect": fold_details["Detect"].to_numpy(),
        "Refine": fold_details["Refine"].to_numpy()
    }

    # 2. block_two_way_anova 순수 통계 모듈 호출 (RCBD Type-II OLS 집행)
    anova_result = block_two_way_anova(
        response_values=response_scores,
        block_factors=block_folds,
        treatment_factors=treatment_factors,
        method="rcbd",
        significance_level=alpha,
        anova_type=2
    )

    return anova_result["anova_table"], anova_result["is_treatment_significant"]


def _gate_type1_error(
    ranking_df: pd.DataFrame,
    fold_details: pd.DataFrame,
    alpha: float
) -> pd.DataFrame:
    """[Gate 7-B1] 제1종 오류(FWER) 제어 절대 성과 유의성 게이트 (1-Sample t-검정 + Holm 보정).

    목적 및 역할:
        각 전처리 버킷이 기록한 5-Fold 점수가 0(무정보/무수익)보다 통계적으로 유의미하게 우수한지 검증합니다.
        18개 버킷에 대해 단일표본 t-검정(H0: mean <= 0 vs H1: mean > 0)을 동시 반복 수행할 때,
        제1종 오류(False Positive, 위양성)가 약 60%(1 - 0.95^18)까지 폭발하는 FWER 팽창을 방어하기 위해
        Holm-Bonferroni 계단식 보정을 집행합니다. 이를 통해 절대적 설명력을 입증하지 못한 가짜 알파 버킷을 기각합니다.

    Args:
        ranking_df: 1차 수치 집계가 완료된 랭킹 데이터프레임.
        fold_details: Fold별 세부 관측치 데이터프레임.
        alpha: 가설군 전체에 적용할 유의수준 (기본값: 0.05).

    Returns:
        pd.DataFrame: 원시 p-value, Holm 보정 p-value 및 절대 유의성 판정 플래그가 추가된 랭킹 데이터프레임.
    """
    # 1. Fold별 점수 피벗 테이블 생성 (Index: Dataset_ID, Columns: Fold)
    fold_pivot = fold_details.pivot(index="Dataset_ID", columns="Fold", values="Composite_Score")

    # 2. 18개 각 버킷에 대해 기준 모평균 0.0 기준 우측 단측(1-Sample) t-검정 수행
    raw_p_values: List[float] = []
    bucket_ids: List[str] = ranking_df["Dataset Bucket ID"].tolist()

    for bucket_id in bucket_ids:
        comp_scores: np.ndarray = fold_pivot.loc[bucket_id].to_numpy(dtype=np.float64)
        t_result = one_sample_t_test(
            sample_values=comp_scores,
            method="student",
            alternative="greater",
            population_mean=0.0
        )
        raw_p_values.append(t_result["p_value"])

    # 3. 18회 다중검정에 따른 FWER(제1종 오류 팽창)을 제어하기 위해 Holm 보정 집행
    type1_result = control_type1_error(
        p_values=raw_p_values,
        method="holm",
        alpha=alpha
    )

    # 4. 보정 유의확률 및 절대 유의성 판정 플래그를 데이터프레임에 바인딩
    ranking_df["p-val (Abs)"] = raw_p_values
    ranking_df["p-adj (Abs)"] = type1_result["adjusted_p_values"]
    ranking_df["is_absolute_significant"] = type1_result["reject"]

    return ranking_df


def _gate_type2_error(
    ranking_df: pd.DataFrame,
    fold_details: pd.DataFrame,
    alpha: float
) -> Tuple[pd.DataFrame, str]:
    """[Gate 7-B2] 제2종 오류(위음성 위험도) 감사 상대 동등성 게이트 (대응표본 t-검정 + NCT 검정력 감사).

    목적 및 역할:
        표본 평균 1위(Baseline) 대비 각 후보 버킷의 성능 차이가 존재하는지 상대적 동등군을 판정합니다.
        소표본(N=5) 환경에서 윌콕슨 검정의 기각 불능 한계(최소 p=0.0625 >= 0.05)를 극복하고자
        연속형 수치 크기를 반영하는 대응표본 t-검정(Paired t-test)을 집행합니다.
        이때 p >= 0.05로 귀무가설(차이 없음)을 기각하지 못했을 때 발생하는 제2종 오류(False Negative, 표본 부족으로
        실제 차이를 감지하지 못한 위험)를 방지하기 위해, 비중심 t-분포(NCT)를 활용하여 사후 검정력(1 - beta)과
        제2종 오류율(beta)을 수리적으로 정량 감사(Audit)합니다.

    Args:
        ranking_df: 랭킹 데이터프레임.
        fold_details: Fold별 세부 관측치 데이터프레임.
        alpha: 상대 동등성 검정 유의수준 (기본값: 0.05).

    Returns:
        Tuple[pd.DataFrame, str]:
            - ranking_df: 상대 비교 p-value, 제2종 오류율(Beta), 검정력(Power), 동등군 플래그가 포함된 데이터프레임.
            - baseline_dataset_id: 상대 비교의 기준점이 된 최고점 버킷 ID.
    """
    # 1. 1차 정렬: 표본 평균 최고점 기준 상대 비교 Baseline 식별
    ranking_df.sort_values(
        by=["Composite Score", "Min Score", "Avg MDA"],
        ascending=[False, False, False],
        inplace=True
    )
    score_baseline_id: str = ranking_df.iloc[0]["Dataset Bucket ID"]

    # 2. Baseline의 5-Fold 점수 벡터 추출
    fold_pivot = fold_details.pivot(index="Dataset_ID", columns="Fold", values="Composite_Score")
    baseline_scores: np.ndarray = fold_pivot.loc[score_baseline_id].to_numpy(dtype=np.float64)

    rel_p_values: List[float] = []
    equivalences: List[str] = []
    beta_risks: List[float] = []
    statistical_powers: List[float] = []

    # 3. 각 버킷별로 Baseline 대비 Paired t-test 및 NCT 사후 검정력(제2종 오류) 산출
    for bucket_id in ranking_df["Dataset Bucket ID"]:
        if bucket_id == score_baseline_id:
            rel_p_values.append(1.0)
            equivalences.append("BASELINE")
            beta_risks.append(0.0)
            statistical_powers.append(1.0)
        else:
            comp_scores = fold_pivot.loc[bucket_id].to_numpy(dtype=np.float64)
            # paired_t_test 수행으로 효과 크기(Cohen's dz) 및 상대 유의확률 도출
            paired_res = paired_t_test(
                sample_a_values=baseline_scores,
                sample_b_values=comp_scores,
                method="student",
                alternative="two-sided"
            )
            p_val = float(paired_res["p_value"])
            cohen_dz = float(paired_res["cohen_dz"])

            # compute_type2_error (비중심 t-분포 적분) 수행으로 제2종 오류율(beta) 및 검정력 도출
            type2_res = compute_type2_error(
                effect_size=cohen_dz,
                sample_size=len(comp_scores),
                alternative="two-sided",
                method="nct",
                alpha=alpha
            )

            rel_p_values.append(p_val)
            beta_risks.append(type2_res["beta"])
            statistical_powers.append(type2_res["power"])
            equivalences.append("YES (p>=0.05)" if p_val >= alpha else "NO (p<0.05)")

    # 4. 상대 비교 p-value, 제2종 오류율, 통계적 동등성 플래그 바인딩
    ranking_df["p-val (vs R1)"] = rel_p_values
    ranking_df["Beta (Type-2)"] = beta_risks
    ranking_df["Power (1-Beta)"] = statistical_powers
    ranking_df["Equivalence"] = equivalences
    ranking_df["is_equivalent"] = ranking_df["Equivalence"].isin(["BASELINE", "YES (p>=0.05)"])

    return ranking_df, score_baseline_id


def _gate_demsar_ranking(
    ranking_df: pd.DataFrame,
    fold_details: pd.DataFrame
) -> pd.DataFrame:
    """[Gate 7-C] 학술 표준 비모수 순위 집계 게이트 (Iman-Davenport F-검정 기반 Demsar Mean Rank).

    목적 및 역할:
        특정 국면(Fold)에서 발생한 이상치(급락/급등)에 취약한 산술평균 점수를 전면 배제하고,
        머신러닝 벤치마크 학술 표준(Demšar, 2006 JMLR)에 따라 Fold별 비모수 순위를 집계합니다.
        일반화 오차(RMSE 순위 50%)와 방향성 예측력(MDA 순위 50%)을 결합하여 전 시계열 구간에 걸쳐
        가장 안정적으로 우수한 순위를 유지한 최상위 동등군 후보를 압축합니다.

    Args:
        ranking_df: 랭킹 데이터프레임.
        fold_details: Fold별 세부 관측치 데이터프레임.

    Returns:
        pd.DataFrame: Demsar Mean Rank 지표가 병합된 랭킹 데이터프레임.
    """
    # 1. RMSE 및 MDA 관측치에 대해 Fold(행) x Dataset(열) 2차원 피벗 행렬 구축
    rmse_pivot = fold_details.pivot(index="Fold", columns="Dataset_ID", values="RMSE")
    mda_pivot = fold_details.pivot(index="Fold", columns="Dataset_ID", values="MDA")

    # 2. friedman_test 모듈을 호출하여 Fold별 비모수 평균 순위 벡터 산출
    rmse_friedman_res = friedman_test(
        observation_matrix=rmse_pivot.to_numpy(),
        method="iman_davenport",
        higher_is_better=False
    )
    mda_friedman_res = friedman_test(
        observation_matrix=mda_pivot.to_numpy(),
        method="iman_davenport",
        higher_is_better=True
    )

    # 3. 산출된 평균 순위를 Dataset_ID 인덱스와 매핑
    rmse_mean_ranks = pd.Series(rmse_friedman_res["mean_ranks"], index=rmse_pivot.columns)
    mda_mean_ranks = pd.Series(mda_friedman_res["mean_ranks"], index=mda_pivot.columns)

    # 4. Demšar (2006) 기준 오차(RMSE 50%)와 방향성(MDA 50%) 가중 평균 순위 합성
    demsar_composite_ranks = (0.5 * rmse_mean_ranks + 0.5 * mda_mean_ranks).rename("Demsar Mean Rank")

    # 5. 랭킹 데이터프레임과 병합하여 Demsar Mean Rank 컬럼 확정
    return ranking_df.merge(demsar_composite_ranks, left_on="Dataset Bucket ID", right_index=True)


def _gate_tie_breaker(
    ranking_df: pd.DataFrame,
    total_elapsed_seconds: float,
    is_omnibus_passed: bool
) -> Tuple[pd.DataFrame, str, Dict[str, Any]]:
    """[Gate 7-D] 표본 보존율 및 하방 안정성 타이브레이커 게이트 (Winsorization 보존율 & Score Sharpe).

    목적 및 역할:
        통계적 동등 집단(Equivalence Class) 내부에서 0.001 단위의 미세한 점수 차이로 챔피언을 결정하는
        표본 과적합을 배제하고, 원시 데이터 보존율과 국면 안정성을 기준으로 최종 챔피언을 확정합니다.
        이상치를 결측 처리하여 정보를 왜곡하는 Masking 방식을 배제하고 표본 손실률이 0%인 Clipping(윈저화) 방식을
        최우선 선호하며, Fold 간 점수 표준편차 대비 성과인 Score Sharpe가 최대인 데이터셋을 1위로 선정합니다.

    Args:
        ranking_df: 랭킹 데이터프레임.
        total_elapsed_seconds: 전체 CV 스크리닝 소요 시간(초).
        is_omnibus_passed: 옴니버스 게이트 통과 여부.

    Returns:
        Tuple[pd.DataFrame, str, Dict[str, Any]]:
            - ranking_df: 타이브레이커 원칙에 따라 정렬 완료된 최종 랭킹 데이터프레임.
            - champion_dataset_id: 최종 1위 챔피언 데이터셋 ID.
            - champion_meta: 챔피언 성능 메타데이터 딕셔너리.
    """
    # 1. 윈저화(Clipping) 기반 표본 보존율 100%(데이터 손실률 0%) 여부 플래그 생성
    ranking_df["is_zero_loss"] = ranking_df["Refine"].astype(str).str.lower().str.contains("clipping")

    # 2. 객관적 정렬 기준에 따른 최종 순위 정렬
    ranking_df.sort_values(
        by=[
            "is_equivalent",
            "is_zero_loss",
            "Demsar Mean Rank",
            "Score Sharpe",
            "Avg RMSE",
            "Avg MDA"
        ],
        ascending=[False, False, True, False, True, False],
        inplace=True
    )

    # 3. 순위 인덱스 재부여 (1위부터 오름차순)
    ranking_df.reset_index(drop=True, inplace=True)
    ranking_df.index += 1
    ranking_df.index.name = "Rank"

    # 4. 최종 1위 챔피언 데이터셋 추출 및 메타데이터 딕셔너리 생성
    champion_record = ranking_df.iloc[0]
    champion_dataset_id: str = champion_record["Dataset Bucket ID"]

    champion_meta = {
        # 1. 기본 식별자 및 상태 메타데이터
        "id": champion_dataset_id,
        "dataset_id": champion_dataset_id,
        "Dataset Bucket ID": champion_dataset_id,
        "features": int(champion_record["Selected Features"]),
        "Selected Features": int(champion_record["Selected Features"]),
        "best_model": champion_record["Best Model"],
        "Best Model": champion_record["Best Model"],
        "is_omnibus_passed": is_omnibus_passed,
        "is_zero_loss": bool(champion_record["is_zero_loss"]),
        "preservation_priority": 1 if bool(champion_record["is_zero_loss"]) else 3,
        "total_elapsed": total_elapsed_seconds,

        # 2. 핵심 평가 지표 (표준 시스템 규격 및 프레젠테이션 호환 Key 전수 바인딩)
        "composite_score": float(champion_record["Composite Score"]),
        "mean_composite_score": float(champion_record["Composite Score"]),
        "Composite Score": float(champion_record["Composite Score"]),
        "min_score": float(champion_record["Min Score"]),
        "Min Score": float(champion_record["Min Score"]),
        "score_sharpe": float(champion_record["Score Sharpe"]),
        "Score Sharpe": float(champion_record["Score Sharpe"]),
        "avg_mda": float(champion_record["Avg MDA"]),
        "mean_mda": float(champion_record["Avg MDA"]),
        "Avg MDA": float(champion_record["Avg MDA"]),
        "avg_rmse": float(champion_record["Avg RMSE"]),
        "mean_rmse": float(champion_record["Avg RMSE"]),
        "Avg RMSE": float(champion_record["Avg RMSE"]),
        "avg_mae": float(champion_record["Avg MAE"]),
        "Avg MAE": float(champion_record["Avg MAE"]),
        "demsar_rank": float(champion_record["Demsar Mean Rank"]),
        "demsar_composite_rank": float(champion_record["Demsar Mean Rank"]),
        "Demsar Mean Rank": float(champion_record["Demsar Mean Rank"]),
        "Demsar Rank": float(champion_record["Demsar Mean Rank"])
    }

    return ranking_df, champion_dataset_id, champion_meta