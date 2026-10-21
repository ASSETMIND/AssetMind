from typing import Optional, Tuple, List
import pandas as pd
import numpy as np


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 벤치마크 심볼 식별자
DEFAULT_KOSPI_TICKER_FINANCE_DATA_READER: str = "KS11"  # FinanceDataReader 전용 KOSPI 종목 코드
DEFAULT_KOSPI_TICKER_YFINANCE: str = "^KS11"            # yfinance 전용 KOSPI 티커 심볼

# 데이터 수집 기간 마진
DATE_MARGIN_DAYS: int = 7                               # 휴일 및 결측 방어를 위한 앞뒤 여유 마진 일수
DEFAULT_MOMENTUM_WINDOW_DAYS: int = 20                  # 레짐 시프트 모멘텀 연산용 기본 롤링 윈도우 일수
DEFAULT_EVENT_SEPARATION_DAYS: int = 15                 # 이벤트 간 최소 시간적 이격 마진 거래일수


# ==============================================================================
# Public API Functions
# ==============================================================================
class BenchmarkProvider:
    """시장 벤치마크 지수 시계열 수집 및 평가 일정 동기화를 전담하는 데이터 프로바이더 클래스.

    Attributes:
        ticker_finance_data_reader (str): FinanceDataReader용 티커 심볼.
        ticker_yfinance (str): yfinance 대체 수집용 티커 심볼.
        margin_days (int): 날짜 조회 마진 일수.
    """

    def __init__(
        self,
        ticker_finance_data_reader: str = DEFAULT_KOSPI_TICKER_FINANCE_DATA_READER,
        ticker_yfinance: str = DEFAULT_KOSPI_TICKER_YFINANCE,
        margin_days: int = DATE_MARGIN_DAYS,
    ) -> None:
        """BenchmarkProvider 인스턴스를 초기화합니다.

        Args:
            ticker_finance_data_reader (str): FinanceDataReader용 심볼. Defaults to 'KS11'.
            ticker_yfinance (str): yfinance용 심볼. Defaults to '^KS11'.
            margin_days (int): 시작/종료일 조회 여유 마진 일수. Defaults to 7.
        """
        self.ticker_finance_data_reader: str = ticker_finance_data_reader
        self.ticker_yfinance: str = ticker_yfinance
        self.margin_days: int = margin_days

    def fetch_benchmark_series(self, evaluation_index: pd.Index) -> pd.Series:
        """평가 데이터셋 날짜 인덱스에 맞춰 시장 벤치마크 지수 종가 시계열을 수집 및 정렬합니다.

        Args:
            evaluation_index (pd.Index): 정렬 기준이 되는 평가 데이터셋 시계열 인덱스.

        Returns:
            pd.Series: 평가 인덱스와 완전 동기화된 벤치마크 종가 시계열.

        Raises:
            ValueError: 입력 evaluation_index가 비어 있는 경우 발생.
            RuntimeError: 모든 수집 데이터 소스(FinanceDataReader, yfinance)에서 데이터 수집이 실패한 경우 발생.
        """
        _validate_evaluation_index(evaluation_index=evaluation_index)

        normalized_index, start_date_string, end_date_string = _resolve_date_boundaries(
            evaluation_index=evaluation_index,
            margin_days=self.margin_days,
        )

        raw_price_series = _fetch_with_failover(
            ticker_finance_data_reader=self.ticker_finance_data_reader,
            ticker_yfinance=self.ticker_yfinance,
            start_date_string=start_date_string,
            end_date_string=end_date_string,
        )

        return _align_series_to_evaluation_index(
            raw_series=raw_price_series,
            target_index=normalized_index,
            original_index=evaluation_index,
        )

    def detect_stress_events(
        self,
        benchmark_series: pd.Series,
        target_series: Optional[pd.Series] = None,
        momentum_window_days: int = DEFAULT_MOMENTUM_WINDOW_DAYS,
        separation_margin_days: int = DEFAULT_EVENT_SEPARATION_DAYS,
    ) -> List[Tuple[str, str]]:
        """벤치마크 및 타겟 시계열로부터 3대 핵심 스트레스/레짐 전환 이벤트를 자동 색출합니다.

        Args:
            benchmark_series (pd.Series): 동기화된 벤치마크(KOSPI) 종가 시계열.
            target_series (Optional[pd.Series]): 평가 데이터셋 정답 타겟(수익률) 시계열. Defaults to None.
            momentum_window_days (int): 모멘텀 급변 탐색용 윈도우 일수. Defaults to 20.
            separation_margin_days (int): 극단 사건 간 최소 이격 마진 일수. Defaults to 15.

        Returns:
            List[Tuple[str, str]]: (이벤트 일자, 국면 명칭) 튜플 시퀀스.
        """
        return _detect_three_stress_events(
            benchmark_series=benchmark_series,
            target_series=target_series,
            momentum_window_days=momentum_window_days,
            separation_margin_days=separation_margin_days,
        )


