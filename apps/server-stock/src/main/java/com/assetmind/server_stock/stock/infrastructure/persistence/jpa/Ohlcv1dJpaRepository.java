package com.assetmind.server_stock.stock.infrastructure.persistence.jpa;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.Ohlcv1dJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys.OhlcvId;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.projection.ChartCandleProjection;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface Ohlcv1dJpaRepository extends JpaRepository<Ohlcv1dJpaEntity, OhlcvId> {

    /**
     * 특정 주식의 지정된 날짜 범위(예: 하루 전체)에 해당하는 1일봉 단건을 조회한다.
     */
    @Query("SELECT o FROM Ohlcv1dJpaEntity o"
            + " WHERE o.stockCode = :stockCode"
            + " AND o.candleTimestamp >= :startDay"
            + " AND o.candleTimestamp < :endDay")
    Optional<Ohlcv1dJpaEntity> findCandleByDay(
            @Param("stockCode") String stockCode,
            @Param("startDay") LocalDateTime startDay,
            @Param("endDay") LocalDateTime endDay
    );

    /**
     * 고정 길이 롤업 - N일봉, N주봉 캔들을 동적으로 집계한다.
     * date_bin() 함수를 사용하여 3일, 1주 등 고정된 절대 시간을 기준으로 그룹을 나누고,
     * 해당 그룹 안에서 첫 번째 값을 시가(Open), 마지막 값을 종가(Close)로 추출한다.
     */
    @Query(value = """
        SELECT
            date_bin(CAST(:intervalString AS interval), candle_timestamp, TIMESTAMP '2000-01-01') AS candleTimestamp,
            (array_agg(open_price ORDER BY candle_timestamp ASC))[1] AS open,
            MAX(high_price) AS high,
            MIN(low_price) AS low,
            (array_agg(close_price ORDER BY candle_timestamp DESC))[1] AS close,
            SUM(volume) AS volume
        FROM ohlcv_1d
        WHERE stock_code = :stockCode AND candle_timestamp <= :endTime
        GROUP BY candleTimestamp
        ORDER BY candleTimestamp DESC
        LIMIT :limit
        """, nativeQuery = true)
    List<ChartCandleProjection> findDynamicDailyCandles(
            @Param("stockCode") String stockCode,
            @Param("intervalString") String intervalString,
            @Param("endTime") LocalDateTime endTime,
            @Param("limit") int limit
    );

    /**
     * 가변 길이 롤업 - 1월봉 캔들을 동적으로 집계한다.
     * 월마다 일수(28~31일)가 다르기 때문에 date_bin 대신 date_trunc('month')를 사용하여
     * 일수를 모두 잘라내고 해당 월의 1일 기준으로 바구니를 묶어 OHLCV를 추출한다.
     */
    @Query(value = """
        SELECT
            date_trunc('month', candle_timestamp) AS candleTimestamp,
            (array_agg(open_price ORDER BY candle_timestamp ASC))[1] AS open,
            MAX(high_price) AS high,
            MIN(low_price) AS low,
            (array_agg(close_price ORDER BY candle_timestamp DESC))[1] AS close,
            SUM(volume) AS volume
        FROM ohlcv_1d
        WHERE stock_code = :stockCode AND candle_timestamp <= :endTime
        GROUP BY candleTimestamp
        ORDER BY candleTimestamp DESC
        LIMIT :limit
        """, nativeQuery = true)
    List<ChartCandleProjection> findMonthlyCandles(
            @Param("stockCode") String stockCode,
            @Param("endTime") LocalDateTime endTime,
            @Param("limit") int limit
    );

    /**
     * 가변 길이 롤업 - 1년봉 캔들을 동적으로 집계한다.
     * 윤년(366일)과 평년(365일)의 차이를 무시하기 위해 date_trunc('year')를 사용하여
     * 월과 일을 모두 잘라내고 해당 연도의 1월 1일 기준으로 바구니를 묶어 OHLCV를 추출한다.
     */
    @Query(value = """
        SELECT
            date_trunc('year', candle_timestamp) AS candleTimestamp,
            (array_agg(open_price ORDER BY candle_timestamp ASC))[1] AS open,
            MAX(high_price) AS high,
            MIN(low_price) AS low,
            (array_agg(close_price ORDER BY candle_timestamp DESC))[1] AS close,
            SUM(volume) AS volume
        FROM ohlcv_1d
        WHERE stock_code = :stockCode AND candle_timestamp <= :endTime
        GROUP BY candleTimestamp
        ORDER BY candleTimestamp DESC
        LIMIT :limit
        """, nativeQuery = true)
    List<ChartCandleProjection> findYearlyCandles(
            @Param("stockCode") String stockCode,
            @Param("endTime") LocalDateTime endTime,
            @Param("limit") int limit
    );

}
