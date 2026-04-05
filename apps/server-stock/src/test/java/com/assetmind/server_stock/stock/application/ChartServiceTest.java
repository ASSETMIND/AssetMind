package com.assetmind.server_stock.stock.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1dRepository;
import com.assetmind.server_stock.stock.domain.repository.Ohlcv1mRepository;
import com.assetmind.server_stock.stock.exception.InvalidChartParameterException;
import com.assetmind.server_stock.stock.presentation.dto.ChartResponseDto;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ChartServiceTest {

    @Mock
    private Ohlcv1mRepository ohlcv1mRepository;

    @Mock
    private Ohlcv1dRepository ohlcv1dRepository;

    @InjectMocks
    private ChartService chartService;

    private final String STOCK_CODE = "005930";
    private final int LIMIT = 10;
    private final LocalDateTime END_TIME = LocalDateTime.of(2026, 4, 1, 12, 0);

    @Test
    @DisplayName("endTime이 null일 경우 현재 시간(now)을 기준으로 조회한다.")
    void givenEndTimeIsNull_whenGetCandles_thenQueryEndTimeNow() {
        // given
        when(ohlcv1mRepository.findDynamicMinuteCandles(any(), any(), any(), anyInt()))
                .thenReturn(List.of());

        // when
        chartService.getCandles(STOCK_CODE, "1m", null, LIMIT);

        // then
        // findDynamicMinuteCandles의 3번째 인자로 LocalDateTime이 전달되었는지 확인
        verify(ohlcv1mRepository).findDynamicMinuteCandles(eq(STOCK_CODE), any(), any(LocalDateTime.class), eq(LIMIT));
    }

    @ParameterizedTest
    @CsvSource({
            "1m, 1 minute",
            "3m, 3 minutes",
            "5m, 5 minutes",
            "15m, 15 minutes",
    })
    @DisplayName("다양한 분봉 타임프레임 요청 시 1분봉 레포지토리의 정확한 interval로 라우팅된다.")
    void givenNMinutes_whenGetCandles_thenRoutingCollectInterval(String timeframe, String expectedInterval) {
        // given
        when(ohlcv1mRepository.findDynamicMinuteCandles(any(), any(), any(), anyInt()))
                .thenReturn(List.of());

        // when
        chartService.getCandles(STOCK_CODE, timeframe, END_TIME, LIMIT);

        // then
        verify(ohlcv1mRepository).findDynamicMinuteCandles(STOCK_CODE, expectedInterval, END_TIME, LIMIT);
    }

    @ParameterizedTest
    @CsvSource({
            "1d, 1 day",
            "3d, 3 days",
            "5d, 5 days",
            "1w, 1 week"
    })
    @DisplayName("일/주봉 타임프레임 요청 시 1일봉 레포지토리의 고정 간격 메서드로 라우팅된다.")
    void givenNDays_whenGetCandles_thenRoutingCollectInterval(String timeframe, String expectedInterval) {
        // given
        when(ohlcv1dRepository.findDynamicDailyCandles(any(), any(), any(), anyInt()))
                .thenReturn(List.of());

        // when
        chartService.getCandles(STOCK_CODE, timeframe, END_TIME, LIMIT);

        // then
        verify(ohlcv1dRepository).findDynamicDailyCandles(STOCK_CODE, expectedInterval, END_TIME, LIMIT);
    }

    @Test
    @DisplayName("1mo(월봉) 요청 시 1일봉 레포지토리의 findMonthlyCandles 메서드로 라우팅된다.")
    void given1MonthTimeframe_whenGetCandles_thenRoutingCollectInterval() {
        // given
        when(ohlcv1dRepository.findMonthlyCandles(any(), any(), anyInt()))
                .thenReturn(List.of());

        // when
        chartService.getCandles(STOCK_CODE, "1mo", END_TIME, LIMIT);

        // then
        verify(ohlcv1dRepository).findMonthlyCandles(STOCK_CODE, END_TIME, LIMIT);
    }

    @Test
    @DisplayName("1y(년봉) 요청 시 1일봉 레포지토리의 findYearlyCandles 메서드로 라우팅된다.")
    void given1YearTimeframe_whenGetCandles_thenRoutingCollectInterval() {
        // given
        when(ohlcv1dRepository.findYearlyCandles(any(), any(), anyInt()))
                .thenReturn(List.of());

        // when
        chartService.getCandles(STOCK_CODE, "1y", END_TIME, LIMIT);

        // then
        verify(ohlcv1dRepository).findYearlyCandles(STOCK_CODE, END_TIME, LIMIT);
    }

    @Test
    @DisplayName("지원하지 않는 잘못된 타임프레임(분봉) 요청 시 InvalidChartParameterException 발생한다.")
    void givenInvalidMinutesTimeframe_whenGetCandles_thenThrowException() {
        // then & when
        assertThatThrownBy(() -> chartService.getCandles(STOCK_CODE, "23m", END_TIME, LIMIT))
                .isInstanceOf(InvalidChartParameterException.class)
                .hasMessageContaining("지원하지 않는 분봉");
    }

    @Test
    @DisplayName("지원하지 않는 잘못된 타임프레임(일/주/월/년봉) 요청 시 InvalidChartParameterException 발생한다.")
    void givenInvalidTimeframe_whenGetCandles_thenThrowException() {
        // then & when
        assertThatThrownBy(() -> chartService.getCandles(STOCK_CODE, "99h", END_TIME, LIMIT))
                .isInstanceOf(InvalidChartParameterException.class)
                .hasMessageContaining("지원하지 않는 일/주/월/년봉");
    }

    @Test
    @DisplayName("조회된 OhlcvDto가 ChartResponseDto.CandleDto로 누락 없이 매핑된다.")
    void givenValidParameters_whenGetCandles_thenReturnResponse() {
        // given
        OhlcvDto mockDto = new OhlcvDto(STOCK_CODE, END_TIME, 100.0, 150.0, 90.0, 120.0, 1000L);
        when(ohlcv1mRepository.findDynamicMinuteCandles(any(), any(), any(), anyInt()))
                .thenReturn(List.of(mockDto));

        // when
        ChartResponseDto response = chartService.getCandles(STOCK_CODE, "1m", END_TIME, LIMIT);

        // then
        assertThat(response.candles()).hasSize(1);
        ChartResponseDto.CandleDto candle = response.candles().get(0);
        assertThat(candle.timestamp()).isEqualTo(END_TIME);
        assertThat(candle.open()).isEqualTo("100.0");
        assertThat(candle.high()).isEqualTo("150.0");
        assertThat(candle.low()).isEqualTo("90.0");
        assertThat(candle.close()).isEqualTo("120.0");
        assertThat(candle.volume()).isEqualTo("1000");
    }
}