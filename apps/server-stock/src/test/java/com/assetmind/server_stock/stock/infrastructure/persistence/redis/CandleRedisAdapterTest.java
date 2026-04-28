package com.assetmind.server_stock.stock.infrastructure.persistence.redis;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.domain.dtos.OhlcvDto;
import com.assetmind.server_stock.stock.domain.enums.CandleType;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.data.redis.DataRedisTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@DataRedisTest
@Testcontainers
@Import(CandleRedisAdapter.class)
public class CandleRedisAdapterTest {

    @Container
    @ServiceConnection(name = "redis")
    static GenericContainer<?> redisContainer = new GenericContainer<>(DockerImageName.parse("redis:alpine")).withExposedPorts(6379);

    @Autowired
    private CandleRedisAdapter candleRedisAdapter;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @AfterEach
    void tearDown() {
        redisTemplate.getConnectionFactory().getConnection().serverCommands().flushDb();
    }

    @Test
    @DisplayName("실시간 체결 이벤트와 CandleType이 파라미터로 들어오면 Key와 스크립트를 통해 성공적으로 저장한다.")
    void givenEventAndType_whenSave_thenSaved() {
        // Given: 가상의 삼성전자 틱 데이터 생성
        String stockCode = "005930";
        Long currentPrice = 180000L;
        Long executionVolume = 10L;

        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode(stockCode)
                .currentPrice(currentPrice)
                .executionVolume(executionVolume)
                .build();

        // When
        candleRedisAdapter.save(event, CandleType.MIN_1);

        // Then
        // 저장된 키 검증
        String keyPattern = "candle:1m:" + stockCode + ":*";
        Set<String> keys = redisTemplate.keys(keyPattern);

        assertThat(keys).isNotNull();
        assertThat(keys).hasSize(1);

        // Hash 내부 데이터가 Lua 스크립트의 로직대로 잘 들어갔는지 검증
        String savedKey = keys.iterator().next();
        Map<Object, Object> entries = redisTemplate.opsForHash().entries(savedKey);

        assertThat(entries)
                .containsEntry("open", String.valueOf(currentPrice))
                .containsEntry("high", String.valueOf(currentPrice))
                .containsEntry("low", String.valueOf(currentPrice))
                .containsEntry("close", String.valueOf(currentPrice))
                .containsEntry("volume", String.valueOf(executionVolume));

        // TTL이 300초로 잘 설정되었는지 검증
        Long expireTime = redisTemplate.getExpire(savedKey);
        assertThat(expireTime)
                .isGreaterThan(0L)
                .isLessThanOrEqualTo(300L);
    }

    @Test
    @DisplayName("Flush할 TargetTime과 CandleType이 파라미터로 들어오면 성공적으로 TargetTime의 데이터를 리스트로 반환하고 메모리에서 제거한다.")
    void givenTargetTimeAndType_whenFlushCandles_thenReturnDtoListAndDeleteDataInMemory() {
        // Given: 스케줄러가 수집할 타겟 시간 설정 (예: 202603271315)
        String targetTime = "202603271315";
        String stockCode = "005930";
        String key = "candle:1m:" + stockCode + ":" + targetTime;

        // Redis에 가상의 1분봉 데이터 강제 주입
        Map<String, String> dummyData = Map.of(
                "open", "75000",
                "high", "76000",
                "low", "74000",
                "close", "75500",
                "volume", "1000"
        );
        redisTemplate.opsForHash().putAll(key, dummyData);

        // When
        List<OhlcvDto> result = candleRedisAdapter.flushCandles(targetTime, CandleType.MIN_1);

        // Then
        // DTO 리스트가 정상적으로 반환되었는지 확인
        assertThat(result).hasSize(1);
        OhlcvDto dto = result.get(0);
        assertThat(dto.stockCode()).isEqualTo(stockCode);
        assertThat(dto.highPrice()).isEqualTo(76000.0);
        assertThat(dto.volume()).isEqualTo(1000L);

        // Flush된 데이터가 Redis 메모리에서 깔끔하게 삭제 되었는지 검증
        Boolean hasKey = redisTemplate.hasKey(key);
        assertThat(hasKey).isFalse();
    }

    @Test
    @DisplayName("Flush할 TargetTime에 해당하는 데이터가 없으면 빈 리스트를 반환한다.")
    void givenEmptyKey_whenFlushCandles_thenReturnEmptyList() {
        // Given: 아무 데이터도 넣지 않음
        String targetTime = "209912312359"; // 데이터가 없을 시간

        // When
        List<OhlcvDto> result = candleRedisAdapter.flushCandles(targetTime, CandleType.MIN_1);

        // Then
        // 빈 리스트를 반환하는지 검증
        assertThat(result).isNotNull();
        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("100개의 스레드가 동시에 같은 종목의 틱 데이터를 저장해도 고가/저가/거래량이 완벽하게 계산된다.")
    void givenConcurrentRequests_whenSave_thenCalculatePerfectly() throws InterruptedException {
        // Given
        int threadCount = 100;
        ExecutorService executorService = Executors.newFixedThreadPool(32);
        CountDownLatch latch = new CountDownLatch(threadCount);

        String stockCode = "005930";

        // When: 100개의 스레드가 동시에 save() 호출
        // 가격을 1000000원부터 1000099원까지 설정
        for (int i = 0; i < threadCount; i++) {
            long price = 1000000L + i;
            RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                    .stockCode(stockCode)
                    .currentPrice(price)
                    .executionVolume(10L)
                    .build();

            executorService.submit(() -> {
                try {
                    candleRedisAdapter.save(event, CandleType.MIN_1);
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await();

        // Then: 1000000 ~ 1000099원까지 각 거래량 10개씩 데이터들이 동시성 문제 없이 원자적으로 잘 저장됐는지 검증
        String keyPattern = "candle:1m:" + stockCode + ":*";
        Set<String> keys = redisTemplate.keys(keyPattern);
        assertThat(keys).hasSize(1);

        String savedKey = keys.iterator().next();

        Map<Object, Object> entries = redisTemplate.opsForHash().entries(savedKey);

        assertThat(entries.get("high")).isEqualTo("1000099"); // 고가, 데이터 중 제일 높은 값
        assertThat(entries.get("low")).isEqualTo("1000000"); // 저가, 데이터 중 제일 낮은 값
        assertThat(entries.get("volume")).isEqualTo("1000"); // 100개의 데이터의 누적 거래량
    }

}
