package com.assetmind.server_stock.market_access.infrastructure.kis.dto;

import lombok.Builder;

/**
 * KIS 실시간 체결 데이터 (H0STCNT0) DTO
 * 46개의 모든 필드를 포함하지 않고 핵심 15개 필드를 포함
 */
@Builder
public record KisRealTimeData(
        String stockCode,              // 종목코드
        String executionTime,       // 체결 시간 (HHmmss)
        Long currentPrice,          // 현재가
        String changeSign,            // 대비 부호 (1:상한, 2:상승, 3:보합, 4:하한, 5:하락)
        Long priceChange,           // 전일 대비
        Double changeRate,          // 등락률
        Long openPrice,             // 시가
        Long highPrice,             // 고가
        Long lowPrice,              // 저가
        Long executionVolume,       // 체결 거래량
        Long cumulativeVolume,      // 누적 거래량
        Long cumulativeAmount,      // 누적 거래 대금
        Double volumePower,         // 체결 강도
        String marketStatus         // 장운영 구분 코드 (첫번째-상태, 두번째-종류)
                                    // 첫번째 -> 1:장개시전, 2:장중, 3:장종류후, 4:시간외단일가, 7:일반Buy-in, 8:당일Buy-in
                                    // 두번째 -> 0:보통, 1:종가, 2:대량, 3:바스켓, 7:정리매매, 8:Buy-in
) {

}
