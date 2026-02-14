package com.assetmind.server_stock.stock.application.mapper;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import org.springframework.stereotype.Component;

/**
 * 주가 데이터 이벤트 DTO를 저장소(JPA, Redis)에 쓰이는 Entity로 매핑한다. 또는
 * 역으로 매핑한다.
 *
 * 1. event -> entity
 */
@Component
public class StockMapper {

    public StockPriceRedisEntity toRedisEntity(RealTimeStockTradeEvent event, String stockName) {
        return StockPriceRedisEntity.builder()
                .stockCode(event.stockCode())
                .stockName(stockName)
                .currentPrice(event.currentPrice())
                .priceChange(event.priceChange())
                .changeRate(event.changeRate())
                .changeSign(event.changeSign())
                .cumulativeAmount(event.cumulativeAmount())
                .cumulativeVolume(event.cumulativeVolume())
                .time(event.time())
                .build();
    }

    public StockDataEntity toJpaEntity(RealTimeStockTradeEvent event) {
        return StockDataEntity.builder()
                .stockCode(event.stockCode())
                .currentPrice(event.currentPrice())
                .openPrice(event.openPrice())
                .highPrice(event.highPrice())
                .lowPrice(event.lowPrice())
                .priceChange(event.priceChange())
                .changeRate(event.changeRate())
                .executionVolume(event.executionVolume())
                .tradingVolume(event.cumulativeVolume())
                .tradingAmount(event.cumulativeAmount())
                .time(event.time())
                .createdAt(event.eventTimeStamp())
                .build();
    }
}
