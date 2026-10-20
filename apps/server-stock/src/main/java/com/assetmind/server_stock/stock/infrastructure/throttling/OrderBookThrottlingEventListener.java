package com.assetmind.server_stock.stock.infrastructure.throttling;

import com.assetmind.server_stock.market_access.domain.event.OrderBookReceivedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * KIS에서 발행된 OrderReceivedEvent(호가 데이터 이벤트)를 캐치해서
 * OrderBookCacheRepository에 저장해주는 중간 역할
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OrderBookThrottlingEventListener {
    private final OrderBookCacheRepository cacheRepository;

    /**
     * KIS 웹소켓 핸들러에서 발행한 호가 수신 이벤트를 감지하여
     * OrderBookCacheRepository 캐시 저장소에 데이터를 저장
     * @param event
     */
    @EventListener
    public void onOrderBookReceived(OrderBookReceivedEvent event) {
        cacheRepository.save(event.orderBook());
    }
}
