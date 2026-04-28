package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.assetmind.server_stock.market_access.application.event.KisWebSocketDisconnectedEvent;
import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties.Account;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisRealTimeData;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.mapper.KisEventMapper;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser.KisRealTimeDataParser;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.io.IOException;
import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith({MockitoExtension.class, OutputCaptureExtension.class})
class KisWebSocketHandlerTest {

    private KisWebSocketHandler handler;

    @Spy
    private ObjectMapper objectMapper; // 실제 JSON 변환 로직 사용

    @Mock
    private WebSocketSession session; // 가짜 세션

    @Mock
    private KisRealTimeDataParser dataParser;

    @Mock
    private KisEventMapper eventMapper;

    @Mock
    private ApplicationEventPublisher eventPublisher;

    @Mock
    private TaskScheduler taskScheduler; // 스케줄러 Mock 추가

    private final String TEST_KEY = "TEST_APP_KEY";
    private final Account TEST_ACCOUNT = new Account("test-app-key", "test-app-secret");
    private final List<String> TEST_CHUNK = List.of("005930", "000660");

    @BeforeEach
    void setUp() {
        // 생성자 직접 주입 방식으로 변경 (POJO)
        handler = new KisWebSocketHandler(
                TEST_KEY,
                TEST_ACCOUNT,
                TEST_CHUNK,
                objectMapper,
                dataParser,
                eventMapper,
                eventPublisher,
                taskScheduler
        );
    }

    @Nested
    @DisplayName("초기 설정 및 구독 요청 테스트")
    class SubscribeNewStock {

        @Test
        @DisplayName("성공: 연결 성공 시 세션 버퍼를 5MB로 늘리고, 대기열의 요청을 스케줄링하여 전송해야 한다")
        void givenNoSession_whenSubscribeNewStock_thenSendAfterConnection() throws Exception {
            // Given: 세션이 없는 상태에서 구독 요청 (setUp에서 2개가 이미 pendingList에 있음)
            List<String> pendingList = (List<String>) ReflectionTestUtils.getField(handler, "pendingSubscriptionList");
            assertThat(pendingList).hasSize(2).contains("005930", "000660");

            // When: 연결 성공 이벤트 발생
            handler.afterConnectionEstablished(session);

            // Then 1: 버퍼 사이즈 5MB 설정 검증
            int expectedBufferSize = 5 * 1024 * 1024;
            verify(session).setTextMessageSizeLimit(expectedBufferSize);
            verify(session).setBinaryMessageSizeLimit(expectedBufferSize);

            // Then 2: TaskScheduler를 통해 2번의 구독 요청이 스케줄링 되었는지 검증
            ArgumentCaptor<Runnable> runnableCaptor = ArgumentCaptor.forClass(Runnable.class);
            verify(taskScheduler, times(2)).schedule(runnableCaptor.capture(), any(Instant.class));

            // 스케줄링된 작업 강제 실행
            when(session.isOpen()).thenReturn(true);
            runnableCaptor.getAllValues().forEach(Runnable::run);

            // Then 3: 최종적으로 메시지가 2번 전송되었는지 확인하고 대기열 비워짐 확인
            verify(session, times(2)).sendMessage(any(TextMessage.class));
            assertThat(pendingList).isEmpty();
        }

        @Test
        @DisplayName("성공: 이미 연결된 상태에서는 대기열 저장 없이 즉시 전송해야 한다")
        void givenSession_whenSubscribeNewStock_thenSendSubscribeRequest() throws Exception {
            // Given: 이미 연결됨
            handler.afterConnectionEstablished(session);
            when(session.isOpen()).thenReturn(true);

            // When
            handler.subscribeNewStock(List.of("035420"));

            // Then: 즉시 전송 확인
            verify(session, times(1)).sendMessage(any(TextMessage.class));
        }
    }

    @Nested
    @DisplayName("실시간 데이터 처리 테스트")
    class RealTimeDataHandling {

        @Test
        @DisplayName("성공: 실시간 데이터 수신 시 파서를 호출하고 데이터를 처리해야 한다")
        void givenRealTimePayload_whenHandleMessage_thenInvokeParser() throws Exception {
            // Given
            String payload = "0|H0STCNT0|001|005930^123000^80000^1^0^2.5^...^100";
            when(dataParser.parse(payload)).thenReturn(List.of(
                    new KisRealTimeData("005930", "123000", 80000L, "1", 0L, 2.5,
                            80000L, 81000L, 79000L, 100L, 1000L, 1000000L, 100.0, "20")
            ));

            // When
            handler.handleMessage(session, new TextMessage(payload));

            // Then
            verify(dataParser, times(1)).parse(payload);
        }
    }

    @Nested
    @DisplayName("예외 처리 및 안전성 테스트")
    class ExceptionHandlingTests {

