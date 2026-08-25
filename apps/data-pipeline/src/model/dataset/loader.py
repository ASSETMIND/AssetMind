import os
import time
from typing import Any, Dict, List, Optional, Tuple
import boto3
import joblib
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

        return X_train, y_train, X_test, y_test, X_inference

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
        Train, Test, Inference 파티션의 시계열 범위 및 기술 통계 감사 대시보드 데이터프레임을 생성합니다.

        Args:
            X_train: 학습 세트 피처 행렬
            y_train: 학습 세트 타겟 시계열
            X_test: 테스트 세트 피처 행렬
            y_test: 테스트 세트 타겟 시계열
            X_inference: 실시간 추론 세트 피처 행렬 (Optional)

        Returns:
            pd.DataFrame: 포맷팅이 완료된 파티션 메타데이터 요약표
        """
        records: List[Dict[str, Any]] = [
            {
                "파티션 (Partition)": "Train Set (개발/CV 튜닝용 80%)",
                "X Shape (행, 피처)": f"{X_train.shape}",
                "y Shape (타겟)": f"{y_train.shape}",
                "시계열 시작일": X_train.index.min().strftime("%Y-%m-%d"),
                "시계열 종료일": X_train.index.max().strftime("%Y-%m-%d"),
                "타겟 평균 (Mean)": f"{y_train.mean():.4f}",
                "타겟 표준편차 (Std)": f"{y_train.std():.4f}",
                "타겟 범위 (Min ~ Max)": f"[{y_train.min():.4f}, {y_train.max():.4f}]"
            },
            {
                "파티션 (Partition)": "Test Set (최종 실전평가용 20%)",
                "X Shape (행, 피처)": f"{X_test.shape}",
                "y Shape (타겟)": f"{y_test.shape}",
                "시계열 시작일": X_test.index.min().strftime("%Y-%m-%d"),
                "시계열 종료일": X_test.index.max().strftime("%Y-%m-%d"),
                "타겟 평균 (Mean)": f"{y_test.mean():.4f}",
                "타겟 표준편차 (Std)": f"{y_test.std():.4f}",
                "타겟 범위 (Min ~ Max)": f"[{y_test.min():.4f}, {y_test.max():.4f}]"
            }
        ]

        if X_inference is not None and not X_inference.empty:
            records.append({
                "파티션 (Partition)": "Inference Set (실시간 추론 전용 T+20)",
                "X Shape (행, 피처)": f"{X_inference.shape}",
                "y Shape (타겟)": "N/A (미래 정답 미도래)",
                "시계열 시작일": X_inference.index.min().strftime("%Y-%m-%d"),
                "시계열 종료일": X_inference.index.max().strftime("%Y-%m-%d"),
                "타겟 평균 (Mean)": "-",
                "타겟 표준편차 (Std)": "-",
                "타겟 범위 (Min ~ Max)": "-"
            })

        return pd.DataFrame(records).set_index("파티션 (Partition)")