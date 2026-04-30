package com.assetmind.server_stock.stock.presentation;

import com.assetmind.server_stock.global.common.ApiResponse;
import com.assetmind.server_stock.stock.application.ChartService;
import com.assetmind.server_stock.stock.presentation.dto.ChartRequestDto;
import com.assetmind.server_stock.stock.presentation.dto.ChartResponseDto;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 프론트엔드 차트 렌더링을 위한 REST API 컨트롤러
 */
@Slf4j
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/stocks")
public class ChartController {

    private final ChartService chartService;

    /**
     * 특정 종목의 차트 캔들 데이터를 조회
     * @param stockCode 조회할 종목 코드
     * @param dto       특정 종목 차트 캔들 조회 요청 DTO
     */
    @GetMapping("/{stockCode}/charts/candles")
    public ApiResponse<ChartResponseDto> getCandles(
            @PathVariable String stockCode,
            @Valid @ModelAttribute ChartRequestDto dto
    ) {
        log.info("[ChartController] 캔들 조회 요청 - 종목: {}, 타임프레임: {}, Limit: {}, 기준시간: {}",
                stockCode, dto.timeframe(), dto.limit(), dto.endTime());

        ChartResponseDto response = chartService.getCandles(stockCode, dto.timeframe(), dto.endTime(), dto.limit());

        return ApiResponse.success(response);
    }
}