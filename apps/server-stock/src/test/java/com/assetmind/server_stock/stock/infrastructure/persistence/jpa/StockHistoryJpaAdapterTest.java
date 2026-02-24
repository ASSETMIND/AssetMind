package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase.Replace;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@DataJpaTest
@Testcontainers
@AutoConfigureTestDatabase(replace = Replace.NONE) // H2 대신 PostgreSQL 컨테이너 사용
@Import(StockHistoryJpaAdapter.class)
@TestPropertySource(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class StockHistoryJpaAdapterTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired
    private StockHistoryJpaAdapter stockHistoryJpaAdapter;

    @Test
    @DisplayName("주식 데이터를 저장하고, 최신순으로 정렬하여 조회한다")
    void givenStockData_whenSaveAndFindData_thenReturnSavedDataOrderByCreatedAt() {
        // given
        String stockCode = "005930";
        LocalDateTime now = LocalDateTime.now();

        // 1. 과거 데이터 (10분 전)
        StockDataEntity oldData = createEntity(stockCode, 100L, now.minusMinutes(10));
        // 2. 최신 데이터 (현재)
        StockDataEntity recentData = createEntity(stockCode, 200L, now);
        // 3. 더 옛날 데이터 (1시간 전)
        StockDataEntity veryOldData = createEntity(stockCode, 50L, now.minusHours(1));

        stockHistoryJpaAdapter.save(oldData);
        stockHistoryJpaAdapter.save(recentData);
        stockHistoryJpaAdapter.save(veryOldData);

        // when (최신 2개만 조회 요청)
        List<StockDataEntity> result = stockHistoryJpaAdapter.findRecentData(stockCode, 2);

        // then
        assertThat(result).hasSize(2);

        // 첫 번째는 가장 최신 데이터여야 함 (200원, now)
        assertThat(result.get(0).getCurrentPrice()).isEqualTo(200L);
        assertThat(result.get(0).getCreatedAt()).isEqualTo(now);

        // 두 번째는 그 다음 최신 데이터여야 함 (100원, 10분 전)
        // (1시간 전 데이터는 limit에 걸려 제외되어야 함)
        assertThat(result.get(1).getCurrentPrice()).isEqualTo(100L);
        assertThat(result.get(1).getCreatedAt()).isEqualTo(now.minusMinutes(10));
    }

    @Test
    @DisplayName("다른 종목의 데이터는 조회되지 않아야 한다")
    void givenOtherStockCode_whenSaveAndFindData_thenReturnOnlySavedData() {
        // given
        String targetCode = "005930"; // 삼성전자
        String otherCode = "035420";  // 네이버

        stockHistoryJpaAdapter.save(createEntity(targetCode, 100L, LocalDateTime.now()));
        stockHistoryJpaAdapter.save(createEntity(otherCode, 200L, LocalDateTime.now()));

        // when
        List<StockDataEntity> result = stockHistoryJpaAdapter.findRecentData(targetCode, 10);

        // then
        assertThat(result).hasSize(1);
        assertThat(result.get(0).getStockCode()).isEqualTo(targetCode);
    }

    private StockDataEntity createEntity(String code, Long price, LocalDateTime time) {
        return StockDataEntity.builder()
                .stockCode(code)
                .currentPrice(price)
                .openPrice(price)
                .highPrice(price)
                .lowPrice(price)
                .priceChange(1000L)
                .changeRate(10.0)
                .executionVolume(10L)
                .tradingVolume(30000L)
                .tradingAmount(1000000L)
                .time(time.toString())
                .createdAt(time)
                .build();
    }
}
