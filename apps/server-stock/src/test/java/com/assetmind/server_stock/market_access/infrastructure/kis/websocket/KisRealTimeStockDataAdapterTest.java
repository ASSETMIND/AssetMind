package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.assetmind.server_stock.market_access.application.event.KisWebSocketDisconnectedEvent;
import com.assetmind.server_stock.market_access.domain.ApiApprovalKey;
import com.assetmind.server_stock.market_access.domain.MarketTokenProvider;
import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties;
import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties.Account;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.mapper.KisEventMapper;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser.KisRealTimeDataParser;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;

@ExtendWith(MockitoExtension.class)
class KisRealTimeStockDataAdapterTest {

    @InjectMocks
    private KisRealTimeStockDataAdapter adapter;

    @Mock private KisProperties kisProperties;
    @Mock private MarketTokenProvider marketTokenProvider;
    @Mock private TaskScheduler taskScheduler;
    @Mock private ObjectMapper objectMapper;
    @Mock private KisRealTimeDataParser dataParser;
    @Mock private KisEventMapper eventMapper;
    @Mock private ApplicationEventPublisher eventPublisher;

    @Mock private WebSocketClient mockWebSocketClient;

    private final Account account1 = new Account("app-key-1", "app-sec-1");
    private final Account account2 = new Account("app-key-2", "app-sec-2");
    private final String TEST_WS_URL = "ws://test.url";

    @BeforeEach
    void setUp() {
        // 내부 생성 로직을 무시하고 모킹된 WebSocketClient를 강제 주입하여 검증에 활용
        ReflectionTestUtils.setField(adapter, "webSocketClient", mockWebSocketClient);
    }

    @Test
    @DisplayName("성공: 웹소켓 클라이언트를 성공적으로 초기화 한다.")
    void whenPrepareConnection_thenInitWebSocketClient() {
        // When
        adapter.prepareConnection();

        // Then
        Object client = ReflectionTestUtils.getField(adapter, "webSocketClient");
        assertThat(client).isNotNull();
        assertThat(client).isInstanceOf(StandardWebSocketClient.class);
    }

    @Test
    @DisplayName("순서: 호출 순서를 보장하기 위해 구독 요청 전에 WebSocketClient가 없으면 먼저 초기화한다.")
    void givenNullWebSocketClient_whenSubscribe_thenInitWebSocketClient() {
        // Given: client가 null인 상태 설정
        ReflectionTestUtils.setField(adapter, "webSocketClient", null);
        when(kisProperties.getAccounts()).thenReturn(List.of(account1));

        // When
        adapter.subscribe(List.of("005930"));

        // Then: subscribe 로직이 내부적으로 prepareConnection을 호출하여 client가 세팅되어야 함
        Object client = ReflectionTestUtils.getField(adapter, "webSocketClient");
        assertThat(client).isNotNull();
        assertThat(client).isInstanceOf(StandardWebSocketClient.class);
    }

    @Test
    @DisplayName("성공: 2개의 계좌로 40개씩 총 80개의 종목을 구독한다.")
    void givenTwoAccounts_whenSubscribe_thenSubscribe80Stock() {
        // Given
        List<String> stocks = generateDummyCodes(80);
        when(kisProperties.getAccounts()).thenReturn(List.of(account1, account2));
        when(kisProperties.getWebsocketUrl()).thenReturn(TEST_WS_URL);

        // 태스크 내부 로직(establishSession) 실행 시 사용할 Mock 반환값 설정
        when(marketTokenProvider.fetchApprovalKey(any(), any())).thenReturn(new ApiApprovalKey("dummy-approval-key"));

        // When
        adapter.subscribe(stocks);

        // Then 1: TaskScheduler에 정확히 2번의 작업이 예약되었는지 확인
        ArgumentCaptor<Runnable> runnableCaptor = ArgumentCaptor.forClass(Runnable.class);
        verify(taskScheduler, times(2)).schedule(runnableCaptor.capture(), any(Instant.class));

        // Then 2: 예약된 태스크를 강제로 실행하여 내부 로직(establishSession) 검증
        List<Runnable> tasks = runnableCaptor.getAllValues();
        tasks.forEach(Runnable::run);

        // Then 3: 물리적 클라이언트(execute)가 2번 호출되었고, 활성 핸들러 리스트에 2개가 추가되었는지 검증
        verify(mockWebSocketClient, times(2)).execute(any(KisWebSocketHandler.class), eq(TEST_WS_URL));

        @SuppressWarnings("unchecked")
        List<KisWebSocketHandler> activeHandlers =
                (List<KisWebSocketHandler>) ReflectionTestUtils.getField(adapter, "activeHandlers");
        assertThat(activeHandlers).hasSize(2);
    }

    @Test
    @DisplayName("경고: 종목 수보다 준비된 계좌(AppKey)가 적으면 가능한 만큼만 종목을 구독한다.")
    void givenInsufficientAccounts_whenSubscribe_thenSubscribePossibleStocks() {
        // Given: 80개 종목(2청크 필요) 이지만 계좌는 1개만 세팅
        List<String> stocks = generateDummyCodes(80);
        when(kisProperties.getAccounts()).thenReturn(List.of(account1));

        // When
        adapter.subscribe(stocks);

        // Then: 계좌 개수에 맞춰 1번만 예약되어야 함
        verify(taskScheduler, times(1)).schedule(any(Runnable.class), any(Instant.class));
    }

