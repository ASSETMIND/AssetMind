package com.assetmind.server_stock.stock.presentation.dto;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.RawTickJpaEntity;
import com.assetmind.server_stock.stock.infrastructure.persistence.entity.StockDataEntity;
import java.time.format.DateTimeFormatter;
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
 * @param cumulativeAmount     - 누적 거래 대금
 * @param cumulativeVolume     - 누적 거래량
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

    private static final DateTimeFormatter TIME_FORMATTER = DateTimeFormatter.ofPattern("HHmmss");

    // 실시간 웹소켓 브로드캐스트용
    public static StockHistoryResponse from(RealTimeStockTradeEvent event) {
        return StockHistoryResponse.builder()
                .stockCode(event.stockCode())
                .currentPrice(String.valueOf(event.currentPrice()))
                .openPrice(String.valueOf(event.openPrice()))
                .highPrice(String.valueOf(event.highPrice()))
                .lowPrice(String.valueOf(event.lowPrice()))
                .priceChange(String.valueOf(event.priceChange()))
                .changeRate(String.valueOf(event.changeRate()))
                .executionVolume(String.valueOf(event.executionVolume()))
                .cumulativeAmount(String.valueOf(event.cumulativeAmount()))
                .cumulativeVolume(String.valueOf(event.cumulativeVolume()))
                .time(event.time())
                .build();
    }

    // DB 과거 내역 페이징 조회용
    public static StockHistoryResponse from(RawTickJpaEntity entity) {
        return StockHistoryResponse.builder()
                .stockCode(entity.getStockCode())
                .currentPrice(String.valueOf(entity.getCurrentPrice()))
                .priceChange(String.valueOf(entity.getPriceChange()))
                .executionVolume(String.valueOf(entity.getVolume()))
                .time(entity.getTradeTimestamp().format(TIME_FORMATTER))
                // 나머지는 null로 설정
                .openPrice(null)
                .highPrice(null)
                .lowPrice(null)
                .changeRate(null)
                .cumulativeAmount(null)
                .cumulativeVolume(null)
                .build();
    }
}
