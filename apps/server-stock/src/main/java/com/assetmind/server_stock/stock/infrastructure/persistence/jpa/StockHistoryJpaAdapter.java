package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.domain.repository.StockHistoryRepository;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Repository;

/**
 * {@link StockHistoryRepository}를 Jpa 기술을 사용하여 구현한 구현체
 */
@Repository
@RequiredArgsConstructor
public class StockHistoryJpaAdapter implements StockHistoryRepository {

    private final StockDataJpaRepository stockDataJpaRepository;

    @Override
    public StockDataEntity save(StockDataEntity dataEntity) {
        return stockDataJpaRepository.save(dataEntity);
    }

    @Override
    public List<StockDataEntity> findRecentData(String stockCode, int limit) {
        Pageable page = PageRequest.of(0, limit);
        return stockDataJpaRepository.findByStockCodeOrderByCreatedAtDesc(stockCode, page);
    }
}
