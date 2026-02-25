package com.assetmind.server_stock.stock.application.provider;

import com.assetmind.server_stock.stock.infrastructure.persistence.jpa.StockMetaRepository;
import jakarta.annotation.PostConstruct;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * 주식 메타데이터(종목코드, 종목명 등)를 메모리에 캐싱하여 제공하는 Provider
 *
 * 실시간 주가 데이터 처리 시 발생하는 DB 부하를 제거하고 조회 속도를 높이기 위해
 * 서버 시작 시점에 DB에서 데이터를 로드하여 {@link ConcurrentHashMap}에 보관
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class StockMetadataProvider {

    private final StockMetaRepository stockMetaRepository;

    // 인메모리 캐시 저장소 (Key: 종목코드, Value: 종목명)
    // 멀티 스레드 환경에서 동시성 이슈 방지를 위해 ConcurrentHashMap 사용
    private final Map<String, String> stockNameCache = new ConcurrentHashMap<>();

    @PostConstruct
    public void init() {
        log.info("[StockMetadataProvider] 주식 메타데이터 캐싱 시작");
        stockMetaRepository.findAll().forEach(data ->
                stockNameCache.put(data.getStockCode(), data.getStockName())
        );
        log.info("[StockMetadataProvider] {} 개의 주식 메타데이터 캐싱", stockNameCache.size());
    }

    // 종목 코드를 기반으로 해당 종목 코드가 캐싱되어있는지 확인
    public boolean isExist(String stockCode) {
        return stockNameCache.containsKey(stockCode);
    }

    // 종목 코드를 기반으로 종목 이름 조회
    public String getStockName(String stockCode) {
        return stockNameCache.getOrDefault(stockCode, stockCode);
    }
}
