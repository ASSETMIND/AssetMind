package com.assetmind.server_stock.market_access.application.port;

import java.util.List;

/**
 * 실시간 주식 데이터 수집을 위한
 * 실시간 데이터 서버에 명령할 내용 정의
 */
public interface RealTimeStockDataPort {

    /**
     * 실시간 데이터 서버에 연결 시도
     * @param approvalKey - 접속에 필요한 인증 키
     */
    void connect(String approvalKey);

    /**
     * 연결 종료
     */
    void disconnect();

    /**
     * 특정 종목들을 구독
     * @param stockCode - 종목 코드 리스트 (예: ["590042", "293000"])
     */
    void subscribe(List<String> stockCode);
}
