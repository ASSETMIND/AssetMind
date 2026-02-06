package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisSubscriptionRequest;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
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
    private final Set<String> subscribedStock = ConcurrentHashMap.newKeySet(); // 중복 구독 방지 Set

    // 연결 전 요청을 임시 저장할 대기열 (동기화 리스트)
    private final List<String> pendingSubscriptionList = Collections.synchronizedList(new ArrayList<>());

    /**
     * [구독 요청] 연결 상태에 따라 즉시 전송하거나 대기열에 저장
     */
    public void subscribeNewStock(List<String> stockCodes) {
        if (approveKey == null) {
            log.error("[KIS WS] 접속키가 설정되지 않았습니다.");
            return;
        }

        log.info("[KIS WS] {}개 종목 구독 요청 시작...", stockCodes.size());

        WebSocketSession session = this.currentSession;
        for (String code : stockCodes) {
            if (session != null && session.isOpen()) {
                // session 존재 (연결됨) -> 즉시 전송
                sendSubscriptionRequest(code);
            } else {
                // session 존재 X (연결 안됨) -> 대기열 저장
                log.info("[KIS WS] 연결 대기 중... 구독 요청 보류 (종목: {})", code);
                pendingSubscriptionList.add(code);
            }
        }
    }

    /**
     * [연결 성공 이벤트] 연결되자마자 대기열 비우기
     */
    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        log.info("[KIS WS] 세션 연결 성공 (Session ID : {})", session.getId());
        this.currentSession = session;

        // 대기중인 요청 일괄 처리
        if (!pendingSubscriptionList.isEmpty()) {
            log.info("[KIS WS] 대기 중이던 {}개 종목 구독 시작...", pendingSubscriptionList.size());

            // 리스트 복사 후 처리
            ArrayList<String> targets = new ArrayList<>(pendingSubscriptionList);
            pendingSubscriptionList.clear();

            for (String code : targets) {
                sendSubscriptionRequest(code);
            }
        }
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        String payload = message.getPayload();

        if (payload == null || payload.isEmpty()) return;

        char firstChar = payload.charAt(0);

        try {
            if (firstChar == '{') {
                // '{'로 시작한다면 JSON 포맷 (구독 응답, PINGPONG)
                processJsonMessage(payload);
            } else {
                // 텍스트 포맷 (실시간 주식 데이터)
                // KIS 데이터 포맷: 암호화여부(0/1) | TR_ID | 데이터(^으로 구분)
                processStockData(payload);
            }
        } catch (Exception e) {
            log.error("[KIS WS] 메시지 처리 중 에러 발생 (Payload: {})", payload, e);
        }
    }

    // JSON 메시지 처리
    private void processJsonMessage(String payload) throws Exception {
        if (payload.contains("PINGPONG")) {
            log.debug("[KIS WS] PONG 수신");
            return;
        }

        // 구독 성공 메시지 등 로그 출력
        log.info(">>> [KIS WS] 제어 메시지: {}", payload);
    }

    // 실시간 주식 데이터 처리
    private void processStockData(String payload) {
        String[] parts = payload.split("\\|");

        // 최소 길이 체크
        if (parts.length < 3) return;

        int count = 1;
        String rawData;

        // 3번째 항목(parts[2])이 숫자인지 먼저 확인 (Try-Catch 대신 정규식 사용)
        if (parts[2].matches("\\d+")) {
            // 숫자다! -> 개수 필드가 존재함
            try {
                count = Integer.parseInt(parts[2]);
            } catch (NumberFormatException e) {
                count = 1; // 혹시라도 실패하면 1개로 처리
            }
            // 데이터는 4번째(인덱스 3)부터 시작
            rawData = (parts.length > 3) ? parts[3] : "";
        } else {
            // 숫자가 아니다 ("H" 등) -> 개수 필드 생략됨, 바로 데이터 시작
            count = 1;
            rawData = parts[2];
        }

        // 데이터가 비어있으면 종료
        if (rawData == null || rawData.isEmpty()) return;

        // 상세 데이터 파싱
        String[] details = rawData.split("\\^");
        final int FIELD_COUNT = 46;

        // 데이터 개수 만큼 반복해서 추출
        for (int i = 0; i < count; i++) {
            // 현재 데이터의 시작 인덱스
            int offset = i * FIELD_COUNT;

            // 배열 범위 체크
            if (offset + 5 >= details.length) break;

            // 주요 필드 추출
            String stockCode = details[offset + 0]; // 종목코드
            String time = details[offset + 1]; // 체결시간
            String currentPrice = details[offset + 2]; // 현재가
            String sign = details[offset + 3]; // 전일대비 부호 (1: 상한, 2: 상승, 3:보합, 4:하한, 5:하락)
            String changeRate = details[offset + 5]; // 등락률
            String volume = details[offset + 12];

            log.info("[체결] {} | 시간:{} | 현재가: {}원 | 등락률: {}% | 거래량: {}", stockCode, time, currentPrice, changeRate, volume);
        }

        // log.info(">>> [실시간 데이터 수신] TR_ID: {}, RawData: {}", trId, data);

        // TODO: 나중에 실제 데이터를 더 세분화하여 값을 추출하고 DB에 저장
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error("[KIS WS] 전송 에러 발생", exception);
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        log.warn("[KIS WS] 연결 종료됨. Code: {}, Reason: {}", status.getCode(), status.getReason());
        this.currentSession = null;
        this.subscribedStock.clear(); // 연결 끊기면 구독 정보도 초기화
    }

    private void sendSubscriptionRequest(String stockCode) {
        if (subscribedStock.contains(stockCode)) return;

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
}
