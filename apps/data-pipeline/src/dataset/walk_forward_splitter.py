from typing import Any, Dict, Generator, List, Optional, Tuple
import numpy as np
import pandas as pd

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_N_SPLITS: int = 5               # Walk-Forward 시계열 교차검증 분할 폴드 수 기본값
DEFAULT_FORECAST_HORIZON: int = 20      # 타깃 예측 기간 및 Purged Embargo Gap 일수 기본값 (20영업일)
DEFAULT_MIN_TRAIN_RATIO: float = 0.5    # 초기 첫 번째 폴드의 최소 훈련 세트 비율 기본값 (50%)
MINIMUM_VALIDATION_SAMPLES: int = 5     # 검증 세트 구성을 위해 요구되는 최소 유효 샘플 수


# ==============================================================================
# Main Class
# ==============================================================================

class WalkForwardSplitter:
    """금융 시계열 무유출(Leakage-Free) Expanding Walk-Forward 교차검증 분할기 클래스."""

    def __init__(
        self,
        n_splits: int = DEFAULT_N_SPLITS,
        forecast_horizon: int = DEFAULT_FORECAST_HORIZON,
        min_train_ratio: float = DEFAULT_MIN_TRAIN_RATIO
    ) -> None:
        """WalkForwardSplitter 인스턴스를 초기화하고 파라미터 유효성을 검증합니다.

        Args:
            n_splits: 교차 검증 폴드 수 (기본값: 5).
            forecast_horizon: 타깃 예측 기간 및 Purged Embargo Gap 일수 (기본값: 20).
            min_train_ratio: 첫 번째 폴드의 최소 훈련 세트 비율 (기본값: 0.5).

        Raises:
            ValueError: 폴드 수가 2 미만이거나 min_train_ratio가 [0.1, 1.0) 범위를 벗어날 때 발생.
        """
        # 1. 입력된 분할 파라미터가 유효한 수치 범위를 만족하는지 검증
        _validate_splitter_parameters(n_splits=n_splits, min_train_ratio=min_train_ratio)

        # 2. 검증 완료된 하이퍼파라미터 인스턴스 속성 바인딩
        self.n_splits: int = n_splits
        self.forecast_horizon: int = forecast_horizon
        self.min_train_ratio: float = min_train_ratio

    def split(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        groups: Optional[Any] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """Scikit-Learn 호환 (train_indices, val_indices) 정수 인덱스 제너레이터를 사출합니다.

        Args:
            X: 전체 학습 피처 데이터프레임.
            y: 타깃 시계열 (인터페이스 호환용, 선택).
            groups: 그룹 레이블 (인터페이스 호환용, 선택).

        Yields:
            Tuple[np.ndarray, np.ndarray]: 각 Fold별 (Train 정수 인덱스 배열, Validation 정수 인덱스 배열).

        Raises:
            ValueError: 샘플 수 부족으로 인해 검증 구간 또는 학습 구간을 구성할 수 없을 때 발생.
        """
        # 1. 전체 시계열 길이 대비 폴드별 균등 검증 윈도우 크기 산출
        total_samples: int = len(X)
        val_size: int = int((total_samples * (1.0 - self.min_train_ratio)) / self.n_splits)

        if val_size < MINIMUM_VALIDATION_SAMPLES:
            raise ValueError(f"샘플 수량이 부족하여 Fold별 Validation 세트를 구성할 수 없습니다. (val_size: {val_size})")

        # 2. 폴드 순서에 따라 Expanding 방식으로 Train 구간과 Validation 구간을 순차 확장
        for fold_index in range(self.n_splits):
            val_end: int = total_samples - (self.n_splits - 1 - fold_index) * val_size
            val_start: int = val_end - val_size
            train_end: int = val_start - self.forecast_horizon

            if train_end <= 0:
                raise ValueError(f"Fold {fold_index + 1}의 Purged Gap 적용 후 Train 샘플이 0개 이하입니다.")

            # 3. Purged Gap 구간을 배제한 순수 Train 및 Validation 넘파이 인덱스 생성
            train_indices: np.ndarray = np.arange(0, train_end)
            val_indices: np.ndarray = np.arange(val_start, val_end)

            yield train_indices, val_indices

    def split_walk_forward(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> Generator[Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series], None, None]:
        """시간 순서대로 물리 슬라이싱된 Fold 데이터셋 튜플을 순차 사출합니다.

        Args:
            X: 전체 학습 피처 행렬.
            y: 전체 학습 타깃 시리즈.

        Yields:
            Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
                각 Fold별 (X_train_fold, y_train_fold, X_val_fold, y_val_fold).
        """
        # split() 제너레이터로부터 각 Fold의 정수 인덱스 튜플 수신
        for train_indices, val_indices in self.split(X=X, y=y):
            # 정수 인덱스 기반으로 DataFrame 및 Series 물리 슬라이싱 수행 후 방출
            X_train_fold: pd.DataFrame = X.iloc[train_indices]
            y_train_fold: pd.Series = y.iloc[train_indices]
            X_val_fold: pd.DataFrame = X.iloc[val_indices]
            y_val_fold: pd.Series = y.iloc[val_indices]

            yield X_train_fold, y_train_fold, X_val_fold, y_val_fold

    def summarize(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None
    ) -> pd.DataFrame:
        """각 폴드의 시계열 구간, Purged Gap 격리 상태 및 샘플 규격을 감사 대시보드 DataFrame으로 사출합니다.

        Args:
            X: 요약 대상을 추출할 피처 행렬.
            y: 타깃 벡터 (선택).

        Returns:
            pd.DataFrame: 각 Fold별 시계열 분할 정보 및 샘플 비중 감사 요약표.
        """
        # 1. 전체 표본 크기 및 검증 윈도우 크기 산출
        total_samples: int = len(X)
        val_size: int = int((total_samples * (1.0 - self.min_train_ratio)) / self.n_splits)
        summary_records: List[Dict[str, Any]] = []
        is_datetime_index: bool = isinstance(X.index, pd.DatetimeIndex)

        # 2. 각 폴드별 경계 좌표(Train, Purged Gap, Val)를 계산하여 레코드 생성
        for fold_index in range(self.n_splits):
            val_end: int = total_samples - (self.n_splits - 1 - fold_index) * val_size
            val_start: int = val_end - val_size
            train_end: int = val_start - self.forecast_horizon

            train_rows: int = train_end
            gap_rows: int = self.forecast_horizon
            val_rows: int = val_end - val_start

            summary_records.append({
                "Fold": f"Fold {fold_index + 1}",
                "Train 기간 (Expanding)": _format_index_range(X.index, 0, train_end - 1, is_datetime_index),
                "Train 규격": f"{train_rows:,} Rows",
                "Purged Gap (20d)": _format_index_range(X.index, train_end, val_start - 1, is_datetime_index),
                "Gap 규격": f"{gap_rows:,} Rows",
                "Validation 기간": _format_index_range(X.index, val_start, val_end - 1, is_datetime_index),
                "Val 규격": f"{val_rows:,} Rows",
                "검증 비고": f"Train {train_rows / total_samples * 100:.1f}% ➔ Val {val_rows / total_samples * 100:.1f}%"
            })

        # 3. 'Fold'를 인덱스로 설정한 감사 DataFrame 사출
        return pd.DataFrame(summary_records).set_index("Fold")

    def get_n_splits(
        self,
        X: Optional[Any] = None,
        y: Optional[Any] = None,
        groups: Optional[Any] = None
    ) -> int:
        """설정된 총 교차 검증 폴드 수를 반환합니다."""
        return self.n_splits


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _validate_splitter_parameters(n_splits: int, min_train_ratio: float) -> None:
    """분할기 초기화 시 입력된 파라미터의 유효성을 검증합니다."""
    if n_splits < 2:
        raise ValueError(f"n_splits는 최소 2 이상이어야 합니다. (유입: {n_splits})")
    if not (0.1 <= min_train_ratio < 1.0):
        raise ValueError(f"min_train_ratio는 0.1 이상 1.0 미만이어야 합니다. (유입: {min_train_ratio})")


def _format_index_range(
    index: pd.Index,
    start_pos: int,
    end_pos: int,
    is_datetime: bool
) -> str:
    """인덱스 위치 범위를 일자 형식(YYYY-MM-DD) 또는 정수 위치 문자열로 포맷팅합니다."""
    if is_datetime:
        start_date_str: str = index[start_pos].strftime("%Y-%m-%d")
        end_date_str: str = index[end_pos].strftime("%Y-%m-%d")
        return f"{start_date_str} ~ {end_date_str}"
    return f"Index [{start_pos} ~ {end_pos}]"