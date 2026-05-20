package com.assetmind.server_stock.stock.infrastructure.throttling;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 0.5초마다 저장소를 스캔하고 변경된 종목만 STOMP 채널로 브로드캐스팅 하는 스케줄러
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OrderBookThrottlingScheduler {
    private final OrderBookCacheRepository cacheRepository;
    private final SimpMessagingTemplate messagingTemplate;

    /**
     * 0.5초 주기로 계속 반복 실행되는 쓰로틀링
     */
    @Scheduled(fixedRate = 500)
    public void flushUpdatedOrderBooks() {
        long startTime = System.currentTimeMillis();
        int flushCount = 0;

        // 현재 인메모리 캐시에 등록된 모든 종목 코드를 순회
        for (String stockCode : cacheRepository.getAllStockCodes()) {
            // flag가 true인(최신 데이터가 변경된) 종목을 가져오고 flag를 false로 초기화
            OrderBook snapshot = cacheRepository.getIfDirtyAndClean(stockCode);

            // 최신 데이터가 변경된 데이터라면 프론트엔드로 전송
            if (snapshot != null) {
                String destination = "/topic/orderbook/" + stockCode;
                messagingTemplate.convertAndSend(destination, snapshot);
                flushCount++;
            }
        }

        // 모니터링 목적의 디버그 로그
        if (flushCount > 0) {
            log.debug("[OrderBookThrottlingScheduler] flush 완료 -> 대상: {}개 종목, 소요 시간: {}ms",
                    flushCount, (System.currentTimeMillis() - startTime));
        }
    }
}
