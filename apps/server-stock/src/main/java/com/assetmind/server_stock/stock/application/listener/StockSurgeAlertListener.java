package com.assetmind.server_stock.stock.application.listener;

import com.assetmind.server_stock.stock.application.StockSurgeAlertService;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

/**
 * 실시간 주가 데이터 이벤트 수신 리스너 클래스(급등락 알림 스로틀링 체크 및 전송)
 *
 * KIS 웹소켓 핸들러에서 발행한 이벤트를 비동기로 수신
 * 수신된 데이터를 기반으로 급등락 알림 스로틀링을 체크하고 전송하는 작업을 위해 Service로 수신한 이벤트를 위임한다.
 *
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class StockSurgeAlertListener {

    private final StockSurgeAlertService stockSurgeAlertService;

    @Async
    @EventListener
    public void handleStockTradeEvent(RealTimeStockTradeEvent event) {
        try {
            stockSurgeAlertService.processSurgeAlert(event);
        } catch (Exception e) {
            log.error("[StockSurgeAlertListener] 급등락 알림 처리 중 에러 발생: {}", event.stockCode(), e);
        }
    }
}
