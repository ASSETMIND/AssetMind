package com.assetmind.server_stock.stock.infrastructure.throttling;

import static org.mockito.Mockito.*;

import com.assetmind.server_stock.market_access.domain.OrderBook;
import com.assetmind.server_stock.market_access.domain.event.OrderBookReceivedEvent;
import java.time.LocalTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class OrderBookThrottlingEventListenerTest {

    @InjectMocks
    private OrderBookThrottlingEventListener eventListener;

    @Mock
    private OrderBookCacheRepository cacheRepository;

    @Test
    @DisplayName("호가 수신 이벤트가 발생하면 캐시 저장소의 save 메서드가 호출된다.")
    void givenReceivedOrderBookEvent_whenOnOrderBookReceived_thenCallSaveMethod() {
        // given
        String stockCode = "005930";
        OrderBook dummyOrderBook = createDummyOrderBook(stockCode);
        OrderBookReceivedEvent event = new OrderBookReceivedEvent(dummyOrderBook);

        // when
        eventListener.onOrderBookReceived(event);

        // then
        verify(cacheRepository, times(1)).save(dummyOrderBook);
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
