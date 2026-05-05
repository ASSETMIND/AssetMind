import { axiosInstance } from '../libs/axios';

// ─── WebSocket URL ────────────────────────────────────────────
// 항상 ws:// 프로토콜로 생성
// VITE_WS_URL 없으면 현재 호스트 기반으로 생성
const rawWsUrl = import.meta.env.VITE_WS_URL as string | undefined;

export const STOCK_WS_URL = rawWsUrl
	? rawWsUrl.replace(/^http/, 'ws') + '/ws-stock'
	: `ws://${typeof window !== 'undefined' ? window.location.host : 'localhost:5173'}/ws-stock`;

export const SURGE_ALERTS_TOPIC = '/topic/surge-alerts';

// ─── 랭킹 ────────────────────────────────────────────────────

export async function getStockRanking(
	type: 'VALUE' | 'VOLUME' = 'VALUE',
	limit = 40,
) {
	const endpoint =
		type === 'VALUE' ? '/stocks/ranking/value' : '/stocks/ranking/volume';
	const { data } = await axiosInstance.get<{ data: any[] }>(endpoint, {
		params: { limit },
	});
	return data.data;
}

// ─── 캔들스틱 차트 ────────────────────────────────────────────

export type CandleTimeframe = '1m' | '5m' | '1d' | '1w' | '1mo';

/** 실제 API 응답: data.candles[] - 모든 필드가 String */
export interface CandleDto {
	timestamp: string; // ISO-8601 (예: "2026-04-01T10:00:00")
	open:      string;
	high:      string;
	low:       string;
	close:     string;
	volume:    string;
}

export async function getStockCandles(
	stockCode: string,
	timeframe: CandleTimeframe = '1d',
	limit = 200,
	endTime?: string,
) {
	const { data } = await axiosInstance.get<{
		data: { stockCode: string; timeframe: string; candles: CandleDto[] };
	}>(
		`/stocks/${stockCode}/charts/candles`,
		{ params: { timeframe, limit, ...(endTime ? { endTime } : {}) } },
	);
	return data.data.candles;
}

// ─── 시계열 (history) ─────────────────────────────────────────
// 체결 틱 데이터 — 캔들 차트에는 candles API 사용

/** 실제 API 응답: data[] - 모든 필드가 String */
export interface StockHistoryDto {
	stockCode:        string;
	currentPrice:     string;
	openPrice:        string | null;
	highPrice:        string | null;
	lowPrice:         string | null;
	priceChange:      string;
	changeRate:       string | null;
	executionVolume:  string;
	cumulativeAmount: string | null;
	cumulativeVolume: string | null;
	time:             string; // HHmmss
}

export async function getStockHistory(stockCode: string, limit = 20) {
	const { data } = await axiosInstance.get<{ data: StockHistoryDto[] }>(
		`/stocks/${stockCode}/history`,
		{ params: { limit } },
	);
	return data.data;
}

// ─── 호가 (Orderbook) ─────────────────────────────────────────

/** 개별 호가 행 */
export interface OrderbookRowDto {
	price: number;
	changeRate: number;
	quantity: number;
}

export interface TradeTickDto {
	price: number;
	quantity: number;
	isBuy: boolean;
	time: string;
}

export interface MarketInfoDto {
	weekHigh: number;
	weekLow: number;
	upperLimit: number;
	lowerLimit: number;
	riseVI?: number;
	fallVI?: number;
	open: number;
	high: number;
	low: number;
	volume: number;
	volumeUnit: string;
	changeFromYesterday: number;
	midPrice?: number;
}

export interface OrderbookDto {
	stockCode: string;
	currentPrice: number;
	currentChangeRate: number;
	asks: OrderbookRowDto[];
	bids: OrderbookRowDto[];
	trades: TradeTickDto[];
	tradeStrength: number;
	marketInfo: MarketInfoDto;
}

export async function getOrderbook(stockCode: string): Promise<OrderbookDto> {
	const { data } = await axiosInstance.get<{ data: OrderbookDto }>(
		`/stocks/${stockCode}/orderbook`,
	);
	return data.data;
}

export const getOrderbookTopic = (stockCode: string) =>
	`/topic/orderbook/${stockCode}`;