import { axiosInstance } from '../libs/axios';
import type { StockRankingDto } from '../types/stock';

const baseUrl = import.meta.env.VITE_WS_URL || '';

// SockJS는 http 핸드셰이크를 사용하므로 ws://를 http://로 변환하고, 중복 경로 방지를 위해 /ws-stock만 붙임
export const STOCK_WS_URL = `${baseUrl.replace(/^ws/, 'http')}/ws-stock`;

export async function getStockRanking(limit = 10) {
	const { data } = await axiosInstance.get<StockRankingDto[]>(
		'/api/stocks/ranking/value',
		{
			params: { limit },
		},
	);
	return data;
}
