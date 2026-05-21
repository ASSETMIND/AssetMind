package com.assetmind.server_stock.stock.presentation;

import com.assetmind.server_stock.global.common.ApiResponse;
import com.assetmind.server_stock.market_access.domain.OrderBook;
import com.assetmind.server_stock.stock.application.OrderBookService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/stocks")
public class OrderBookController {
    private final OrderBookService orderBookService;

    /**
     * 종목 상세 페이지 최초 진입 시 사용할 호가 스냅샷 조회 API
     */
    @GetMapping("/{stockCode}/orderbook")
    public ApiResponse<OrderBook> getOrderBookSnapshot(@PathVariable String stockCode) {
        OrderBook snapshot = orderBookService.getOrderBookSnapshot(stockCode);

        if (snapshot == null) {
            return ApiResponse.success("해당 종목의 호가 스냅샷이 존재하지 않습니다.");
        }

        return ApiResponse.success(snapshot);
    }
}
