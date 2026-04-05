package com.assetmind.server_stock.stock.presentation.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import java.time.LocalDateTime;
import java.util.List;
import lombok.Builder;

/**
 * 프론트엔드 차트 렌더링을 위한 최종 API 응답 객체
 */
@Builder
public record ChartResponseDto(
        String stockCode,
        String timeframe,
        List<CandleDto> candles
) {

    @Builder
    public record CandleDto(
            @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss")
            LocalDateTime timestamp,
            String open,
            String high,
            String low,
            String close,
            String volume
    ) {
    }
}