from typing import Tuple, Optional
import pandas as pd
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler


def standard_scale(
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], StandardScaler]:
    """X_train의 평균과 표준편차를 기준으로 Z-Score 표준화(StandardScaling)를 수행합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 데이터프레임.
        X_test (Optional[pd.DataFrame]): 평가/테스트 피처 데이터프레임 (기본값: None).

    Returns:
        Tuple[pd.DataFrame, Optional[pd.DataFrame], StandardScaler]: 
            스케일링된 X_train_scaled, X_test_scaled 및 학습된 StandardScaler 객체.
    """
    scaler = StandardScaler()

    # [설계 의도] X_train 기준으로만 fit_transform을 수행하여 Look-ahead Bias 완벽 차단
    scaled_train_array = scaler.fit_transform(X_train)
    X_train_scaled = pd.DataFrame(
        scaled_train_array,
        index=X_train.index,
        columns=X_train.columns
    )

    X_test_scaled: Optional[pd.DataFrame] = None
    if X_test is not None:
        scaled_test_array = scaler.transform(X_test)
        X_test_scaled = pd.DataFrame(
            scaled_test_array,
            index=X_test.index,
            columns=X_test.columns
        )

    return X_train_scaled, X_test_scaled, scaler


def robust_scale(
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], RobustScaler]:
    """X_train의 중앙값(Median)과 사분위수 범위(IQR)를 기준으로 RobustScaling을 수행합니다.

    금융 데이터 특유의 Fat-tail(두터운 꼬리 분포) 및 잔여 극단치에 강건하게 대응합니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 데이터프레임.
        X_test (Optional[pd.DataFrame]): 평가/테스트 피처 데이터프레임 (기본값: None).

    Returns:
        Tuple[pd.DataFrame, Optional[pd.DataFrame], RobustScaler]: 
            스케일링된 X_train_scaled, X_test_scaled 및 학습된 RobustScaler 객체.
    """
    scaler = RobustScaler()

    scaled_train_array = scaler.fit_transform(X_train)
    X_train_scaled = pd.DataFrame(
        scaled_train_array,
        index=X_train.index,
        columns=X_train.columns
    )

    X_test_scaled: Optional[pd.DataFrame] = None
    if X_test is not None:
        scaled_test_array = scaler.transform(X_test)
        X_test_scaled = pd.DataFrame(
            scaled_test_array,
            index=X_test.index,
            columns=X_test.columns
        )

    return X_train_scaled, X_test_scaled, scaler


def minmax_scale(
    X_train: pd.DataFrame,
    X_test: Optional[pd.DataFrame] = None,
    feature_range: Tuple[float, float] = (-1, 1)
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], MinMaxScaler]:
    """X_train의 최소값/최대값을 기준으로 지정된 수치 범위로 Min-Max 스케일링을 수행합니다.

    LSTM 등 신경망 활성화 함수(Tanh, Sigmoid) 입력값 규격화 시 사용됩니다.

    Args:
        X_train (pd.DataFrame): 학습 피처 데이터프레임.
        X_test (Optional[pd.DataFrame]): 평가/테스트 피처 데이터프레임 (기본값: None).
        feature_range (Tuple[float, float]): 변환 수치 범위 (기본값: (-1, 1)).

    Returns:
        Tuple[pd.DataFrame, Optional[pd.DataFrame], MinMaxScaler]: 
            스케일링된 X_train_scaled, X_test_scaled 및 학습된 MinMaxScaler 객체.
    """
    scaler = MinMaxScaler(feature_range=feature_range)

    scaled_train_array = scaler.fit_transform(X_train)
    X_train_scaled = pd.DataFrame(
        scaled_train_array,
        index=X_train.index,
        columns=X_train.columns
    )

    X_test_scaled: Optional[pd.DataFrame] = None
    if X_test is not None:
        scaled_test_array = scaler.transform(X_test)
        X_test_scaled = pd.DataFrame(
            scaled_test_array,
            index=X_test.index,
            columns=X_test.columns
        )

    return X_train_scaled, X_test_scaled, scaler
