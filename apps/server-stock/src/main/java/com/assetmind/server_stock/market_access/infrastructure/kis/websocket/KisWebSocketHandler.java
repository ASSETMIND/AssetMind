package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisSubscriptionRequest;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

/**
 * KIS(한국투자증권) 웹소켓 메시지 핸들러
 * 웹소켓 세션 이벤트(연결, 종료, 에러) 처리
 * 실시간 데이터 수신 및 파싱 (JSON -> Domain/DTO)
 * 구독 요청 전송 (미세 딜레이 적용)
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class KisWebSocketHandler extends TextWebSocketHandler {

    private final ObjectMapper objectMapper;

    @Setter
    private String approveKey;
    private WebSocketSession currentSession;
    private final Set<String> subscribedStock = ConcurrentHashMap.newKeySet();

    public void subscribeNewStock(List<String> stockCodes) {
        if (currentSession == null || !currentSession.isOpen()) {
            log.warn("[KIS WS] 세션이 닫혀 있어, 구독 요청을 보낼 수 없습니다.");
            return;
        }

        if (approveKey == null) {
            log.error("[KIS WS] 접속키가 설정되지 않았습니다.");
            return;
        }

        log.info("[KIS WS] {}개 종목 구독 요청 시작...", stockCodes.size());

        for (String code : stockCodes) {
            if (subscribedStock.contains(code)) {
                continue;
            }

            sendSubscriptionRequest(approveKey, code);
        }
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        log.info("[KIS WS] 세션 연결 성공 (Session ID : {})", session.getId());
        this.currentSession = session;
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        try {
            String payload = message.getPayload();

            JsonNode node = objectMapper.readTree(payload);

            log.info(">>> [KIS WS] Data: {}", node.toPrettyString());
        } catch (Exception e) {
            log.error(">>> [KIS WS] 메시지 처리 중 에러 발생", e);
        }
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error("[KIS WS] 전송 에러 발생", exception)
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        log.warn("[KIS WS] 연결 종료됨. Code: {}, Reason: {}", status.getCode(), status.getReason());
        this.currentSession = null;
        this.subscribedStock.clear(); // 연결 끊기면 구독 정보도 초기화
    }

    /**
     * [연결 종료] 외부(Adapter)에서 종료 요청 시 호출
     */
    public void closeConnection() {
        try {
            if (currentSession != null && currentSession.isOpen()) {
                log.info("[KIS WS] 웹소켓 세션을 정상 종료합니다.");
                currentSession.close(CloseStatus.NORMAL);
            }
        } catch (Exception e) {
            log.error("[KIS WS] 세션 종료 중 에러 발생", e);
        } finally {
            // 명시적으로 한 번 더 정리
            this.currentSession = null;
            this.subscribedStock.clear();
        }
    }

    private void sendSubscriptionRequest(String approveKey, String stockCode) {
        try {
            KisSubscriptionRequest request = KisSubscriptionRequest.of(approveKey, stockCode);
            String jsonPayload = objectMapper.writeValueAsString(request);

            currentSession.sendMessage(new TextMessage(jsonPayload));

            subscribedStock.add(stockCode);
            log.info("[KIS WS] 구독 요청 전송 완료: {}", stockCode);

            // 연속 전송 시 서버 부하/차단 방지를 위한 미세 딜레이 (Throttling)
            Thread.sleep(50);
        } catch (JsonProcessingException e) {
            log.error("[KIS WS] JSON 변환 오류. 종목코드: {} (구독 건너뜀)", stockCode, e);
        } catch (InterruptedException e) {
            log.warn("[KIS WS] 구독 요청 중단 (인터럽트 발생)");
            Thread.currentThread().interrupt();
        } catch (IOException e) {
            log.error("[KIS WS] 메시지 전송 실패 (I/O Error). 종목코드: {}", stockCode, e);
        } catch (Exception e) {
            log.error("[KIS WS] 알 수 없는 오류 발생. 종목코드: {}", stockCode, e);
        }
    }
}
