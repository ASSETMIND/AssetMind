package com.assetmind.server_stock.stock.presentation.dto;

import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import lombok.Builder;

/**
 * 실시간 주식 시계열 데이터 응답 DTO
 * @param stockCode         - 종목 코드
 * @param currentPrice      - 현재가
 * @param openPrice         - 시가
 * @param highPrice         - 고가
 * @param lowPrice          - 저가
 * @param priceChange       - 전일 대비 (+1000, -500)
 * @param changeRate        - 등락률 (+1.5, -2)
 * @param executionVolume   - 체결량
 * @param tradingAmount     - 누적 거래 대금
 * @param tradingVolume     - 누적 거래량
 * @param time              - 체결 시간
 */
@Builder
public record StockHistoryResponse(
        String stockCode,
        String currentPrice,
        String openPrice,
        String highPrice,
        String lowPrice,
        String priceChange,
        String changeRate,
        String executionVolume,
        String cumulativeAmount,
        String cumulativeVolume,
        String time
) {
    public static StockHistoryResponse from(StockDataEntity entity) {
        return StockHistoryResponse.builder()
                .stockCode(entity.getStockCode())
                .currentPrice(String.valueOf(entity.getCurrentPrice()))
                .openPrice(String.valueOf(entity.getOpenPrice()))
                .highPrice(String.valueOf(entity.getHighPrice()))
                .lowPrice(String.valueOf(entity.getLowPrice()))
                .priceChange(String.valueOf(entity.getPriceChange()))
                .changeRate(String.valueOf(entity.getChangeRate()))
                .executionVolume(String.valueOf(entity.getExecutionVolume()))
                .cumulativeAmount(String.valueOf(entity.getTradingAmount()))
                .cumulativeVolume(String.valueOf(entity.getTradingVolume()))
                .time(entity.getTime())
                .build();
    }
}
