package com.assetmind.server_stock.stock.integration;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.BDDMockito.*;
import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisRealTimeData;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.KisWebSocketHandler;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.mapper.KisEventMapper;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser.KisRealTimeDataParser;
import com.assetmind.server_stock.stock.application.StockService;
import com.assetmind.server_stock.stock.application.listener.StockTradeEventListener;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.jackson.JacksonAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.web.socket.TextMessage;

@ExtendWith(OutputCaptureExtension.class)
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

    @MockitoBean
    private StockService stockService;

    @Test
    @DisplayName("성공: 이벤트 테스트용 컨텍스트에서 이벤트 발행 및 수신 검증")
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

    @Test
    @DisplayName("실패: 서비스 계층에서 예외가 발생해도 리스너가 스레드를 보호하고 로그를 남긴다.")
    void givenServiceException_whenHandleEvent_thenCatchAndLogError(CapturedOutput output) {
        // given: 임의의 실시간 체결 이벤트 생성
        RealTimeStockTradeEvent dummyEvent = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .currentPrice(80000L)
                .changeSign("3") // 보합 기호
                .build();

        // Mocking: 서비스 계층에서 DB 타임아웃 등의 치명적 에러가 터졌다고 가정
        doThrow(new RuntimeException("DB Connection Timeout!"))
                .when(stockService).processRealTimeTrade(any(RealTimeStockTradeEvent.class));

        // when & then 1: 예외가 리스너 밖으로 새어나가지 않는지 검증 (스레드 생존 검증)
        assertDoesNotThrow(() -> eventListener.handleStockTradeEvent(dummyEvent));

        // when & then 2: 캡처된 로그(output)에 의도한 ERROR 로그가 찍혔는지 검증
        assertThat(output.getOut())
                .contains("[Stock Trade Event] 처리 중 에러 발생")
                .contains("DB Connection Timeout!");
    }

}
