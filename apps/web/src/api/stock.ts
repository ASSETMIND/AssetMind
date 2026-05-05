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

export type CandleTimeframe = '1m' | '5m' | '1d' | '1w' | '1M';

export interface CandleDto {
	time: string | number;
	open: number;
	high: number;
	low: number;
	close: number;
	volume?: number;
}

export async function getStockCandles(
	stockCode: string,
	timeframe: CandleTimeframe = '1d',
	limit = 100,
	endTime?: string,
) {
	const { data } = await axiosInstance.get<{ data: CandleDto[] }>(
		`/stocks/${stockCode}/charts/candles`,
		{ params: { timeframe, limit, ...(endTime ? { endTime } : {}) } },
	);
	return data.data;
}

// ─── 가격 히스토리 ────────────────────────────────────────────

export interface StockHistoryDto {
	date: string;
	open: number;
	high: number;
	low: number;
	close: number;
	volume: number;
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