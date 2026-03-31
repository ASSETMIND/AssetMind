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
}