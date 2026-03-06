package com.assetmind.server_stock.stock.presentation;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.presentation.dto.StockSurgeAlertResponse;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.messaging.simp.SimpMessagingTemplate;

@ExtendWith(MockitoExtension.class)
class StompAlertMessagingAdapterTest {

    @Mock
    private SimpMessagingTemplate messagingTemplate;

    @InjectMocks
    private StompAlertMessagingAdapter adapter;

    @Test
    @DisplayName("성공: Event 객체를 Response DTO로 매핑하여 STOMP로 브로드캐스트 한다.")
    void givenEvent_whenSend_thenBroadcast() {
        // given
        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .currentPrice(80000L)
                .changeRate(10.5)
                .build();
        String trend = "급등";

        // when
        adapter.send(event, trend);

        // then
        // STOMP로 쏜 객체를 낚아채서(Capture) 값 검증
        ArgumentCaptor<StockSurgeAlertResponse> captor = ArgumentCaptor.forClass(StockSurgeAlertResponse.class);
        verify(messagingTemplate).convertAndSend(eq("/topic/surge-alerts"), captor.capture());

        StockSurgeAlertResponse sentResponse = captor.getValue();
        assertEquals("005930", sentResponse.stockCode());
        assertEquals("급등", sentResponse.rate());
        assertEquals(80000L, sentResponse.currentPrice());
        assertEquals(10.5, sentResponse.changeRate());
        assertNotNull(sentResponse.alertTime());
    }
}