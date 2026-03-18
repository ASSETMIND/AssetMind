package com.assetmind.server_stock.stock.presentation;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.application.port.AlertMessagingPort;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.stock.presentation.dto.StockSurgeAlertResponse;
import java.time.LocalDateTime;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;

/**
 * {@link AlertMessagingPort}에 대한 구현체(Adapter)로 써
 * STOMP를 이용하여 급등락 알림을 전송
 */
@Component
@RequiredArgsConstructor
public class StompAlertMessagingAdapter implements AlertMessagingPort {

    private final SimpMessagingTemplate messagingTemplate;
    private final StockMetadataProvider provider;

    @Override
    public void send(RealTimeStockTradeEvent event, String rate) {
        StockSurgeAlertResponse response = StockSurgeAlertResponse.builder()
                .stockCode(event.stockCode())
                .stockName(provider.getStockName(event.stockCode()))
                .rate(rate)
                .currentPrice(String.valueOf(event.currentPrice()))
                .changeRate(String.valueOf(event.changeRate()))
                .alertTime(LocalDateTime.now())
                .build();
        messagingTemplate.convertAndSend("/topic/surge-alerts", response);
    }
}
