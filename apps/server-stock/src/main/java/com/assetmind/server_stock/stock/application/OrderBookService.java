package com.assetmind.server_stock.stock.application;

import com.assetmind.server_stock.global.error.ErrorCode;
import com.assetmind.server_stock.market_access.domain.OrderBook;
import com.assetmind.server_stock.stock.application.provider.StockMetadataProvider;
import com.assetmind.server_stock.stock.exception.InvalidOrderBookParameterException;
import com.assetmind.server_stock.stock.infrastructure.throttling.OrderBookCacheRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class OrderBookService {

    private final OrderBookCacheRepository cacheRepository;
    private final StockMetadataProvider stockMetadataProvider;

    /**
     * 특정 종목의 최신 호가 스냅샷을 조회
     */
    public OrderBook getOrderBookSnapshot(String stockCode) {

        if(!stockMetadataProvider.isExist(stockCode)) {
            throw new InvalidOrderBookParameterException(ErrorCode.UNSUPPORTED_ORDER_BOOK);
        }

        return cacheRepository.getSnapshot(stockCode);
    }
}
