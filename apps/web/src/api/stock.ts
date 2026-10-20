import { axiosInstance } from '../libs/axios';

// ─── WebSocket URL ────────────────────────────────────────────
const rawWsUrl = import.meta.env.VITE_WS_URL as string | undefined;

export const STOCK_WS_URL = rawWsUrl
	? rawWsUrl.replace(/^http/, 'ws') + '/ws-stock'
	: `ws://${typeof window !== 'undefined' ? window.location.host : 'localhost:5173'}/ws-stock`;

export const ORDERBOOK_WS_URL = `ws://${typeof window !== 'undefined' ? window.location.host : 'localhost:5173'}/ws-orderbook`;

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

export interface CandleDto {
	timestamp: string;
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

// ─── 시계열 ─────────────────────────────────────────

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
	time:             string;
}

export async function getStockHistory(stockCode: string, limit = 20) {
	const { data } = await axiosInstance.get<{ data: StockHistoryDto[] }>(
		`/stocks/${stockCode}/history`,
		{ params: { limit } },
	);
	return data.data;
}

// ─── 호가 ─────────────────────────────────────────

export interface OrderbookLevelDto {
	level:    number;
	askPrice: string;
	askSize:  string;
	bidPrice: string;
	bidSize:  string;
}

export interface OrderbookDto {
	stockCode:    string;
	marketTime:   string;
	totalAskSize: string;
	totalBidSize: string;
	levels:       OrderbookLevelDto[];
}

/** 초기 진입 시 REST 스냅샷 조회
 *  - 정상: OrderbookDto 반환
 *  - 데이터 미수집(장 시작 전 등): null 반환
 *  - 잘못된 종목코드 등 오류: null 반환
 */
export async function getOrderbook(stockCode: string): Promise<OrderbookDto | null> {
	try {
		const { data } = await axiosInstance.get<{
			success: boolean;
			message: string | null;
			data: OrderbookDto | null;
		}>(`/stocks/${stockCode}/orderbook`);
		return data.data ?? null;
	} catch {
		return null;
	}
}

export const getOrderbookTopic = (stockCode: string) =>
	`/topic/orderbook/${stockCode}`;