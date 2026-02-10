package com.assetmind.server_stock.market_access.infrastructure.kis.websocket.mapper;

import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisRealTimeData;
import com.assetmind.server_stock.stock.application.listner.dto.RealTimeStockTradeEvent;
import java.time.LocalDateTime;
import org.springframework.stereotype.Component;

@Component
public class KisEventMapper {

    public RealTimeStockTradeEvent toEvent(KisRealTimeData data) {
        return RealTimeStockTradeEvent.builder()
                .stockCode(data.stockCode())
                .time(data.executionTime())
                .currentPrice(data.currentPrice())
                .priceChange(data.priceChange())
                .changeSign(data.changeSign())
                .executionVolume(data.executionVolume())
                .cumulativeAmount(data.cumulativeAmount())
                .cumulativeVolume(data.cumulativeVolume())
                .eventTimeStamp(LocalDateTime.now())
                .build();
    }
}
