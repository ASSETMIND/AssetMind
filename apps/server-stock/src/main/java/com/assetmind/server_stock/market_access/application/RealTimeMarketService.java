package com.assetmind.server_stock.market_access.application;

import com.assetmind.server_stock.market_access.application.port.RealTimeStockDataPort;
import com.assetmind.server_stock.market_access.domain.ApiApprovalKey;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

/**
 * 실시간 주식 데이터 수집 총괄 서비스
 * 서버의 시작/종료에 맞춰 연결 수명주기를 관리하고,
 * 필요한 데이터를 구독하도록 지시
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RealTimeMarketService {

    private final MarketAccessService marketAccessService; // 인증 담당
    private final RealTimeStockDataPort realTimeStockDataPort; // 연결 담당
    private final StockMetadataProvider stockMetadataProvider; // 구독 요청 주식 메타데이터 제공자

    /**
     * [서버 시작 시] 자동으로 실행
     * 1. 인증키 발급
     * 2. 웹소켓 연결
     * 3. 기본 종목 구독
     *
     * @PostConstruct 대신 ApplicationReadyEvent를 사용하여,
     * 주식 메타데이터 DB 캐싱 등 모든 초기화가 안전하게 끝난 후 KIS에 웹소켓 연결 시작
     */
    @EventListener(ApplicationReadyEvent.class)
    public void startMarketDataCollection() {
        log.info(">>> [RealTimeMarketService] 실시간 주식 데이터 수집 서비스를 시작합니다.");

        try {

            // 1. StockMetaDataProvider에서 캐싱된 전체 종목 코드 가져오기
            List<String> stockCodes = stockMetadataProvider.getAllStockCodes();

            if (stockCodes.isEmpty()) {
                log.warn(">>> [RealTimeMarketService] 구독할 주식 메타 데이터가 존재하지 않습니다.");
                return;
            }

            log.info(">>> [RealTimeMarketService] 구독 대상 종목 수: {}", stockCodes.size());

            // 2. 인증키 가져오기 (이미 구현된 로직 활용)
            ApiApprovalKey approvalKey = marketAccessService.getApprovalKey();
            String keyString = approvalKey.value();

            // 3. 연결 시작
            realTimeStockDataPort.connect(keyString);

            // 4. 구독 요청
            // 주의: connect()는 비동기라 연결 되기 전에 subscribe가 호출될 수 있음.
            // 하지만 Handler 내부에서 세션 체크를 하고 있으므로 안전하거나,
            // 혹은 연결 확립 후(Handler.afterConnectionEstablished)에 구독하는 방식이 더 안전함.
            // 여기서는 '명령을 내린다'는 의미로 호출함.
            realTimeStockDataPort.subscribe(stockCodes);

        } catch (Exception e) {
            log.error(">>> [RealTimeMarketService] 연결 구독 요청 중 치명적 오류 발생", e);
        }
    }

    /**
     * [서버 종료 시] 우아한 종료 (Graceful Shutdown)
     */
    @PreDestroy
    public void stopMarketDataCollection() {
        log.warn(">>> [RealTimeMarketService] 서버 종료 감지. 연결을 해제합니다.");
        realTimeStockDataPort.disconnect();
    }
}
