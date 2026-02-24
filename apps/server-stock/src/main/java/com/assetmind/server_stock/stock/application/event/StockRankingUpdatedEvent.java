package com.assetmind.server_stock.stock.application.event;

import com.assetmind.server_stock.stock.presentation.dto.StockRankingResponse;

/**
 * 실시간 주식 랭킹(거래대금/거래량) 갱신 완료 이벤트
 *
 * 발행 시점: {@code StockService}에서 Redis(ZSet)에 랭킹 점수 업데이트가 완료된 직후 발행됩니다.
 *
 * 주요 목적:
 * 메인 페이지나 랭킹 탭을 보고 있는 불특정 다수의 클라이언트에게 순위 변동 정보를 전송하기 위함입니다.
 * History 이벤트와 분리함으로써, 향후 트래픽 제어(Throttling, 예: 1초에 1번만 전송) 로직을 독립적으로 적용할 수 있습니다.
 *
 * 구독 채널: {@code /topic/ranking} (전체 랭킹 구독자)
 *
 * @param response - 전송할 랭킹 데이터 DTO (현재가, 등락률, 누적 거래대금 등 포함)
 */
public record StockRankingUpdatedEvent(
        StockRankingResponse response
) {

}
