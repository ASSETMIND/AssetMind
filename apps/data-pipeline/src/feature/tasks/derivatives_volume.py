"""
선물 가격 및 현물 종가 간의 추정 괴리율(Basis Proxy), 선물 장중 변동 폭(Futures Intraday Range),
그리고 주식 거래량 및 가상자산 거래대금의 이상 유입 비율(Volume/Value Anomaly) 지표를 산출하는 모듈입니다.
기관 및 대형 주체들의 파생상품 수급 신호와 시장 거래 자금의 급증 이상 징후를 정량화하여
회귀 모델이 대형 수급 이탈/유입 및 거래량 분출에 따른 1달 Horizon 수익률 변화를 학습하도록 돕습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: FeatureService로부터 전달받은 원본/이전 단계 금융 시계열 데이터프레임(`df: pd.DataFrame`).
2. Schema Validation: `_validate_required_columns()`를 호출하여 선물/현물 가격, 고가/저가/시가, 주식 거래량 및 코인 거래대금 컬럼 존재 여부 사전 검증.
3. Feature Computation:
   - 선물-현물 추정 괴리율: proxy_basis_rate = (futures_price / spot_price) - 1.0 연산.
   - 선물 장중 변동 폭: futures_intraday_range = (high_price - low_price) / open_price 연산.
   - 거래량/거래대금 이상치: 주식 거래량 및 코인 거래대금 각각에 대해 Anomaly Ratio = Value / MA20(Value) 연산.
4. Output: 파생상품 수급 및 거래량/거래대금 이상치 파생 피처 컬럼들이 추가 결합된 데이터프레임(`pd.DataFrame`) 반환.

주요 기능:
- [Futures Basis Proxy] 선물 가격과 현물 종가 간의 괴리율을 계산하여 파생상품 시장의 선행 수급 심리 수치화.
- [Futures Intraday Volatility Range] 선물 시장의 당일 고가-저가 변동 폭을 시가 대비 비율로 산출하여 파생 시장의 위험 회귀 동향 포착.
- [Volume & Value Anomaly Ratio] 주식 거래량 및 코인 거래대금의 20일 이동평균 대비 당일 비율을 산출하여 자금 쏠림 분출 포착.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 파생상품 괴리율 및 거래량 비율 정규화 vs 절대 거래량/가격 차이 직접 사용:
  - 장점: 자산 가격 수준이나 절대 거래량 스케일 차이에 영향을 받지 않는 정규화된(Ratio-based) continuous 스케일 확보.
  - 단점: 거래량이 거의 없는 저유동성 장세에서 이동평균 분모가 극소화될 때 이상 비율 수치가 과도하게 스파이크될 수 있음.
  - 근거: 회귀 모델의 안정적 학습을 위해 비율 정규화 방식을 적용하되, 분모 0 보완 처리(`replace(0, np.nan)`)로 수리적 발산 위험을 차단함.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd

from src.feature.tasks.abstract_feature import AbstractFeature
from src.common.exceptions import FeatureCalculationExecutionError


class DerivativesVolume(AbstractFeature):
    """선물 가격 및 현물 종가, 거래량/거래대금 시계열을 바탕으로 파생 수급 피처를 산출하는 모듈.

    Attributes:
        task_name (str): 모듈 식별 명칭.
        futures_basis (Dict[str, str]): 선물-현물 괴리율 관련 가격 컬럼 설정.
        futures_intraday_range (Dict[str, str]): 선물 장중 변동 폭 관련 가격 컬럼 설정.
        volume_and_value_anomaly (Dict[str, Any]): 거래량/거래대금 이상치 관련 컬럼 및 윈도우 설정.
    """

    def __init__(
        self,
        task_name: str,
        futures_basis: Dict[str, str],
        futures_intraday_range: Dict[str, str],
        volume_and_value_anomaly: Dict[str, Any]
    ) -> None:
        """DerivativesVolume 인스턴스를 초기화하고 생성자 인자를 멤버 변수에 바인딩합니다.

        Args:
            task_name (str): 모듈 식별 명칭 (예: "DerivativesVolume").
            futures_basis (Dict[str, str]): 선물 괴리율 설정 (futures_price, spot_price).
            futures_intraday_range (Dict[str, str]): 선물 변동 폭 설정 (high_price, low_price, open_price).
            volume_and_value_anomaly (Dict[str, Any]): 거래량/대금 설정 (equity_volume, coin_value, anomaly_window_days).
        """
        super().__init__(task_name=task_name)
        # [설계 의도] 명시적 주입을 보존하여 무상태(Stateless) 인스턴스 구성
        self.futures_basis: Dict[str, str] = futures_basis
        self.futures_intraday_range: Dict[str, str] = futures_intraday_range
        self.volume_and_value_anomaly: Dict[str, Any] = volume_and_value_anomaly

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """입력 데이터프레임의 선물 가격, 현물 종가 및 거래량/대금 데이터를 기반으로 파생 피처들을 산출합니다.

        Args:
            df (pd.DataFrame): 정제가 완료된 입력 시계열 데이터프레임.

        Returns:
            pd.DataFrame: 파생상품 및 거래량/대금 이상치 파생 피처들이 추가된 데이터프레임.

        Raises:
            RequiredColumnNotFoundError: 필수 입력 컬럼이 데이터프레임에 존재하지 않을 때 발생.
            FeatureCalculationExecutionError: 파생상품 및 거래량 롤링 연산 중 수리적 발산 발생 시 전파.
        """
        # [설계 의도] 1단계: 필수 선물/현물/거래량 컬럼 존재 여부 사전 방어 검증
        required_cols: List[str] = [
            self.futures_basis["futures_price"],
            self.futures_basis["spot_price"],
            self.futures_intraday_range["high_price"],
            self.futures_intraday_range["low_price"],
            self.futures_intraday_range["open_price"],
            self.volume_and_value_anomaly["equity_volume"]
        ]
        self._validate_required_columns(df=df, required_columns=required_cols)

        try:
            processed_dataframe: pd.DataFrame = df.copy()

            # [설계 의도] 2단계: 선물-현물 괴리율(proxy_basis_rate) 산출
            raw_futs_price: pd.Series = processed_dataframe[self.futures_basis["futures_price"]]
            raw_spot_price: pd.Series = processed_dataframe[self.futures_basis["spot_price"]]
            
            futs_price: pd.Series = raw_futs_price.mask(raw_futs_price <= 0).ffill().bfill()
            spot_price: pd.Series = raw_spot_price.mask(raw_spot_price <= 0).ffill().bfill()
            
            processed_dataframe["proxy_basis_rate"] = (
                futs_price / spot_price.replace(0, np.nan)
            ) - 1.0

            # [설계 의도] 3단계: 선물 장중 변동 폭 비율(futures_intraday_range) 산출
            raw_futs_high: pd.Series = processed_dataframe[self.futures_intraday_range["high_price"]]
            raw_futs_low: pd.Series = processed_dataframe[self.futures_intraday_range["low_price"]]
            raw_futs_open: pd.Series = processed_dataframe[self.futures_intraday_range["open_price"]]
            
            futs_high: pd.Series = raw_futs_high.mask(raw_futs_high <= 0).ffill().bfill()
            futs_low: pd.Series = raw_futs_low.mask(raw_futs_low <= 0).ffill().bfill()
            futs_open: pd.Series = raw_futs_open.mask(raw_futs_open <= 0).ffill().bfill()
            
            processed_dataframe["futures_intraday_range"] = (
                (futs_high - futs_low) / futs_open.replace(0, np.nan)
            )

            # [설계 의도] 4단계: 주식 거래량 및 코인 거래대금 이상치 비율(volume_anomaly_20d, value_anomaly_20d) 산출
            eq_vol_col: str = self.volume_and_value_anomaly["equity_volume"]
            raw_eq_vol: pd.Series = processed_dataframe[eq_vol_col]
            eq_vol: pd.Series = raw_eq_vol.mask(raw_eq_vol <= 0).ffill().bfill()
            
            anomaly_win: int = self.volume_and_value_anomaly["anomaly_window_days"]
            eq_vol_ma: pd.Series = eq_vol.rolling(window=anomaly_win).mean()
            processed_dataframe[f"volume_anomaly_{anomaly_win}d"] = eq_vol / eq_vol_ma.replace(0, np.nan)

            # 가상자산 거래대금 컬럼이 데이터셋에 존재하는 경우에만 동적으로 연산 수행
            coin_val_col: str = self.volume_and_value_anomaly.get("coin_value", "")
            if coin_val_col and coin_val_col in processed_dataframe.columns:
                raw_coin_val: pd.Series = processed_dataframe[coin_val_col]
                coin_val: pd.Series = raw_coin_val.mask(raw_coin_val <= 0).ffill().bfill()
                coin_val_ma: pd.Series = coin_val.rolling(window=anomaly_win).mean()
                processed_dataframe[f"value_anomaly_{anomaly_win}d"] = coin_val / coin_val_ma.replace(0, np.nan)

            return processed_dataframe

        except FeatureCalculationExecutionError as calculation_err:
            raise calculation_err
        except Exception as unexpected_err:
            raise FeatureCalculationExecutionError(
                message=f"[{self.task_name}] 파생상품/거래량 피처 연산 중 예기치 않은 시스템 예외가 발생했습니다.",
                feature_name="derivatives_volume_all",
                task_name=self.task_name,
                original_exception=unexpected_err
            ) from unexpected_err