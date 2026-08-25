"""
미국 국채 금리 스프레드, 한/미 기준금리 격차 동향, 미국 증시 대비 국내 증시의 시차 반영 갭, 
가상자산과 증시 간의 롤링 상관계수 등 거시경제(Macro) 및 교차 자산(Cross-Asset) 지표를 생성하는 모듈입니다.
거시경제 금리 환경 변화 및 글로벌 자산 간의 리드-랙(Lead-Lag) 관계와 위험 선호 심리 변화를 정량화하여
회귀 모델이 글로벌 매크로 환경 변화에 따른 자산 수익률 영향을 학습하도록 돕습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: FeatureService로부터 전달받은 원본/이전 단계 금융 시계열 데이터프레임(`df: pd.DataFrame`).
2. Schema Validation: `_validate_required_columns()`를 호출하여 매크로 및 타 자산 관련 원시 컬럼들의 존재 여부 사전 검증.
3. Feature Computation:
   - 미국 장단기 금리차 변화량: (10년물 - 2년물) 금리 스프레드를 구한 뒤 지정된 lookback_days(20일) 동안의 변화량 계산.
   - 한/미 금리차 모멘텀: (한국 기준금리 - 미국 기준금리) 격차의 지정된 window_days(20일) 동안의 변동 모멘텀 계산.
   - 미국/한국 증시 시차 갭: 미국 증시(S&P500/NASDAQ)의 T-time_lag_days(1일) 수익률과 한국 증시(KOSPI) T 시점 수익률 간의 다이버전스 연산.
   - 코인-증시 롤링 상관계수: 가상자산(BTC) 로그 수익률과 미국 증시 로그 수익률 간의 롤링 correlation_window_days(20일) 상관계수 연산.
4. Output: 거시경제 및 교차 자산 파생 피처 컬럼들이 추가 결합된 데이터프레임(`pd.DataFrame`) 반환.

주요 기능:
- [Yield Curve Spread Dynamics] 미국 국채 10년물-2년물 금리 스프레드 변동을 추적하여 글로벌 경기 변동 신호 반영.
- [Cross-Border Rate Differential] 한/미 기준금리 격차 변화 모멘텀을 통해 외국인 자금 유출입 환경 측정.
- [Inter-market Time Lag Impact] 시차로 인해 발생하는 글로벌 선도 시장(미국)과 국내 시장 간의 수익률 전달 시차 갭 수치화.
- [Risk-On/Off Sentiment Tracking] 가상자산과 주식 시장 간 롤링 상관계수를 통해 글로벌 위험 자산 선호 레짐 포착.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 거시 지표 모멘텀 변환 vs 원시 금리/지수 직접 사용:
  - 장점: 비정착성(Non-stationary)을 지닌 금리/지수 절대 수준을 변화량 및 수익률 차이로 변환하여 정착성을 확보하고 회귀 단위 왜곡 방지.
  - 단점: 주말 및 각국 휴장일 차이로 인해 금리/해외 지수 시계열에 결측이 발생할 경우 롤링 연산 차원이 일시 왜곡될 수 있음.
  - 근거: 상위 전처리 파이프라인에서 시계열 forward fill(`ffill`) 처리가 선행되므로, 정착성을 보장하는 모멘텀 변환 연산 채택이 필연적임.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd

from src.feature.tasks.abstract_feature import AbstractFeature
from src.common.exceptions import FeatureCalculationExecutionError


class MacroCrossAsset(AbstractFeature):
    """거시경제 금리 및 타 자산(미국 증시, 코인) 가격을 바탕으로 교차 자산 파생 피처를 산출하는 모듈.

    Attributes:
        task_name (str): 모듈 식별 명칭.
        us_treasury_spread (Dict[str, Any]): 미국 국채 금리 컬럼 및 윈도우 설정.
        us_kr_rate_difference (Dict[str, Any]): 한/미 기준금리 컬럼 및 윈도우 설정.
        us_kr_market_lag (Dict[str, Any]): 미국/한국 증시 컬럼 및 시차 설정.
        coin_equity_correlation (Dict[str, Any]): 가상자산/증시 컬럼 및 상관계수 윈도우 설정.
    """

    def __init__(
        self,
        task_name: str,
        us_treasury_spread: Dict[str, Any],
        us_kr_rate_difference: Dict[str, Any],
        us_kr_market_lag: Dict[str, Any],
        coin_equity_correlation: Dict[str, Any]
    ) -> None:
        """MacroCrossAsset 인스턴스를 초기화하고 생성자 인자를 멤버 변수에 바인딩합니다.

        Args:
            task_name (str): 모듈 식별 명칭 (예: "MacroCrossAsset").
            us_treasury_spread (Dict[str, Any]): 미국 국채 설정 (ten_year_yield, two_year_yield, change_lookback_days).
            us_kr_rate_difference (Dict[str, Any]): 한/미 금리 설정 (korea_base_rate, us_base_rate, momentum_window_days).
            us_kr_market_lag (Dict[str, Any]): 증시 시차 설정 (us_equity, korea_equity, time_lag_days).
            coin_equity_correlation (Dict[str, Any]): 코인 상관관계 설정 (coin_price, equity_price, correlation_window_days).
        """
        super().__init__(task_name=task_name)
        # [설계 의도] MLOps 무상태성 원칙에 따라 명시적 인자 주입을 보존하고 파라미터 세트를 보관
        self.us_treasury_spread: Dict[str, Any] = us_treasury_spread
        self.us_kr_rate_difference: Dict[str, Any] = us_kr_rate_difference
        self.us_kr_market_lag: Dict[str, Any] = us_kr_market_lag
        self.coin_equity_correlation: Dict[str, Any] = coin_equity_correlation

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """입력 데이터프레임의 거시경제 및 교차 자산 가격 시계열을 기반으로 파생 피처들을 산출합니다.

        Args:
            df (pd.DataFrame): 정제가 완료된 입력 시계열 데이터프레임.

        Returns:
            pd.DataFrame: 매크로 및 교차 자산 파생 피처들이 추가된 데이터프레임.

        Raises:
            RequiredColumnNotFoundError: 매크로 연산에 필요한 필수 컬럼이 데이터프레임에 존재하지 않을 때 발생.
            FeatureCalculationExecutionError: 금리/지수 롤링 연산 중 수리적 발산 발생 시 전파.
        """
        # [설계 의도] 1단계: 필수 매크로 및 타 자산 컬럼 스키마 유무 사전 검증
        required_cols: List[str] = [
            self.us_treasury_spread["ten_year_yield"],
            self.us_treasury_spread["two_year_yield"],
            self.us_kr_rate_difference["korea_base_rate"],
            self.us_kr_rate_difference["us_base_rate"],
            self.us_kr_market_lag["us_equity"],
            self.us_kr_market_lag["korea_equity"],
            self.coin_equity_correlation["coin_price"],
            self.coin_equity_correlation["equity_price"]
        ]
        self._validate_required_columns(df=df, required_columns=required_cols)

        try:
            processed_dataframe: pd.DataFrame = df.copy()

            # [설계 의도] 2단계: 미국 장단기 금리차(10Y - 2Y) 및 20일 변동량 산출
            us_10y: pd.Series = processed_dataframe[self.us_treasury_spread["ten_year_yield"]]
            us_2y: pd.Series = processed_dataframe[self.us_treasury_spread["two_year_yield"]]
            change_win: int = self.us_treasury_spread["change_lookback_days"]

            yield_spread_series: pd.Series = us_10y - us_2y
            processed_dataframe[f"us_yield_spread_change_{change_win}d"] = (
                yield_spread_series - yield_spread_series.shift(change_win)
            )

            # [설계 의도] 3단계: 한/미 기준금리 차이(KR - US) 및 모멘텀 산출
            kr_rate: pd.Series = processed_dataframe[self.us_kr_rate_difference["korea_base_rate"]]
            us_rate: pd.Series = processed_dataframe[self.us_kr_rate_difference["us_base_rate"]]
            mom_win: int = self.us_kr_rate_difference["momentum_window_days"]

            rate_diff_series: pd.Series = kr_rate - us_rate
            processed_dataframe["korea_us_rate_diff_momentum"] = (
                rate_diff_series - rate_diff_series.shift(mom_win)
            )

            # [설계 의도] 4단계: 미국/한국 증시 시차 갭 (T-1 미국 수익률 - T 한국 수익률) 산출
            us_eq: pd.Series = processed_dataframe[self.us_kr_market_lag["us_equity"]]
            kr_eq: pd.Series = processed_dataframe[self.us_kr_market_lag["korea_equity"]]
            lag_days: int = self.us_kr_market_lag["time_lag_days"]

            us_eq_log_return: pd.Series = np.log(us_eq) - np.log(us_eq.shift(1))
            kr_eq_log_return: pd.Series = np.log(kr_eq) - np.log(kr_eq.shift(1))

            # 미국 전일 수익률(T - lag_days) 대비 한국 당일 수익률(T) 반영 갭
            processed_dataframe["us_kr_market_lag_return"] = (
                us_eq_log_return.shift(lag_days) - kr_eq_log_return
            )

            # [설계 의도] 5단계: 가상자산-증시 롤링 상관계수 산출 (btc_equity_corr_20d)
            coin_price: pd.Series = processed_dataframe[self.coin_equity_correlation["coin_price"]]
            corr_win: int = self.coin_equity_correlation["correlation_window_days"]

            coin_log_return: pd.Series = np.log(coin_price) - np.log(coin_price.shift(1))

            processed_dataframe[f"btc_equity_corr_{corr_win}d"] = coin_log_return.rolling(
                window=corr_win
            ).corr(us_eq_log_return)

            return processed_dataframe

        except FeatureCalculationExecutionError as calculation_err:
            raise calculation_err
        except Exception as unexpected_err:
            raise FeatureCalculationExecutionError(
                message=f"[{self.task_name}] 매크로/교차 자산 피처 연산 중 예기치 않은 시스템 예외가 발생했습니다.",
                feature_name="macro_cross_asset_all",
                task_name=self.task_name,
                original_exception=unexpected_err
            ) from unexpected_err