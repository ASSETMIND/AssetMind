"""
학습용 피처 데이터(X_train)의 통계량(평균, 표준편차, 사분위수, 최소/최대값)만을 기준으로
피처 스케일링(Standard, Robust, MinMax)을 수행하고, 테스트 데이터(X_test)에는 동일한 스케일러 통계량을
적용(transform)하여 Look-ahead Bias(Data Leakage)를 원천 차단하는 피처 스케일링 모듈입니다.
추가로 학습된 스케일러 객체의 직렬화(pickle save/load) 유틸리티를 제공하여 실시간 추론 및 서빙 환경에서 동일 스케일 조율을 보장합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 학습용 피처 데이터프레임(`X_train: pd.DataFrame`), 선택적 평가 피처 데이터프레임(`X_test: Optional[pd.DataFrame]`).
2. Train Fitting: `X_train`에 대해서만 `fit_transform()`을 실행하여 스케일러 통계량 학습 및 변환.
3. Test Transforming: `X_test` 유입 시, 학습된 스케일러 객체의 `transform()`만 수행하여 데이터 유출 차단.
4. Output: 스케일링된 데이터프레임(`X_train_scaled`, `X_test_scaled`) 및 학습된 Scaler 객체 반환.

주요 기능:
- [Data Leakage Prevention] X_train 통계량 기반의 엄격한 fit-transform 분리를 통한 Look-ahead Bias 제거.
- [Multi-Scaling Lineup] Z-Score 표준화(Standard), 이상치 저항 스케일링(Robust), 범위 규격화(MinMax) 3종 스케일러 라인업 제공.
- [Scaler Artifact Serialization] pickle 기반 스케일러 객체 직렬화 저장/복원 유틸리티 제공.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- X_train 독점 fit-transform 적용 vs 전체 데이터셋 선제적 fit-transform:
  - 장점: 미래 시점 테스트 데이터의 분포 지식이 학습 데이터에 유출되는 현상을 100% 방지하여 평가 신뢰성 수호.
  - 단점: Train과 Test의 분포 차이가 극심한 유동성 장세에서 Test Set에 Out-of-Bound 수치가 유입될 수 있음.
  - 근거: MLOps 백테스팅 및 실시간 추론 정합성을 위해 Train-Test 통계 분리는 양보할 수 없는 대원칙이므로 X_train fit 스킴을 강제함.
"""

import pickle
from typing import Tuple, Optional, Any
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
    """X_train의 중위수(Median)와 사분위범위(IQR)를 기준으로 Robust Scaling을 수행합니다.

    금융 시계열 극단치(Outliers)에 강건한 스케일링을 제공합니다.

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


def save_scaler(scaler: Any, file_path: str) -> None:
    """학습된 스케일러 객체를 바이너리 파일(.pkl)로 직렬화하여 저장합니다.

    Args:
        scaler (Any): 학습 완료된 Scikit-Learn Scaler 객체.
        file_path (str): 저장 경로 (예: "artifacts/scaler.pkl").
    """
    with open(file_path, "wb") as file:
        pickle.dump(scaler, file)


def load_scaler(file_path: str) -> Any:
    """바이너리 파일(.pkl)로부터 스케일러 객체를 복원 로드합니다.

    Args:
        file_path (str): 저장된 스케일러 파일 경로.

    Returns:
        Any: 복원된 Scaler 객체.
    """
    with open(file_path, "rb") as file:
        return pickle.load(file)