package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.assetmind.server_stock.market_access.application.event.KisWebSocketDisconnectedEvent;
import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties.Account;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisRealTimeData;
import com.assetmind.server_stock.market_access.infrastructure.kis.dto.KisSubscriptionRequest;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.mapper.KisEventMapper;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.parser.KisRealTimeDataParser;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

/**
 * KIS(한국투자증권) 웹소켓 메시지 핸들러
 * 웹소켓 세션 이벤트(연결, 종료, 에러) 처리
 * 실시간 데이터 수신 및 파싱 (JSON -> Domain/DTO)
 * 구독 요청 전송 (미세 딜레이 적용)
 *
 * 핵심 로직: 실시간 데이터 수신 -> 파싱 -> Spring Event 발행
 */
@Slf4j
public class KisWebSocketHandler extends TextWebSocketHandler {

    private final ObjectMapper objectMapper;
    private final KisRealTimeDataParser dataParser;
    private final KisEventMapper eventMapper;
    private final ApplicationEventPublisher eventPublisher;
    private final TaskScheduler taskScheduler;

    private final String approveKey;
    private final Account account;
    private final List<String> chunk;

    private WebSocketSession currentSession;
    private final Set<String> subscribedStock = ConcurrentHashMap.newKeySet(); // 중복 구독 방지 Set

    // 연결 전 요청을 임시 저장할 대기열 (동기화 리스트)
    private final List<String> pendingSubscriptionList = Collections.synchronizedList(new ArrayList<>());

    public KisWebSocketHandler(String approveKey, Account account, List<String> chunk, ObjectMapper objectMapper, KisRealTimeDataParser dataParser,
            KisEventMapper eventMapper, ApplicationEventPublisher eventPublisher, TaskScheduler taskScheduler) {
        this.approveKey = approveKey;
        this.account = account;
        this.chunk = chunk;
        this.objectMapper = objectMapper;
        this.dataParser = dataParser;
        this.eventMapper = eventMapper;
        this.eventPublisher = eventPublisher;
        this.taskScheduler = taskScheduler;

        // 객체 생성 시 자신이 담당할 종목들을 대기열에 세팅
        this.pendingSubscriptionList.addAll(chunk);
    }

    /**
     * [구독 요청] 연결 상태에 따라 즉시 전송하거나 대기열에 저장
     */
    public void subscribeNewStock(List<String> stockCodes) {
        if (approveKey == null) {
            log.error("[KIS WS Handler] 접속키가 설정되지 않았습니다.");
            return;
        }

        log.info("[KIS WS Handler] {}개 종목 구독 요청 시작...", stockCodes.size());

        WebSocketSession session = this.currentSession;
        for (String code : stockCodes) {
            if (session != null && session.isOpen()) {
                // session 존재 (연결됨) -> 즉시 전송
                sendSubscriptionRequest(code);
            } else {
                // session 존재 X (연결 안됨) -> 대기열 저장
                log.info("[KIS WS Handler] 연결 대기 중... 구독 요청 보류 (종목: {})", code);
                pendingSubscriptionList.add(code);
            }
        }
    }

    /**
     * [연결 성공 이벤트] 연결되자마자 대기열 비우기
     */
    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        // 기본 스프링과 톰캣의 버퍼크기는 8KB로 증권사의 문자열 데이터를 받기에는 너무 적다고 판단
        // 현재 세션의 버퍼크기를 5MB로 설정
        int maxBufferSize = 5 * 1024 * 1024; // 5MB
        session.setTextMessageSizeLimit(maxBufferSize);
        session.setBinaryMessageSizeLimit(maxBufferSize);

        log.info("[KIS WS Handler] 세션 연결 성공 (Session ID : {})", session.getId());
        this.currentSession = session;

        // 대기중인 요청 일괄 처리
        if (!pendingSubscriptionList.isEmpty()) {

            // 리스트 복사 후 처리
            ArrayList<String> targets = new ArrayList<>(pendingSubscriptionList);
            pendingSubscriptionList.clear();

            log.info("[KIS WS Handler] 대기 중이던 {}개 종목 구독 시작...", targets.size());

            for (int i = 0; i < targets.size(); i++) {
                String code = targets.get(i);
                taskScheduler.schedule(() -> sendSubscriptionRequest(code), Instant.now().plusMillis(i * 50L));
            }
        }
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        String payload = message.getPayload();

        if (payload.isEmpty()) return;

        try {
            if (payload.startsWith("{")) {
                // '{'로 시작한다면 JSON 포맷 (구독 응답, PINGPONG)
                processJsonMessage(payload);
            } else {
                // 텍스트 포맷 (실시간 주식 데이터)
                // KIS 데이터 포맷: 암호화여부(0/1) | TR_ID | 데이터(^으로 구분)
                handleRealTimeData(payload);
            }
        } catch (Exception e) {
            log.error("[KIS WS Handler] 메시지 처리 중 에러 발생 (Payload: {})", payload, e);
        }
    }

    // JSON 메시지 처리
    private void processJsonMessage(String payload) throws Exception {
        if (payload.contains("PINGPONG")) {
            return;
        }

        // 구독 성공 메시지 등 로그 출력
        log.info(">>> [KIS WS Handler] 제어 메시지: {}", payload);
    }

    // 실시간 주식 데이터 처리
    private void handleRealTimeData(String payload) {
        List<KisRealTimeData> dataList = dataParser.parse(payload);

        dataList.forEach(data -> {
            try {
                log.info("[KIS WS Handler] 실시간 체결 데이터 : {}", data.toString());
                eventPublisher.publishEvent(eventMapper.toEvent(data));
            } catch (Exception e) {
                log.error("[KIS WS Handler] 개별 체결 데이터 처리 및 발행 중 에러 발생. Data: {}", data, e);
            }
        });
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.error("[KIS WS Handler] 전송 에러 발생", exception);
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        log.warn("[KIS WS Handler] 연결 종료됨. Code: {}, Reason: {}", status.getCode(), status.getReason());
        this.currentSession = null;

        // 의도적으로 끊은게 아닐 때 Adapter 에게 재연결 요청 이벤트 발행
        if (status.getCode() != CloseStatus.NORMAL.getCode() || status.getCode() == 1000) {
            log.info("[KIS WS Handler] 재연결 이벤트 발행");
            eventPublisher.publishEvent(new KisWebSocketDisconnectedEvent(this, this.account, this.chunk));
        }
    }

    private void sendSubscriptionRequest(String stockCode) {
        if (subscribedStock.contains(stockCode)) return;

        try {
            KisSubscriptionRequest request = KisSubscriptionRequest.of(approveKey, stockCode);
            String jsonPayload = objectMapper.writeValueAsString(request);

            if (currentSession != null && currentSession.isOpen()) {
                currentSession.sendMessage(new TextMessage(jsonPayload));

                subscribedStock.add(stockCode);
            }
            log.info("[KIS WS] 구독 요청 전송 완료: {}", stockCode);

        } catch (JsonProcessingException e) {
            log.error("[KIS WS] JSON 변환 오류. 종목코드: {} (구독 건너뜀)", stockCode, e);
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
