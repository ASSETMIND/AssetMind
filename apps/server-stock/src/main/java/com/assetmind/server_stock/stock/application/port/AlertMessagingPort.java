package com.assetmind.server_stock.stock.application.port;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;

/**
 * 급등락 알림을 전송하는 행위를 정의한 인터페이스(Port)
 */
public interface AlertMessagingPort {

    /**
     * 급등락 알림을 클라이언트에게 발송
     * @param event - 실시간 체결 데이터 DTO
     * @param rate - "급등" or "급락"
     */
    void send(RealTimeStockTradeEvent event, String rate);
}
