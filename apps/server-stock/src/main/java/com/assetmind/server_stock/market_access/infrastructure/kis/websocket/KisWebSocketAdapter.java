package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.assetmind.server_stock.market_access.application.port.RealTimeStockDataPort;
import java.io.IOException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ScheduledFuture;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;

/**
 * KIS(한국투자증권) 웹소켓 서버에 연결 및 재접속 관리
 * 실제 웹소켓 라이브러리를 사용해서 연결하고 핑을 쏘고 재접속을 관리
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class KisWebSocketAdapter implements RealTimeStockDataPort {

    private final KisWebSocketHandler kisWebSocketHandler;
    private final ThreadPoolTaskScheduler taskScheduler;

    private final WebSocketClient client = new StandardWebSocketClient();

    @Value("${kis.websocket-url}")
    private String kisWsUrl;

    private ScheduledFuture<?> reconnectTask;
    private ScheduledFuture<?> pingTask;

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
                startPing(session);
            }
        });
    }

    @Override
    public void disconnect() {
        log.info("[KIS Adapter] 연결 종료 요청");

        // Ping 스케줄러 중지
        stopPing();

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

    private void scheduleReconnect(String approvalKey) {
        stopPing();
        log.info("[KIS Adapter] 3초 후 재접속을 시도합니다...");
        this.reconnectTask = taskScheduler.schedule(
                () -> this.connect(approvalKey),
                Instant.now().plusSeconds(3)
        );
    }

    /**
     * [Heartbeat] 60초마다 서버에 PING 메시지를 전송
     */
    private void startPing(WebSocketSession socketSession) {
        stopPing();

        pingTask = taskScheduler.scheduleAtFixedRate(() -> {
            try {
                if (socketSession.isOpen()) {
                    socketSession.sendMessage(new TextMessage("PING"));
                }
            } catch (IOException e) {
                log.error("[KIS Adapter] PING 전송 실패");
            }
        }, Instant.now().plusSeconds(60), Duration.ofSeconds(60));
    }

    /**
     * 실행 중인 Ping 스케줄링 중지
     */
    private void stopPing() {
        if (pingTask != null && !pingTask.isCancelled()) {
            pingTask.cancel(true);
            pingTask = null;
        }
    }
}
