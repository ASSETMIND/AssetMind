package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1mJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys.OhlcvId;
import java.time.LocalDateTime;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface Ohlcv1mJpaRepository extends JpaRepository<Ohlcv1mJpaEntity, OhlcvId> {

    /**
     * 특정 종목의 특정 시간대(예: 오늘 하루) 1분봉 데이터를 조회
     * (1일봉 롤업 집계용 쿼리 메서드)
     */
    @Query("SELECT o FROM Ohlcv1mJpaEntity o"
            + " WHERE o.stockCode = :stockCode"
            + " AND o.candleTimestamp >= :startTime"
            + " AND o.candleTimestamp < :endTime")
    List<Ohlcv1mJpaEntity> findCandlesByTimeRange(
            @Param("stockCode") String stockCode,
            @Param("startTime") LocalDateTime startTime,
            @Param("endTime") LocalDateTime endTime
    );
}
