package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.assetmind.server_stock.market_access.application.MarketAccessService;
import com.assetmind.server_stock.market_access.domain.ApiApprovalKey;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisSubscriptionRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.PingMessage;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.handler.TextWebSocketHandler;

/**
 * KIS 실시간 WebSocket 생명 주기를 관리
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class KisWebSocketHandler extends TextWebSocketHandler {

    private final MarketAccessService marketAccessService; // 키 발급 서비스
    private final WebSocketClient webSocketClient;
    private final ObjectMapper objectMapper; // JSON 변환 매퍼

    @Value("${kis.websocket-url}")
    private String webSocketUrl;

    // 구독할 종목 리스트 데이터 (추후 DB에서 가져오는 형식으로 구현) - StockSubscriptionService
    // 삼성전자(005930), SK하이닉스(000660), NAVER(035420)
    private final List<String> targetStocks = List.of("005930", "000660", "035420");

    // 스레드 안정성을 위해 volatile 사용 (단일 세션 유지)
    private volatile WebSocketSession currentSession;

    // Ping 및 재접속 관리용 스케쥴러 (단일 스레드로 관리하여 리소스 낭비 방지)
    private final ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();

    /**
     * 웹소켓 서버에 연결 시도
     * 웹 구동 시점이나 재접속이 필요할 때 호출
     */
    public void connect() {
        try {
            log.info(">>> [KIS] 웹소켓 연결 시도: {}", webSocketUrl);
            webSocketClient.execute(this, webSocketUrl)
                    .thenAccept(session -> {
                        log.debug("handshake 완료. Session ID: {}", session.getId());
                    })
                    .exceptionally(throwable -> {
                        log.error(">>> [KIS] handshake 실패 (연결 불가)", throwable);
                        scheduleReconnect(); // 실패시 재접속 시도
                        return null;
                    });
        } catch (Exception e) {
            log.error(">>> [KIS] 연결 시도 중 에러 발생", e);
            scheduleReconnect(); // 실패시 재접속 시도
        }
    }

    /**
     * 연결 성공 시 호출
     * 접속키 발급 -> 구독 요청 -> Ping 스케줄링 순서로 초기화를 진행
     */
    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws Exception {
        log.info(">>> [KIS] 웹소켓 연결 활성화됨 (Session ID: {})", session.getId());
        this.currentSession = session;

        try {
            // 접속키 발급
            ApiApprovalKey approvalKey = marketAccessService.getApprovalKey();

            // 구독할 종목 리스트 조회
            List<String> targets = targetStocks;

            // 순차적 각 주식별 순차적 구독 요청
            for (String stockCode : targets) {
                sendSubscription(session, approvalKey, stockCode);
                // API 서버 부하 방지 및 순서 보장을 위한 미세 지연
                Thread.sleep(50);
            }

            // Ping(Heartbeat) 시작
            startPingScheduler(session);
        } catch (Exception e) {
            log.error(">>> [KIS] 초기화(인증/구독) 실패, 세션을 종료합니다.", e);
            closeSession(session);
        }
    }

    /**
     * KIS 서버 구격에 맞는 국내주식 실시간 체결가 구독 요청 메시지를 전송
     */
    private void sendSubscription(WebSocketSession session, ApiApprovalKey key, String stockCode)
            throws IOException {
        // DTO를 사용하여 JSON 구조 생성
        KisSubscriptionRequest request = KisSubscriptionRequest.of(key.value(), stockCode);
        String jsonPayload = objectMapper.writeValueAsString(request);

        // 연결이 안되어있으면 구독 요청 실패
        if (!session.isOpen()) {
            log.warn(">>> [KIS] 세션이 닫혀있어 구독 요청 실패: {}", stockCode);
            return;
        }

        // 연결이 되어있으면 종목 코드에 맞는 실시간 체결가를 요청
        session.sendMessage(new TextMessage(jsonPayload));
        log.info(">>> [KIS] 구독 요청 전송 완료: {}", stockCode);
    }

    /**
     * KIS 서버로부터 들어오는 모든 텍스트 메시지를 처리
     */
    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        String payload = message.getPayload();

        log.info("<<< [KIS] 수신 데이터: {}", payload);
    }

    /**
     * 통신 에러 발생시 처리
     * 에러가 발생하면 세션을 닫고 재접속 시도
     */
    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error(">>> [KIS] 전송 에러 발생: {}", exception.getMessage());

        // 에러 발생시 세션을 닫아서 재접속 로직을 유도
        closeSession(session);
    }

    /**
     * KIS WebSocket 세션과 연결이 종료된 이후 실행
     * - 세션 참조 변수를 정리
     * - 의도적 종료가 아니라면 잘못된 종료로 판단하고 재접속 로직 실행
     */
    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        log.info(">>> [KIS] 연결 종료됨 (Status: {} - {})", status.getCode(), status.getReason());

        // 현재 세션 참조 정리
        if (currentSession != null && currentSession.getId().equals(session.getId())) {
            currentSession = null;
        }

        // 의도적인 종료가 아니라면 재접속 로직 실행
        if (status.getCode() != CloseStatus.NORMAL.getCode()) {
            scheduleReconnect();
        }
    }

    /**
     * 1분(60초) 주기로 PING 메세지를 전송하여 연결 유지
     * (KIS API 권장사항 준수 100초 이내로 세션 유지 Heartbeat 응답 필수)
     */
    private void startPingScheduler(WebSocketSession session) {
        scheduler.scheduleAtFixedRate(() -> {
            try {
                if (!session.isOpen())  return;

                session.sendMessage(new PingMessage());
                log.debug(">>> [KIS] Ping 전송 (연결 유지)");
            } catch (IOException e) {
                log.error("Ping 전송 실패", e);
            }
        }, 60, 60, TimeUnit.SECONDS);
    }

    /**
     * 연결 끊김 시 3초 대기 후 재접속을 시도
     */
    private void scheduleReconnect() {
        log.info(">>> [KIS] 3초 후 재접속을 시도합니다...");
        scheduler.schedule(this::connect, 3, TimeUnit.SECONDS);
    }

    /**
     * 세선 종료
     */
    private void closeSession(WebSocketSession session) {
        try {
            if (!session.isOpen()) return;

            session.close();
        } catch (IOException e) {
            log.error(">>> [KIS] 세선 종료 중 에러 발생: {}", e.getMessage());
        }
    }
}
