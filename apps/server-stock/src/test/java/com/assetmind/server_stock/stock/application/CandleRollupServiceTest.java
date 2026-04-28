package com.assetmind.server_stock.stock.application;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

public class CandleRollupServiceTest {

    private final CandleRollupService candleRollupService = new CandleRollupService();

    @Test
    @DisplayName("1분봉 3개를 5분봉 1개로 롤업한다.")
    void given1mCandles_whenRollupTo5m_thenReturn5mCandles() {
        // Given: 09:00, 09:01, 09:02 캔들 준비
        List<OhlcvDto> sourceCandles = List.of(
                new OhlcvDto("005930", LocalDateTime.of(2026, 3, 30, 9, 0), 1000.0, 1100.0, 900.0, 1050.0, 10L),
                new OhlcvDto("005930", LocalDateTime.of(2026, 3, 30, 9, 1), 1050.0, 1200.0, 1000.0, 1150.0, 20L),
                new OhlcvDto("005930", LocalDateTime.of(2026, 3, 30, 9, 2), 1150.0, 1150.0, 800.0, 850.0, 30L)
        );

        // When
        List<OhlcvDto> result = candleRollupService.rollup(sourceCandles, CandleType.MIN_5);

        // Then
        assertThat(result).hasSize(1);
        OhlcvDto rolledUp = result.getFirst();
        assertThat(rolledUp.candleTimestamp()).isEqualTo(LocalDateTime.of(2026, 3, 30, 9, 0)); // 00분 바구니
        assertThat(rolledUp.openPrice()).isEqualTo(1000.0);  // 첫 시가
        assertThat(rolledUp.highPrice()).isEqualTo(1200.0);  // 최고가
        assertThat(rolledUp.lowPrice()).isEqualTo(800.0);    // 최저가
        assertThat(rolledUp.closePrice()).isEqualTo(850.0);  // 마지막 종가
        assertThat(rolledUp.volume()).isEqualTo(60L);        // 5분간의 누적 거래량
    }

    @Test
    @DisplayName("1일봉 2개를 주봉 1개로 월요일 기준에 맞춰 롤업한다.")
    void given1dCandles_whenRollupTo1w_thenReturn1wCandles() {
        // Given: 3월 25일(수), 3월 27일(금) 캔들 준비
        List<OhlcvDto> sourceCandles = List.of(
                new OhlcvDto("005930", LocalDateTime.of(2026, 3, 25, 0, 0), 100.0, 150.0, 90.0, 120.0, 1000L),
                new OhlcvDto("005930", LocalDateTime.of(2026, 3, 27, 0, 0), 120.0, 200.0, 110.0, 180.0, 2000L)
        );

        // When
        List<OhlcvDto> result = candleRollupService.rollup(sourceCandles, CandleType.WEEK_1);

        // Then
        assertThat(result).hasSize(1);
        OhlcvDto rolledUp = result.getFirst();

        // 2026년 3월 25일(수)가 속한 주의 월요일은 3월 23일
        assertThat(rolledUp.candleTimestamp()).isEqualTo(LocalDateTime.of(2026, 3, 23, 0, 0));
        assertThat(rolledUp.openPrice()).isEqualTo(100.0);
        assertThat(rolledUp.closePrice()).isEqualTo(180.0);
        assertThat(rolledUp.volume()).isEqualTo(3000L);
    }

    @Test
    @DisplayName("1일봉 2개를 월봉 1개로 달력 기준에 맞춰 롤업한다.")
    void given1dCandles_whenRollupTo1m_thenReturn1mCandles() {
        // Given: 3월 5일, 3월 28일 캔들 준비
        List<OhlcvDto> sourceCandles = List.of(
                new OhlcvDto("005930", LocalDateTime.of(2026, 3, 5, 0, 0), 500.0, 520.0, 490.0, 510.0, 500L),
                new OhlcvDto("005930", LocalDateTime.of(2026, 3, 28, 0, 0), 510.0, 600.0, 480.0, 580.0, 1500L)
        );

        // When
        List<OhlcvDto> result = candleRollupService.rollup(sourceCandles, CandleType.MONTH_1);

        // Then
        assertThat(result).hasSize(1);
        OhlcvDto rolledUp = result.getFirst();
        // 해당 월의 1일로 맞춰져야 함
        assertThat(rolledUp.candleTimestamp()).isEqualTo(LocalDateTime.of(2026, 3, 1, 0, 0));
        assertThat(rolledUp.openPrice()).isEqualTo(500.0);
        assertThat(rolledUp.highPrice()).isEqualTo(600.0);
        assertThat(rolledUp.lowPrice()).isEqualTo(480.0);
        assertThat(rolledUp.closePrice()).isEqualTo(580.0);
        assertThat(rolledUp.volume()).isEqualTo(2000L);
    }

    @Test
    @DisplayName("1일봉 2개를 년봉 1개로 해당 년도 1월 1일 기준에 맞춰 롤업한다.")
    void given1dCandles_whenRollupTo1y_thenReturn1yCandles() {
        // Given: 2026년 3월, 2026년 11월 캔들 준비
        List<OhlcvDto> sourceCandles = List.of(
                new OhlcvDto("005930", LocalDateTime.of(2026, 3, 15, 0, 0), 1000.0, 2000.0, 800.0, 1500.0, 10000L),
                new OhlcvDto("005930", LocalDateTime.of(2026, 11, 20, 0, 0), 1500.0, 3000.0, 1400.0, 2800.0, 20000L)
        );

        // When
        List<OhlcvDto> result = candleRollupService.rollup(sourceCandles, CandleType.YEAR_1);

        // Then
        assertThat(result).hasSize(1);
        OhlcvDto rolledUp = result.getFirst();
        // 해당 연도의 1월 1일로 맞춰져야 함
        assertThat(rolledUp.candleTimestamp()).isEqualTo(LocalDateTime.of(2026, 1, 1, 0, 0));
        assertThat(rolledUp.openPrice()).isEqualTo(1000.0);
        assertThat(rolledUp.highPrice()).isEqualTo(3000.0);
        assertThat(rolledUp.lowPrice()).isEqualTo(800.0);
        assertThat(rolledUp.closePrice()).isEqualTo(2800.0);
        assertThat(rolledUp.volume()).isEqualTo(30000L);
    }

    @Test
    @DisplayName("빈 리스트가 들어오면 빈 리스트를 반환한다.")
    void givenEmptyCandles_whenRollup_thenReturnEmptyList() {
        // Given
        List<OhlcvDto> emptyList = List.of();

        // When
        List<OhlcvDto> result = candleRollupService.rollup(emptyList, CandleType.MIN_5);

        // Then
        assertThat(result).isEmpty();
    }
}
