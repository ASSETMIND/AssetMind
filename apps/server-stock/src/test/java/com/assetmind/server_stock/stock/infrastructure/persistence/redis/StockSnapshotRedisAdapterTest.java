package com.assetmind.server_stock.stock.infrastructure.persistence.redis;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.data.redis.DataRedisTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@DataRedisTest
@Import(StockSnapshotRedisAdapter.class)
@Testcontainers
class StockSnapshotRedisAdapterTest {

    @Container
    @ServiceConnection(name = "redis")
    static GenericContainer<?> redisContainer = new GenericContainer<>(DockerImageName.parse("redis:alpine")).withExposedPorts(6379);

    @Autowired
    private StockSnapshotRedisAdapter stockSnapshotRedisAdapter;

    @Autowired
    private StockPriceRedisRepository stockPriceRedisRepository;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @AfterEach
    void tearDown() {
        RedisConnectionFactory connectionFactory = redisTemplate.getConnectionFactory();

        if (connectionFactory != null) {
            connectionFactory.getConnection().serverCommands().flushAll();
        }
    }

    @Test
    @DisplayName("주식 데이터를 저장하면 상세정보(Hash)와 랭킹점수(ZSet)가 모두 저장된다")
    void givenStockData_whenSave_thenSavedStockDataAndRanking() {
        // given
        // 삼성전자: 거래대금 100만, 거래량 500주
        StockPriceRedisEntity entity = createEntity("005930", "삼성전자", 1_000_000L, 500L);

        // when
        stockSnapshotRedisAdapter.save(entity);

        // then
        // 1. Redis Hash 저장 확인
        StockPriceRedisEntity savedEntity = stockPriceRedisRepository.findById("005930").orElseThrow();
        assertThat(savedEntity.getStockName()).isEqualTo("삼성전자");
        assertThat(savedEntity.getCumulativeAmount()).isEqualTo(1_000_000L);

        // 2. Redis ZSet (랭킹) 점수 확인
        // 거래대금 랭킹
        Double valueScore = redisTemplate.opsForZSet().score("ranking:trade_value", "005930");
        assertThat(valueScore).isEqualTo(1_000_000.0);

        // 거래량 랭킹
        Double volumeScore = redisTemplate.opsForZSet().score("ranking:trade_volume", "005930");
        assertThat(volumeScore).isEqualTo(500.0);
    }

    @Test
    @DisplayName("거래대금(Amount) 상위 종목을 내림차순으로 정확하게 가져온다")
    void givenLimitCount_whenGetTopStocksByTradeValue_thenReturnTradeValueRankingData() {
        // given
        // A: 1000원 (3등)
        stockSnapshotRedisAdapter.save(createEntity("A", "종목A", 1000L, 0L));
        // B: 3000원 (1등)
        stockSnapshotRedisAdapter.save(createEntity("B", "종목B", 3000L, 0L));
        // C: 2000원 (2등)
        stockSnapshotRedisAdapter.save(createEntity("C", "종목C", 2000L, 0L));

        // when (상위 3개 조회)
        List<StockPriceRedisEntity> result = stockSnapshotRedisAdapter.getTopStocksByTradeValue(3);

        // then
        assertThat(result).hasSize(3);

        // 1등: B
        assertThat(result.get(0).getStockCode()).isEqualTo("B");
        assertThat(result.get(0).getCumulativeAmount()).isEqualTo(3000L);

        // 2등: C
        assertThat(result.get(1).getStockCode()).isEqualTo("C");

        // 3등: A
        assertThat(result.get(2).getStockCode()).isEqualTo("A");
    }

    @Test
    @DisplayName("거래량(Volume) 상위 종목을 내림차순으로 정확하게 가져온다")
    void givenLimitCount_whenGetTopStocksByTradeVolume_thenReturnTradeVolumeRankingData() {
        // given (거래대금 순위와 거래량 순위를 다르게 섞음)
        // A: 대금 꼴등(100), 거래량 1등(5000)
        stockSnapshotRedisAdapter.save(createEntity("A", "종목A", 100L, 5000L));

        // B: 대금 1등(300), 거래량 3등(10)
        stockSnapshotRedisAdapter.save(createEntity("B", "종목B", 300L, 10L));

        // C: 대금 2등(200), 거래량 2등(200)
        stockSnapshotRedisAdapter.save(createEntity("C", "종목C", 200L, 200L));

        // when (상위 3개 조회)
        List<StockPriceRedisEntity> result = stockSnapshotRedisAdapter.getTopStocksByTradeVolume(3);

        // then
        assertThat(result).hasSize(3);

        // 거래량 1등은 A여야 함 (대금은 꼴등이지만)
        assertThat(result.get(0).getStockCode()).isEqualTo("A");
        assertThat(result.get(0).getCumulativeVolume()).isEqualTo(5000L);

        // 거래량 2등 C
        assertThat(result.get(1).getStockCode()).isEqualTo("C");

        // 거래량 3등 B
        assertThat(result.get(2).getStockCode()).isEqualTo("B");
    }

    @Test
    @DisplayName("요청한 limit 개수만큼만 잘라서 반환한다")
    void givenLimitCount_whenGet_thenReturnCollectLimitCountData() {
        // given (5개 저장)
        for (int i = 1; i <= 5; i++) {
            stockSnapshotRedisAdapter.save(createEntity("CODE" + i, "NAME" + i, (long) (i * 100), 0L));
        }

        // when (상위 2개만 요청)
        List<StockPriceRedisEntity> result = stockSnapshotRedisAdapter.getTopStocksByTradeValue(2);

        // then
        assertThat(result).hasSize(2);
        // 가장 높은 값은 i=5 (500)
        assertThat(result.get(0).getStockCode()).isEqualTo("CODE5");
        assertThat(result.get(1).getStockCode()).isEqualTo("CODE4");
    }

    @Test
    @DisplayName("데이터가 없을 때 빈 리스트를 반환한다")
    void givenNoDataInRedis_whenGet_thenEmptyList() {
        // given (데이터 없음)

        // when
        List<StockPriceRedisEntity> result = stockSnapshotRedisAdapter.getTopStocksByTradeValue(10);

        // then
        assertThat(result).isNotNull();
        assertThat(result).isEmpty();
    }

    // --- Helper Method: Builder 패턴 사용 ---
    private StockPriceRedisEntity createEntity(String code, String name, Long amount, Long volume) {
        return StockPriceRedisEntity.builder()
                .stockCode(code)
                .stockName(name)
                .cumulativeAmount(amount)
                .cumulativeVolume(volume)
                .currentPrice(10000L)
                .priceChange(500L)
                .changeRate(5.0)
                .time("120000")
                .build();
    }
}