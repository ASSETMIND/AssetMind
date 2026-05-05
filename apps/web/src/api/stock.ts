import { axiosInstance } from '../libs/axios';

const baseUrl = import.meta.env.VITE_WS_URL || '';
export const STOCK_WS_URL = `${baseUrl.replace(/^ws/, 'http')}/ws-stock`;
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
	time: string;   // ISO 8601 또는 Unix timestamp (서버 응답 형식)
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
		{
			params: {
				timeframe,
				limit,
				...(endTime ? { endTime } : {}),
			},
		},
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

export async function getStockHistory(
	stockCode: string,
	limit = 20,
) {
	const { data } = await axiosInstance.get<{ data: StockHistoryDto[] }>(
		`/stocks/${stockCode}/history`,
		{ params: { limit } },
	);
	return data.data;
}