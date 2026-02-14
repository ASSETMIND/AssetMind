package com.assetmind.server_stock.stock.presentation;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.BDDMockito.*;

import com.assetmind.server_stock.stock.application.event.StockHistorySavedEvent;
import com.assetmind.server_stock.stock.application.event.StockRankingUpdatedEvent;
import com.assetmind.server_stock.stock.presentation.dto.StockHistoryResponse;
import com.assetmind.server_stock.stock.presentation.dto.StockRankingResponse;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.messaging.MessagingException;
import org.springframework.messaging.simp.SimpMessagingTemplate;

@ExtendWith(MockitoExtension.class)
class StockWebSocketEventHandlerTest {

    @Mock
    private SimpMessagingTemplate messagingTemplate;

    @InjectMocks
    private StockWebSocketEventHandler stockWebSocketEventHandler;

    @Test
    @DisplayName("성공: StockHistorySavedEvent를 받으면 해당 종목의 토픽 구독자에게 데이터를 전송한다.")
    void givenStockHistorySavedEvent_whenHandleSavedHistory_thenSendDataToSubscriber() {
        // given
        String stockCode = "005930";
        StockHistoryResponse mockHistoryResponse = StockHistoryResponse.builder()
                .stockCode(stockCode)
                .build();

        StockHistorySavedEvent historyEvent = new StockHistorySavedEvent(stockCode,
                mockHistoryResponse);

        // when
        stockWebSocketEventHandler.handleSavedHistory(historyEvent);

        // then
        // handleSavedHistory 메서드 수행 시, 정의된 토픽으로 한번 호출 되는지 확인
        verify(messagingTemplate, times(1))
                .convertAndSend(eq("/topic/stocks/" + stockCode), eq(mockHistoryResponse));
    }

    @Test
    @DisplayName("실패: StockHistorySavedEvent를 받고 데이터를 전송 중 예외가 발생해도 프로세스가 중단되지 않고 로그를 남기고 종료한다.")
    void givenStockHistorySavedEvent_whenOccurErrorInSending_thenNotThrowExceptionLogging() {
        // given
        String stockCode = "005930";
        StockHistoryResponse mockHistoryResponse = StockHistoryResponse.builder()
                .stockCode(stockCode)
                .build();

        StockHistorySavedEvent historyEvent = new StockHistorySavedEvent(stockCode,
                mockHistoryResponse);

        willThrow(new MessagingException("WebSocket 전송 실패"))
                .given(messagingTemplate)
                .convertAndSend(any(String.class), any(Object.class));

        // when & then
        // handleSavedHistory 메서드 수행 도중 예외가 밖으로 던져지지 않았는지 검증
        assertThatCode(() -> stockWebSocketEventHandler.handleSavedHistory(historyEvent))
                .doesNotThrowAnyException();
    }

    @Test
    @DisplayName("성공: StockRankingUpdatedEvent를 받으면 해당 종목의 토픽 구독자에게 데이터를 전송한다.")
    void givenStockRankingUpdatedEvent_whenHandleUpdatedRanking_thenSendDataToSubscriber() {
        // given
        String stockCode = "005930";
        StockRankingResponse mockRankingResponse = StockRankingResponse.builder()
                .stockCode(stockCode)
                .build();

        StockRankingUpdatedEvent rankingUpdatedEvent = new StockRankingUpdatedEvent(
                mockRankingResponse);

        // when
        stockWebSocketEventHandler.handleUpdatedRanking(rankingUpdatedEvent);

        // then
        // handleUpdatedRanking 메서드 수행 시, 정의된 토픽으로 한번 호출 되는지 확인
        verify(messagingTemplate, times(1))
                .convertAndSend(eq("/topic/ranking"), eq(mockRankingResponse));
    }

    @Test
    @DisplayName("실패: StockRankingUpdatedEvent를 받고 데이터를 전송 중 예외가 발생해도 프로세스가 중단되지 않고 로그를 남기고 종료한다.")
    void givenStockRankingUpdatedEvent_whenOccurErrorInSending_thenNotThrowExceptionLogging() {
        // given
        String stockCode = "005930";
        StockRankingResponse mockRankingResponse = StockRankingResponse.builder()
                .stockCode(stockCode)
                .build();

        StockRankingUpdatedEvent rankingUpdatedEvent = new StockRankingUpdatedEvent(
                mockRankingResponse);

        // when & then
        // handleUpdatedRanking 메서드 수행 도중 예외가 밖으로 던져지지 않았는지 검증
        assertThatCode(() -> stockWebSocketEventHandler.handleUpdatedRanking(rankingUpdatedEvent))
                .doesNotThrowAnyException();
    }
}