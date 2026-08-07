"""
금융 시계열 가격 데이터의 변동성(Volatility), 변동성 레짐(Regime) 전환, 
분포의 고차 모멘트(왜도 및 첨도), 정규화된 가격 위치 및 변동 폭 지표를 산출하는 리스크 분석 모듈입니다.
현재 시장의 공포/안정 국면 이행 여부와 비대칭적 하락 위험(Tail Risk)을 수치화하여
회귀 모델이 시장 변동성 레짐에 따른 예측 가중치를 조정할 수 있도록 돕습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: FeatureService로부터 전달받은 원본/이전 단계 금융 시계열 데이터프레임(`df: pd.DataFrame`).
2. Schema Validation: `_validate_required_columns()`를 호출하여 연산 대상 가격 컬럼(`source_price`) 존재 여부 사전 검증.
3. Feature Computation:
   - 롤링 역사적 변동성: 일별 로그 수익률의 롤링 표준편차($\sigma_{20d}, \sigma_{60d}$) 연산.
   - 변동성 레짐 비율: 단기 변동성(20일)을 장기 변동성(60일)으로 나눈 비율($\sigma_{20d} / \sigma_{60d}$) 연산.
   - 고차 모멘트: 최근 20일간 일별 로그 수익률의 롤링 왜도(Skewness) 및 롤링 첨도(Kurtosis) 연산.
   - 캔들/가격 위치 및 변동 폭: 롤링 20일 최고가/최저가 범위 내 현재 가격의 상대적 위치(0~1) 및 정규화된 변동 폭 산출.
4. Output: 변동성 및 위험 레짐 파생 피처 컬럼들이 추가 결합된 데이터프레임(`pd.DataFrame`) 반환.

주요 기능:
- [Rolling Historical Volatility] 다기간(20일, 60일) 일별 로그 수익률의 롤링 표준편차를 통해 시장 리스크 수치화.
- [Volatility Regime Ratio] 단기/장기 변동성 비율을 산출하여 충격 유입에 따른 공포/안정 국면 전환 포착.
- [Higher Order Moments] 롤링 왜도(Skewness) 및 첨도(Kurtosis)를 산출하여 하락 위험의 비대칭성 및 Fat-tail 위험 정량화.
- [Price Position & Range] 20일 롤링 최고/최저 범위 내 현재 가격 위치 정규화 및 변동 폭 비율 계산.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 롤링 모멘트(왜도/첨도) 산출 vs 단순 변동성 지표만 사용:
  - 장점: 단순 변동성이 제공하지 못하는 '어느 방향으로 치우쳐 폭락하는지'에 대한 비대칭적 위험 신호를 모델에 전달함.
  - 단점: 롤링 윈도우(20일) 내 샘플 수가 적은 경우 수리적 모멘트 추정치의 분산이 커질 수 있음.
  - 근거: 1달 Horizon 회귀 예측에서 극단치(Tail Risk)에 의한 오차를 줄이기 위해 고차 모멘트 피처 제공이 필수적이므로 포함함.
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd

from feature.tasks.abstract_feature import AbstractFeature
from src.common.exceptions import FeatureCalculationExecutionError


class VolatilityRisk(AbstractFeature):
    """원시 가격 데이터를 바탕으로 롤링 변동성, 레짐 비율, 왜도/첨도 및 가격 위치 피처를 산출하는 모듈.

    Attributes:
        task_name (str): 모듈 식별 명칭.
        source_price (str): 기준 원시 가격 컬럼명.
        volatility_lookback_days (List[int]): 역사적 변동성 산출 주기 목록 (예: [20, 60]).
        volatility_regime_windows (Dict[str, int]): 단기/장기 변동성 레짐 윈도우 설정.
        higher_moments_window_days (int): 고차 모멘트(왜도/첨도) 산출 윈도우 거래일 수.
        price_range_window_days (int): 가격 위치 및 변동 폭 산출 윈도우 거래일 수.
    """

    def __init__(
        self,
        task_name: str,
        source_price: str,
        volatility_lookback_days: List[int],
        volatility_regime_windows: Dict[str, int],
        higher_moments_window_days: int,
        price_range_window_days: int
    ) -> None:
        """VolatilityRisk 인스턴스를 초기화하고 생성자 인자를 멤버 변수에 바인딩합니다.

        Args:
            task_name (str): 모듈 식별 명칭 (예: "VolatilityRisk").
            source_price (str): 기준 원시 가격 컬럼명 (예: "kis_kospi_daily_close").
            volatility_lookback_days (List[int]): 변동성 주기 목록.
            volatility_regime_windows (Dict[str, int]): 레짐 윈도우 설정 (short_window_days, long_window_days).
            higher_moments_window_days (int): 고차 모멘트 윈도우 크기.
            price_range_window_days (int): 가격 범주 윈도우 크기.
        """
        super().__init__(task_name=task_name)
        # [설계 의도] 명시적 인자로 주입받아 무상태성(Stateless) 멤버 변수로 보존
        self.source_price: str = source_price
        self.volatility_lookback_days: List[int] = volatility_lookback_days
        self.volatility_regime_windows: Dict[str, int] = volatility_regime_windows
        self.higher_moments_window_days: int = higher_moments_window_days
        self.price_range_window_days: int = price_range_window_days

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """입력 데이터프레임의 원시 가격 시계열을 바탕으로 변동성 및 위험 레짐 관련 파생 피처들을 산출합니다.

        Args:
            df (pd.DataFrame): 정제가 완료된 입력 시계열 데이터프레임.

        Returns:
            pd.DataFrame: 변동성 및 위험 레짐 파생 피처들이 추가된 데이터프레임.

        Raises:
            RequiredColumnNotFoundError: source_price 컬럼이 데이터프레임에 존재하지 않을 때 발생.
            FeatureCalculationExecutionError: 수수료/로그 연산 중 0 이하 가격 발견, 수리적 발산 발생 시 전파.
        """
        # [설계 의도] 1단계: 필수 입력 컬럼 존재 여부 사전 방어 검증
        self._validate_required_columns(df=df, required_columns=[self.source_price])

        try:
            processed_dataframe: pd.DataFrame = df.copy()
            price_series: pd.Series = processed_dataframe[self.source_price]

            # [설계 의도] 2단계: 로그 변환 전 0 이하 비정상 가격 유입 검증
            if (price_series <= 0).any():
                raise FeatureCalculationExecutionError(
                    message=f"[{self.task_name}] 원시 가격 컬럼({self.source_price}) 내에 0 이하 수치가 존재하여 변동성을 연산할 수 없습니다.",
                    feature_name="volatility_risk_all",
                    task_name=self.task_name
                )

            daily_log_return_series: pd.Series = np.log(price_series) - np.log(price_series.shift(1))

            # [설계 의도] 3단계: 롤링 역사적 변동성 산출 (volatility_20d, volatility_60d)
            for window_days in self.volatility_lookback_days:
                vol_feature_name: str = f"volatility_{window_days}d"
                processed_dataframe[vol_feature_name] = daily_log_return_series.rolling(
                    window=window_days
                ).std()

            # [설계 의도] 4단계: 변동성 레짐 비율 산출 (vol_regime_ratio = short_vol / long_vol)
            short_win: int = self.volatility_regime_windows["short_window_days"]
            long_win: int = self.volatility_regime_windows["long_window_days"]

            short_vol_series: pd.Series = daily_log_return_series.rolling(window=short_win).std()
            long_vol_series: pd.Series = daily_log_return_series.rolling(window=long_win).std()

            processed_dataframe["vol_regime_ratio"] = short_vol_series / long_vol_series.replace(0, np.nan)

            # [설계 의도] 5단계: 고차 모멘트 산출 (rolling_skew_20d, rolling_kurt_20d)
            moments_win: int = self.higher_moments_window_days
            processed_dataframe[f"rolling_skew_{moments_win}d"] = daily_log_return_series.rolling(
                window=moments_win
            ).skew()
            processed_dataframe[f"rolling_kurt_{moments_win}d"] = daily_log_return_series.rolling(
                window=moments_win
            ).kurt()

            # [설계 의도] 6단계: 정규화된 가격 위치 및 변동 폭 산출 (price_position_20d, norm_atr_20d)
            range_win: int = self.price_range_window_days
            rolling_max_series: pd.Series = price_series.rolling(window=range_win).max()
            rolling_min_series: pd.Series = price_series.rolling(window=range_win).min()

            price_range_series: pd.Series = rolling_max_series - rolling_min_series

            # Position in range: (P_t - Min) / (Max - Min)
            processed_dataframe[f"price_position_{range_win}d"] = (
                price_series - rolling_min_series
            ) / price_range_series.replace(0, np.nan)

            # Normalized ATR proxy: RollingMean(Price_Range) / Price_t
            processed_dataframe[f"norm_atr_{range_win}d"] = (
                price_range_series.rolling(window=range_win).mean()
            ) / price_series.replace(0, np.nan)

            return processed_dataframe

        except FeatureCalculationExecutionError as calculation_err:
            raise calculation_err
        except Exception as unexpected_err:
            raise FeatureCalculationExecutionError(
                message=f"[{self.task_name}] 변동성/위험 피처 연산 중 예기치 않은 시스템 예외가 발생했습니다.",
                feature_name="volatility_risk_all",
                task_name=self.task_name,
                original_exception=unexpected_err
            ) from unexpected_err