package com.assetmind.server_stock.stock.infrastructure.persistence.entity;

import java.io.Serializable;
import lombok.Builder;
import lombok.Getter;
import org.springframework.data.annotation.Id;
import org.springframework.data.redis.core.RedisHash;

/**
 * 실시간 최신가를 빠르게 조회하기 위한 인메모리(Redis) 객체
 */
@Getter
@RedisHash(value = "stock_snapshot", timeToLive = 600) // TTL : 10분, 실시간 데이터이므로 과거의 데이터는 오래 캐싱할 필요가 없음
public class StockPriceRedisEntity implements Serializable {

    @Id
    private String stockCode;       // 종목 코드, Redis 각 Value의 Key 값

    private String stockName;       // 종목 이름

    private Long currentPrice;      // 현재가

    private Long priceChange;       // 전일 대비 변동 금액

    private Double changeRate;      // 등락률

    private Long cumulativeAmount;  // 누적 거래 대금

    private Long cumulativeVolume;  // 누적 거래량

    private String time;            // 체결 시간 (HHmmss)

    @Builder
    public StockPriceRedisEntity(String stockCode, String stockName, Long currentPrice, Long priceChange,
            Double changeRate, Long cumulativeAmount, Long cumulativeVolume, String time) {
        this.stockCode = stockCode;
        this.stockName = stockName;
        this.currentPrice = currentPrice;
        this.priceChange = priceChange;
        this.changeRate = changeRate;
        this.cumulativeAmount = cumulativeAmount;
        this.cumulativeVolume = cumulativeVolume;
        this.time = time;
    }
}
