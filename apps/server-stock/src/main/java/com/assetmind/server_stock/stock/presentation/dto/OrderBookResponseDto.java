package com.assetmind.server_stock.stock.presentation.dto;

import java.util.List;
import lombok.Builder;

/**
 * 프론트엔드 호가 데이터 STOMP 채널로 내려갈 최종 응답 객체
 */
@Builder
public record OrderBookResponseDto(
        String stockCode,   // 종목 코드
        String marketTime,  // 호가 수신 시간
        String totalAskSize,// 총 매도 호가 잔량
        String totalBidSize,// 총 매수 호가 잔량
        List<OrderBookLevelResponse> levels // 10개의 호가
) {

    /**
     * 단일 호가 레벨 데이터
     */
    @Builder
    public record OrderBookLevelResponse(
            int level, // 호가 단계 (1 ~ 10)
            String askPrice,// 매도 호가
            String askSize, // 매도 잔량
            String bidPrice,// 매수 호가
            String bidSize // 매수 잔량
    ) {}
}
