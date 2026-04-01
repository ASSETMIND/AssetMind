package com.assetmind.server_stock.stock.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "raw_tick")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RawTickJpaEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "stock_code", nullable = false, length = 20)
    private String stockCode;

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
