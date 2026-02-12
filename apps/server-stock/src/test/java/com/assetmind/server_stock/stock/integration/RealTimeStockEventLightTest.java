package com.assetmind.server_stock.stock.integration;

import static org.mockito.BDDMockito.*;
import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisRealTimeData;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.KisWebSocketHandler;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.mapper.KisEventMapper;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser.KisRealTimeDataParser;
import com.assetmind.server_stock.stock.application.listener.StockTradeEventListener;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.jackson.JacksonAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.web.socket.TextMessage;

@SpringBootTest(classes = {
        KisWebSocketHandler.class,          // 발행자
        StockTradeEventListener.class,      // 수신자
        KisEventMapper.class,               // 매퍼
        KisRealTimeDataParser.class,
        JacksonAutoConfiguration.class
})
public class RealTimeStockEventLightTest {

    @Autowired
    private KisWebSocketHandler webSocketHandler;

    @MockitoSpyBean
    private StockTradeEventListener eventListener;

    @MockitoBean
    private KisRealTimeDataParser parser;

    @Test
    @DisplayName("이벤트 테스트용 컨텍스트에서 이벤트 발행 및 수신 검증")
    void givenStockData_whenPublishEvent_thenSubscribeEvent() throws Exception {
        // given
        KisRealTimeData mockData = KisRealTimeData.builder()
                .stockCode("005930")
                .executionTime("10000")
                .currentPrice(160000L)
                .changeSign("1")
                .priceChange(-500L)
                .changeRate(-1.0)
                .executionVolume(10L)
                .cumulativeVolume(100L)
                .cumulativeAmount(16000000L)
                .build();

        given(parser.parse(anyString())).willReturn(List.of(mockData));

        // when: Kis에서 실시간 주가 데이터 수신 상황 구성
        webSocketHandler.handleMessage(null, new TextMessage("Payload From KIS"));

        // then: 리스너 수신 확인
        ArgumentCaptor<RealTimeStockTradeEvent> captor = ArgumentCaptor.forClass(RealTimeStockTradeEvent.class);

        // 리스너가 호출되었는지 확인
        verify(eventListener).handleStockTradeEvent(captor.capture());

        // 데이터 검증
        RealTimeStockTradeEvent event = captor.getValue();
        assertThat(event.stockCode()).isEqualTo("005930");
        assertThat(event.changeSign()).isEqualTo("1");

    }

}
