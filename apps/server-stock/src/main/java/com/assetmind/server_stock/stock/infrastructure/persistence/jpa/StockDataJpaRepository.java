package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface StockDataJpaRepository extends JpaRepository<StockDataEntity, Long> {

    @Query("SELECT s FROM StockDataEntity s WHERE s.stockCode = :stockCode ORDER BY s.createdAt DESC")
    List<StockDataEntity> findByStockCodeOrderByCreatedAtDesc(@Param("stockCode") String stockCode, Pageable pageable);
}
