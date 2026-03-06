package com.assetmind.server_stock.stock.application.listener;

import static org.assertj.core.api.Assertions.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.BDDMockito.*;
import static org.mockito.Mockito.*;

import com.assetmind.server_stock.stock.application.StockSurgeAlertService;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import org.assertj.core.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.BDDMockito;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;

@ExtendWith({MockitoExtension.class, OutputCaptureExtension.class})
class StockSurgeAlertListenerTest {

    @InjectMocks
    private StockSurgeAlertListener listener;

    @Mock
    private StockSurgeAlertService service;

    @Test
    @DisplayName("성공: 성공적으로 이벤트를 수신 시 Service로 event 처리 로직을 정상적으로 위임한다.")
    void givenEvent_whenHandleStockTradeEvent_thenDelegateProcessToService() {
        // given
        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .changeRate(13.0)
                .build();

        // when
        listener.handleStockTradeEvent(event);

        // then
        verify(service, times(1)).processSurgeAlert(event);
    }

    @Test
    @DisplayName("실패: Service 에서 event 처리 중 예외가 발생해도 리스너가 예외를 잡아서 로깅한다.")
    void givenService_whenHandleStockTradeEvent_thenLoggingException(CapturedOutput output) {
        // 실제로는 서비스에서 예외를 던지는 코드가 존재하지 않지만,
        // Service가 호출하는 Infra 영역의 예상치 못한 런타임 예외(Redis 서버 다운, STOMP 장애 등)에도 로깅하는지 검증

        // given
        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .changeRate(13.0)
                .build();

        doThrow(new RuntimeException("Test Exception")).when(service).processSurgeAlert(event);

        // when & then
        listener.handleStockTradeEvent(event);
        verify(service, times(1)).processSurgeAlert(event);

        // 로깅 검증
        assertThat(output.getOut())
                .contains("[StockSurgeAlertListener] 급등락 알림 처리 중 에러 발생");
    }
}