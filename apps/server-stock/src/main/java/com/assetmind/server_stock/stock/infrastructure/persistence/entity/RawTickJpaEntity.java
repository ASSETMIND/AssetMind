package com.assetmind.server_stock.stock.infrastructure.persistence.entity;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.keys.TickId;
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
@Table(name = "raw_tick")
@IdClass(TickId.class)
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RawTickJpaEntity {
    @Id
    @Column(name = "stock_code", nullable = false, length = 20)
    private String stockCode;

    @Id
    @Column(name = "trade_timestamp", nullable = false)
    private LocalDateTime tradeTimestamp;

    @Column(name = "current_price", nullable = false)
    private Double currentPrice;

    @Column(name = "price_change", nullable = false)
    private Double priceChange;

    @Column(name = "volume", nullable = false)
    private Long volume;

    @Builder
    public RawTickJpaEntity(String stockCode, Double currentPrice, Double priceChange, Long volume, LocalDateTime tradeTimestamp) {
        this.stockCode = stockCode;
        this.currentPrice = currentPrice;
        this.priceChange = priceChange;
        this.volume = volume;
        this.tradeTimestamp = tradeTimestamp;
    }
}
