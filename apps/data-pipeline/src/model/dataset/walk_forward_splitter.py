"""
[모듈 목적 및 상세 설명]
금융 시계열 파이프라인에서 Look-ahead Bias(미래 참조 편향) 및 데이터 누수(Data Leakage)를 수리적으로 완벽히 차단하며, 
머신러닝 단일 모델 하이퍼파라미터 최적화(Optuna HPO) 및 교차검증을 위해 시간 순서에 따라 동적 Expanding Window 기반의 
다중 폴드 시계열 교차검증(Walk-Forward CV)을 수행하는 WalkForwardSplitter 모듈입니다.
각 검증 폴드의 Train 구간과 Validation 구간 경계면에 20영업일(T+20) Purged Embargo Gap을 물리적으로 배치하여 
타겟 라벨 중복에 의한 미래 정보 유출 및 오버피팅을 원천 방지합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 학습용 피처 행렬(X: pd.DataFrame), 타겟 시계열(y: pd.Series), 폴드 수(n_splits), 예측 갭(forecast_horizon).
2. Window Allocation: 전체 시계열 길이와 최소 학습 비율(min_train_ratio)을 바탕으로 폴드별 Validation 윈도우 크기(val_size) 동적 연산.
3. Purged Gap Slicing: 각 Fold의 Validation 시작 지점 직전 forecast_horizon(20일) 구간을 물리적 Purged Gap으로 격리.
4. Fold Splitting:
   - split(): Scikit-Learn 표준 프로토콜에 부합하는 (train_indices, val_indices) 정수 넘파이 인덱스 제너레이터 방출.
   - split_walk_forward(): TimeSeriesOptimizer 전용 슬라이싱 데이터셋 (X_train_fold, y_train_fold, X_val_fold, y_val_fold) 제너레이터 방출.
5. Output: 폴드별 인덱스/슬라이스 제너레이터 반환 및 summarize()를 통한 구조화된 감사 대시보드 데이터프레임(pd.DataFrame) 사출.

주요 기능:
- [Data Leakage Prevention via Purged Gap] 폴드 경계면마다 20영업일 Purged Gap을 배치하여 Look-ahead Bias 수리적 차단.
- [Expanding-Window Time-Series CV] 시간 순서를 엄격히 준수하며 과거 데이터를 점진적으로 누적 학습하는 동적 윈도우 지원.
- [Dual-Mode Interface Support] Scikit-Learn 인덱스 표준(split) 및 프레임워크 전용 슬라이싱(split_walk_forward) 다형성 동시 지원.
- [Structured Audit Reporting] summarize()를 통해 각 폴드의 분할 일자, 행 규격, 갭 격리 상태를 구조화된 DataFrame으로 사출.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Expanding Window CV vs Rolling Window CV:
  - 장점: 과거 금융 시장 데이터를 지속적으로 누적 학습하여 데이터 활용도를 극대화하고 모델의 장기 모수 추정 안정성을 확보함.
  - 단점: 후반부 폴드로 갈수록 학습 샘플 수가 점진적으로 증가하여 HPO 최적화 루프의 연산 비용(소요 시간)이 증가함.
  - 근거: 거시 금융 팩터의 장기 체제(Regime) 변화를 포착하기 위해서는 단기 롤링 대비 축적된 장기 시계열 패턴 학습이 실무적으로 우수함.
"""

from typing import Any, Dict, Generator, List, Optional, Tuple
import numpy as np
import pandas as pd


