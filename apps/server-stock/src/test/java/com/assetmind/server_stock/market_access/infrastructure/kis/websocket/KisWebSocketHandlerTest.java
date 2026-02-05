package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.io.IOException;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class KisWebSocketHandlerTest {

    @InjectMocks
    private KisWebSocketHandler handler;

    @Spy
    private ObjectMapper objectMapper; // 실제 JSON 변환 로직 사용

    @Mock
    private WebSocketSession session; // 가짜 세션

    private final String TEST_KEY = "TEST_APP_KEY";

    @BeforeEach
    void setUp() {
        handler.setApproveKey(TEST_KEY);
    }

    @Nested
    @DisplayName("구독 요청 및 버퍼링 테스트")
    class SubscribeNewStock {

        @Test
        @DisplayName("성공: 세션 연결 전 요청은 리스트에 저장되었다가, 연결 후 한꺼번에 전송되어야 한다")
        void givenNoSession_whenSubscribeNewStock_thenSendAfterConnection() throws Exception {
            // Given: 세션이 없는 상태
            List<String> codes = List.of("005930", "000660");

            // When 1: 구독 요청
            handler.subscribeNewStock(codes);

            // Then 1: 세션이 없으니 전송 메서드는 호출되면 안 됨
            verify(session, never()).sendMessage(any());

            // 내부 상태 검증: 대기열에 2개 들어갔는지 확인
            List<String> pendingList = (List<String>) ReflectionTestUtils.getField(handler, "pendingSubscriptionList");
            assertThat(pendingList).hasSize(2).contains("005930", "000660");

            // When 2: 연결 성공 이벤트 발생
            handler.afterConnectionEstablished(session);

            // Then 2: 연결 직후 메시지 2번 전송 확인
            verify(session, times(2)).sendMessage(any(TextMessage.class));
            assertThat(pendingList).isEmpty(); // 대기열은 비워져야 함
        }

        @Test
        @DisplayName("성공: 이미 연결된 상태에서는 대기열 없이 바로 전송해야 한다")
        void givenSession_whenSubscribeNewStock_thenSendSubscribeRequest() throws Exception {
            // Given: 이미 연결됨
            when(session.isOpen()).thenReturn(true);
            handler.afterConnectionEstablished(session);

            // When
            handler.subscribeNewStock(List.of("035420"));

            // Then: 바로 전송 확인
            verify(session, times(1)).sendMessage(any(TextMessage.class));
        }
    }

    @Nested
    @DisplayName("데이터 파싱 테스트")
    class AfterConnectionEstablished {

        @BeforeEach
        void initSession() {
            // 파싱 테스트를 위해 세션 연결 상태 가정
            handler.afterConnectionEstablished(session);
        }

        @Test
        @DisplayName("성공: 일반적인 주식 체결 데이터(Count=1) 파싱")
        void givenNormalStockData_whenHandleMessage_thenParsingPayload() {
            // 0|ID|개수|데이터(종목코드^시간^현재가^...^등락률...)
            String payload = "0|H0STCNT0|001|005930^123000^80000^1^0^2.5^dummy^dummy^dummy^dummy^dummy^dummy^100";

            assertDoesNotThrow(() -> handler.handleMessage(session, new TextMessage(payload)));
            // 로그가 찍히고 에러가 없으면 통과
        }

        @Test
        @DisplayName("성공: 멀티 레코드(Count=2) 데이터 파싱")
        void givenMultiStockData_whenHandleMessage_thenParsingPayload() {
            // 데이터 2건이 이어서 들어옴
            String record1 = "005930^123000^80000^1^0^2.5^d^d^d^d^d^d^100";
            String record2 = "000660^123001^150000^2^0^-1.0^d^d^d^d^d^d^200";
            String payload = "0|H0STCNT0|002|" + record1 + "^" + record2;

            assertDoesNotThrow(() -> handler.handleMessage(session, new TextMessage(payload)));
        }

        @Test
        @DisplayName("성공: 'H' 에러 데이터 (개수 필드 누락) 방어 처리")
        void givenErrorStockData_whenHandleMessage_thenParsingPayload() {
            // 0|ID|데이터 (가운데 개수 필드가 없고 바로 데이터가 옴) -> parts[2]가 숫자가 아님
            // "H" 에러 유발 케이스
            String payload = "0|H0STCNT0|005930^123000^80000^1^0^2.5^d^d^d^d^d^d^100";

            assertDoesNotThrow(() -> handler.handleMessage(session, new TextMessage(payload)));
            // NumberFormatException 없이 정상 처리되어야 함
        }

        @Test
        @DisplayName("성공: JSON 제어 메시지 (PINGPONG 등) 처리")
        void givenJsonOperatorData_whenHandleMessage_thenParsingPayload() {
            String jsonPayload = "{\"header\":{\"tr_id\":\"PINGPONG\"}}";
            assertDoesNotThrow(() -> handler.handleMessage(session, new TextMessage(jsonPayload)));
        }
    }

    @Nested
    @DisplayName("예외 처리 및 안전성 테스트")
    class ExceptionHandlingTests {

        @Test
        @DisplayName("실패: JSON 에러, 객체 변환 실패 시 시스템이 죽지 않고 로그만 남겨야 한다")
        void givenJsonError_whenSubscribeNewStock_thenNotExitSystem() throws Exception {
            // Given: 연결된 상태
            handler.afterConnectionEstablished(session);
            when(session.isOpen()).thenReturn(true);

            // Mock: ObjectMapper가 에러를 뱉도록 설정
            doThrow(new JsonProcessingException("Mock Error") {})
                    .when(objectMapper).writeValueAsString(any());

            // When & Then
            assertDoesNotThrow(() -> handler.subscribeNewStock(List.of("005930")));
            // 에러를 catch 했으므로 전송은 안 됨
            verify(session, never()).sendMessage(any());
        }

        @Test
        @DisplayName("실패: 전송에러, IO 예외 발생 시 다음 종목 처리는 계속되어야 한다")
        void givenTransportError_whenSubscribeNewStock_thenNotExitSystem() throws Exception {
            // Given
            handler.afterConnectionEstablished(session);
            when(session.isOpen()).thenReturn(true);

            // Mock: 첫 번째 전송에서 IO 에러 발생
            doThrow(new IOException("Network Error"))
                    .doNothing() // 두 번째는 성공
                    .when(session).sendMessage(any(TextMessage.class));

            // When: 2개 종목 구독
            handler.subscribeNewStock(List.of("FAIL_STOCK", "SUCCESS_STOCK"));

            // Then: 반복문이 멈추지 않고 2번 모두 시도했는지 확인
            verify(session, times(2)).sendMessage(any(TextMessage.class));
        }
    }

    @Nested
    @DisplayName("자원 정리 (Cleanup) 테스트")
    class CloseConnection {

        @Test
        @DisplayName("성공: closeConnection 호출 시 세션 종료 및 변수 초기화한다.")
        void whenCloseConnection_thenCleanUpSessionAndFiled() throws Exception {
            // Given
            when(session.isOpen()).thenReturn(true);
            handler.afterConnectionEstablished(session);

            // 구독 데이터 강제 주입
            Set<String> stocks = (Set<String>) ReflectionTestUtils.getField(handler, "subscribedStock");
            stocks.add("005930");

            // When
            handler.closeConnection();

            // Then 1: 세션 close 호출 확인
            verify(session).close(CloseStatus.NORMAL);

            // Then 2: 내부 변수 초기화 확인 (Finally 블록)
            Object currentSession = ReflectionTestUtils.getField(handler, "currentSession");
            assertThat(currentSession).isNull();
            assertThat(stocks).isEmpty();
        }

        @Test
        @DisplayName("성공: 종료 중 에러가 발생해도 자원 정리는 수행되어야 한다")
        void givenCloseError_whenCloseConnection_thenCleanUpSessionAndFiled() throws Exception {
            // Given
            when(session.isOpen()).thenReturn(true);
            handler.afterConnectionEstablished(session);

            // close 호출 시 에러 발생
            doThrow(new IOException("Close Error")).when(session).close(any());

            // When
            assertDoesNotThrow(() -> handler.closeConnection());

            // Then: 에러가 났어도 변수는 비워져야 함 (Finally 검증)
            Object currentSession = ReflectionTestUtils.getField(handler, "currentSession");
            assertThat(currentSession).isNull();
        }
    }
}