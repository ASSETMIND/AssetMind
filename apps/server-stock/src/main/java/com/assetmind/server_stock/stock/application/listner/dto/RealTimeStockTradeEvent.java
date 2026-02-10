package com.assetmind.server_stock.stock.application.listner.dto;

import java.time.LocalDateTime;
import lombok.Builder;

/**
 * 실시간 체결 데이터 이벤트 전송 시 넣을 데이터 DTO
 */
@Builder
public record RealTimeStockTradeEvent(
        String stockCode,               // 종목 코드
        String time,                    // 체결 시간

        // --- 가격 정보 ---
        Long currentPrice,              // 현재가
        Long priceChange,               // 전일 대비
        Long changeSign,                // 대비 부호 (1:상한, 2:상승, 3:보합, 4:하한, 5:하락)
        Double changeRate,              // 등락률

        // --- 가격 정보 ---
        Long executionVolume,           // 순간 체결량
        Long cumulativeAmount,          // 누적 거래대금
        Long cumulativeVolume,          // 누적 거래량

        // --- 이벤트 메타 정보 ---
        LocalDateTime eventTimeStamp    // 이벤트 발생 시각
) {

}
