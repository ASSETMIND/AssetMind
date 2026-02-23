package com.assetmind.server_stock.stock.integration;

import static org.assertj.core.api.Assertions.*;

import com.assetmind.server_stock.support.IntegrationTestSupport;
import java.lang.reflect.Type;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.messaging.converter.MappingJackson2MessageConverter;
import org.springframework.messaging.simp.stomp.StompFrameHandler;
import org.springframework.messaging.simp.stomp.StompHeaders;
import org.springframework.messaging.simp.stomp.StompSession;
import org.springframework.messaging.simp.stomp.StompSession.Subscription;
import org.springframework.messaging.simp.stomp.StompSessionHandlerAdapter;
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

    private WebSocketStompClient socketStompClient;

    private static final String WEBSOCKET_ENDPOINT = "/ws-stock";
    private static final String SUBSCRIBE_TOPIC = "/topic";

    @BeforeEach
    void setup() {
        // STOMP 클라이언트 초기화 - 프론트엔드 브라우저 역할
        WebSocketClient webSocketClient = new SockJsClient(
                List.of(new WebSocketTransport(new StandardWebSocketClient()))
        );
        this.socketStompClient = new WebSocketStompClient(webSocketClient);
        this.socketStompClient.setMessageConverter(new MappingJackson2MessageConverter());
    }

    @Test
    @DisplayName("성공: 테스트 클라이언트가 웹소켓 엔드포인트에 접속하고 토픽을 구독하여 메시지를 수신한다.")
    void givenWebSocketURL_whenConnectAndSubscribe_thenCreatedSessionAndReceiveMessage() throws Exception{
        // given
        String wsUrl = "ws://localhost:" + port + WEBSOCKET_ENDPOINT;
        CompletableFuture<String> resultFuture = new CompletableFuture<>(); // 비동기 응답을 기다릴 객체

        // when
        // 연결
        StompSession session = socketStompClient
                .connectAsync(wsUrl, new StompSessionHandlerAdapter() {
                })
                .get(5, TimeUnit.SECONDS);

        // 구독
        Subscription subscription = session.subscribe(SUBSCRIBE_TOPIC, new StompFrameHandler() {

            @Override
            public Type getPayloadType(StompHeaders headers) {
                return String.class;
            }

            @Override
            public void handleFrame(StompHeaders headers, Object payload) {
                // 서버로부터 메시지가 오면 CompletableFuture에 값을 채워 넣음
                resultFuture.complete((String) payload);
            }
        });

        // then
        assertThat(session.isConnected()).isTrue(); // 연결 검증
        assertThat(subscription).isNotNull();

        // 구독 검증: 구독에 성공했다면 해당 채널에 메시지를 던졌으면 받아야함
        String testMessage = "Hello assetmind";
        session.send(SUBSCRIBE_TOPIC, testMessage);

        String receivedMessage = resultFuture.get(3, TimeUnit.SECONDS);
        assertThat(receivedMessage).isEqualTo(testMessage);
    }
}
