package com.assetmind.server_stock.stock.presentation;

import com.assetmind.server_stock.stock.application.event.StockHistorySavedEvent;
import com.assetmind.server_stock.stock.application.event.StockRankingUpdatedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class StockWebSocketEventHandler {

    private final SimpMessagingTemplate messagingTemplate;

    /**
     * 상세 페이지용 (차트/호가)
     * - 특정 종목(/topic/stocks/{stockCode}) 구독자에게 전송
     */
    @Async // 별도 스레드에서 실행 (DB 트랜잭션 방해 X)
    @EventListener
    public void handleSavedHistory(StockHistorySavedEvent event) {
        try {
            messagingTemplate.convertAndSend("/topic/stocks/" + event.stockCode(), event.response());
        } catch (Exception e) {
            log.error("[Stock WebSocket Event Handler] 특정 종목 시계열 데이터 전송 에러 : {}", e.getMessage());
        }
    }

    /**
     * 메인 페이지용 (거래대금/거래량 랭킹)
     * - 전체 랭킹(/topic/ranking) 구독자에게 전송
     */
    @Async // 별도 스레드에서 실행 (DB 트랜잭션 방해 X)
    @EventListener
    public void handleUpdatedRanking(StockRankingUpdatedEvent event) {
        try {
            // 메인 차트를 보는 모든 구독자에게 전송하는거라 부하가 생길 가능성이 높음
            // 부하가 생길 경우 0.5 ~ 1초에 한번 전송으로 로직을 구성할 수 있음
            messagingTemplate.convertAndSend("/topic/ranking", event.response());
        } catch (Exception e) {
            log.error("[Stock WebSocket Event Handler] 랭킹 데이터 전송 에러 : {}", e.getMessage());
        }
    }
}
