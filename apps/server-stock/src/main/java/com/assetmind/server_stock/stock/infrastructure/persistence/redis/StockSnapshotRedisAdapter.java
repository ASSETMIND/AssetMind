package com.assetmind.server_stock.stock.infrastructure.persistence.redis;

import com.assetmind.server_stock.stock.domain.repository.StockSnapshotRepository;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

/**
 * {@link StockSnapshotRepository}를 Redis 기술을 사용하여 구현한 구현체
 */
@Repository
@RequiredArgsConstructor
public class StockSnapshotRedisAdapter implements StockSnapshotRepository {

    // 기본 CRUD (Hash 저장용)
    private final StockPriceRedisRepository redisRepository;

    // 랭킹 연산 (Sorted Set용)
    // StockPriceRedisRepository는 CrudRepository를 상속받았기 때문에 Redis의 Sorted Set 기능을 지원하지 않음
    // 그래서 따로 랭킹을 저장하기 위한 Redis Template가 필요함
    private final StringRedisTemplate redisTemplate;

    // 누적거래대금 랭킹을 위한 Key
    private static final String RANKING_TRADE_VALUE_KEY = "ranking:trade_value";
    // 누적거래량 랭킹을 위한 Key
    private static final String RANKING_TRADE_VOLUME_KEY = "ranking:trade_volume";


    @Override
    public void save(StockPriceRedisEntity entity) {
        // 실시간 주가 데이터 스냅샷 저장
        redisRepository.save(entity);

        // 거래대금 랭킹 업데이트
        // Key: ranking:trade_value, Value: 종목코드, Score: 누적거래대금
        if (entity.getCumulativeAmount() != null) {
            redisTemplate.opsForZSet().add(RANKING_TRADE_VALUE_KEY, entity.getStockCode(), entity.getCumulativeAmount());
        }

        // 거래량 랭킹 업데이트
        // Key: ranking:trade_volume, Value: 종목코드, Score: 누적거래량
        if (entity.getCumulativeVolume() != null) {
            redisTemplate.opsForZSet().add(RANKING_TRADE_VOLUME_KEY, entity.getStockCode(), entity.getCumulativeVolume());
        }
    }

    @Override
    public List<StockPriceRedisEntity> getTopStocksByTradeValue(int limit) {
        // ZSET에서 Score(누적거래대금)이 높은 순으로 상위 N개 레코드 조회
        // reverseRange: 내림차순
        Set<String> topRecords = redisTemplate.opsForZSet()
                .reverseRange(RANKING_TRADE_VALUE_KEY, 0, limit - 1);

        if (topRecords == null || topRecords.isEmpty()) {
            return Collections.emptyList();
        }

        // 조회된 상위 N개 주식 코드로 주식 상세 조회
        Iterable<StockPriceRedisEntity> entities = redisRepository.findAllById(topRecords);

        List<StockPriceRedisEntity> resultList = new ArrayList<>();
        entities.forEach(resultList::add);

        // 랭킹 순서에 맞게 재정렬
        resultList.sort((a, b) -> {
            long valA = a.getCumulativeAmount() == null ? 0 : a.getCumulativeAmount();
            long valB = b.getCumulativeAmount() == null ? 0 : b.getCumulativeAmount();
            return Long.compare(valB, valA);
        });

        return resultList;
    }

    @Override
    public List<StockPriceRedisEntity> getTopStocksByTradeVolume(int limit) {
        // ZSET에서 Score(누적거래량)이 높은 순으로 상위 N개 레코드 조회
        Set<String> topRecords = redisTemplate.opsForZSet()
                .reverseRange(RANKING_TRADE_VOLUME_KEY, 0, limit - 1);

        if (topRecords == null || topRecords.isEmpty()) {
            return Collections.emptyList();
        }

        Iterable<StockPriceRedisEntity> entities = redisRepository.findAllById(topRecords);
        List<StockPriceRedisEntity> resultList = new ArrayList<>();
        entities.forEach(resultList::add);

        // 랭킹 순서에 맞게 재정렬
        resultList.sort((a, b) -> {
            long valA = a.getCumulativeVolume() == null ? 0 : a.getCumulativeVolume();
            long valB = b.getCumulativeVolume() == null ? 0 : b.getCumulativeVolume();
            return Long.compare(valB, valA);
        });

        return resultList;
    }
}
