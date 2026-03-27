package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import static org.assertj.core.api.Assertions.assertThat;

import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1mJpaEntity;
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
}
