package com.assetmind.server_stock.stock.application;

import static org.mockito.BDDMockito.*;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.application.port.AlertMessagingPort;
import com.assetmind.server_stock.stock.application.port.AlertThrottlingPort;
import org.assertj.core.api.Assertions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;

@ExtendWith({MockitoExtension.class, OutputCaptureExtension.class})
class StockSurgeAlertServiceTest {

    @InjectMocks
    private StockSurgeAlertService service;

    @Mock
    private AlertMessagingPort messagingPort;

    @Mock
    private AlertThrottlingPort throttlingPort;

    @Test
    @DisplayName("성공(알림 발송): 등락률이 10% 이상이고 스로틀링이 허용되면 알림을 발송한다.")
    void givenOverPlus10PercentEvent_whenProcessSurgeAlert_thenSendSurgeAlert(CapturedOutput output) {
        // given
        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .changeRate(11.0)
                .currentPrice(210000L)
                .build();
        when(throttlingPort.allowAlert(event.stockCode())).thenReturn(true);

        // when
        service.processSurgeAlert(event);

        // then
        // 쓰로틀링 체크 검증
        verify(throttlingPort, times(1)).allowAlert(event.stockCode());

        // 알림 발송 검증
        verify(messagingPort, times(1)).send(event, "급등");

        // 로깅 검증
        Assertions.assertThat(output.getOut())
                .contains("[StockSurgeAlertService]");
    }

    @Test
    @DisplayName("성공(알림 발송): 등락률이 -10% 이하이고 스로틀링이 허용되면 알림을 발송한다.")
    void givenUnderMinus10PercentEvent_whenProcessSurgeAlert_thenSendSurgeAlert() {
        // given
        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .changeRate(-11.0)
                .currentPrice(190000L)
                .build();
        when(throttlingPort.allowAlert(event.stockCode())).thenReturn(true);

        // when
        service.processSurgeAlert(event);

        // then
        verify(throttlingPort, times(1)).allowAlert(event.stockCode());
        verify(messagingPort, times(1)).send(event, "급락");
    }

    @Test
    @DisplayName("실패(알림 미발송): 등락률이 존재하지 않다면 알림을 발송하지 않는다.")
    void givenNullChangeRate_whenProcessSurgeAlert_thenReturnAnything() {
        // given
        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .changeRate(null)
                .build();

        // when
        service.processSurgeAlert(event);

        // then
        verify(throttlingPort, never()).allowAlert(event.stockCode());
        verify(messagingPort, never()).send(event, "");
    }

    @Test
    @DisplayName("실패(알림 미발송): 등락률이 절댓값 10% 미만이라면 알림을 발송하지 않는다.")
    void givenUnder10PercentChangeRate_whenProcessSurgeAlert_thenReturnAnything() {
        // given
        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .changeRate(1.0)
                .build();

        // when
        service.processSurgeAlert(event);

        // then
        verify(throttlingPort, never()).allowAlert(event.stockCode());
        verify(messagingPort, never()).send(event, "");
    }

    @Test
    @DisplayName("실패(알림 미발송): 등락률이 절댓값 10% 이상이지만 스로틀링이 허용되지 않으면 알림을 발송하지 않는다.")
    void givenThrottlingIsFalse_whenProcessSurgeAlert_thenReturnAnything() {
        // given
        RealTimeStockTradeEvent event = RealTimeStockTradeEvent.builder()
                .stockCode("005930")
                .changeRate(11.0)
                .build();
        when(throttlingPort.allowAlert(event.stockCode())).thenReturn(false);

        // when
        service.processSurgeAlert(event);

        // then
        verify(throttlingPort, times(1)).allowAlert(event.stockCode());
        verify(messagingPort, never()).send(event, "");
    }
}