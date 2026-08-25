"""
금융 시계열 데이터의 날짜/시계열 주축 정보를 바탕으로 달력 주기성(Calendar Seasonality) 및 
월말/분기말 기관 투자자들의 포트폴리오 리밸런싱(Rebalancing) 수급 패턴 지표를 산출하는 모듈입니다.
월(Month, 1~12) 정보의 연속적 주기성을 인식할 수 있도록 삼각함수(Sin/Cos) 인코딩을 적용하고,
월말 및 분기말 임계 거래일 도래 여부를 바이너리 플래그로 사출하여 회귀 모델이 계절적 영향도를 학습하도록 돕습니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: FeatureService로부터 전달받은 원본/이전 단계 금융 시계열 데이터프레임(`df: pd.DataFrame`).
2. Date Index/Column Parsing: `trade_date` 컬럼 또는 DatetimeIndex로부터 날짜(DateTime) 시계열 추출 및 DatetimeAccessor 바인딩.
3. Feature Computation:
   - 월 주기 삼각함수 인코딩: month_sin = sin(2π * month / 12), month_cos = cos(2π * month / 12) 연산.
   - 월말/분기말 리밸런싱 플래그: 해당 월의 남은 일수가 설정된 period_end_threshold_days(3일) 이내인지 판별하여 `is_month_end`, `is_quarter_end` (0 또는 1) 사출.
4. Output: 달력 계절성 및 리밸런싱 플래그 파생 피처 컬럼들이 추가 결합된 데이터프레임(`pd.DataFrame`) 반환.

주요 기능:
- [Cyclical Month Trigonometric Encoding] 1월과 12월의 인접성을 회귀 모델이 원형 연속 공간으로 인식하도록 Sin/Cos 주기적 변환 적용.
- [Month-End / Quarter-End Flag] 월말 및 분기말 기관 리밸런싱 및 윈도우 드레싱(Window Dressing) 기간 도래 여부를 정량 플래그화.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 삼각함수 주기 인코딩(Sin/Cos) vs 단순 정수형 월(1~12) 데이터 직접 사용:
  - 장점: 1월(1)과 12월(12) 사이의 숫자가 수리적으로 멀어져 보이는 절댓값 왜곡을 방지하고, 연속적인 원형 주기를 모델에 전달함.
  - 단점: 1개의 월 정보가 2개의 피처(Sin, Cos)로 분할 사출되므로 피처 차원이 1개 증가함.
  - 근거: 시계열 주기성 반영 시 연속적 거리 보정이 모델의 일반화에 훨씬 우월하므로 차원 1개 증가 오버헤드를 감수함.
"""

import numpy as np
import pandas as pd

from src.feature.tasks.abstract_feature import AbstractFeature
from src.common.exceptions import FeatureCalculationExecutionError


class CalendarSeasonality(AbstractFeature):
    """시계열 날짜 정보를 바탕으로 월 주기 삼각함수 인코딩 및 월말/분기말 플래그 피처를 산출하는 모듈.

    Attributes:
        task_name (str): 모듈 식별 명칭.
        enable_cyclical_month_encoding (bool): 월 주기 삼각함수(Sin/Cos) 인코딩 포함 여부.
        period_end_threshold_days (int): 월말/분기말 판단 임계 거래일 수 (예: 3일).
    """

    def __init__(
        self,
        task_name: str,
        enable_cyclical_month_encoding: bool,
        period_end_threshold_days: int
    ) -> None:
        """CalendarSeasonality 인스턴스를 초기화하고 생성자 인자를 멤버 변수에 바인딩합니다.

        Args:
            task_name (str): 모듈 식별 명칭 (예: "CalendarSeasonality").
            enable_cyclical_month_encoding (bool): 주기 삼각함수 인코딩 포함 토글.
            period_end_threshold_days (int): 월말/분기말 임계 일수.
        """
        super().__init__(task_name=task_name)
        # [설계 의도] MLOps 무상태성 원칙에 따라 명시적 주입 인자를 멤버 변수로 보존
        self.enable_cyclical_month_encoding: bool = enable_cyclical_month_encoding
        self.period_end_threshold_days: int = period_end_threshold_days

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """입력 데이터프레임의 날짜/시간 정보를 바탕으로 계절성 및 달력 파생 피처들을 산출합니다.

        Args:
            df (pd.DataFrame): 정제가 완료된 입력 시계열 데이터프레임.

        Returns:
            pd.DataFrame: 계절성 파생 피처들이 추가된 데이터프레임.

        Raises:
            FeatureCalculationExecutionError: 날짜 정보를 데이터프레임 컬럼 또는 인덱스에서 파싱할 수 없을 때 발생.
        """
        try:
            processed_dataframe: pd.DataFrame = df.copy()

            # [설계 의도] 1단계: trade_date 컬럼 또는 DatetimeIndex로부터 날짜 시계열 파싱
            if "trade_date" in processed_dataframe.columns:
                date_series: pd.Series = pd.to_datetime(processed_dataframe["trade_date"])
            elif isinstance(processed_dataframe.index, pd.DatetimeIndex):
                date_series = processed_dataframe.index.to_series()
            else:
                raise FeatureCalculationExecutionError(
                    message=f"[{self.task_name}] 데이터프레임 내에 'trade_date' 컬럼이나 DatetimeIndex가 존재하지 않아 계절성 피처를 산출할 수 없습니다.",
                    feature_name="calendar_seasonality_all",
                    task_name=self.task_name
                )

            # [설계 의도] 2단계: 월 주기 삼각함수 인코딩 (month_sin, month_cos)
            if self.enable_cyclical_month_encoding:
                month_series: pd.Series = date_series.dt.month
                processed_dataframe["month_sin"] = np.sin(2.0 * np.pi * month_series / 12.0)
                processed_dataframe["month_cos"] = np.cos(2.0 * np.pi * month_series / 12.0)

            # [설계 의도] 3단계: 월말 및 분기말 리밸런싱 플래그 (is_month_end, is_quarter_end)
            days_in_month_series: pd.Series = date_series.dt.days_in_month
            day_series: pd.Series = date_series.dt.day

            # 해당 월의 남은 일수가 threshold 이내인지 검증
            is_month_end_series: pd.Series = (
                (days_in_month_series - day_series) < self.period_end_threshold_days
            ).astype(int)

            processed_dataframe["is_month_end"] = is_month_end_series

            month_series = date_series.dt.month
            is_quarter_month_series: pd.Series = month_series.isin([3, 6, 9, 12])
            processed_dataframe["is_quarter_end"] = (
                is_quarter_month_series & (is_month_end_series == 1)
            ).astype(int)

            return processed_dataframe

        except FeatureCalculationExecutionError as calculation_err:
            raise calculation_err
        except Exception as unexpected_err:
            raise FeatureCalculationExecutionError(
                message=f"[{self.task_name}] 계절성/달력 피처 연산 중 예기치 않은 시스템 예외가 발생했습니다.",
                feature_name="calendar_seasonality_all",
                task_name=self.task_name,
                original_exception=unexpected_err
            ) from unexpected_err