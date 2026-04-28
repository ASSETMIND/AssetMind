package com.assetmind.server_stock.stock.presentation.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDateTime;
import org.springframework.format.annotation.DateTimeFormat;

/**
 * 특정 종목 차트 캔들 조회 요청 DTO
 * @param timeframe 타임프레임 (예: 1m, 5m, 1d, 1w, 1mo)
 * @param limit     조회할 캔들 개수 (기본값: 200)
 * @param endTime   조회 기준 시간 (과거 스크롤 시 전달, 미전달 시 현재 시간 기준)
 */
public record ChartRequestDto(
        @NotBlank(message = "타임프레임(timeframe)은 필수입니다. (예: 1m, 1d)")
        String timeframe,

        @Min(value = 1, message = "조회 개수는 최소 1개 이상이어야 합니다.")
        Integer limit,

        @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME)
        LocalDateTime endTime
) {
    public ChartRequestDto {
        if (limit == null) {
            limit = 200;
        }
    }
}
