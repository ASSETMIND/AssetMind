package com.assetmind.server_stock.stock.application.event;

import com.assetmind.server_stock.stock.presentation.dto.StockHistoryResponse;

/**
 * 특정 종목의 실시간 체결 데이터 저장 완료 이벤트
 *
 * 발행 시점: {@code StockService}에서 DB(MySQL)에 체결 내역(History) 저장이 완료된 직후 발행
 *
 * 주요 목적:
 * 상세 페이지(차트/호가창)를 보고 있는 클라이언트에게 실시간 데이터를 전송하기 위함입니다.
 * 트랜잭션(DB 저장)과 전송 로직(WebSocket)을 분리하여, 전송 지연이 DB 커넥션 점유로 이어지는 것을 방지
 *
 * 구독 채널: {@code /topic/stocks/{stockCode}} (개별 종목 구독자)
 *
 * @param stockCode - 종목 코드 (구독 채널 라우팅용, 예: "005930")
 * @param response - 전송할 상세 데이터 DTO (시가, 고가, 저가, 체결량 등 포함)
 */
public record StockHistorySavedEvent(
        String stockCode,
        StockHistoryResponse response
) {

}
