package com.assetmind.server_stock.market_access.domain.event;

import com.assetmind.server_stock.market_access.domain.OrderBook;

/**
 * 실시간 호가 데이터 파싱 완료되었음을 애플리케이션 내부에 알리는 이벤트
 */
public record OrderBookReceivedEvent(
        OrderBook orderBook
) {
}

