import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useWebSocket } from '../web-socket/use-web-socket';
import { useStockStore } from '../../store/use-stock-store';
import type { StockRankingDto, RankingType } from '../../types/stock';
import { STOCK_WS_URL, getStockRanking } from '../../api/stock';
import { usePageVisibility } from '../common/use-page-visibility';

export type { RankingType };

const formatStockData = (item: any): StockRankingDto => ({
	stockCode:        item.stockCode,
	stockName:        item.stockName,
	currentPrice:     Number(item.currentPrice)     || 0,
	priceChange:      Number(item.priceChange)       || 0,
	changeRate:       Number(item.changeRate)        || 0,
	cumulativeAmount: Number(item.cumulativeAmount)  || 0,
	cumulativeVolume: Number(item.cumulativeVolume)  || 0,
});

export const useStockRanking = (type: RankingType = 'VALUE', limit = 40) => {
	const isVisible = usePageVisibility();

	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL, {
		autoDisconnectInBackground: true,
	});

	const { setInitialStocks, updateStocks } = useStockStore();
	const messageBuffer = useRef<StockRankingDto[]>([]);
	const queryKey = ['stockRanking', type, limit];

	const { isLoading, refetch } = useQuery<StockRankingDto[]>({
		queryKey,
		queryFn: async () => {
			const data = await getStockRanking(type, limit);
			const formatted = data.map(formatStockData);
			setInitialStocks(formatted);
			return formatted;
		},
		staleTime: 1000 * 60,
	});

	const refetchRef = useRef(refetch);
	refetchRef.current = refetch;

	useEffect(() => {
		if (isVisible) {
			refetchRef.current();
		}
	}, [isVisible]);

	useEffect(() => {
		if (!isConnected || !isVisible) return;

		const topic = `/topic/ranking/${type.toLowerCase()}`;
		const subscription = subscribe(topic, (raw: unknown) => {
			// MSW mock: { type: 'RANKING_VALUE_UPDATE', data: [...] }
			const msg = raw as { type?: string; data?: any[] };
			const list = Array.isArray(msg.data)
				? msg.data
				: Array.isArray(raw)
					? (raw as any[])
					: [raw];

			const parsed = list.map(formatStockData);
			messageBuffer.current.push(...parsed);
		});

		const batchInterval = setInterval(() => {
			if (messageBuffer.current.length === 0) return;
			const currentBuffer = [...messageBuffer.current];
			messageBuffer.current = [];
			updateStocks(currentBuffer, type, limit);
		}, 300);

		return () => {
			subscription?.unsubscribe();
			clearInterval(batchInterval);
		};
	}, [isConnected, isVisible, subscribe, limit, type, updateStocks]);

	return { isConnected, isLoading };
};