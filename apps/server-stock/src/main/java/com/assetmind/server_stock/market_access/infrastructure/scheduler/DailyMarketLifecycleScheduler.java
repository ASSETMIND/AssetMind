package com.assetmind.server_stock.market_access.infrastructure.scheduler;

import com.assetmind.server_stock.market_access.application.port.RealTimeStockDataPort;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 장 시작/마감시에 KIS 세션과 연결을 수립 및 종료 하여 실시간 체결 데이터 수집 파이프라인을 초기화 및 종료를 담당하는 스케줄러
 * 장 시작 전(오전 8시 30분)에 실시간 체결 데이터 파이프라인을 연결하고
 * 장(정규장) 마감 이후 (오후 4시 30분)에 실시간 체결 데이터 파이프라인을 종료하여
 * 새벽내내 핑퐁을 쏘는 자원 낭비를 방지
 */
@Slf4j
@RequiredArgsConstructor
@Component
public class DailyMarketLifecycleScheduler {
    private final RealTimeStockDataPort realTimeStockDataPort;

    private final StockMetadataProvider stockMetadataProvider;

    /**
     * 매주 월~금 오전 8시 30분 파이프라인 연결
     */
    @Scheduled(cron = "0 30 8 * * MON-FRI", zone = "Asia/Seoul")
    public void wakeUpPipeline() {
        log.info("[DailyMarketLifecycleScheduler] 장 시작 준비: 체결 데이터 수집 파이프라인 초기화 및 연결 시작");
        try {
            // 네트워크 연결을 위한 기초 세팅
            realTimeStockDataPort.prepareConnection();

            Thread.sleep(1000);

            // KOSPI 80 개의 종목 조회
            List<String> targetStocks = stockMetadataProvider.getAllStockCodes();

            // 종목 구독 요청(Adapter 내부에서 40개씩 청킹하여 구독)
            realTimeStockDataPort.subscribe(targetStocks);
        } catch (Exception e) {
            log.error("[DailyMarketLifecycleScheduler] 체결 데이터 수집 파이프라인 연결 중 에러 발생", e);
        }
    }

    /**
     * 매주 월~금 오후 4시 30분 파이프라인 종료
     */
    @Scheduled(cron = "0 30 16 * * MON-FRI", zone = "Asia/Seoul")
    public void sleepPipeline() {
        log.info("[DailyMarketLifecycleScheduler] 장 마감: 체결 데이터 수집 파이프라인 자원 반환 및 웹소켓 연결 종료");
        try {
            // 진행 중인 모든 실시간 연결 안전하게 종료
            realTimeStockDataPort.disconnect();

            log.info("[DailyMarketLifecycleScheduler] 체결 데이터 수잡 파이프라인 정상적으로 종료");
        } catch (Exception e) {
            log.error("[DailyMarketLifecycleScheduler] 체결 데이터 수집 파이프라인 종료 중 에러 발생", e);
        }
    }
}
