package com.assetmind.server_stock.stock.application.port;

/**
 * 실시간으로 중복된 알림이 계속 push 되는 것을 방지하기 위하여
 * 중복된 알림은 일정기간 텀을 주고 알림을 주는 방식(쓰로틀링)을 이용
 */
public interface AlertThrottlingPort {

    /**
     * 특정 종목에 대한 알림 발송 허용 여부를 반환
     * @param stockCode 종목 코드 (예: "005930")
     * @return 알림 발송 가능 여부 (true: 발송 가능, false: 이미 발송되어 쓰로틀링 됨)
     */
    boolean allowAlert(String stockCode);
}
