package com.assetmind.server_stock.stock.infrastructure.throttling;

import static org.mockito.BDDMockito.*;
import static org.mockito.Mockito.*;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import java.time.LocalTime;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.BDDMockito;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.messaging.simp.SimpMessagingTemplate;

@ExtendWith(MockitoExtension.class)
class OrderBookThrottlingSchedulerTest {

    @InjectMocks
    private OrderBookThrottlingScheduler scheduler;

    @Mock
    private OrderBookCacheRepository cacheRepository;

    @Mock
    private SimpMessagingTemplate messagingTemplate;

    @Test
    @DisplayName("캐시 저장소에 flag가 ture인 종목이 있다면, 해당 종목만 STOMP 채널로 발송한다.")
    void givenUpdatedOrderBook_whenFlushUpdatedOrderBooks_thenBroadcastTargetStocks() {
        // given
        String updatedStockCode = "005930";
        String stockCode = "000660";
        OrderBook updatedOrderBook = createDummyOrderBook(updatedStockCode);

        // 캐시 저장소에 두 종목이 있다고 가정
        given(cacheRepository.getAllStockCodes()).willReturn(Set.of(updatedStockCode, stockCode));

        // Updated된 종목은 데이터를 반환하고, clean 종목은 null을 반환한다고 가정
        given(cacheRepository.getIfDirtyAndClean(updatedStockCode)).willReturn(updatedOrderBook);
        given(cacheRepository.getIfDirtyAndClean(stockCode)).willReturn(null);

        // when
        scheduler.flushUpdatedOrderBooks();

        // then
        verify(messagingTemplate).convertAndSend("/topic/orderbook/" + updatedStockCode, updatedOrderBook);
        verify(messagingTemplate, never()).convertAndSend(eq("/topic/orderbook/" + stockCode),
                Optional.ofNullable(any()));
    }

    private OrderBook createDummyOrderBook(String stockCode) {
        return OrderBook.builder().
                stockCode(stockCode)
                .marketTime(LocalTime.now())
                .totalBidSize(100L)
                .totalAskSize(100L)
                .levels(List.of())
                .build();
    }
}
