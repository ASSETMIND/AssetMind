import time
from typing import Any, Dict, List, Tuple
import pandas as pd
from tqdm import tqdm
from src.feature.feature_service import FeatureService


def generate_domain_features(
    datasets: Dict[str, pd.DataFrame],
    feature_service: FeatureService
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """18종 데이터셋 전체에 대해 파생 피처 및 타겟 변수를 일괄 생성하고 요약 리포트를 반환합니다.

    Args:
        datasets: 18종 골드 데이터셋 딕셔너리 (Key: bucket_job_id, Value: DataFrame)
        feature_service: 피처 엔지니어링 코어 서비스 인스턴스

    Returns:
        Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
            - 파생 피처가 추가된 18종 데이터셋 딕셔너리
            - 데이터셋별 입력/출력 셰이프 및 소요 시간 요약 대시보드
    """
    engineered_datasets: Dict[str, pd.DataFrame] = {}
    summary_records: List[Dict[str, Any]] = []

    total_datasets_count: int = len(datasets)
    print("=" * 122)
    print(f" 🚀 [Batch Feature Engineering Launch] Target Datasets: {total_datasets_count} Sets")
    print("=" * 122)

    start_total_time: float = time.time()
    progress_bar = tqdm(datasets.items(), desc="Engineering Features", unit="dataset")

    for dataset_id, raw_dataframe in progress_bar:
        step_start_time: float = time.time()
        progress_bar.set_postfix_str(f"Processing: {dataset_id[:35]}...")

        # 단일 데이터셋 피처 생성 실행
        engineered_dataframe: pd.DataFrame = feature_service.execute(market_data=raw_dataframe)
        engineered_datasets[dataset_id] = engineered_dataframe

        in_rows, in_cols = raw_dataframe.shape
        out_rows, out_cols = engineered_dataframe.shape
        added_cols: int = out_cols - in_cols
        elapsed_seconds: float = time.time() - step_start_time

        summary_records.append({
            "Dataset Bucket ID": dataset_id,
            "Input Shape": f"({in_rows}, {in_cols})",
            "Output Shape": f"({out_rows}, {out_cols})",
            "Generated Features": f"+{added_cols}",
            "Target Status": "VALID (target_return_20d)" if "target_return_20d" in engineered_dataframe.columns else "MISSING",
            "Elapsed Time": f"{elapsed_seconds:.3f}s"
        })

    total_elapsed: float = time.time() - start_total_time
    summary_dataframe: pd.DataFrame = pd.DataFrame(summary_records)

    print(f"\n 📊 [Feature Engineering Report] Completed in {total_elapsed:.2f}s")
    return engineered_datasets, summary_dataframe


def report_domain_groups(
    raw_sample: pd.DataFrame,
    engineered_sample: pd.DataFrame
) -> pd.DataFrame:
    """새로 생성된 파생 피처들이 6대 도메인 그룹 규격에 부합하는지 정밀 감사 리포트를 생성합니다.

    Args:
        raw_sample: 피처 엔지니어링 이전의 원본 샘플 데이터프레임
        engineered_sample: 피처 엔지니어링이 완료된 샘플 데이터프레임

    Returns:
        pd.DataFrame: 6대 도메인 피처 그룹별 사출 현황 요약표
    """
    newly_generated_columns = [col for col in engineered_sample.columns if col not in raw_sample.columns]

    group_specifications: Dict[str, List[str]] = {
        "Target Feature": ["target_return_20d"],
        "Trend & Momentum (Multi-Asset)": ["return_lag_5d", "return_lag_20d", "return_lag_60d", "return_lag_120d", "ma_ratio_5_20", "ma_ratio_20_60", "risk_adjusted_return_20d"],
        "Volatility & Risk (Multi-Asset)": ["volatility_20d", "volatility_60d", "vol_regime_ratio", "rolling_skew_20d", "rolling_kurt_20d", "price_position_20d", "norm_atr_20d"],
        "Macro & Cross-Asset": ["us_yield_spread_20d", "korea_us_rate_diff_momentum", "us_kr_market_lag_return", "btc_equity_corr_20d"],
        "Derivatives & Volume": ["proxy_basis_rate", "futures_intraday_range", "volume_anomaly_20d", "value_anomaly_20d"],
        "Calendar & Seasonality": ["month_sin", "month_cos", "is_month_end", "is_quarter_end"]
    }

    report_records: List[Dict[str, Any]] = []

    for group_name, standard_factors in group_specifications.items():
        # 1. 해당 그룹의 표준 팩터 규격과 일치하는 사출 피처 검색
        matched_features = [
            col for col in newly_generated_columns
            if any(col == factor or col.endswith(f"_{factor}") for factor in standard_factors)
        ]
        # 2. 실제로 사출되어 활성화된 표준 팩터 목록 추출
        activated_factors = [
            factor for factor in standard_factors
            if any(feature == factor or feature.endswith(f"_{factor}") for feature in matched_features)
        ]

        total_feature_count = len(matched_features)
        standard_factor_count = len(standard_factors)
        activated_factor_count = len(activated_factors)

        report_records.append({
            "피처 그룹 (Feature Group)": group_name,
            "활성화 상태": "ENABLED" if total_feature_count > 0 else "DISABLED",
            "표준 팩터 규격": f"{activated_factor_count} / {standard_factor_count} 종",
            "총 사출 피처 수": f"{total_feature_count:,} 개",
            "표준 파생 팩터 목록": ", ".join(activated_factors) if activated_factors else "-"
        })

    return pd.DataFrame(report_records)