"""
금융 시계열 가격 데이터의 단기 조정을 감지하고 중장기 추세 방향성 및 모멘텀 강도를 수치화하는 
추세/모멘텀 피처 생성 모듈입니다. 다기간 로그 수익률, 이동평균 이격 비율(MA Ratio), 
및 위험 조정 모멘텀(Risk-Adjusted Return)을 산출하여 회귀 모델이 자산의 방향성과 과열 정도를 학습하도록 돕습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: FeatureService로부터 전달받은 원본/이전 단계 금융 시계열 데이터프레임(`df: pd.DataFrame`).
2. Schema Validation: `_validate_required_columns()`를 호출하여 연산 대상 가격 컬럼(`source_price`) 존재 여부 사전 검증.
3. Feature Computation:
   - 다기간 로그 수익률: 설정된 return_lookback_days(5, 20, 60, 120일)에 대해 $R_{t, k} = \ln(P_t) - \ln(P_{t-k})$ 연산.
   - 이동평균 이격 비율: short/long 윈도우 페어에 대해 $\text{MA}_{short}(P_t) / \text{MA}_{long}(P_t) - 1.0$ 연산.
   - 위험 조정 모멘텀: 지정된 윈도우 기간 동안의 로그 수익률을 일별 수익률의 롤링 표준편차(변동성)로 나눈 위험 조정 수익률 연산.
4. Output: 추세 및 모멘텀 파생 피처 컬럼들이 추가 결합된 데이터프레임(`pd.DataFrame`) 반환.

주요 기능:
- [Multi-Horizon Log Return] 단기(5일), 중기(20일, 60일), 장기(120일) 추세 모멘텀을 로그 수익률로 정규화 산출.
- [Moving Average Disparity] 단기/장기 이동평균선 이격 비율을 계산하여 시장의 과열 및 평균 회귀(Mean Reversion) 신호 수치화.
- [Risk-Adjusted Return] 단순 수익률을 동기간 변동성(Standard Deviation)으로 나누어 자산 상승세의 질적 우수성 측정.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 단순 이동평균 이격도(Abs Distance) vs 비율 기반 이격도(Ratio Distance):
  - 장점: 비율 기반 이격도를 사용하여 자산 가격 수준(Price Level)에 영향받지 않는 정규화된 continuous 스케일 확보.
  - 단점: 자산 가격이 장기 평균선 부근에 위치할 때 분모 근처에서 미세한 수치 변동 민감도 증가.
  - 근거: 다양한 가격대를 가진 다종 자산 통합 모델 학습 시 정규화 스케일 작용이 모델 일반화에 압도적으로 유리하므로 비율 연산을 채택함.
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd

from src.feature.tasks.abstract_feature import AbstractFeature
from src.common.exceptions import FeatureCalculationExecutionError



class TrendMomentum(AbstractFeature):
    """원시 가격 데이터를 바탕으로 다기간 수익률, 이동평균 이격도, 위험조정 모멘텀 피처를 산출하는 모듈.

    Attributes:
        task_name (str): 모듈 식별 명칭.
        source_price (str): 기준 원시 가격 컬럼명.
        return_lookback_days (List[int]): 로그 수익률 산출 주기 목록 (예: [5, 20, 60, 120]).
        moving_average_ratios (List[Dict[str, int]]): 단기/장기 이동평균 윈도우 페어 목록.
        risk_adjusted_window_days (int): 위험 조정 모멘텀 산출 윈도우 거래일 수.
    """

    def __init__(
        self,
        task_name: str,
        source_price: str,
        return_lookback_days: List[int],
        moving_average_ratios: List[Dict[str, int]],
        risk_adjusted_window_days: int
    ) -> None:
        """TrendMomentum 인스턴스를 초기화하고 생성자 인자를 멤버 변수에 바인딩합니다.

        Args:
            task_name (str): 모듈 식별 명칭 (예: "TrendMomentum").
            source_price (str): 기준 원시 가격 컬럼명 (예: "kis_kospi_daily_close").
            return_lookback_days (List[int]): 로그 수익률 주기 목록.
            moving_average_ratios (List[Dict[str, int]]): 이동평균선 페어 윈도우 설정.
            risk_adjusted_window_days (int): 위험 조정 모멘텀 윈도우 크기.
        """
        super().__init__(task_name=task_name)
        # [설계 의도] 외부 YAML 설정에서 주입된 파라미터 세트를 무상태(Stateless) 멤버 변수로 명시적 보존
        self.source_price: str = source_price
        self.return_lookback_days: List[int] = return_lookback_days
        self.moving_average_ratios: List[Dict[str, int]] = moving_average_ratios
        self.risk_adjusted_window_days: int = risk_adjusted_window_days

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """입력 데이터프레임의 모든 종가 컬럼을 기반으로 추세 및 모멘텀 파생 피처들을 일괄 산출합니다.

        Args:
            df (pd.DataFrame): 정제가 완료된 입력 시계열 데이터프레임.

        Returns:
            pd.DataFrame: 원본 컬럼 보존 및 추세/모멘텀 파생 피처들이 추가된 데이터프레임.

        Raises:
            RequiredColumnNotFoundError: 매칭되는 가격 컬럼이 데이터프레임에 존재하지 않을 때 발생.
            FeatureCalculationExecutionError: 로그 연산 중 0 이하 가격 발견, 수리적 발산 발생 시 전파.
        """
        # [설계 의도] 1단계: 패턴 매칭(_close) 또는 단일 컬럼 기반 대상 종가 컬럼 목록 동적 추출
        if self.source_price.startswith("_"):
            target_price_columns: List[str] = [
                col for col in df.columns if col.endswith(self.source_price)
            ]
        else:
            target_price_columns = [self.source_price]

        # 스키마 무결성 방어 검증 (매칭되는 가격 컬럼이 1개도 없으면 예외 사출)
        self._validate_required_columns(df=df, required_columns=target_price_columns)

        try:
            processed_dataframe: pd.DataFrame = df.copy()

            # [설계 의도] 2단계: 탐색된 모든 종가 컬럼에 대해 순차적 모멘텀 피처 일괄 사출
            for price_col in target_price_columns:
                raw_price_series: pd.Series = processed_dataframe[price_col]

                # 0 이하 결측/마스킹 수치를 결측치로 치환 후 시계열 직전 유효 가격 보간(ffill -> bfill)
                price_series: pd.Series = raw_price_series.mask(raw_price_series <= 0).ffill().bfill()

                # 시계열 전체가 0 이하이거나 유효 가격이 전혀 존재하지 않는 완전 결손 컬럼은 안전하게 스킵
                if price_series.isna().all() or (price_series <= 0).any():
                    continue

                # [설계 의도] 자산 식별 Prefix 생성 (기준 타겟 자산인 kis_kospi_daily_close는 하위 호환성을 위해 Prefix 생략)
                if price_col == "kis_kospi_daily_close":
                    prefix: str = ""
                else:
                    asset_key: str = price_col.replace("_daily_close", "").replace("_close", "")
                    prefix = f"{asset_key}_"

                log_price_series: pd.Series = np.log(price_series)

                # [설계 의도] 3단계: 다기간 로그 수익률 산출 (예: return_lag_5d, kis_nasdaq_return_lag_5d)
                for lookback_days in self.return_lookback_days:
                    feature_name: str = f"{prefix}return_lag_{lookback_days}d"
                    processed_dataframe[feature_name] = log_price_series - log_price_series.shift(lookback_days)

                # [설계 의도] 4단계: 이동평균선 이격 비율 산출 (예: ma_ratio_5_20, kis_nasdaq_ma_ratio_5_20)
                for ma_pair in self.moving_average_ratios:
                    short_days: int = ma_pair["short_window_days"]
                    long_days: int = ma_pair["long_window_days"]

                    short_ma_series: pd.Series = price_series.rolling(window=short_days).mean()
                    long_ma_series: pd.Series = price_series.rolling(window=long_days).mean()

                    ma_feature_name: str = f"{prefix}ma_ratio_{short_days}_{long_days}"
                    processed_dataframe[ma_feature_name] = (short_ma_series / long_ma_series) - 1.0

                # [설계 의도] 5단계: 위험 조정 모멘텀 산출 (예: risk_adjusted_return_20d, kis_nasdaq_risk_adjusted_return_20d)
                daily_log_return_series: pd.Series = log_price_series - log_price_series.shift(1)
                rolling_volatility_series: pd.Series = daily_log_return_series.rolling(
                    window=self.risk_adjusted_window_days
                ).std()

                period_log_return_series: pd.Series = log_price_series - log_price_series.shift(self.risk_adjusted_window_days)

                risk_adj_feature_name: str = f"{prefix}risk_adjusted_return_{self.risk_adjusted_window_days}d"
                processed_dataframe[risk_adj_feature_name] = period_log_return_series / rolling_volatility_series.replace(0, np.nan)

            return processed_dataframe

        except FeatureCalculationExecutionError as calculation_err:
            raise calculation_err
        except Exception as unexpected_err:
            raise FeatureCalculationExecutionError(
                message=f"[{self.task_name}] 추세/모멘텀 피처 연산 중 예기치 않은 시스템 예외가 발생했습니다.",
                feature_name="trend_momentum_all",
                task_name=self.task_name,
                original_exception=unexpected_err
            ) from unexpected_err