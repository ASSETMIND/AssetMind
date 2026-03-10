package com.assetmind.server_stock.stock.application;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.stock.application.event.StockHistorySavedEvent;
import com.assetmind.server_stock.stock.application.event.StockRankingUpdatedEvent;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.application.mapper.StockMapper;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.stock.domain.repository.StockHistoryRepository;
import com.assetmind.server_stock.stock.domain.repository.StockSnapshotRepository;
import com.assetmind.server_stock.stock.exception.StockNotFoundException;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import com.assetmind.server_stock.stock.presentation.dto.StockHistoryResponse;
import com.assetmind.server_stock.stock.presentation.dto.StockRankingResponse;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 주가 데이터를 저장소를 이용하여 저장 및 조회를 해주고 예외를 처리하는 오케스트레이션 역할을 한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true) // 기본적으로 조회 전용으로 설정 (성능 향상)
public class StockService {

    private final StockSnapshotRepository stockSnapshotRepository;
    private final StockHistoryRepository stockHistoryRepository;
    private final StockMetadataProvider stockMetadataProvider;
    private final StockMapper stockMapper;
    private final ApplicationEventPublisher eventPublisher;

    // 실시간 주가 처리
    @Transactional // 쓰기 작업
    public void processRealTimeTrade(RealTimeStockTradeEvent event) {

        if (event == null || event.stockCode() == null || event.stockCode().isBlank()) {
            throw new IllegalArgumentException("실시간 체결 데이터 이벤트에 필수 값이 누락되었습니다. (event: " + event + ")");
        }

        log.info("[StockService] 체결 데이터 수신: {}", event.stockCode());

        // 캐싱된 국내 전체 주식에서 실시간 주식 데이터의 주식 이름 추출
        String stockName = stockMetadataProvider.getStockName(event.stockCode());

        // 실시간 주식 데이터 캐싱
        StockPriceRedisEntity redisEntity = stockMapper.toRedisEntity(event, stockName);
        stockSnapshotRepository.save(redisEntity);

        // 메인 랭킹용(메인 차트 페이지) 이벤트 발행
        StockRankingResponse rankingResponse = StockRankingResponse.from(redisEntity);
        log.info("[StockService] Redis Entity: {}", rankingResponse);
        eventPublisher.publishEvent(new StockRankingUpdatedEvent(rankingResponse));

        // 실시간 주식 시계열 데이터 저장
        StockDataEntity jpaEntity = stockMapper.toJpaEntity(event);
        stockHistoryRepository.save(jpaEntity);

        // 상세 페이지용 이벤트 발행
        StockHistoryResponse historyResponse = StockHistoryResponse.from(jpaEntity);
        eventPublisher.publishEvent(new StockHistorySavedEvent(event.stockCode(), historyResponse));
    }

    // 누적 거래대금 순 조회
    public List<StockRankingResponse> getTopStocksByTradeValue(int limit) {
        return stockSnapshotRepository.getTopStocksByTradeValue(limit).stream()
                .map(StockRankingResponse::from)
                .toList();
    }

    // 누적 거래량 순 조회
    public List<StockRankingResponse> getTopStocksByTradeVolume(int limit) {
        return stockSnapshotRepository.getTopStocksByTradeVolume(limit).stream()
                .map(StockRankingResponse::from)
                .toList();
    }

    // 특정 주식의 시계열 데이터 조회
    public List<StockHistoryResponse> getStockRecentHistory(String stockCode, int limit) {
        if (!stockMetadataProvider.isExist(stockCode)) {
            throw new StockNotFoundException(ErrorCode.NOT_FOUND_STOCK);
        }

        return stockHistoryRepository.findRecentData(stockCode, limit).stream()
                .map(StockHistoryResponse::from)
                .toList();
    }
}
