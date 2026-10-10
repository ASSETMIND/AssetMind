import os
import time
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd

class ChampionDatasetLoader:
    """AssetMind 챔피언 데이터셋 로드 및 파티션 메타데이터 무결성 검증 클래스."""

    REQUIRED_PARTITION_KEYS: List[str] = ["X_train", "y_train", "X_test", "y_test"]

    @classmethod
    def load_champion_dataset(
        cls,
        dataset_path: str = "champion_dataset.pkl"
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame]:
        """
        직렬화된 챔피언 데이터셋을 로드하고 필수 파티션 키 정합성을 검증합니다.

        Args:
            dataset_path: 챔피언 데이터셋 피클 파일 경로

        Returns:
            Tuple[X_train, y_train, X_test, y_test, X_inference]: 검증 완료된 파티션 튜플

        Raises:
            FileNotFoundError: 데이터셋 아티팩트 파일이 존재하지 않는 경우
            KeyError: 필수 파티션 키가 누락된 경우
        """
        # [설계 의도] 상위 파이프라인(get_best_dataset.ipynb) 선행 실행 여부 방어 검증
        if not os.path.exists(dataset_path):
            raise FileNotFoundError(
                f"'{dataset_path}' 파일이 존재하지 않습니다. "
                "먼저 get_best_dataset.ipynb를 실행하여 챔피언 데이터셋을 생성해 주세요."
            )

        start_load_time: float = time.perf_counter()
        champion_partitions: Dict[str, Any] = joblib.load(dataset_path)
        load_elapsed_seconds: float = time.perf_counter() - start_load_time
        file_size_kb: float = os.path.getsize(dataset_path) / 1024.0

        # [설계 의도] 파티션 딕셔너리 필수 키 무결성 검증
        for key in cls.REQUIRED_PARTITION_KEYS:
            if key not in champion_partitions:
                raise KeyError(f"챔피언 데이터셋 아티팩트에 필수 파티션 '{key}'가 누락되었습니다.")

        X_train: pd.DataFrame = champion_partitions["X_train"]
        y_train: pd.Series = champion_partitions["y_train"]
        X_test: pd.DataFrame = champion_partitions["X_test"]
        y_test: pd.Series = champion_partitions["y_test"]
        X_inference: pd.DataFrame = champion_partitions.get("X_inference", pd.DataFrame())

        print("=" * 122)
        print(
            f" 🚀 [Champion Dataset Ingestion] '{dataset_path}' 로드 완료 "
            f"({load_elapsed_seconds * 1000.0:.2f} ms | 크기: {file_size_kb:.2f} KB)"
        )
        print(f" 📌 Model-Ready Feature Dimension: {len(X_train.columns)}개 정예 피처 선별 완비")
        print("=" * 122)

        # [설계 의도] 파티션별 결함 피처(NaN, Inf, Constant) 정밀 색출 및 조건부 조기 경보
        cls._alert_partition_defects(
            partitions={
                "Train Set": X_train,
                "Test Set": X_test,
                "Inference Set": X_inference
            }
        )

        return X_train, y_train, X_test, y_test, X_inference

    @staticmethod
    def _alert_partition_defects(partitions: Dict[str, pd.DataFrame]) -> None:
        """파티션별 피처 결함을 색출하여 결함이 존재하는 경우에만 실명 리포트를 출력합니다."""
        detected_defects: Dict[str, Dict[str, List[str]]] = {}

        for partition_name, feature_dataframe in partitions.items():
            if feature_dataframe is None or feature_dataframe.empty:
                continue

            partition_defect_map: Dict[str, List[str]] = {}

            # 1. 결측치(NaN) 피처 색출
            nan_columns = feature_dataframe.columns[feature_dataframe.isna().any()].tolist()
            if nan_columns:
                partition_defect_map["NaN"] = nan_columns

            # 2. 무한대(Inf) 피처 색출
            inf_columns = feature_dataframe.columns[np.isinf(feature_dataframe.to_numpy()).any(axis=0)].tolist()
            if inf_columns:
                partition_defect_map["Inf"] = inf_columns

            # 3. 고유값 1개 이하 동결(Constant) 피처 색출
            constant_columns = feature_dataframe.columns[feature_dataframe.nunique() <= 1].tolist()
            if constant_columns:
                partition_defect_map["Constant"] = constant_columns

            if partition_defect_map:
                detected_defects[partition_name] = partition_defect_map

        # 결함이 1건 이상 감지된 경우에만 경고 블록 사출
        if detected_defects:
            print(" [Data Hygiene Alert] 피처 행렬 내 무결성 결함 감지 (색출 목록)")
            for partition_name, defect_types in detected_defects.items():
                for defect_type, column_names in defect_types.items():
                    print(f" ▶ [{partition_name}] {defect_type} 결함 ({len(column_names)}개 피처):")
                    print(f"   {column_names}")

    @staticmethod
    def _inspect_feature_hygiene(feature_dataframe: pd.DataFrame) -> str:
        """피처 행렬의 결측치, 무한대, 분산 0 상수 컬럼 잔존 여부를 검사하여 요약 문자열을 반환합니다."""
        if feature_dataframe.empty:
            return f"{feature_dataframe.shape} | 데이터 없음"

        missing_count: int = int(feature_dataframe.isna().sum().sum())
        infinite_count: int = int(np.isinf(feature_dataframe.to_numpy()).sum())
        constant_count: int = int((feature_dataframe.nunique() <= 1).sum())
        total_defect_count: int = missing_count + infinite_count + constant_count

        if total_defect_count == 0:
            return f"{feature_dataframe.shape} | 무결 (결함 0건)"
        return (
            f"{feature_dataframe.shape} | 결함 {total_defect_count}건 "
            f"(NaN:{missing_count}, Inf:{infinite_count}, Const:{constant_count})"
        )

    @classmethod
    def create_partition_summary(
        cls,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_inference: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Train, Test, Inference 파티션의 시계열 무결성, 통계 모멘트 및 표류율 감사 대시보드를 생성합니다.

        Args:
            X_train: 학습 세트 피처 행렬
            y_train: 학습 세트 타겟 시계열
            X_test: 테스트 세트 피처 행렬
            y_test: 테스트 세트 타겟 시계열
            X_inference: 실시간 추론 세트 피처 행렬 (Optional)

        Returns:
            pd.DataFrame: 포맷팅이 완료된 파티션 메타데이터 요약표
        """
        train_mean: float = float(y_train.mean())
        train_standard_deviation: float = float(y_train.std())

        test_mean: float = float(y_test.mean())
        test_standard_deviation: float = float(y_test.std())

        mean_drift_ratio: float = (
            test_mean / train_mean if train_mean != 0.0 else np.nan
        )
        volatility_drift_ratio: float = (
            test_standard_deviation / train_standard_deviation
            if train_standard_deviation != 0.0
            else np.nan
        )

        records: List[Dict[str, Any]] = [
            {
                "파티션 (Partition)": "Train Set (개발/CV 튜닝용 80%)",
                "X 규격 (행, 피처) & 무결성": cls._inspect_feature_hygiene(X_train),
                "y Shape (타겟)": f"{y_train.shape}",
                "시계열 시작일": X_train.index.min().strftime("%Y-%m-%d") if hasattr(X_train.index.min(), "strftime") else str(X_train.index.min()),
                "시계열 종료일": X_train.index.max().strftime("%Y-%m-%d") if hasattr(X_train.index.max(), "strftime") else str(X_train.index.max()),
                "타겟 평균 (Mean)": f"{train_mean:.4f}",
                "타겟 표준편차 (Std)": f"{train_standard_deviation:.4f}",
                "타겟 범위 (Min ~ Max)": f"[{y_train.min():.4f}, {y_train.max():.4f}]",
                "타겟 형태 (Skew / Kurt)": f"{y_train.skew():.2f} / {y_train.kurt():.2f}",
                "양수 비율 (Pos %)": f"{(y_train > 0).mean() * 100.0:.1f}%",
                "타겟 표류율 (Target Drift)": "기준점 (Baseline)"
            },
            {
                "파티션 (Partition)": "Test Set (최종 실전평가용 20%)",
                "X 규격 (행, 피처) & 무결성": cls._inspect_feature_hygiene(X_test),
                "y Shape (타겟)": f"{y_test.shape}",
                "시계열 시작일": X_test.index.min().strftime("%Y-%m-%d") if hasattr(X_test.index.min(), "strftime") else str(X_test.index.min()),
                "시계열 종료일": X_test.index.max().strftime("%Y-%m-%d") if hasattr(X_test.index.max(), "strftime") else str(X_test.index.max()),
                "타겟 평균 (Mean)": f"{test_mean:.4f}",
                "타겟 표준편차 (Std)": f"{test_standard_deviation:.4f}",
                "타겟 범위 (Min ~ Max)": f"[{y_test.min():.4f}, {y_test.max():.4f}]",
                "타겟 형태 (Skew / Kurt)": f"{y_test.skew():.2f} / {y_test.kurt():.2f}",
                "양수 비율 (Pos %)": f"{(y_test > 0).mean() * 100.0:.1f}%",
                "타겟 표류율 (Target Drift)": f"μ: {mean_drift_ratio:.2f}x | σ: {volatility_drift_ratio:.2f}x"
            }
        ]

        if X_inference is not None and not X_inference.empty:
            records.append({
                "파티션 (Partition)": "Inference Set (실시간 추론 전용 T+20)",
                "X 규격 (행, 피처) & 무결성": cls._inspect_feature_hygiene(X_inference),
                "y Shape (타겟)": "N/A (미래 정답 미도래)",
                "시계열 시작일": X_inference.index.min().strftime("%Y-%m-%d") if hasattr(X_inference.index.min(), "strftime") else str(X_inference.index.min()),
                "시계열 종료일": X_inference.index.max().strftime("%Y-%m-%d") if hasattr(X_inference.index.max(), "strftime") else str(X_inference.index.max()),
                "타겟 평균 (Mean)": "-",
                "타겟 표준편차 (Std)": "-",
                "타겟 범위 (Min ~ Max)": "-",
                "타겟 형태 (Skew / Kurt)": "-",
                "양수 비율 (Pos %)": "-",
                "타겟 표류율 (Target Drift)": "-"
            })

        return pd.DataFrame(records).set_index("파티션 (Partition)")