class WalkForwardSplitter:
    """금융 시계열 무유출(Leakage-Free) Expanding Walk-Forward CV 분할 엔진 클래스."""

    def __init__(
        self,
        n_splits: int = 5,
        forecast_horizon: int = 20,
        min_train_ratio: float = 0.5
    ) -> None:
        """WalkForwardSplitter 인스턴스를 초기화합니다.

        Args:
            n_splits (int): 교차 검증 폴드 수 (기본값: 5).
            forecast_horizon (int): 타겟 예측 기간 및 Purged Embargo Gap 일수 (기본값: 20).
            min_train_ratio (float): 초기 첫 번째 폴드의 최소 훈련 세트 비율 (기본값: 0.5).

        Raises:
            ValueError: n_splits가 2 미만이거나 min_train_ratio가 유효 범위를 벗어날 경우 발생.
        """
        # [설계 의도] 최소 폴드 수 및 훈련 비율 파라미터 유효성 검증 (Fail-Fast)
        if n_splits < 2:
            raise ValueError(f"n_splits는 최소 2 이상이어야 합니다. (유입: {n_splits})")
        if not (0.1 <= min_train_ratio < 1.0):
            raise ValueError(f"min_train_ratio는 0.1 이상 1.0 미만이어야 합니다. (유입: {min_train_ratio})")

        self.n_splits: int = n_splits
        self.forecast_horizon: int = forecast_horizon
        self.min_train_ratio: float = min_train_ratio

    def split(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        groups: Optional[Any] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """Scikit-Learn 표준 호환 (train_indices, val_indices) 정수 인덱스 제너레이터를 사출합니다.

        Args:
            X (pd.DataFrame): 전체 학습 데이터 피처 행렬.
            y (Optional[pd.Series]): 전체 학습 데이터 타겟 벡터.
            groups (Optional[Any]): 그룹 레이블 (인터페이스 호환용, 미사용).

        Yields:
            Tuple[np.ndarray, np.ndarray]: 각 Fold별 (Train 정수 인덱스 배열, Validation 정수 인덱스 배열).

        Raises:
            ValueError: 샘플 수 부족으로 인해 Fold별 검증 세트 또는 Train 구간 구성이 불가능한 경우.
        """
        total_samples: int = len(X)
        # [설계 의도] 전체 시계열 길이 대비 검증 윈도우 크기를 균등하게 분할
        val_size: int = int((total_samples * (1.0 - self.min_train_ratio)) / self.n_splits)

        if val_size < 5:
            raise ValueError(f"샘플 수량이 부족하여 Fold별 Validation 세트를 구성할 수 없습니다. (val_size: {val_size})")

        for fold_idx in range(self.n_splits):
            # [설계 의도] 시간 흐름을 보존하며 Expanding 방식으로 Train 종단점과 Val 시작점을 순차 확장
            val_end: int = total_samples - (self.n_splits - 1 - fold_idx) * val_size
            val_start: int = val_end - val_size
            train_end: int = val_start - self.forecast_horizon

            if train_end <= 0:
                raise ValueError(f"Fold {fold_idx + 1}의 Purged Gap 적용 후 Train 샘플이 0개 이하입니다.")

            # [설계 의도] Purged Gap(20일)을 배제한 순수 훈련 및 검증 인덱스 배열 생성
            train_indices: np.ndarray = np.arange(0, train_end)
            val_indices: np.ndarray = np.arange(val_start, val_end)

            yield train_indices, val_indices

    def split_walk_forward(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> Generator[Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series], None, None]:
        """TimeSeriesOptimizer 연동을 위해 슬라이싱된 Fold 데이터셋 튜플을 순차 사출합니다.

        Args:
            X (pd.DataFrame): 전체 학습 피처 행렬.
            y (pd.Series): 전체 학습 타겟 시리즈.

        Yields:
            Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
                각 Fold별 (X_train_fold, y_train_fold, X_val_fold, y_val_fold).
        """
        # [설계 의도] split() 제너레이터의 인덱스를 기반으로 DataFrame/Series 물리 슬라이스를 생성하여 반환
        for train_indices, val_indices in self.split(X=X, y=y):
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
            X (pd.DataFrame): 요약 대상을 추출할 피처 행렬.
            y (Optional[pd.Series]): 타겟 벡터 (Optional).

        Returns:
            pd.DataFrame: 각 Fold별 시계열 분할 정보 및 샘플 비중 감사 요약표.
        """
        total_samples: int = len(X)
        val_size: int = int((total_samples * (1.0 - self.min_train_ratio)) / self.n_splits)
        records: List[Dict[str, Any]] = []

        is_datetime: bool = isinstance(X.index, pd.DatetimeIndex)

        for fold_idx in range(self.n_splits):
            val_end: int = total_samples - (self.n_splits - 1 - fold_idx) * val_size
            val_start: int = val_end - val_size
            train_end: int = val_start - self.forecast_horizon
            gap_start: int = train_end
            gap_end: int = val_start

            # [설계 의도] DatetimeIndex 존재 여부에 따른 보고서용 시계열 일자 포맷팅
            if is_datetime:
                train_range: str = f"{X.index[0].strftime('%Y-%m-%d')} ~ {X.index[train_end - 1].strftime('%Y-%m-%d')}"
                gap_range: str = f"{X.index[gap_start].strftime('%Y-%m-%d')} ~ {X.index[gap_end - 1].strftime('%Y-%m-%d')}"
                val_range: str = f"{X.index[val_start].strftime('%Y-%m-%d')} ~ {X.index[val_end - 1].strftime('%Y-%m-%d')}"
            else:
                train_range = f"Index [0 ~ {train_end - 1}]"
                gap_range = f"Index [{gap_start} ~ {gap_end - 1}]"
                val_range = f"Index [{val_start} ~ {val_end - 1}]"

            train_rows: int = train_end
            gap_rows: int = self.forecast_horizon
            val_rows: int = val_end - val_start

            records.append({
                "Fold": f"Fold {fold_idx + 1}",
                "Train 기간 (Expanding)": train_range,
                "Train 규격": f"{train_rows:,} Rows",
                "Purged Gap (20d)": gap_range,
                "Gap 규격": f"{gap_rows:,} Rows",
                "Validation 기간": val_range,
                "Val 규격": f"{val_rows:,} Rows",
                "검증 비고": f"Train {train_rows / total_samples * 100:.1f}% ➔ Val {val_rows / total_samples * 100:.1f}%"
            })

        return pd.DataFrame(records).set_index("Fold")

    def get_n_splits(
        self,
        X: Optional[Any] = None,
        y: Optional[Any] = None,
        groups: Optional[Any] = None
    ) -> int:
        """설정된 총 교차 검증 폴드 수를 반환합니다."""
        return self.n_splits