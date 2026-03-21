import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useWebSocket } from '../web-socket/use-web-socket';
import type { StockRankingDto } from '../../types/stock';
import { STOCK_WS_URL, getStockRanking } from '../../api/stock';

export type RankingType = 'VALUE' | 'VOLUME';

const formatStockData = (item: any): StockRankingDto => ({
	stockCode: item.stockCode,
	stockName: item.stockName,
	currentPrice: Number(item.currentPrice) || 0,
	priceChange: Number(item.priceChange) || 0,
	changeRate: Number(item.changeRate) || 0,
	cumulativeAmount: Number(item.cumulativeAmount) || 0,
	cumulativeVolume: Number(item.cumulativeVolume) || 0,
});

export const useStockRanking = (type: RankingType = 'VALUE', limit = 40) => {
	const queryClient = useQueryClient();
	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL);

	const queryKey = ['stockRanking', type, limit];
	const { data: rankingData = [], isLoading } = useQuery<StockRankingDto[]>({
		queryKey,
		queryFn: async () => {
			const data = await getStockRanking(type, limit);
			return data.map(formatStockData);
		},
		staleTime: 1000 * 60, // 1분간 캐시 유지 (웹소켓 연결 전 임시 유지용)
		gcTime: 1000 * 60 * 5,
	});

	useEffect(() => {
		if (!isConnected) return;

		const topic = '/topic/ranking';

		const subscription = subscribe(topic, (data: any) => {
			const rawList = Array.isArray(data) ? data : [data];
			const parsedList = rawList.map(formatStockData);

			// 웹소켓 수신 시 React Query 캐시 업데이트
			queryClient.setQueryData<StockRankingDto[]>(queryKey, (prev = []) => {
				const stockMap = new Map(prev.map((item) => [item.stockCode, item]));
				parsedList.forEach((item) => {
					stockMap.set(item.stockCode, item);
				});

				const mergedList = Array.from(stockMap.values());

				if (type === 'VALUE') {
					mergedList.sort((a, b) => b.cumulativeAmount - a.cumulativeAmount);
				} else {
					mergedList.sort((a, b) => b.cumulativeVolume - a.cumulativeVolume);
				}

				return mergedList.slice(0, limit);
			});
		});

		return () => {
			subscription?.unsubscribe();
		};
	}, [isConnected, subscribe, limit, type, queryClient]);

	return { rankingData, isConnected, isLoading };
};
