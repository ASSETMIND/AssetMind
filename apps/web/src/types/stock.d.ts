// ─── API 응답 타입 ────────────────────────────────────────────

export interface StockRankingDto {
	stockCode: string; // 종목 코드
	stockName: string; // 종목 이름
	currentPrice: number; // 현재가
	changeRate: number; // 등락률
	cumulativeAmount: number; // 누적 거래 대금
	cumulativeVolume: number; // 누적 거래량
}

// ─── UI 컴포넌트 타입 ─────────────────────────────────────────

export interface StockRow {
	id: string;
	rank: number;
	isFavorite: boolean;
	logoUrl?: string;
	name: string;
	price: number;
	changeRate: number;
	tradeAmount: number;
	buyRatio: number;
	tickerState?: 'rise' | 'fall' | 'idle';
}

export type RankingType = 'VALUE' | 'VOLUME';

export type PageState =
	| 'default'
	| 'skeleton'
	| 'realtime'
	| 'error'
	| 'empty'
	| 'market-closed'
	| 'extreme';