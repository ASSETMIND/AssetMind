package com.assetmind.server_stock.market_access.domain;

import java.time.LocalTime;
import java.util.List;

/**
 * 호가 데이터 모델
 */
public record OrderBook(
        String stockCode, // 종목 코드
        LocalTime marketTime, // 호가 수신 시간
        Long totalAskSize, // 총 매도 호가 잔량
        Long totalBidSize, // 총 매수 호가 잔량
        List<Level> levels // 1~10 호가
) {

    public record Level(
            int level, // 1~10
            Float askPrice, // 매도 호가
            Float askSize, // 매도 잔량
            Float bidPrice, // 매수 호가
            Float bidSize // 매수 잔량
    ) {}

}
