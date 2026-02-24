package com.assetmind.server_stock.stock.presentation;

import com.assetmind.server_stock.global.common.ApiResponse;
import com.assetmind.server_stock.stock.application.StockService;
import com.assetmind.server_stock.stock.presentation.dto.StockHistoryResponse;
import com.assetmind.server_stock.stock.presentation.dto.StockRankingResponse;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/stocks")
@Validated
public class StockController {

    private final StockService stockService;

    /**
     * 거래대금 순 랭킹 조회
     */
    @GetMapping("/ranking/value")
    public ApiResponse<List<StockRankingResponse>> getRankingByTradeValue(
            @RequestParam(defaultValue = "10") @Min(1) @Max(100) int limit
    ) {
        List<StockRankingResponse> result = stockService.getTopStocksByTradeValue(
                limit);

        return ApiResponse.success(result);
    }

    /**
     * 거래량 순 랭킹 조회
     */
    @GetMapping("/ranking/volume")
    public ApiResponse<List<StockRankingResponse>> getRankingByTradeVolume(
            @RequestParam(defaultValue = "10") @Min(1) @Max(100) int limit
    ) {
        List<StockRankingResponse> result = stockService.getTopStocksByTradeVolume(
                limit);

        return ApiResponse.success(result);
    }

    /**
     * 특정 종목 시계열 데이터 조회
     */
    @GetMapping("{stockCode}/history")
    public ApiResponse<List<StockHistoryResponse>> getStockHistory(
            @PathVariable @NotBlank String stockCode,
            @RequestParam(defaultValue = "30") @Min(1) @Max(120) int limit
    ) {
        List<StockHistoryResponse> result = stockService.getStockRecentHistory(
                stockCode, limit);

        return ApiResponse.success(result);
    }

}
