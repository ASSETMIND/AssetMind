package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1mJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys.OhlcvId;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.projection.ChartCandleProjection;
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

    @Query(value = """
          SELECT 
              date_bin(CAST(:intervalString AS INTERVAL), candle_timestamp, TIMESTAMP '2000-01-01') AS candleTimestamp,
              (array_agg(open_price ORDER BY candle_timestamp ASC))[1] AS open,
              MAX(high_price) AS high,
              MIN(low_price) AS low,
              (array_agg(close_price ORDER BY candle_timestamp DESC ))[1] AS close,
              SUM(volume) AS volume
          FROM ohlcv_1m
          WHERE stock_code = :stockCode AND candle_timestamp <= :endTime
          GROUP BY candleTimestamp
          ORDER BY candleTimestamp DESC
          LIMIT :limit
        """, nativeQuery = true)
    List<ChartCandleProjection> findDynamicMinuteCandles(
            @Param("stockCode") String stockCode,
            @Param("intervalString") String intervalString,
            @Param("endTime") LocalDateTime endTime,
            @Param("limit") int limit
    );
}
