package com.assetmind.server_stock.stock.application;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.application.mapper.StockMapper;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.stock.domain.repository.StockHistoryRepository;
import com.assetmind.server_stock.stock.domain.repository.StockSnapshotRepository;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 주가 데이터를 저장소를 이용하여 저장 및 조회를 해주고 예외를 처리하는 오케스트레이션 역할을 한다.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true) // 기본적으로 조회 전용으로 설정 (성능 향상)
public class StockService {

    private final StockSnapshotRepository stockSnapshotRepository;
    private final StockHistoryRepository stockHistoryRepository;
    private final StockMetadataProvider stockMetadataProvider;
    private final StockMapper stockMapper;

    // 실시간 주가 처리
    @Transactional // 쓰기 작업
    public void processRealTimeTrade(RealTimeStockTradeEvent event) {
        // 캐싱된 국내 전체 주식에서 실시간 주식 데이터의 주식 이름 추출
        String stockName = stockMetadataProvider.getStockName(event.stockCode());

        // 실시간 주식 데이터 캐싱
        stockSnapshotRepository.save(stockMapper.toRedisEntity(event, stockName));

        // 실시간 주식 데이터 저장
        stockHistoryRepository.save(stockMapper.toJpaEntity(event));
    }

    // 누적 거래대금 순 조회
    public List<StockPriceRedisEntity> getTopStocksByTradeValue(int limit) {
        return stockSnapshotRepository.getTopStocksByTradeValue(limit);
    }

    // 누적 거래량 순 조회
    public List<StockPriceRedisEntity> getTopStocksByTradeVolume(int limit) {
        return stockSnapshotRepository.getTopStocksByTradeVolume(limit);
    }

    // 특정 주식의 시계열 데이터 조회
    public List<StockDataEntity> getStockRecentHistory(String stockCode, int limit) {
        return stockHistoryRepository.findRecentData(stockCode, limit);
    }
}
