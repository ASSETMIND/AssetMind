package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import static org.assertj.core.api.Assertions.assertThat;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1mJpaEntity;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
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
@Import(Ohlcv1mJpaAdapter.class)
@TestPropertySource(properties = "spring.sql.init.mode=never")
class Ohlcv1mJpaAdapterTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired
    private Ohlcv1mJpaAdapter ohlcv1mJpaAdapter;

    @Autowired
    private Ohlcv1mJpaRepository ohlcv1mJpaRepository;

    @Test
    @DisplayName("OhlcvDto 리스트가 주어지면 JpaEntity로 변환하여 DB에 성공적으로 저장한다.")
    void givenDtoList_whenSaveAll_thenSavedToDatabase() {
        // Given: 2개의 1분봉 DTO 생성
        OhlcvDto dto1 = new OhlcvDto(
                "005930", LocalDateTime.of(2026, 3, 27, 9, 1),
                75000.0, 76000.0, 74000.0, 75500.0, 1000L
        );
        OhlcvDto dto2 = new OhlcvDto(
                "000660", LocalDateTime.of(2026, 3, 27, 9, 1),
                150000.0, 151000.0, 149000.0, 150500.0, 500L
        );
        List<OhlcvDto> dtoList = List.of(dto1, dto2);

        // When: 어댑터를 통해 DB에 저장 (내부적으로 saveAll 호출)
        ohlcv1mJpaAdapter.saveAll(dtoList);

        // Then: 실제 DB에서 꺼내서 변환과 저장이 완벽했는지 검증
        List<Ohlcv1mJpaEntity> savedEntities = ohlcv1mJpaRepository.findAll();

        assertThat(savedEntities).hasSize(2);

        // 삼성전자 데이터 검증
        Ohlcv1mJpaEntity savedSamsung = savedEntities.stream()
                .filter(e -> e.getStockCode().equals("005930"))
                .findFirst().orElseThrow();

        assertThat(savedSamsung.getClosePrice()).isEqualTo(75500.0);
        assertThat(savedSamsung.getVolume()).isEqualTo(1000L);
    }

    @Test
    @DisplayName("특정 날짜를 주면 해당 날짜의 00:00:00 ~ 23:59:59 사이의 캔들만 정확히 조회한다.")
    void givenSpecificDate_whenFindCandlesByDate_thenReturnOnlyThatDatesCandles() {
        // Given: 어제, 오늘, 내일의 1분봉 데이터를 섞어서 준비
        String stockCode = "005930";
        LocalDate today = LocalDate.of(2026, 3, 30);

        OhlcvDto yesterdayDto = new OhlcvDto(stockCode, LocalDateTime.of(2026, 3, 29, 23, 59), 100.0, 100.0, 100.0, 100.0, 10L);
        OhlcvDto todayDto1 = new OhlcvDto(stockCode, LocalDateTime.of(2026, 3, 30, 9, 0), 200.0, 200.0, 200.0, 200.0, 20L);
        OhlcvDto todayDto2 = new OhlcvDto(stockCode, LocalDateTime.of(2026, 3, 30, 15, 30), 300.0, 300.0, 300.0, 300.0, 30L);
        OhlcvDto tomorrowDto = new OhlcvDto(stockCode, LocalDateTime.of(2026, 3, 31, 9, 0), 400.0, 400.0, 400.0, 400.0, 40L);

        // 어댑터의 saveAll을 활용해 실제 PostgreSQL 컨테이너에 INSERT
        ohlcv1mJpaAdapter.saveAll(List.of(yesterdayDto, todayDto1, todayDto2, tomorrowDto));

        // When: 3월 30일 데이터만 달라고 조회
        List<OhlcvDto> result = ohlcv1mJpaAdapter.findCandlesByDate(stockCode, today);

        // Then: 29일, 31일 데이터는 제외되고 정확히 오늘 데이터 2개만 반환되어야 함
        assertThat(result).hasSize(2);
        assertThat(result)
                .extracting(OhlcvDto::candleTimestamp)
                .containsExactlyInAnyOrder(
                        LocalDateTime.of(2026, 3, 30, 9, 0),
                        LocalDateTime.of(2026, 3, 30, 15, 30)
                );
    }

    @Test
    @DisplayName("N분봉 동적 집계: 1분봉들이 지정된 N분 간격으로 정확한 OHLCV(시/고/저/종/거래량)로 롤업된다.")
    void givenMinuteCandles_whenFindDynamicMinuteCandles_thenAggregatedCorrectly() {
        // Given: date_bin의 기준점(2000-01-01 00:00:00)에 3분 치 1분봉 데이터를 넣는다
        String stockCode = "005930";
        ohlcv1mJpaAdapter.saveAll(List.of(
                // 1분차 (00:00): 시가 100, 고가 120, 저가 90, 종가 110, 거래량 10
                new OhlcvDto(stockCode, LocalDateTime.of(2000, 1, 1, 0, 0), 100.0, 120.0, 90.0, 110.0, 10L),
                // 2분차 (00:01): 시가 110, 고가 150, 저가 100, 종가 140, 거래량 20
                new OhlcvDto(stockCode, LocalDateTime.of(2000, 1, 1, 0, 1), 110.0, 150.0, 100.0, 140.0, 20L),
                // 3분차 (00:02): 시가 140, 고가 160, 저가 80, 종가 155, 거래량 30
                new OhlcvDto(stockCode, LocalDateTime.of(2000, 1, 1, 0, 2), 140.0, 160.0, 80.0, 155.0, 30L),

                // 다음 바구니(Bin) 데이터 (00:03 ~ 00:05 구간) - 집계가 따로 묶이는지 확인용 데이터
                new OhlcvDto(stockCode, LocalDateTime.of(2000, 1, 1, 0, 3), 155.0, 170.0, 150.0, 165.0, 40L)
        ));

        // When: '3 minutes' 간격으로 집계 요청 (Limit 10)
        // endTime을 00:04로 주어서 첫 번째 바구니(00:00~00:02)와 두 번째 바구니 일부(00:03)가 조회되도록 함
        LocalDateTime endTime = LocalDateTime.of(2000, 1, 1, 0, 4);
        List<OhlcvDto> result = ohlcv1mJpaAdapter.findDynamicMinuteCandles(stockCode, "3 minutes", endTime, 10);

        // Then: 2개의 바구니(3분봉 2개)가 최신순(DESC)으로 조회되어야 함
        assertThat(result).hasSize(2);

        // 첫 번째 결과 (최신 바구니: 00:03 ~ 00:05 구간) -> 00:03 데이터 1개만 있음
        OhlcvDto latestAggregatedDto = result.get(0);
        assertThat(latestAggregatedDto.candleTimestamp()).isEqualTo(LocalDateTime.of(2000, 1, 1, 0, 3));
        assertThat(latestAggregatedDto.closePrice()).isEqualTo(165.0);
        assertThat(latestAggregatedDto.volume()).isEqualTo(40L);

        // 두 번째 결과 (과거 바구니: 00:00 ~ 00:02 구간) -> 3개의 1분봉이 완벽하게 롤업되어야 함
        OhlcvDto pastAggregatedDto = result.get(1);
        assertThat(pastAggregatedDto.candleTimestamp()).isEqualTo(LocalDateTime.of(2000, 1, 1, 0, 0));

        // OHLCV 롤업 로직 상세 검증
        assertThat(pastAggregatedDto.openPrice()).isEqualTo(100.0);   // 첫 분(00:00)의 시가
        assertThat(pastAggregatedDto.highPrice()).isEqualTo(160.0);   // 3분 중 최고가
        assertThat(pastAggregatedDto.lowPrice()).isEqualTo(80.0);     // 3분 중 최저가
        assertThat(pastAggregatedDto.closePrice()).isEqualTo(155.0);  // 마지막 분(00:02)의 종가
        assertThat(pastAggregatedDto.volume()).isEqualTo(60L);        // 거래량 총합 (10 + 20 + 30)
    }
}
