package com.assetmind.server_stock.stock.application.mapper;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.RawTickJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import org.springframework.stereotype.Component;

/**
 * 주가 데이터 이벤트 DTO를 저장소(JPA, Redis)에 쓰이는 Entity로 매핑한다. 또는
 * 역으로 매핑한다.
 *
 * 1. event -> entity
 */
@Component
public class StockMapper {

    private static final DateTimeFormatter TIME_FORMATTER = DateTimeFormatter.ofPattern("HHmmss");

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

    public RawTickJpaEntity toJpaEntity(RealTimeStockTradeEvent event) {

        LocalTime parsedTime = LocalTime.parse(event.time(), TIME_FORMATTER);

        return RawTickJpaEntity.builder()
                .stockCode(event.stockCode())
                .tradeTimestamp(LocalDateTime.of(LocalDate.now(), parsedTime))
                .currentPrice(Double.valueOf(String.valueOf(event.currentPrice())))
                .priceChange(Double.valueOf(String.valueOf(event.priceChange())))
                .volume(event.executionVolume())
                .build();
    }
}
