package com.assetmind.server_stock.market_access.application.port;

import java.util.List;

/**
 * 실시간 주식 데이터 수집을 위한
 * 실시간 데이터 서버에 명령할 내용 정의
 */
public interface RealTimeStockDataPort {

    /**
     * 실시간 데이터 수집을 위한 사전 준비
     * 웹소켓 클라이언트 초기화 등 네티워크 연결을 위한 기초 세팅을 수행
     */
    void prepareConnection();

    /**
     * 특정 종목들에 대한 실시간 데이터 구독을 추가
     */
    void subscribe(List<String> stockCodes);

    /**
     * 진행 중인 모든 실시간 데이터 수집(연결)을 안전하게 종료
     */
    void disconnect();
}
