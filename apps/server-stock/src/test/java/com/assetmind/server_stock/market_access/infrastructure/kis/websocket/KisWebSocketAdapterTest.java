package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.client.WebSocketClient;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ScheduledFuture;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class KisWebSocketAdapterTest {

    private KisWebSocketAdapter adapter; // 테스트 대상

    @Mock
    private KisWebSocketHandler handler;

    @Mock
    private ThreadPoolTaskScheduler taskScheduler;

    @Mock
    private WebSocketClient mockClient; // 내부 Client를 대체할 Mock

    @Mock
    private WebSocketSession mockSession;

    @Mock
    private ScheduledFuture<?> mockFuture;

    private final String TEST_URL = "ws://test.url";
    private final String TEST_KEY = "APP_KEY";

    @BeforeEach
    void setUp() {
        // Adapter 생성자 주입 (생성자 내부에서 실제 StandardWebSocketClient가 만들어짐)
        adapter = new KisWebSocketAdapter(handler, taskScheduler);

        // 내부의 client 필드를 Mock 객체로 교체 (Reflection)
        // 생성자에서 만든 진짜 클라이언트 대신, 우리가 제어 가능한 가짜 클라이언트를 심음
        ReflectionTestUtils.setField(adapter, "client", mockClient);

        // URL 값 주입 (@Value 대용)
        ReflectionTestUtils.setField(adapter, "kisWsUrl", TEST_URL);
    }

    @Test
    @DisplayName("성공: 연결에 성공하면 핸들러 설정을 마치고 재접속을 예약하지 않는다")
    void givenMockSuccess_whenConnect_thenLogSuccessAndNoReconnect() {
        // Given
        // client.execute 호출 시 '성공한 Future(mock)'를 반환하도록 설정
        when(mockClient.execute(eq(handler), eq(TEST_URL)))
                .thenReturn(CompletableFuture.completedFuture(mockSession));

        // When
        adapter.connect(TEST_KEY);

        // Then
        verify(handler).setApproveKey(TEST_KEY); // 키 주입 확인
        verify(mockClient).execute(handler, TEST_URL); // 연결 시도 확인
        verify(taskScheduler, never()).schedule(any(Runnable.class), any(java.time.Instant.class)); // 재접속 예약 없어야 함
    }

    @Test
    @DisplayName("실패: 연결 중 예외 발생 시 스케줄러를 통해 재접속을 예약해야 한다")
    void givenMockFail_whenConnect_thenScheduleReconnect() {
        // Given
        // client.execute 호출 시 '실패한 Future'를 반환하도록 설정
        CompletableFuture<WebSocketSession> failedFuture = CompletableFuture.failedFuture(new RuntimeException("Connection Error"));

        when(mockClient.execute(eq(handler), eq(TEST_URL)))
                .thenReturn(failedFuture);

        // When
        adapter.connect(TEST_KEY);

        // Then
        // 재접속 스케줄링이 호출되었는지 확인 (3초 뒤)
        verify(taskScheduler).schedule(any(Runnable.class), any(java.time.Instant.class));
    }

    @Test
    @DisplayName("성공: 구독 요청은 핸들러에게 그대로 전달되어야 한다")
    void whenSubscribe_thenDelegateToHandler() {
        // Given
        List<String> codes = List.of("005930", "000660");

        // When
        adapter.subscribe(codes);

        // Then
        verify(handler).subscribeNewStock(codes);
    }

    @Test
    @DisplayName("성공: 종료 요청 시 예약된 재접속 태스크를 취소하고 핸들러를 닫아야 한다")
    void givenScheduledTask_whenDisconnect_thenCancelTaskAndCloseHandler() {
        // Given: 재접속 태스크가 예약되어 있는 상태라고 가정
        ReflectionTestUtils.setField(adapter, "reconnectTask", mockFuture);
        when(mockFuture.isDone()).thenReturn(false); // 아직 실행 안 된 태스크

        // When
        adapter.disconnect();

        // Then
        verify(mockFuture).cancel(true); // 태스크 취소 확인
        verify(handler).closeConnection(); // 핸들러 종료 확인
    }

    @Test
    @DisplayName("성공: 웹소켓 끊김 이벤트를 수신하면 3초 뒤 재연결 스케줄러를 등록해야 한다")
    void givenDisconnectEvent_whenOnEvent_thenScheduleReconnect() {
        // Given: Handler가 발행했다고 가정할 가짜 이벤트 객체 생성
        com.assetmind.server_stock.market_access.application.event.KisWebSocketDisconnectedEvent event =
                new com.assetmind.server_stock.market_access.application.event.KisWebSocketDisconnectedEvent(TEST_KEY);

        // When: Adapter의 이벤트 리스너 메서드가 호출됨 (Spring Event가 동작한 상황을 시뮬레이션)
        adapter.onKisWebSocketDisconnected(event);

        // Then: TaskScheduler의 schedule() 메서드가 1번 호출되어 재연결이 예약되었는지 검증
        verify(taskScheduler, times(1)).schedule(any(Runnable.class), any(java.time.Instant.class));
    }
}