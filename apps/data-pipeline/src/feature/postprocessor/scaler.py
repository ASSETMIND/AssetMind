from typing import Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_ROLLING_WINDOW: int = 60                           # 롤링 적응형 표준화 기본 윈도우 크기 (60영업일)
DEFAULT_ROLLING_MIN_PERIODS: int = 20                      # 롤링 통계량 산출을 위한 최소 관측치 일수 (20영업일)
DEFAULT_CLIP_BOUND: float = 3.0                            # 극단치 억제 및 외삽 방지를 위한 윈저화 클리핑 임계치 (3-sigma)
DEFAULT_MINMAX_RANGE: Tuple[float, float] = (-1.0, 1.0)    # Min-Max 스케일링 변환 기본 수치 범위


# ==============================================================================
# Public API Functions
# ==============================================================================

def rolling_scale(
    full_feature_matrix: pd.DataFrame,
    window: int = DEFAULT_ROLLING_WINDOW,
    min_periods: int = DEFAULT_ROLLING_MIN_PERIODS,
    clip_bound: float = DEFAULT_CLIP_BOUND
) -> pd.DataFrame:
    """시간순 전체 피처 시계열에 대해 롤링 적응형 표준화 및 이상치 유계화(Clipping)를 수행합니다.

    Args:
        full_feature_matrix: 시간순으로 정렬된 전체 피처 데이터프레임.
        window: 롤링 윈도우 크기 (기본값: 60영업일).
        min_periods: 통계량 계산을 위한 최소 관측치 수 (기본값: 20영업일).
        clip_bound: 이상치 클리핑 상하한선 (기본값: 3.0 -> ±3σ).

    Returns:
        pd.DataFrame: 롤링 스케일링 및 유계화가 완료된 피처 데이터프레임.
    """
    # 1. 입력 피처 행렬 공백 검사
    if full_feature_matrix.empty or full_feature_matrix.shape[1] == 0:
        return full_feature_matrix.copy()

    # 2. 롤링 윈도우 기반 평균 및 표준편차 산출 (0 분산 및 결측 보정 포함)
    rolling_mean, rolling_std = _calculate_rolling_statistics(
        full_feature_matrix=full_feature_matrix,
        window=window,
        min_periods=min_periods
    )

    # 3. 롤링 Z-Score 표준화 수행: (X - rolling_mean) / rolling_std
    scaled_matrix: pd.DataFrame = (full_feature_matrix - rolling_mean) / rolling_std

    # 4. 잔여 결측치 0.0 대치 및 극단치 유계화([-clip_bound, clip_bound]) 적용
    return scaled_matrix.fillna(0.0).clip(-clip_bound, clip_bound)


def robust_scale(
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], RobustScaler]:
    """X_train의 중앙값(Median)과 사분위수 범위(IQR)를 기준으로 RobustScaling을 수행합니다.

    Args:
        X_train: 학습 피처 데이터프레임.
        X_test: 평가/테스트 피처 데이터프레임 (기본값: None).

    Returns:
        Tuple[pd.DataFrame, Optional[pd.DataFrame], RobustScaler]:
            스케일링된 X_train, X_test 및 학습된 RobustScaler 객체.
    """
    # 1. RobustScaler 인스턴스 초기화
    scaler = RobustScaler()

    # 2. 학습 및 테스트 데이터프레임 스케일링 변환 수행
    X_train_scaled, X_test_scaled = _apply_sklearn_scaler(
        scaler=scaler,
        X_train=X_train,
        X_test=X_test
    )

    return X_train_scaled, X_test_scaled, scaler


def standard_scale(
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], StandardScaler]:
    """X_train의 평균과 표준편차를 기준으로 Z-Score 표준화(StandardScaling)를 수행합니다.

    Args:
        X_train: 학습 피처 데이터프레임.
        X_test: 평가/테스트 피처 데이터프레임 (기본값: None).

    Returns:
        Tuple[pd.DataFrame, Optional[pd.DataFrame], StandardScaler]:
            스케일링된 X_train, X_test 및 학습된 StandardScaler 객체.
    """
    # 1. StandardScaler 인스턴스 초기화
    scaler = StandardScaler()

    # 2. 학습 및 테스트 데이터프레임 스케일링 변환 수행
    X_train_scaled, X_test_scaled = _apply_sklearn_scaler(
        scaler=scaler,
        X_train=X_train,
        X_test=X_test
    )

    return X_train_scaled, X_test_scaled, scaler