        @Test
        @DisplayName("실패: JSON 에러 발생 시 시스템이 죽지 않고 로그만 남겨야 한다")
        void givenJsonError_whenSubscribeNewStock_thenNotExitSystem() throws Exception {
            // Given
            handler.afterConnectionEstablished(session);
            when(session.isOpen()).thenReturn(true);

            doThrow(new JsonProcessingException("Mock Error") {})
                    .when(objectMapper).writeValueAsString(any());

            // When & Then
            assertDoesNotThrow(() -> handler.subscribeNewStock(List.of("005930")));
            verify(session, never()).sendMessage(any());
        }

        @Test
        @DisplayName("실패: 전송 IO 에러 발생 시 다음 종목 처리는 계속되어야 한다")
        void givenTransportError_whenSubscribeNewStock_thenNotExitSystem() throws Exception {
            // Given
            handler.afterConnectionEstablished(session);
            when(session.isOpen()).thenReturn(true);

            doThrow(new IOException("Network Error"))
                    .doNothing()
                    .when(session).sendMessage(any(TextMessage.class));

            // When
            handler.subscribeNewStock(List.of("FAIL_STOCK", "SUCCESS_STOCK"));

            // Then
            verify(session, times(2)).sendMessage(any(TextMessage.class));
        }

        @Test
        @DisplayName("성공/실패: 다건 데이터 중 1건 매핑에 실패해도, 나머지는 정상 발행되어야 한다")
        void givenMultipleData_whenOneFails_thenContinuePublishing(CapturedOutput output) throws Exception {
            // Given
            String payload = "0|H0STCNT0|002|MockData...";
            KisRealTimeData successData = new KisRealTimeData("005930", "123000", 80000L, "1", 0L, 2.5,
                    80000L, 81000L, 79000L, 100L, 1000L, 1000000L, 100.0, "20");
            KisRealTimeData failData = new KisRealTimeData("035420", "123000", 80000L, "1", 0L, 2.5,
                    80000L, 81000L, 79000L, 100L, 1000L, 1000000L, 100.0, "20");

            when(dataParser.parse(payload)).thenReturn(List.of(failData, successData));

            RealTimeStockTradeEvent dummyEvent = RealTimeStockTradeEvent.builder().stockCode("005930").build();
            when(eventMapper.toEvent(failData)).thenThrow(new RuntimeException("매핑 도중 에러 발생"));
            when(eventMapper.toEvent(successData)).thenReturn(dummyEvent);

            // When
            assertDoesNotThrow(() -> handler.handleMessage(session, new TextMessage(payload)));

            // Then
            verify(eventPublisher, times(1)).publishEvent(any(RealTimeStockTradeEvent.class));
            assertThat(output.getOut()).contains("매핑 도중 에러 발생");
        }

        @Test
        @DisplayName("실패: 수신 메시지 파싱 중 치명적 에러가 발생해도 세션이 죽지 않아야 한다")
        void givenFatalError_whenHandleMessage_thenCatchAndLog(CapturedOutput output) throws Exception {
            // Given
            String badPayload = "CRITICAL_BAD_PAYLOAD";
            when(dataParser.parse(badPayload)).thenThrow(new NullPointerException("Parser Crashed!"));

            // When
            assertDoesNotThrow(() -> handler.handleMessage(session, new TextMessage(badPayload)));

            // Then
            assertThat(output.getOut()).contains("Parser Crashed!");
        }
    }

    @Nested
    @DisplayName("자원 정리 (Cleanup) 및 재연결 테스트")
    class DisconnectionTests {

        @Test
        @DisplayName("성공: closeConnection 호출 시 세션 종료 및 변수를 초기화한다")
        void whenCloseConnection_thenCleanUpSessionAndFiled() throws Exception {
            // Given
            handler.afterConnectionEstablished(session);
            when(session.isOpen()).thenReturn(true);

            Set<String> stocks = (Set<String>) ReflectionTestUtils.getField(handler, "subscribedStock");
            stocks.add("005930");

            // When
            handler.closeConnection();

            // Then
            verify(session).close(CloseStatus.NORMAL);
            assertThat(ReflectionTestUtils.getField(handler, "currentSession")).isNull();
            assertThat(stocks).isEmpty();
        }

        @Test
        @DisplayName("성공: 서버 에러(비정상 종료)로 연결이 끊어지면 Adapter를 깨우는 재연결 이벤트를 발행해야 한다")
        void whenConnectionClosed_thenPublishDisconnectedEvent() {
            // When
            handler.afterConnectionClosed(session, CloseStatus.SERVER_ERROR);

            // Then
            ArgumentCaptor<KisWebSocketDisconnectedEvent> eventCaptor = ArgumentCaptor.forClass(KisWebSocketDisconnectedEvent.class);
            verify(eventPublisher).publishEvent(eventCaptor.capture());

            KisWebSocketDisconnectedEvent event = eventCaptor.getValue();
            assertThat(event.disconnectedHandler()).isEqualTo(handler);
            assertThat(event.account()).isEqualTo(TEST_ACCOUNT);
            assertThat(event.disconnectedStocks()).isEqualTo(TEST_CHUNK);
        }
    }
}