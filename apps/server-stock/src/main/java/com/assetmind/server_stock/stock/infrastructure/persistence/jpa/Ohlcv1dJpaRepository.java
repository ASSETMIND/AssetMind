package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1dJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys.OhlcvId;
import java.time.LocalDateTime;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface Ohlcv1dJpaRepository extends JpaRepository<Ohlcv1dJpaEntity, OhlcvId> {

    @Query("SELECT o FROM Ohlcv1dJpaEntity o"
            + " WHERE o.stockCode = :stockCode"
            + " AND o.candleTimestamp >= :startDay"
            + " AND o.candleTimestamp < :endDay")
    Optional<Ohlcv1dJpaEntity> findCandleByDay(
            @Param("stockCode") String stockCode,
            @Param("startDay") LocalDateTime startDay,
            @Param("endDay") LocalDateTime endDay
    );
}
