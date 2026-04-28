package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import static org.assertj.core.api.Assertions.assertThat;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1dJpaEntity;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@DataJpaTest
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(Ohlcv1dJpaAdapter.class)
@TestPropertySource(properties = "spring.sql.init.mode=never")
class Ohlcv1dJpaAdapterTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired
    private Ohlcv1dJpaAdapter ohlcv1dJpaAdapter;

    @Autowired
    private Ohlcv1dJpaRepository ohlcv1dJpaRepository;

    @Test
    @DisplayName("OhlcvDto 리스트가 주어지면 JpaEntity로 변환하여 DB에 성공적으로 일괄 저장(saveAll)한다.")
    void givenDtoList_whenSaveAll_thenSavedToDatabase() {
        // Given
        OhlcvDto dto1 = new OhlcvDto("005930", LocalDateTime.of(2026, 3, 30, 0, 0), 75000.0, 76000.0, 74000.0, 75500.0, 1000L);
        OhlcvDto dto2 = new OhlcvDto("000660", LocalDateTime.of(2026, 3, 30, 0, 0), 150000.0, 151000.0, 149000.0, 150500.0, 500L);

        // When
        ohlcv1dJpaAdapter.saveAll(List.of(dto1, dto2));

        // Then
        List<Ohlcv1dJpaEntity> savedEntities = ohlcv1dJpaRepository.findAll();
        assertThat(savedEntities).hasSize(2);
    }

    @Test
    @DisplayName("단건 OhlcvDto가 주어지면 JpaEntity로 변환하여 DB에 성공적으로 저장(save)한다.")
    void givenSingleDto_whenSave_thenSavedToDatabase() {
        // Given
        OhlcvDto dto = new OhlcvDto("005930", LocalDateTime.of(2026, 3, 31, 0, 0), 100.0, 120.0, 90.0, 110.0, 5000L);

        // When
        ohlcv1dJpaAdapter.save(dto);

        // Then
        List<Ohlcv1dJpaEntity> savedEntities = ohlcv1dJpaRepository.findAll();
        assertThat(savedEntities).hasSize(1);
        assertThat(savedEntities.getFirst().getStockCode()).isEqualTo("005930");
        assertThat(savedEntities.getFirst().getClosePrice()).isEqualTo(110.0);
    }

    @Test
    @DisplayName("특정 날짜(LocalDate)로 조회 시, 해당 날짜의 1일봉 데이터를 Optional로 정확히 반환한다.")
    void givenDate_whenFindCandleByDay_thenReturnOptionalCandle() {
        // Given: 3월 30일 1일봉 데이터 DB 저장
        String stockCode = "005930";
        LocalDate targetDate = LocalDate.of(2026, 3, 30);

        OhlcvDto savedDto = new OhlcvDto(stockCode, LocalDateTime.of(2026, 3, 30, 0, 0), 75000.0, 76000.0, 74000.0, 75500.0, 1000L);
        ohlcv1dJpaAdapter.save(savedDto);

        // When: 3월 30일 데이터 조회 요청
        Optional<OhlcvDto> result = ohlcv1dJpaAdapter.findCandleByDay(stockCode, targetDate);

        // Then: 데이터가 존재해야 하며, 저장한 값과 정확히 일치해야 함
        assertThat(result).isPresent();
        assertThat(result.get().candleTimestamp()).isEqualTo(LocalDateTime.of(2026, 3, 30, 0, 0));
        assertThat(result.get().stockCode()).isEqualTo(stockCode);
        assertThat(result.get().closePrice()).isEqualTo(75500.0);
    }

    @Test
    @DisplayName("조회하려는 날짜에 데이터가 없으면 Optional.empty()를 반환한다.")
    void givenDateWithNoData_whenFindCandleByDay_thenReturnEmptyOptional() {
        // Given: DB는 텅 빈 상태
        String stockCode = "005930";
        LocalDate emptyDate = LocalDate.of(2026, 3, 31);

        // When
        Optional<OhlcvDto> result = ohlcv1dJpaAdapter.findCandleByDay(stockCode, emptyDate);

        // Then
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("N일봉 동적 집계: 기간 내의 1일봉들이 정확한 OHLCV(시/고/저/종/거래량)로 롤업된다.")
    void givenDailyCandles_whenFindDynamicDailyCandles_thenAggregatedCorrectly() {
        // Given: 2000년 1월 1일 ~ 1월 3일 (3일간의 데이터)
        String stockCode = "005930";
        ohlcv1dJpaAdapter.saveAll(List.of(
                // 1일차: 시가 100, 고가 120, 저가 90, 종가 110, 거래량 10
                new OhlcvDto(stockCode, LocalDateTime.of(2000, 1, 1, 0, 0), 100.0, 120.0, 90.0, 110.0, 10L),
                // 2일차: 시가 110, 고가 150, 저가 100, 종가 140, 거래량 20 (최고가 150 갱신)
                new OhlcvDto(stockCode, LocalDateTime.of(2000, 1, 2, 0, 0), 110.0, 150.0, 100.0, 140.0, 20L),
                // 3일차: 시가 140, 고가 160, 저가 80, 종가 155, 거래량 30 (최저가 80 갱신, 최종 종가 155)
                new OhlcvDto(stockCode, LocalDateTime.of(2000, 1, 3, 0, 0), 140.0, 160.0, 80.0, 155.0, 30L)
        ));

        // When: 3 days 간격으로 집계 요청 (Limit 10)
        LocalDateTime endTime = LocalDateTime.of(2026, 4, 4, 0, 0);
        List<OhlcvDto> result = ohlcv1dJpaAdapter.findDynamicDailyCandles(stockCode, "3 days", endTime, 10);

        // Then
        assertThat(result).isNotEmpty();
        OhlcvDto aggregatedDto = result.getFirst(); // 3일 치가 하나의 캔들로 묶임

        // OHLCV 연산 검증
        assertThat(aggregatedDto.openPrice()).isEqualTo(100.0);   // 첫 날의 시가
        assertThat(aggregatedDto.highPrice()).isEqualTo(160.0);   // 3일 중 최고가
        assertThat(aggregatedDto.lowPrice()).isEqualTo(80.0);     // 3일 중 최저가
        assertThat(aggregatedDto.closePrice()).isEqualTo(155.0);  // 마지막 날의 종가
        assertThat(aggregatedDto.volume()).isEqualTo(60L);        // 거래량 총합 (10 + 20 + 30)
    }

    @Test
    @DisplayName("월봉 집계(date_trunc): 여러 달에 걸친 데이터가 각 월별 1일 기준으로 분리되어 집계된다.")
    void givenCandlesAcrossMonths_whenFindMonthlyCandles_thenGroupedByMonth() {
        // Given: 3월 데이터 2개, 4월 데이터 1개
        String stockCode = "005930";
        ohlcv1dJpaAdapter.saveAll(List.of(
                // 3월 데이터 (3월 15일, 3월 25일)
                new OhlcvDto(stockCode, LocalDateTime.of(2026, 3, 15, 0, 0), 100.0, 150.0, 90.0, 140.0, 10L),
                new OhlcvDto(stockCode, LocalDateTime.of(2026, 3, 25, 0, 0), 140.0, 180.0, 130.0, 170.0, 20L),
                // 4월 데이터 (4월 5일)
                new OhlcvDto(stockCode, LocalDateTime.of(2026, 4, 5, 0, 0), 170.0, 200.0, 160.0, 190.0, 30L)
        ));

        LocalDateTime endTime = LocalDateTime.of(2026, 4, 30, 0, 0);

        // When: 월봉 조회
        List<OhlcvDto> result = ohlcv1dJpaAdapter.findMonthlyCandles(stockCode, endTime, 10);

        // Then: 4월(최신) 1개, 3월(과거) 1개 -> 총 2개의 월봉이 나와야 함 (DESC 정렬)
        assertThat(result).hasSize(2);

        // 첫 번째 결과 (최신인 4월봉)
        assertThat(result.get(0).candleTimestamp()).isEqualTo(LocalDateTime.of(2026, 4, 1, 0, 0)); // 4월 1일로 버림(trunc)됨
        assertThat(result.get(0).closePrice()).isEqualTo(190.0);
        assertThat(result.get(0).volume()).isEqualTo(30L);

        // 두 번째 결과 (과거인 3월봉) - 3월 데이터 2개가 하나로 합쳐짐
        assertThat(result.get(1).candleTimestamp()).isEqualTo(LocalDateTime.of(2026, 3, 1, 0, 0)); // 3월 1일로 버림(trunc)됨
        assertThat(result.get(1).openPrice()).isEqualTo(100.0); // 3/15의 시가
        assertThat(result.get(1).closePrice()).isEqualTo(170.0); // 3/25의 종가
        assertThat(result.get(1).highPrice()).isEqualTo(180.0); // 3월 중 최고가
        assertThat(result.get(1).volume()).isEqualTo(30L); // 10 + 20
    }

    @Test
    @DisplayName("년봉 집계(date_trunc): 해가 바뀌는 데이터가 연도별 1월 1일 기준으로 정확히 분리된다.")
    void givenCandlesAcrossYears_whenFindYearlyCandles_thenGroupedByYear() {
        // Given: 2025년 데이터 1개, 2026년 데이터 1개
        String stockCode = "005930";
        ohlcv1dJpaAdapter.saveAll(List.of(
                // 2025년 연말
                new OhlcvDto(stockCode, LocalDateTime.of(2025, 12, 31, 0, 0), 50000.0, 55000.0, 49000.0, 54000.0, 100L),
                // 2026년 연초
                new OhlcvDto(stockCode, LocalDateTime.of(2026, 1, 2, 0, 0), 54000.0, 60000.0, 53000.0, 59000.0, 200L)
        ));

        LocalDateTime endTime = LocalDateTime.of(2026, 12, 31, 0, 0);

        // When: 년봉 조회
        List<OhlcvDto> result = ohlcv1dJpaAdapter.findYearlyCandles(stockCode, endTime, 10);

        // Then: 2026년 봉, 2025년 봉 총 2개가 DESC 순서로 반환되어야 함
        assertThat(result).hasSize(2);

        // 첫 번째 (최신 2026년봉)
        assertThat(result.get(0).candleTimestamp()).isEqualTo(LocalDateTime.of(2026, 1, 1, 0, 0)); // 2026-01-01로 묶임
        assertThat(result.get(0).closePrice()).isEqualTo(59000.0);

        // 두 번째 (과거 2025년봉)
        assertThat(result.get(1).candleTimestamp()).isEqualTo(LocalDateTime.of(2025, 1, 1, 0, 0)); // 2025-01-01로 묶임
        assertThat(result.get(1).closePrice()).isEqualTo(54000.0);
    }
}