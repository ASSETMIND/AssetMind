package com.assetmind.server_stock.stock.presentation.dto;

import java.time.LocalDateTime;
import lombok.Builder;

@Builder
public record StockSurgeAlertResponse(
        String stockCode,           // 종목 코드
        String stockName,           // 종목 이름
        String rate,                // "급등" 또는 "급락"
        String currentPrice,          // 현재가
        String changeRate,          // 등락률
        LocalDateTime alertTime     // 알림 발생 시간
) {

}
