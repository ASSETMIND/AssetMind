package com.assetmind.server_stock.stock.integration;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.KisWebSocketHandler;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.mapper.KisEventMapper;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser.KisRealTimeDataParser;
import com.assetmind.server_stock.support.IntegrationTestSupport;
import com.assetmind.server_stock.support.MockKisDataFeeder;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.lang.reflect.Type;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.messaging.converter.MappingJackson2MessageConverter;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.messaging.simp.stomp.StompFrameHandler;
import org.springframework.messaging.simp.stomp.StompHeaders;
import org.springframework.messaging.simp.stomp.StompSession;
import org.springframework.messaging.simp.stomp.StompSession.Subscription;
import org.springframework.messaging.simp.stomp.StompSessionHandlerAdapter;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;
import org.springframework.web.socket.messaging.WebSocketStompClient;
import org.springframework.web.socket.sockjs.client.SockJsClient;
import org.springframework.web.socket.sockjs.client.WebSocketTransport;

// 랜덤 포트로 실제 서블릿 컨테이너를 띄워 웹소켓 통신 환경을 구성
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class StockWebSocketIntegrationTest extends IntegrationTestSupport {

    @LocalServerPort
    private int port;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private KisRealTimeDataParser dataParser;

    @Autowired
    private KisEventMapper eventMapper;

    @Autowired
    private ApplicationEventPublisher eventPublisher;

    @Autowired
    private TaskScheduler taskScheduler;

    private WebSocketStompClient socketStompClient;

    private KisWebSocketHandler kisWebSocketHandler;

    private static final String WEBSOCKET_ENDPOINT = "/ws-stock";
    private static final String SUBSCRIBE_SPECIFIC_TOPIC = "/topic/stocks/035420";
    private static final String SUBSCRIBE_RANKING_TOPIC = "/topic/ranking";

    @BeforeEach
    void setup() {
        // STOMP 클라이언트 초기화 - 프론트엔드 브라우저 역할
        WebSocketClient webSocketClient = new SockJsClient(
                List.of(new WebSocketTransport(new StandardWebSocketClient()))
        );
        this.socketStompClient = new WebSocketStompClient(webSocketClient);
        this.socketStompClient.setMessageConverter(new MappingJackson2MessageConverter());

        // 빈 Account와 테스트용 Chunk 리스트를 포함하는 테스용 KIS handler
        this.kisWebSocketHandler = new KisWebSocketHandler(
                "test-approval-key",
                null,
                List.of("035420", "005930"),
                objectMapper,
                dataParser,
                eventMapper,
                eventPublisher,
                taskScheduler
        );
    }

    @Test
    @DisplayName("성공: 테스트 클라이언트가 웹소켓 엔드포인트에 접속하고 토픽을 구독하여 메시지를 수신한다.")
    void givenWebSocketURL_whenConnectAndSubscribe_thenCreatedSessionAndReceiveMessage() throws Exception{
        // given
        String wsUrl = "ws://localhost:" + port + WEBSOCKET_ENDPOINT;
        CompletableFuture<Map<String, Object>> resultFuture = new CompletableFuture<>(); // 비동기 응답을 기다릴 객체

        // when
        // 연결
        StompSession session = socketStompClient
                .connectAsync(wsUrl, new StompSessionHandlerAdapter() {
                })
                .get(5, TimeUnit.SECONDS);

        // 구독
        Subscription subscription = session.subscribe(SUBSCRIBE_SPECIFIC_TOPIC, new StompFrameHandler() {

            @Override
            public Type getPayloadType(StompHeaders headers) {
                return Map.class;
            }

            @Override
            public void handleFrame(StompHeaders headers, Object payload) {
                // 서버로부터 메시지가 오면 CompletableFuture에 값을 채워 넣음
                resultFuture.complete((Map<String, Object>) payload);
            }
        });

        // then
        assertThat(session.isConnected()).isTrue(); // 연결 검증
        assertThat(subscription).isNotNull();

        // 구독 검증: 구독에 성공했다면 해당 채널에 메시지를 던졌으면 받아야함
        Map<String, Object> testMessage = Map.of("message", "Hello assetmind");
        session.send(SUBSCRIBE_SPECIFIC_TOPIC, testMessage);

        Map<String, Object> receivedMessage = resultFuture.get(3, TimeUnit.SECONDS);
        assertThat(receivedMessage.get("message")).isEqualTo("Hello assetmind");
    }

    @Test
    @DisplayName("성공: 특정 종목의 KIS 다건 체결 데이터(003)이 유입되면 파싱되어 프론트엔드로 브로드캐스트 된다.")
    void givenKisMultipleData_whenHandleMessage_thenBroadCastToClient() throws Exception {
        // given: STOMP 연결 및 구독 준비
        String wsUrl = "ws://localhost:" + port + WEBSOCKET_ENDPOINT;

        List<Map<String, Object>> receivedMessages = new CopyOnWriteArrayList<>(); // 주식 체결 데이터 3건을 담을 List
        CountDownLatch latch = new CountDownLatch(3); // 3건 대기

        StompSession session = socketStompClient
                .connectAsync(wsUrl, new StompSessionHandlerAdapter() {})
                .get(5, TimeUnit.SECONDS);

        session.subscribe(SUBSCRIBE_SPECIFIC_TOPIC, new StompFrameHandler() {
            @Override
            public Type getPayloadType(StompHeaders headers) {
                return Map.class; // 실제 JSON 객체가 올 것이므로 Map으로 대기
            }

            @Override
            public void handleFrame(StompHeaders headers, Object payload) {
                // 주식 체결 데이터가 들어올 때 마다 List에 담고 카운트 1감소
                receivedMessages.add((Map<String, Object>) payload);
                latch.countDown();
            }
        });

        // 서버가 구독을 등록할 대기 시간 생성
        Thread.sleep(3000);

        // when
        // MockDataFeeder로 가짜 다건 데이터 생성 후 강제 주입
        String mockKisData = MockKisDataFeeder.createMockDataWithCount("035420", "75000", 3);

        WebSocketSession mockSession = Mockito.mock(WebSocketSession.class);
        TextMessage textMessage = new TextMessage(mockKisData);

        // KIS 핸들러의 handleMessage를 직접 호출하여 데이터 유입 시뮬레이션
        kisWebSocketHandler.handleMessage(mockSession, textMessage);

        boolean completed = latch.await(5, TimeUnit.SECONDS); // 5초 동안 3건의 메시지가 도착할 때 까지 대기


        // then: 프론트엔드가 5초 내에 파싱된 응답을 받는지 검증

        // 수신 후 최종 리스트 상태 확인
        System.out.println("[수신 완료] 수신된 메시지 총 개수: " + receivedMessages.size());
        for (int i = 0; i < receivedMessages.size(); i++) {
            System.out.println("[" + (i+1) + "번째 응답]" + receivedMessages.get(i));
        }

        assertThat(completed).isTrue();
        assertThat(receivedMessages).hasSize(3);
        
        // 검증: 3건 주식 데이터의 가격이 75000, 75100, 75200 모두 파싱되었는지
        List<String> prices = receivedMessages.stream()
                .map(msg -> String.valueOf(msg.get("currentPrice")))
                .toList();

        assertThat(prices).containsExactlyInAnyOrder("75000", "75100", "75200");
    }

    @Test
    @DisplayName("성공: KIS 체결 데이터가 유입되면 메인 랭킹용 데이터가 /topic/ranking 으로 브로드캐스트 된다.")
    void givenKisData_whenHandleMessage_thenBroadCastToRankingTopic() throws Exception {
        // given: STOMP 연결 및 랭킹 토픽 구독 준비
        String wsUrl = "ws://localhost:" + port + WEBSOCKET_ENDPOINT;
        CompletableFuture<Map<String, Object>> resultFuture = new CompletableFuture<>();

        StompSession session = socketStompClient
                .connectAsync(wsUrl, new StompSessionHandlerAdapter() {
                })
                .get(5, TimeUnit.SECONDS);

        session.subscribe(SUBSCRIBE_RANKING_TOPIC, new StompFrameHandler() {
            @Override
            public Type getPayloadType(StompHeaders headers) {
                return Map.class;
            }

            @Override
            @SuppressWarnings("unchecked")
            public void handleFrame(StompHeaders headers, Object payload) {
                // 랭킹 데이터가 도착하면 Future에 담기
                resultFuture.complete((Map<String, Object>) payload);
            }
        });

        // 서버가 구독을 등록할 대기 시간 생성
        Thread.sleep(3000);

        // when: 단건 데이터 1개 생성
        String mockKisData = MockKisDataFeeder.createMockDataWithCount("005930", "75000", 1);
        WebSocketSession mockSession = Mockito.mock(WebSocketSession.class);
        TextMessage textMessage = new TextMessage(mockKisData);

        // KIS 핸들러에 데이터 주입 -> 파싱 -> Redis 저장 -> 랭킹 이벤트 발행 -> 웹소켓 전송
        kisWebSocketHandler.handleMessage(mockSession, textMessage);

        // then: 5초 내에 랭킹 응답을 받는지 검증
        Map<String, Object> receivedData = resultFuture.get(5, TimeUnit.SECONDS);

        System.out.println("[랭킹 토픽 수신 완료] 데이터: " + receivedData);

        // 검증: 수신된 JSON(StockRankingResponse)에 종목코드와 가격이 제대로 들어있는지 확인
        String jsonString = receivedData.toString();
        assertThat(jsonString).contains("005930");
        assertThat(jsonString).contains("75000");
    }
}
