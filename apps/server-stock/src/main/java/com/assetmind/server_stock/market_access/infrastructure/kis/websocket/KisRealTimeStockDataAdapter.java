package com.assetmind.server_stock.market_access.infrastructure.kis.websocket;

import com.assetmind.server_stock.market_access.application.event.KisWebSocketDisconnectedEvent;
import com.assetmind.server_stock.market_access.application.port.RealTimeStockDataPort;
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
import java.util.concurrent.CopyOnWriteArrayList;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;

/**
 * KIS 실시간 주식 데이터 수집 어댑터
 * 40개 제한 멀티플렉싱(Multiplexing), 다중 AppKey 관리 등
 * KIS에 종속적인 모든 인프라 로직을 이곳에서 담당
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class KisRealTimeStockDataAdapter implements RealTimeStockDataPort {

    private final KisProperties kisProperties;
    private final MarketTokenProvider marketTokenProvider;
    private final TaskScheduler taskScheduler;

    // KisWebSocketHandler 생성을 위한 의존객체들
    private final ObjectMapper objectMapper;
    private final KisRealTimeDataParser dataParser;
    private final KisEventMapper eventMapper;
    private final ApplicationEventPublisher eventPublisher;


    private WebSocketClient webSocketClient;

    // 활성화된 핸들러(세션)들을 추적 및 관리
    private final List<KisWebSocketHandler> activeHandlers = new CopyOnWriteArrayList<>();

    private static final int MAX_SUBSCRIBE_PER_SESSION = 40;

    @Override
    public void prepareConnection() {
        log.info("[KIS Adapter] 웹소켓 클라이언트 초기화");

        this.webSocketClient = new StandardWebSocketClient();
    }

    @Override
    public void subscribe(List<String> stockCodes) {
        if (this.webSocketClient == null) {
            prepareConnection(); // 호출 순서 보장
        }

        List<Account> accounts = kisProperties.getAccounts();

        // KIS 웹소켓 요청 한도에 맞춰 40개씩 분할
        List<List<String>> partitionedStocks = partitionList(stockCodes, MAX_SUBSCRIBE_PER_SESSION);

        for (int i = 0; i < partitionedStocks.size(); i++) {
            if (i >= accounts.size()) {
                log.warn("App Key가 부족합니다. (등록된 키: {}개, 필요한 키: {}개", accounts.size(), partitionedStocks.size());
                break;
            }

            List<String> chunk = partitionedStocks.get(i);
            Account account = accounts.get(i);
            int sessionIndex = i + 1;

            // KIS 서버 부하 방지를 위해 각 세션 연결 시도는 1초 간격으로 스케일링
            Instant executionTime = Instant.now().plusSeconds(i);
            taskScheduler.schedule(() -> {
                log.info("[KIS WS Session #{}] {}개 종목 연결 및 구독 시도", sessionIndex, chunk.size());

                try {
                    establishSession(account, chunk);
                } catch (Exception e) {
                    log.error("[KIS WS Session #{}] 연결 실패", sessionIndex, e);
                }
            }, executionTime);
        }

    }

    @Override
    public void disconnect() {
        log.info("🛑 열려있는 모든 KIS 웹소켓 세션을 종료합니다. (현재 활성 세션: {}개)", activeHandlers.size());
        for (KisWebSocketHandler handler : activeHandlers) {
            handler.closeConnection();
        }
        activeHandlers.clear();
    }

    /**
     * 핸들러가 연결이 끊어지면서 보낸 이벤트를 수신하여 해당 핸들러 객체를 지우고 재연결을 시도
     * @param event
     */
    @EventListener
    public void handleWebSocketDisconnected(KisWebSocketDisconnectedEvent event) {
        log.warn("[KIS Adapter] 웹소켓 끊김 이벤트 수신. 기존 핸들러 제거 및 재연결 프로세스 시작");

        activeHandlers.remove(event.disconnectedHandler());

        // 최초 재연결 시도는 1회차(retryCount = 1)로 시작
        scheduleReconnect(event.account(), event.disconnectedStocks(), 1);
    }

    /**
     * 실패하면 스스로를 다시 호출하는 재연결 스케줄러
     */
    private void scheduleReconnect(Account account, List<String> chunk, int retryCount) {
        // 재시도 횟수에 따라 대기 시간을 지수 단위로 늘림, 최대 60초
        int delaySeconds = Math.min(3 * (int) Math.pow(2, retryCount - 1), 60);
        Instant executionTime = Instant.now().plusSeconds(delaySeconds);

        taskScheduler.schedule(() -> {
            log.info(">>> [Reconnect Task] {}개 종목 재연결 시도 ({}회차)", chunk.size(), retryCount);

            try {
                establishSession(account, chunk);
                log.info(">>> [Reconnect Task] 재연결 성공! ({}회차 만에 복구됨)", retryCount);
            } catch (Exception e) {
                log.error(">>> [Reconnect Task] 재연결 실패. {}초 뒤 다시 시도합니다.", delaySeconds, e);
                // 실패했을 경우 retryCount를 올려서 다시 스케줄링!
                scheduleReconnect(account, chunk, retryCount + 1);
            }
        }, executionTime);
    }

    // ["삼성전자", "하이닉스" .. ] -> [ ["삼성전자", ...], ["하이닉스", ...] ] 로 쪼개주는 메서드
    private <T> List<List<T>> partitionList(List<T> list, int size) {
        List<List<T>> partitions = new ArrayList<>();
        for (int i = 0; i < list.size(); i+= size) {
            // 40개 씩 나눠야하는데 40개 보다 작으면 IndexOutOfBounds 에러를 방지하기 위해 40개보다 작은 값으로 자름
            partitions.add(new ArrayList<>(list.subList(i, Math.min(i + size, list.size()))));
        }
        return partitions;
    }

    /**
     * 특정 계좌 정보와 종목 리스트를 받아 실제 웹소켓 세션을 확립합니다.
     */
    private void establishSession(Account account, List<String> chunk) {
        // 접속키 발급
        ApiApprovalKey approvalKey = marketTokenProvider.fetchApprovalKey(account.appKey(), account.appSecret());

        // 핸들러 생성
        KisWebSocketHandler handler = new KisWebSocketHandler(
                approvalKey.value(), account, chunk,
                objectMapper, dataParser, eventMapper, eventPublisher, taskScheduler
        );

        // 관리 리스트에 추가 및 물리적 연결 실행
        activeHandlers.add(handler);
        webSocketClient.execute(handler, kisProperties.getWebsocketUrl());
    }
}
