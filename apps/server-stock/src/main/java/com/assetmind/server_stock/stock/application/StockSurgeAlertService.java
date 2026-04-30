package com.assetmind.server_stock.stock.application;

import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import com.assetmind.server_stock.stock.application.port.AlertMessagingPort;
import com.assetmind.server_stock.stock.application.port.AlertThrottlingPort;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 실시간 주식 급등락 알림 처리를 담당하는 애플리케이션 서비스
 *
 * {@link StockSurgeAlertService}로부터 전달받은 이벤트를 분석하여 알림 발송 조건(10% 등락률)을 검증하고,
 * {@link com.assetmind.server_stock.stock.application.port.AlertThrottlingPort}를 호출하여
 * 알림 중복을 방지하는 오케스트레이션 역할을 수행
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class StockSurgeAlertService {

    private final AlertThrottlingPort alertThrottlingPort;

    private final AlertMessagingPort alertMessagingPort;

    /**
     * 수신된 실시간 체결 데이터를 기반으로 급등락 알림 로직을 처리
     * @param event - KIS 웹소켓 핸들러를 통해 수신한 파싱된 실시간 주식 체결 데이터 DTO
     */
    public void processSurgeAlert(RealTimeStockTradeEvent event) {
        // 수신된 주식 체결 데이터의 등락률이 10프로 이상인지 확인
        // 10프로 미만이라면 바로 메서드 수행 종료
        if (event.changeRate() == null || Math.abs(event.changeRate()) <= 10.0) {
            return;
        }

        // 알림 중복 체크(스로틀링 체크)
        // 알림 발송 조건(등락률 10% 이상)을 만족했더라도, ThrottlingPort를 호출하여 알림을 보내고 30분이 지났는지 확인(중복방지)
        if (alertThrottlingPort.allowAlert(event.stockCode())) {
            String rate = event.changeRate() > 0 ? "급등" : "급락";
            alertMessagingPort.send(event, rate);
            log.info("[StockSurgeAlertService] {} 종목 {}! 현재가: {}원", event.stockCode(), rate, event.currentPrice());
        }
    }

}
