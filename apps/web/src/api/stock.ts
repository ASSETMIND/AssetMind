import { axiosInstance } from '../libs/axios';
import type { StockRankingDto } from '../types/stock';

export const STOCK_WS_URL = import.meta.env.VITE_WS_URL
	? `${import.meta.env.VITE_WS_URL}/stocks`
	: 'ws://localhost:8080/stocks';

export const getStockRanking = async (limit = 10) => {
	const { data } = await axiosInstance.get<StockRankingDto[]>(
		'/api/stocks/ranking/value',
		{
			params: { limit },
		},
	);
	return data;
};
