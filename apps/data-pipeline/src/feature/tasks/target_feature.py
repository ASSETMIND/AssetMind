"""
[모듈 목적 및 상세 설명]
머신러닝 및 딥러닝 회귀(Regression) 모델이 학습에 사용할 예측 정답 라벨인 
1개월 Horizon(20영업일, T+20) 연속 로그 수익률(target_return_20d)을 산출하는 타겟 변수 생성 모듈입니다.
미래 시점의 가격을 참조하기 위해 negative shift 연산을 수행하며, 시계열 가산성(Additivity)과 
정상성(Stationarity)을 보장하도록 로그 변환을 적용합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: FeatureService로부터 전달받은 원본/정제 금융 시계열 데이터프레임(`df: pd.DataFrame`).
2. Schema Validation: `_validate_required_columns()`를 구동하여 타겟 생성의 기준이 되는 원시 가격 컬럼(`source_price`) 존재 여부 검증.
3. Target Calculation: T+20 시점의 미래 가격 대비 현재 가격의 비율을 계산하고, 자연로그(ln) 함수를 적용하여 타겟 피처 산출.
   $$Y_t = \ln\left(\frac{P_{t+20}}{P_t}\right) = \ln(P_{t+20}) - \ln(P_t)$$
4. Output: 생성된 타겟 피처 컬럼(`target_name`)이 추가된 데이터프레임(`pd.DataFrame`) 반환.

주요 기능:
- [Multi-horizon Target Generation] 설정된 forecast_horizon_days(기본 20일)에 맞춰 미래 가격을 타겟 피처로 변환.
- [Mathematical Volatility Neutralization] 단순 가격 변동 폭 대신 로그 수익률을 사용하여 정규성 및 시계열 연속성 확보.
- [Defensive Value Boundary Guard] 원시 가격 데이터 내 0 이하 값 존재 시 수리적 발산(NaN/Inf) 방지를 위한 가드레일 작동 및 TargetGenerationError 전파.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Shift 기반 미래 타겟 사전 계산 vs 학습 루프 내 실시간 타겟 계산:
  - 장점: 데이터 파이프라인 단계에서 정답 라벨을 사전에 완벽히 결합하여 사출하므로, 후행 모델 학습 및 검증 루프의 연산 오버헤드를 대폭 단축함.
  - 단점: Shift 연산 특성상 데이터프레임의 최하단 N개 행(Horizon 거래일)에 타겟 결측치(NaN)가 반드시 유입됨.
  - 근거: 최하단 타겟 결측치는 모델링 직전 Train/Test Split 단계에서 제거되므로, 파이프라인 단계의 정답 라벨 사전 사출이 컴퓨팅 효율성 관점에서 월등히 우수함.
"""

import numpy as np
import pandas as pd

from src.feature.tasks.abstract_feature import AbstractFeature
from src.common.exceptions import TargetGenerationError

class TargetFeature(AbstractFeature):
    """1개월 Horizon 회귀 예측용 로그 수익률 타겟 피처를 생성하는 세부 피처 모듈.

    Attributes:
        task_name (str): 모듈 식별 명칭.
        source_price (str): 타겟 변수 산출의 기준이 되는 원시 종가 컬럼명.
        target_name (str): 최종 사출될 타겟 피처 컬럼명.
        forecast_horizon_days (int): 미래 예측 Horizon 거래일 수 (예: 20영업일).
    """

    def __init__(
        self,
        task_name: str,
        source_price: str,
        target_name: str,
        forecast_horizon_days: int
    ) -> None:
        """TargetFeature 인스턴스를 초기화하고 명시적 인자를 멤버 변수에 바인딩합니다.

        Args:
            task_name (str): 모듈 식별 명칭 (예: "TargetFeature").
            source_price (str): 기준 원시 가격 컬럼명 (예: "kis_kospi_daily_close").
            target_name (str): 사출될 타겟 피처 컬럼명 (예: "target_return_20d").
            forecast_horizon_days (int): 예측 기간 거래일 수 (예: 20).
        """
        super().__init__(task_name=task_name)
        # [설계 의도] 명시적 생성자 인자를 바인딩하여 무상태성과 런타임 검증 정합성을 확보
        self.source_price: str = source_price
        self.target_name: str = target_name
        self.forecast_horizon_days: int = forecast_horizon_days

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """입력 데이터프레임의 원시 가격 시계열을 바탕으로 미래 로그 수익률 타겟 피처를 산출합니다.

        Args:
            df (pd.DataFrame): 정제가 완료된 입력 시계열 데이터프레임.

        Returns:
            pd.DataFrame: target_name 컬럼이 추가된 데이터프레임.

        Raises:
            RequiredColumnNotFoundError: source_price 컬럼이 데이터프레임에 존재하지 않을 때 발생.
            TargetGenerationError: 가격 데이터가 0 이하이거나 로그/shift 연산 중 크래시 발생 시 전파.
        """
        # [설계 의도] 1단계: 연산 전 필수 원시 가격 컬럼 존재 여부 사전 검증
        self._validate_required_columns(df=df, required_columns=[self.source_price])

        try:
            processed_df: pd.DataFrame = df.copy()
            price_series: pd.Series = processed_df[self.source_price]

            # [설계 의도] 2단계: 로그 변환 전 0 이하 부정 정수 유입 여부 검증 (자연로그 정의역 방어)
            if (price_series <= 0).any():
                raise TargetGenerationError(
                    message=f"[{self.task_name}] 원시 가격 컬럼({self.source_price}) 내에 0 이하의 비정상 수치가 존재하여 로그 타겟을 생성할 수 없습니다.",
                    target_horizon=self.forecast_horizon_days
                )

            # [설계 의도] 3단계: Shift(-forecast_horizon_days)를 통한 미래 T+20 시점 가격 산출 및 로그 수익률 계산
            future_price_series: pd.Series = price_series.shift(-self.forecast_horizon_days)
            
            # Y_t = ln(P_{t+20}) - ln(P_t)
            target_series: pd.Series = np.log(future_price_series) - np.log(price_series)

            processed_df[self.target_name] = target_series
            return processed_df

        except TargetGenerationError as target_err:
            raise target_err
        except Exception as unexpected_err:
            raise TargetGenerationError(
                message=f"[{self.task_name}] 타겟 피처({self.target_name}) 계산 연산 중 예기치 않은 예외가 발생했습니다.",
                target_horizon=self.forecast_horizon_days,
                original_exception=unexpected_err
            ) from unexpected_err