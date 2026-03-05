package com.assetmind.server_stock.stock.application.listener;

import com.assetmind.server_stock.stock.application.StockService;
import com.assetmind.server_stock.stock.application.listener.dto.RealTimeStockTradeEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

/**
 * 실시간 주가 데이터 이벤트 수신 리스너 클래스
 *
 * 웹소켓 핸들러에서 발행한 이벤트를 비동기로 수신
 * 수신된 데이터를 기반으로 로깅, DB 저장 등의 수신 후 작업을 수행
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class StockTradeEventListener {

    private final StockService stockService;

    /**
     * 이벤트 수신 시 실행되는 메서드
     * @Async를 적용하여 웹소켓 스레드와 분리된 별도의 스레드에서 실행하여
     * 실시간 시세 수신에는 영향이 없도록 구성
     */
    @Async
    @EventListener
    public void handleStockTradeEvent(RealTimeStockTradeEvent event) {
        try {
            printEventLog(event);

            // TODO: 비즈니스 로직 수행 (서비스 연동 하여 DB 저장)
            stockService.processRealTimeTrade(event);
        } catch (Exception e) {
            // @Async가 적용된 비동기 메서드 이므로 메인 스레드로 예외가 전파되지 않음
            // 문제 파악을 위한 로그를 남김
            log.error("[Stock Trade Event] 처리 중 에러 발생 : {}", e.getMessage(), e);
        }
    }

    private void printEventLog(RealTimeStockTradeEvent event) {
        // 상승/하락 기호 결정
        String signMark = getSignMark(event.changeSign());

        log.info("📈 [Stock Trade Event] {} | 현재가: {}원 ({}{}) | 순간체결: {}주",
                event.stockCode(),
                String.format("%,d", event.currentPrice()),
                signMark,
                event.priceChange(),
                event.executionVolume()
        );
    }

    private String getSignMark(String changeSign) {
        if ("1".equals(changeSign) || "2".equals(changeSign)) return "▲"; // 상한, 상승
        if ("4".equals(changeSign) || "5".equals(changeSign)) return "▼"; // 하한, 하락
        return "-"; // 보합
    }
}
