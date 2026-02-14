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

/**
 * 과거 주식 데이터를 저장하기 위한 영속성 객체
 */
@Getter
@Entity
@Table(name = "stock_data")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class StockDataEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String stockCode;       // 종목 코드

    // --- 가격 정보 ---
    @Column(nullable = false)
    private Long currentPrice;      // 현재가 (Close)
    private Long openPrice;         // 시가 (Open)
    private Long highPrice;         // 고가 (High)
    private Long lowPrice;          // 저가 (Low)

    // --- 등락 정보 ---
    private Long priceChange;       // 전일 대비 (+1000, -500)
    private Double changeRate;      // 등락률 (+1.5, -0.5)

    // --- 거래량 정보 ---
    private Long executionVolume;   // 체결량
    private Long tradingVolume;     // 누적 거래량 (Volume)
    private Long tradingAmount;     // 누적 거래대금 (Trade Value)

    private String time;            // 체결시간 (HHmmss)

    @Column(updatable = false)
    private LocalDateTime createdAt; // DB 저장 시점 (데이터 수신 시점)

    @Builder
    public StockDataEntity(String stockCode, Long currentPrice, Long openPrice, Long highPrice, Long lowPrice,
            Long priceChange, Double changeRate, Long executionVolume, Long tradingVolume, Long tradingAmount, String time,LocalDateTime createdAt) {
        this.stockCode = stockCode;
        this.currentPrice = currentPrice;
        this.openPrice = openPrice;
        this.highPrice = highPrice;
        this.lowPrice = lowPrice;
        this.priceChange = priceChange;
        this.changeRate = changeRate;
        this.executionVolume = executionVolume;
        this.tradingVolume = tradingVolume;
        this.tradingAmount = tradingAmount;
        this.time = time;
        this.createdAt = (createdAt == null) ? LocalDateTime.now() : createdAt;
    }
}
