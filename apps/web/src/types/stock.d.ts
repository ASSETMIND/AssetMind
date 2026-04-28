/**
 * [WebSocket Connection Spec]
 * Endpoint: http://{domain}/ws-stock (SockJS)
 * Protocol: STOMP
 */
export interface StockRankingDto {
	stockCode: string; // 종목 코드
	stockName: string; // 종목 이름
	currentPrice: number; // 현재가
	changeRate: number; // 등락률
	priceChange: number; // 전일 대비 증감액
	cumulativeAmount: number; // 누적 거래 대금
	cumulativeVolume: number; // 누적 거래량
}

/**
 * [API Spec] STOMP: /topic/ranking
 * 서버에서 내려오는 원본 데이터 (모든 필드가 String)
 */
export interface StockRankingResponse {
	stockCode: string;
	stockName: string;
	currentPrice: string;
	priceChange: string;
	changeRate: string;
	cumulativeAmount: string;
	cumulativeVolume: string;
}

/**
 * [API Spec] STOMP: /topic/stocks/{stockCode}
 * 개별 종목 상세 실시간 데이터 (모든 필드가 String)
 */
export interface StockDetailResponse {
	stockCode: string;
	currentPrice: string;
	openPrice: string;
	highPrice: string;
	lowPrice: string;
	priceChange: string;
	changeRate: string;
	executionVolume: string;
	cumulativeAmount: string;
	cumulativeVolume: string;
	time: string; // HHMMSS
}

/**
 * [API Spec] STOMP: /topic/surge-alerts
 * 실시간 급등락 전역 알림 응답 데이터 타입 (모든 필드가 String)
 */
export interface SurgeAlertPayload {
	stockCode: string;
	stockName: string;
	rate: string;
	currentPrice: string;
	changeRate: string;
	alertTime: string;
}
