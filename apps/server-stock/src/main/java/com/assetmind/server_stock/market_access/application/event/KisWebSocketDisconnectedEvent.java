package com.assetmind.server_stock.market_access.application.event;

import com.assetmind.server_stock.market_access.infrastructure.kis.config.KisProperties.Account;
import com.assetmind.server_stock.market_access.infrastructure.kis.websocket.KisWebSocketHandler;
import java.util.List;

/**
 * KIS 웹소켓 세션이 끊어졌을 때 발행되는 이벤트
 * 어댑터가 이 이벤트를 수신하여 죽은 핸들러를 메모리에서 정리하고,
 * 담당하던 종목들만 타켓팅하여 새로운 세션으로 재연결할 수 있도록 핵심 파라미터를 전달
 */
public record KisWebSocketDisconnectedEvent(
        // 세션이 끊어진 핸들러
        KisWebSocketHandler disconnectedHandler,

        // 끊어진 세션을 담당했던 계좌 정보
        Account account,

        // 끊어진 세션이 책임지고 있던 40개의 종목 리스트
        List<String> disconnectedStocks
){

}