    @Test
    @DisplayName("예외: 구독 시도(태스크 실행) 중 예외가 발생하면 던지지 않고 로깅한다.")
    void givenException_whenSubscribe_thenLogging() {
        // Given
        when(kisProperties.getAccounts()).thenReturn(List.of(account1));

        // 내부 태스크 실행 중 에러가 나도록 TokenProvider Mocking 설정
        when(marketTokenProvider.fetchApprovalKey(any(), any())).thenThrow(new RuntimeException("Token API 장애 발생"));

        adapter.subscribe(List.of("005930"));

        // 스케줄러에 등록된 Runnable 추출
        ArgumentCaptor<Runnable> runnableCaptor = ArgumentCaptor.forClass(Runnable.class);
        verify(taskScheduler).schedule(runnableCaptor.capture(), any(Instant.class));

        Runnable scheduledTask = runnableCaptor.getValue();

        // When & Then: 태스크를 실행했을 때 예외가 밖으로 새어나오지 않고 내부 catch 블록에서 처리되어야 함
        assertDoesNotThrow(scheduledTask::run);

        // 연결이 실패했으므로 execute 메서드는 호출되지 않아야 함
        verify(mockWebSocketClient, never()).execute(any(), any());
    }

    @Test
    @DisplayName("성공: 연결을 끊기 위해 모든 활성 handler에게 closeConnection()을 명령하고 리스트를 clear 한다.")
    void givenActiveHandler_whenDisconnect_thenClearActiveHandler() {
        // Given
        KisWebSocketHandler mockHandler1 = mock(KisWebSocketHandler.class);
        KisWebSocketHandler mockHandler2 = mock(KisWebSocketHandler.class);

        @SuppressWarnings("unchecked")
        List<KisWebSocketHandler> activeHandlers =
                (List<KisWebSocketHandler>) ReflectionTestUtils.getField(adapter, "activeHandlers");
        activeHandlers.add(mockHandler1);
        activeHandlers.add(mockHandler2);

        // When
        adapter.disconnect();

        // Then: 각각의 핸들러에 close 명령이 내려졌고, 리스트가 비워져야 함
        verify(mockHandler1, times(1)).closeConnection();
        verify(mockHandler2, times(1)).closeConnection();
        assertThat(activeHandlers).isEmpty();
    }

    @Test
    @DisplayName("성공: 웹소켓 끊김 이벤트 수신 시, 해당 죽은 handler를 제거하고 3초 뒤 재연결 스케줄링을 해야한다")
    void givenDisconnectEvent_whenHandleWebSocketDisconnected_thenReconnected() {
        // Given
        KisWebSocketHandler deadHandler = mock(KisWebSocketHandler.class);
        List<String> failedChunk = List.of("005930", "000660");

        KisWebSocketDisconnectedEvent event =
                new KisWebSocketDisconnectedEvent(deadHandler, account1, failedChunk);

        // 관리 리스트에 죽은 핸들러를 미리 넣어둠
        @SuppressWarnings("unchecked")
        List<KisWebSocketHandler> activeHandlers =
                (List<KisWebSocketHandler>) ReflectionTestUtils.getField(adapter, "activeHandlers");
        activeHandlers.add(deadHandler);

        when(kisProperties.getWebsocketUrl()).thenReturn(TEST_WS_URL);
        when(marketTokenProvider.fetchApprovalKey(any(), any())).thenReturn(new ApiApprovalKey("new-key"));

        // When 1: 이벤트 수신
        adapter.handleWebSocketDisconnected(event);

        // Then 1: 즉시 리스트에서 시체가 지워져야 함
        assertThat(activeHandlers).doesNotContain(deadHandler);

        // Then 2: 3초 뒤 스케줄링이 예약됨
        ArgumentCaptor<Runnable> runnableCaptor = ArgumentCaptor.forClass(Runnable.class);
        verify(taskScheduler, times(1)).schedule(runnableCaptor.capture(), any(Instant.class));

        // When 2: 예약된 재연결 태스크 실행
        runnableCaptor.getValue().run();

        // Then 3: 새로운 핸들러로 웹소켓 연결이 시도되었는지 확인
        verify(mockWebSocketClient, times(1)).execute(any(KisWebSocketHandler.class), eq(TEST_WS_URL));
    }

    @Test
    @DisplayName("예외: 재연결 프로세스 중 handler 생성이 실패하면 예외를 던지지 않고 로깅한다.")
    void givenDisconnectEventAndException_whenHandleWebSocketDisconnected_thenLogging() {
        // Given
        KisWebSocketDisconnectedEvent event =
                new KisWebSocketDisconnectedEvent(mock(KisWebSocketHandler.class), account1, List.of("005930"));

        // 재연결 태스크 안에서 예외가 발생하도록 조작
        when(marketTokenProvider.fetchApprovalKey(any(), any())).thenThrow(new RuntimeException("재인증 실패"));

        adapter.handleWebSocketDisconnected(event);

        // 스케줄러에 등록된 태스크 가로채기
        ArgumentCaptor<Runnable> runnableCaptor = ArgumentCaptor.forClass(Runnable.class);
        verify(taskScheduler).schedule(runnableCaptor.capture(), any(Instant.class));

        // When & Then: 태스크 실행 시 죽지 않아야 함
        assertDoesNotThrow(() -> runnableCaptor.getValue().run());
    }

    /**
     * 테스트용 더미 종목 코드 생성 유틸
     */
    private List<String> generateDummyCodes(int count) {
        List<String> codes = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            codes.add(String.format("%06d", i));
        }
        return codes;
    }
}