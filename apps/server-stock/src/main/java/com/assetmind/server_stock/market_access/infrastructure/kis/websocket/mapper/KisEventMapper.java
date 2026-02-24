package com.assetmind.server_stock.market_access.infrastructure.kis.websocket.mapper;

import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisRealTimeData;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import java.time.LocalDateTime;
import org.springframework.stereotype.Component;

@Component
public class KisEventMapper {

    public RealTimeStockTradeEvent toEvent(KisRealTimeData data) {
        return RealTimeStockTradeEvent.builder()
                .stockCode(data.stockCode())
                .time(data.executionTime())

                // --- 가격 정보 ---
                .currentPrice(data.currentPrice())
                .openPrice(data.openPrice())
                .highPrice(data.highPrice())
                .lowPrice(data.lowPrice())
                .priceChange(data.priceChange())
                .changeSign(data.changeSign())
                .changeRate(data.changeRate())

                // --- 거래량 정보 ---
                .executionVolume(data.executionVolume())
                .cumulativeAmount(data.cumulativeAmount())
                .cumulativeVolume(data.cumulativeVolume())

                .eventTimeStamp(LocalDateTime.now())
                .build();
    }
}
