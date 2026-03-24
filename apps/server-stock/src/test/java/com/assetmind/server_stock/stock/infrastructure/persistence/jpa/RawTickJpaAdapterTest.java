package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import static org.assertj.core.api.Assertions.*;
import static org.junit.jupiter.api.Assertions.*;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.RawTickJpaEntity;
import java.time.LocalDateTime;
import java.util.List;
import org.assertj.core.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase.Replace;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.context.TestPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@DataJpaTest
@Testcontainers
@AutoConfigureTestDatabase(replace = Replace.NONE)
@Import(RawTickJpaAdapter.class)
@TestPropertySource(properties = "spring.sql.init.mode=never")
class RawTickJpaAdapterTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired
    private RawTickJpaRepository rawTickJpaRepository;

    @Autowired
    private RawTickJpaAdapter rawTickJpaAdapter;

    @Test
    @DisplayName("실시간 체결 데이터를 저장하고, 최신순으로 정렬하여 조회한다.")
    void givenStockData_whenSaveAndFindData_thenReturnSavedDataOrderByCreatedAt() {
        // given
        String stockCode = "005930";
        LocalDateTime now = LocalDateTime.of(2026, 3, 20, 12, 0, 0);

        // 10분전 틱 데이터
        RawTickJpaEntity before10MData = createRawTickEntity(stockCode, 180000.0,
                now.minusMinutes(10));
        // 5분전 틱 데이터
        RawTickJpaEntity before5MData = createRawTickEntity(stockCode, 182000.0,
                now.minusMinutes(5));
        // 1분전 틱 데이터
        RawTickJpaEntity before1MData = createRawTickEntity(stockCode, 182500.0,
                now.minusMinutes(1));

        // 다른 종목의 노이즈 데이터
        RawTickJpaEntity otherData = createRawTickEntity("000660", 1000000.0, now);

        rawTickJpaRepository.saveAll(List.of(before1MData, before5MData, before10MData, otherData));

        // when
        List<RawTickJpaEntity> result = rawTickJpaAdapter.findRecentData(stockCode, 2);

        // then
        assertThat(result).hasSize(2); // 2개만 조회가 됐는지

        // 가장 최신 데이터 (1분전)가 첫 번째 데이터로 조회됐는지
        assertThat(result.get(0).getTradeTimestamp()).isEqualTo(before1MData.getTradeTimestamp());
        assertThat(result.get(0).getCurrentPrice()).isEqualTo(before1MData.getCurrentPrice());

        // 두번 째 최신 데이터 (5분전)이 두 번째 데이터로 조회됐는지
        assertThat(result.get(1).getTradeTimestamp()).isEqualTo(before5MData.getTradeTimestamp());
        assertThat(result.get(1).getCurrentPrice()).isEqualTo(before5MData.getCurrentPrice());

    }


    private RawTickJpaEntity createRawTickEntity(String stockCode, Double price, LocalDateTime time) {
        return  RawTickJpaEntity.builder()
                .stockCode(stockCode)
                .tradeTimestamp(time)
                .currentPrice(price)
                .priceChange(3.0)
                .volume(100L)
                .build();
    }
}