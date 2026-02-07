package com.assetmind.server_stock.stock.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

/**
 * 과거 주식 데이터를 저장하기 위한 영속성 객체
 */
@Entity
@Table(name = "stock_data")
@EntityListeners(AuditingEntityListener.class)
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class StockDataEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String stockCode;       // 종목 코드

    @Column(nullable = false)
    private Long price;             // 현재가

    @Column(nullable = false)
    private String time;            // 체결 시간 (HHmmss)

    private Long volume;            // 누적 거래량

    private Double changeRate;      // 등락률

    @CreatedDate
    @Column(updatable = false)
    private LocalDateTime createdAt; // DB 저장 시점 (데이터 수신 시점)

    @Builder
    public StockDataEntity(String stockCode, Long price, String time, Long volume, Double changeRate) {
        this.stockCode = stockCode;
        this.price = price;
        this.time = time;
        this.volume = volume;
        this.changeRate = changeRate;
    }
}
