import { useEffect, useState } from 'react';
import { useWebSocket } from '../web-socket/use-web-socket';
import type { StockRankingDto, StockRankingResponse } from '../../types/stock';
import { STOCK_WS_URL } from '../../api/stock';

export type RankingType = 'VALUE' | 'VOLUME';

export const useStockRanking = (type: RankingType = 'VALUE', limit = 10) => {
	const [rankingData, setRankingData] = useState<StockRankingDto[]>([]);

	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL);

	// 랭킹 타입이 변경되면 기존 데이터 초기화
	useEffect(() => {
		setRankingData([]);
	}, [type]);

	// 연결(및 재연결) 시 STOMP 구독 및 초기 데이터 요청
	useEffect(() => {
		if (!isConnected) return;

		// API 명세서에 따른 구독 토픽 (/topic/ranking)
		const topic = '/topic/ranking';

		// 1. 토픽 구독 (데이터 수신)
		const subscription = subscribe(topic, (data: any) => {
			console.log('웹소켓 수신 데이터:', data);
			const rawList = Array.isArray(data) ? data : [data];

			try {
				const parsedList: StockRankingDto[] = rawList.map(
					(item: StockRankingResponse) => ({
						stockCode: item.stockCode,
						stockName: item.stockName,
						currentPrice: Number(item.currentPrice),
						priceChange: Number(item.priceChange),
						changeRate: Number(item.changeRate),
						cumulativeAmount: Number(item.cumulativeAmount),
						cumulativeVolume: Number(item.cumulativeVolume),
					}),
				);

				setRankingData((prev) => {
					// 기존 데이터와 새로운 데이터를 병합 (stockCode 기준)
					const stockMap = new Map(prev.map((item) => [item.stockCode, item]));
					parsedList.forEach((item) => {
						stockMap.set(item.stockCode, item);
					});

					const mergedList = Array.from(stockMap.values());

					// 정렬 및 제한
					if (type === 'VALUE') {
						mergedList.sort((a, b) => b.cumulativeAmount - a.cumulativeAmount);
					} else {
						mergedList.sort((a, b) => b.cumulativeVolume - a.cumulativeVolume);
					}

					return mergedList.slice(0, limit);
				});
			} catch (error) {
				console.error('Failed to parse stock ranking data:', error);
			}
		});

		return () => {
			subscription?.unsubscribe();
		};
	}, [isConnected, subscribe, limit, type]);

	return { rankingData, isConnected };
};
