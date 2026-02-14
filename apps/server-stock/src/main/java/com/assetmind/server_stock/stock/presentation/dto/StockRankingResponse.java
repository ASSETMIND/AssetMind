package com.assetmind.server_stock.stock.presentation.dto;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockPriceRedisEntity;
import lombok.Builder;

/**
 * 실시간 주식 데이터 랭킹 순 응답 DTO
 * @param stockCode         - 종목 코드
 * @param stockName         - 종목 이름
 * @param currentPrice      - 현재가
 * @param changeRate        - 등락률
 * @param cumulativeAmount  - 누적 거래 대금
 * @param cumulativeVolume  - 누적 거래량
 */
@Builder
public record StockRankingResponse(
        String stockCode,
        String stockName,
        String currentPrice,
        String changeRate,
        String cumulativeAmount,
        String cumulativeVolume
) {
    public static StockRankingResponse from(StockPriceRedisEntity entity) {
        return StockRankingResponse.builder()
                .stockCode(entity.getStockCode())
                .stockName(entity.getStockName())
                .currentPrice(String.valueOf(entity.getCurrentPrice()))
                .changeRate(String.valueOf(entity.getChangeRate()))
                .cumulativeAmount(String.valueOf(entity.getCumulativeAmount()))
                .cumulativeVolume(String.valueOf(entity.getCumulativeVolume()))
                .build();
    }
}
