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
    def __init__(
        self,
        task_name: str,
        source_price: str,
        target_name: str,
        forecast_horizon_days: int,
        use_adaptive_standardization: bool = True,
        regime_window_days: int = 60,
        clamp_sigma: float = 3.0
    ) -> None:
        super().__init__(task_name=task_name)
        self.source_price: str = source_price
        self.target_name: str = target_name
        self.forecast_horizon_days: int = forecast_horizon_days
        self.use_adaptive_standardization: bool = use_adaptive_standardization
        self.regime_window_days: int = regime_window_days
        self.clamp_sigma: float = clamp_sigma

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        self._validate_required_columns(df=df, required_columns=[self.source_price])

        try:
            processed_df: pd.DataFrame = df.copy()
            raw_price_series: pd.Series = processed_df[self.source_price]

            price_series: pd.Series = raw_price_series.mask(raw_price_series <= 0).ffill().bfill()

            if price_series.isna().all() or (price_series <= 0).any():
                raise TargetGenerationError(
                    message=f"[{self.task_name}] 원시 가격 컬럼({self.source_price}) 내에 유효 가격이 존재하지 않아 로그 타겟을 생성할 수 없습니다.",
                    target_horizon=self.forecast_horizon_days
                )

            # 1. 미래 T+Horizon 가격 및 원시 누적 로그 수익률 산출
            future_price_series: pd.Series = price_series.shift(-self.forecast_horizon_days)
            raw_target_series: pd.Series = np.log(future_price_series) - np.log(price_series)

            if not self.use_adaptive_standardization:
                processed_df[self.target_name] = raw_target_series
                return processed_df

            # 2. 직전 t 시점까지의 일별 로그 수익률 산출 (과거 데이터만 참조, 미래 누수 0%)
            daily_return_series: pd.Series = np.log(price_series / price_series.shift(1))

            # 3. 과거 W영업일 일별 평균 및 표준편차 롤링 추정
            rolling_daily_mean: pd.Series = daily_return_series.rolling(
                window=self.regime_window_days, min_periods=20
            ).mean()
            rolling_daily_std: pd.Series = daily_return_series.rolling(
                window=self.regime_window_days, min_periods=20
            ).std()

            # 4. 예측 Horizon 단위 스케일링
            expected_drift_horizon: pd.Series = rolling_daily_mean * float(self.forecast_horizon_days)
            expected_vol_horizon: pd.Series = rolling_daily_std * np.sqrt(float(self.forecast_horizon_days))
            expected_vol_horizon = expected_vol_horizon.replace(0, np.nan).bfill()

            # 5. 국면 적응형 Z-Score 표준화 및 극단치 유계화 (±clamp_sigma)
            standardized_target: pd.Series = (raw_target_series - expected_drift_horizon) / expected_vol_horizon
            clamped_target: pd.Series = standardized_target.clip(
                lower=-self.clamp_sigma, upper=self.clamp_sigma
            )

            processed_df[self.target_name] = clamped_target
            return processed_df

        except TargetGenerationError as target_err:
            raise target_err
        except Exception as unexpected_err:
            raise TargetGenerationError(
                message=f"[{self.task_name}] 타겟 피처({self.target_name}) 계산 연산 중 예기치 않은 예외가 발생했습니다.",
                target_horizon=self.forecast_horizon_days,
                original_exception=unexpected_err
            ) from unexpected_err