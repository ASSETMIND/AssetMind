package com.assetmind.server_stock.stock.infrastructure.throttling;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Repository;

/**
 * KIS에서 실시간으로 받는 호가 데이터를 인메모리에 저장하는 저장소
 */
@Repository
public class OrderBookCacheRepository {
    // Key - 종목코드, Value - CachedOrderBook
    private final Map<String, CachedOrderBook> cacheMap = new ConcurrentHashMap<>();

    /**
     * KIS 실시간 호가 데이터가 유입되면 호출되는 메서드
     * 최신 데이터로 덮어쓰고 Flag를 true로 변경
     */
    public void save(OrderBook orderBook) {
        cacheMap.compute(orderBook.stockCode(), (code, existingCache) -> {
            if (existingCache == null) {
                return new CachedOrderBook(orderBook);
            } else {
                existingCache.update(orderBook);
                return existingCache;
            }
        });
    }

    /**
     * 현재 캐싱되어 관리되고 있는 모든 종목 코드 목록을 반환
     */
    public Set<String> getAllStockCodes() {
        return cacheMap.keySet();
    }

    /**
     * 스케줄러가 호출할 메서드
     * 변경 사항이 있는 종목이라면 최신 데이터를 반환하고 동시에 flag를 초기화
     */
    public OrderBook getIfDirtyAndClean(String stockCode) {
        CachedOrderBook cached = cacheMap.get(stockCode);
        if (cached != null && cached.isDirty()) {
            return cached.getOrderBookAndClean();
        }
        return null;
    }
}
