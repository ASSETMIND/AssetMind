package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.assetmind.server_stock.market_access.application.event.KisWebSocketDisconnectedEvent;
import com.assetmind.server_stock.market_access.application.port.RealTimeStockDataPort;
import jakarta.websocket.ContainerProvider;
import jakarta.websocket.WebSocketContainer;
import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ScheduledFuture;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;

/**
 * KIS(한국투자증권) 웹소켓 서버에 연결 및 재접속 관리
 * 실제 웹소켓 라이브러리를 사용해서 연결하고 핑을 쏘고 재접속을 관리
 */
@Slf4j
@Component
public class KisWebSocketAdapter implements RealTimeStockDataPort {

    private final KisWebSocketHandler kisWebSocketHandler;
    private final ThreadPoolTaskScheduler taskScheduler;
    private final WebSocketClient client;

    @Value("${kis.websocket-url}")
    private String kisWsUrl;

    private ScheduledFuture<?> reconnectTask;

    public KisWebSocketAdapter(KisWebSocketHandler kisWebSocketHandler, ThreadPoolTaskScheduler taskScheduler) {
        this.kisWebSocketHandler = kisWebSocketHandler;
        this.taskScheduler = taskScheduler;

        // 버퍼 사이즈를 늘린 컨테이너 생성
        WebSocketContainer webSocketContainer = ContainerProvider.getWebSocketContainer();
        webSocketContainer.setDefaultMaxTextMessageBufferSize(1024 * 1024); // 1MB (텍스트)
        webSocketContainer.setDefaultMaxBinaryMessageBufferSize(1024 * 1024); // 1MB (바이너리)

        // 설정된 컨테이너로 클라이언트 생성
        this.client = new StandardWebSocketClient(webSocketContainer);
    }

    @Override
    public void connect(String approvalKey) {
        log.info("[KIS Adapter] 웹소켓 연결 시도... URL: {}", kisWsUrl);

        kisWebSocketHandler.setApproveKey(approvalKey);

        CompletableFuture<WebSocketSession> future = client.execute(kisWebSocketHandler, kisWsUrl);

        future.whenComplete((session, throwable) -> {
            if (throwable != null) {
                // [실패] 에러(throwable)가 존재하면 연결 실패
                log.error("[KIS Adapter] 연결 실패. 에러: {}", throwable.getMessage());
                scheduleReconnect(approvalKey);
            } else {
                // [성공] 에러가 없으면 연결 성공
                log.info("[KIS Adapter] 연결 성공! Session ID: {}", session.getId());
            }
        });
    }

    @Override
    public void disconnect() {
        log.info("[KIS Adapter] 의도적인 연결 종료 요청");

        // 재접속 예약된게 있다면 취소
        if (reconnectTask != null && !reconnectTask.isDone()) {
            reconnectTask.cancel(true);
        }

        kisWebSocketHandler.closeConnection();

        log.info("[KIS Adapter] 연결 종료 완료");
    }

    @Override
    public void subscribe(List<String> stockCode) {
        kisWebSocketHandler.subscribeNewStock(stockCode);
    }

    @EventListener
    public void onKisWebSocketDisconnected(KisWebSocketDisconnectedEvent event) {
        log.warn("[KIS Adapter] 웹소켓 끊김 이벤트 수신. 재연결 프로세스 시작");
        scheduleReconnect(event.approveKey());
    }

    private void scheduleReconnect(String approvalKey) {
        log.info("[KIS Adapter] 3초 후 재접속을 시도합니다...");
        this.reconnectTask = taskScheduler.schedule(
                () -> this.connect(approvalKey),
                Instant.now().plusSeconds(3)
        );
    }
}