def minmax_scale(
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame] = None,
    feature_range: Tuple[float, float] = DEFAULT_MINMAX_RANGE
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], MinMaxScaler]:
    """X_train의 최솟값/최댓값을 기준으로 지정된 수치 범위로 Min-Max 스케일링을 수행합니다.

    Args:
        X_train: 학습 피처 데이터프레임.
        X_test: 평가/테스트 피처 데이터프레임 (기본값: None).
        feature_range: 변환 수치 범위 (기본값: (-1.0, 1.0)).

    Returns:
        Tuple[pd.DataFrame, Optional[pd.DataFrame], MinMaxScaler]:
            스케일링된 X_train, X_test 및 학습된 MinMaxScaler 객체.
    """
    # 1. MinMaxScaler 인스턴스 초기화
    scaler = MinMaxScaler(feature_range=feature_range)

    # 2. 학습 및 테스트 데이터프레임 스케일링 변환 수행
    X_train_scaled, X_test_scaled = _apply_sklearn_scaler(
        scaler=scaler,
        X_train=X_train,
        X_test=X_test
    )

    return X_train_scaled, X_test_scaled, scaler


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _calculate_rolling_statistics(
    full_feature_matrix: pd.DataFrame,
    window: int,
    min_periods: int
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """롤링 윈도우 기준의 평균과 표준편차를 계산하고 0 분산 및 결측을 보정합니다.

    Args:
        full_feature_matrix: 대상 피처 시계열 데이터프레임.
        window: 롤링 윈도우 일수.
        min_periods: 최소 관측치 수.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 결측 및 0 분산이 보정된 (rolling_mean, rolling_std).
    """
    # 1. 롤링 윈도우 평균 및 표준편차 산출
    rolling_mean: pd.DataFrame = full_feature_matrix.rolling(
        window=window,
        min_periods=min_periods
    ).mean()
    rolling_std: pd.DataFrame = full_feature_matrix.rolling(
        window=window,
        min_periods=min_periods
    ).std()

    # 2. 표준편차 0인 구간 방어 (영분모 방지) 및 결측 정제
    clean_rolling_std: pd.DataFrame = rolling_std.replace(0.0, np.nan).fillna(1.0)
    clean_rolling_mean: pd.DataFrame = rolling_mean.bfill().fillna(0.0)

    return clean_rolling_mean, clean_rolling_std


def _apply_sklearn_scaler(
    scaler: Union[StandardScaler, RobustScaler, MinMaxScaler],
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame]
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """스케일러를 X_train에 적합(fit_transform)하고 X_test가 제공된 경우 동일 기준으로 변환(transform)합니다.

    Args:
        scaler: Scikit-Learn 스케일러 인스턴스.
        X_train: 학습 피처 데이터프레임.
        X_test: 평가/테스트 피처 데이터프레임 (선택).

    Returns:
        Tuple[pd.DataFrame, Optional[pd.DataFrame]]: 스케일링된 (X_train_scaled, X_test_scaled).
    """
    # 1. 학습 데이터가 비어있을 경우 원본 반환 (Fail-Safe)
    if X_train.empty or X_train.shape[1] == 0:
        return X_train.copy(), (X_test.copy() if X_test is not None else None)

    # 2. X_train 기준으로 fit_transform 수행하여 스케일링된 데이터프레임 생성
    scaled_train_array: np.ndarray = scaler.fit_transform(X_train)
    X_train_scaled: pd.DataFrame = pd.DataFrame(
        scaled_train_array,
        index=X_train.index,
        columns=X_train.columns
    )

    # 3. X_test가 존재하는 경우 학습된 스케일러로 변환 수행
    X_test_scaled: Optional[pd.DataFrame] = None
    if X_test is not None:
        if X_test.empty or X_test.shape[1] == 0:
            X_test_scaled = X_test.copy()
        else:
            scaled_test_array: np.ndarray = scaler.transform(X_test)
            X_test_scaled = pd.DataFrame(
                scaled_test_array,
                index=X_test.index,
                columns=X_test.columns
            )

    return X_train_scaled, X_test_scaled