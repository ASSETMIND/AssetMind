package com.assetmind.server_stock.stock.infrastructure.persistence.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.NoArgsConstructor;

/**
 * 정적 데이터(종목명, 시장 구분 등)를 저장하기 위한 영속성 객체
 */
@Entity
@Table(name = "stock_meta_data")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class StockMetaEntity {

    @Id
    private String stockCode; // 종목코드

    private String stockName; // 종목이름

    private String market; // KOSPI, KOSDAQ

    @Builder
    public StockMetaEntity(String stockCode, String stockName, String market) {
        this.stockCode = stockCode;
        this.stockName = stockName;
        this.market = market;
    }
}
