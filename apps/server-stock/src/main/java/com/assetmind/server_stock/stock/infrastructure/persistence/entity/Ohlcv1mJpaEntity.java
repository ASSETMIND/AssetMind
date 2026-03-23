package com.assetmind.server_stock.stock.infrastructure.persistence.entity;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys.OhlcvId;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "ohlcv_1m")
@IdClass(OhlcvId.class)
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Ohlcv1mJpaEntity {

    @Id
    @Column(name = "stock_code", nullable = false, length = 20)
    private String stockCode;

    @Id
    @Column(name = "candle_timestamp", nullable = false)
    private LocalDateTime candleTimestamp;

    @Column(name = "open_price", nullable = false)
    private Double openPrice;

    @Column(name = "high_price", nullable = false)
    private Double highPrice;

    @Column(name = "low_price", nullable = false)
    private Double lowPrice;

    @Column(name = "close_price", nullable = false)
    private Double closePrice;

    @Column(name = "volume", nullable = false)
    private Long volume;

    @Builder
    public Ohlcv1mJpaEntity(String stockCode, LocalDateTime candleTimestamp,
            Double openPrice, Double highPrice, Double lowPrice, Double closePrice, Long volume) {
        this.stockCode = stockCode;
        this.candleTimestamp = candleTimestamp;
        this.openPrice = openPrice;
        this.highPrice = highPrice;
        this.lowPrice = lowPrice;
        this.closePrice = closePrice;
        this.volume = volume;
    }

}