def fetch_kospi_benchmark_series(evaluation_index: pd.Index) -> pd.Series:
    """기본 KOSPI 티커를 기준으로 평가 데이터셋에 정합된 벤치마크 시계열을 즉시 수집하는 함수형 진입점.

    Args:
        evaluation_index (pd.Index): 정렬 기준 평가 데이터셋 인덱스.

    Returns:
        pd.Series: 평가 인덱스와 동기화된 KOSPI 종가 시계열.

    Raises:
        ValueError: 입력 evaluation_index가 비어 있는 경우 발생.
        RuntimeError: 데이터 수집에 전면 실패한 경우 발생.
    """
    provider = BenchmarkProvider()
    return provider.fetch_benchmark_series(evaluation_index=evaluation_index)


def detect_market_stress_events(
    benchmark_series: pd.Series,
    target_series: Optional[pd.Series] = None,
    momentum_window_days: int = DEFAULT_MOMENTUM_WINDOW_DAYS,
    separation_margin_days: int = DEFAULT_EVENT_SEPARATION_DAYS,
) -> List[Tuple[str, str]]:
    """계량금융 시계열 역학(Peak, MDD Trough, Volatility/Momentum Shock) 기반 3대 극단점을 자동 사출하는 공개 함수.

    Args:
        benchmark_series (pd.Series): 벤치마크 종가 시계열.
        target_series (Optional[pd.Series]): 평가 정답 타겟 시계열. Defaults to None.
        momentum_window_days (int): 모멘텀 윈도우 일수. Defaults to 20.
        separation_margin_days (int): 극단 사건 간 최소 이격 마진 일수. Defaults to 15.

    Returns:
        List[Tuple[str, str]]: [(이벤트일자, 이벤트명칭), ...] 형태의 3대 국면 리스트.
    """
    provider = BenchmarkProvider()
    return provider.detect_stress_events(
        benchmark_series=benchmark_series,
        target_series=target_series,
        momentum_window_days=momentum_window_days,
        separation_margin_days=separation_margin_days,
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_evaluation_index(evaluation_index: pd.Index) -> None:
    """평가 데이터셋 인덱스의 유효성 및 공백 여부를 검증합니다."""
    if evaluation_index is None or len(evaluation_index) == 0:
        raise ValueError("[BenchmarkProvider] evaluation_index가 비어 있거나 존재하지 않습니다.")


def _resolve_date_boundaries(
    evaluation_index: pd.Index,
    margin_days: int,
) -> Tuple[pd.DatetimeIndex, str, str]:
    """시간대 정제 및 조회 시작일과 종료일 문자열을 도출합니다."""
    # [설계 의도] 시간대(Timezone) 정보 정제 및 캘린더 휴일로 인한 결측 방어용 마진 일수 확보
    normalized_index = pd.DatetimeIndex([pd.to_datetime(timestamp).tz_localize(None) for timestamp in evaluation_index])
    start_date_string = (normalized_index.min() - pd.Timedelta(days=margin_days)).strftime("%Y-%m-%d")
    end_date_string = (normalized_index.max() + pd.Timedelta(days=margin_days)).strftime("%Y-%m-%d")
    return normalized_index, start_date_string, end_date_string


def _fetch_with_failover(
    ticker_finance_data_reader: str,
    ticker_yfinance: str,
    start_date_string: str,
    end_date_string: str,
) -> pd.Series:
    """1차 FinanceDataReader 수집 실패 시 2차 yfinance로 자동 우회 수집합니다."""
    # 1. FinanceDataReader 1차 수집 시도
    series = _fetch_from_finance_data_reader(
        ticker=ticker_finance_data_reader,
        start_date_string=start_date_string,
        end_date_string=end_date_string,
    )
    if series is not None and not series.empty:
        return series

    # 2. yfinance 대체 수집 (Failover)
    series = _fetch_from_yfinance(
        ticker=ticker_yfinance,
        start_date_string=start_date_string,
        end_date_string=end_date_string,
    )
    if series is not None and not series.empty:
        return series

    # 3. 전 소스 수집 실패 시 방어적 예외 사출
    raise RuntimeError(
        "[_fetch_with_failover] 벤치마크 지수 데이터를 수집할 수 없습니다. "
        "인터넷 연결 상태 및 'pip install finance-datareader yfinance' 설치 여부를 확인하십시오."
    )


def _fetch_from_finance_data_reader(
    ticker: str,
    start_date_string: str,
    end_date_string: str,
) -> Optional[pd.Series]:
    """FinanceDataReader 라이브러리를 통해 종가 시계열을 수집합니다."""
    try:
        import FinanceDataReader as fdr
        dataframe = fdr.DataReader(ticker, start=start_date_string, end=end_date_string)
        if not dataframe.empty and "Close" in dataframe.columns:
            return dataframe["Close"]
    except Exception:
        return None
    return None


def _fetch_from_yfinance(
    ticker: str,
    start_date_string: str,
    end_date_string: str,
) -> Optional[pd.Series]:
    """yfinance 라이브러리를 통해 종가 시계열을 수집합니다."""
    try:
        import yfinance as yf
        dataframe = yf.download(ticker, start=start_date_string, end=end_date_string, progress=False)
        if not dataframe.empty:
            if isinstance(dataframe.columns, pd.MultiIndex):
                return dataframe["Close"][ticker]
            if "Close" in dataframe.columns:
                return dataframe["Close"]
    except Exception:
        return None
    return None


def _align_series_to_evaluation_index(
    raw_series: pd.Series,
    target_index: pd.DatetimeIndex,
    original_index: pd.Index,
) -> pd.Series:
    """시계열 인덱스를 평가 데이터셋 구간에 일치시키고 보간하여 반환합니다."""
    # [설계 의도] 시간대 비인식 인덱스로 정규화 후 전방/후방 채우기(ffill/bfill)로 거래일 간극 완전 보간
    raw_series.index = pd.DatetimeIndex([pd.to_datetime(timestamp).tz_localize(None) for timestamp in raw_series.index])
    aligned_series = raw_series.reindex(target_index).ffill().bfill()
    aligned_series.index = original_index
    return aligned_series


def _detect_three_stress_events(
    benchmark_series: pd.Series,
    target_series: Optional[pd.Series],
    momentum_window_days: int,
    separation_margin_days: int,
) -> List[Tuple[str, str]]:
    """시계열 극한치 이론(EVT) 및 탈군집화(Declustering)에 기반하여 3대 독립 국면 일자를 특정합니다."""
    # 1. Peak Alpha Gain Day: 타겟 수익률 최대일 (타겟 부재 시 벤치마크 20일 모멘텀 정점)
    if target_series is not None and not target_series.empty:
        peak_date_timestamp = target_series.idxmax()
    else:
        rolling_momentum = benchmark_series.pct_change(periods=momentum_window_days)
        peak_date_timestamp = rolling_momentum.idxmax()

    # 2. Worst MDD Stress Day: 벤치마크 누적 드로다운(Underwater) 최저점(Trough) 일자
    cumulative_maximum = benchmark_series.cummax()
    drawdown_series = (benchmark_series / cumulative_maximum) - 1.0
    worst_mdd_date_timestamp = drawdown_series.idxmin()

    # 3. Regime Shift Shock Day: Worst MDD와 시간적으로 이격된 최대 모멘텀 반전 변곡일
    # [설계 의도] 극단치 군집(Clustered Extremes)으로 인한 중복 수렴을 방지하기 위해
    # Worst MDD 발생일 전후 마진 구간을 배제한 후 모멘텀 급락 변곡점을 독립 탐색
    rolling_drawdown_drop = benchmark_series.pct_change(periods=momentum_window_days).copy()

    worst_mdd_location = benchmark_series.index.get_loc(worst_mdd_date_timestamp)
    margin_start_location = max(0, worst_mdd_location - separation_margin_days)
    margin_end_location = min(len(benchmark_series), worst_mdd_location + separation_margin_days + 1)

    masked_drop = rolling_drawdown_drop.copy()
    masked_drop.iloc[margin_start_location:margin_end_location] = np.nan

    if masked_drop.notna().any():
        regime_shock_timestamp = masked_drop.idxmin()
    else:
        regime_shock_timestamp = cumulative_maximum.idxmax()

    return [
        (pd.to_datetime(peak_date_timestamp).strftime("%Y-%m-%d"), "Peak Alpha Gain Day"),
        (pd.to_datetime(regime_shock_timestamp).strftime("%Y-%m-%d"), "Regime Shift Shock Day"),
        (pd.to_datetime(worst_mdd_date_timestamp).strftime("%Y-%m-%d"), "Worst MDD Stress Day"),
    ]