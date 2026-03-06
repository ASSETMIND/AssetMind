import { useEffect, useState } from 'react';
import { useWebSocket } from '../web-socket/use-web-socket';
import type { StockRankingDto, StockRankingResponse } from '../../types/stock';
import { STOCK_WS_URL } from '../../api/stock';

export type RankingType = 'VALUE' | 'VOLUME';

export const useStockRanking = (type: RankingType = 'VALUE', limit = 10) => {
	const [rankingData, setRankingData] = useState<StockRankingDto[]>([]);

	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL);

	// 연결(및 재연결) 시 STOMP 구독 및 초기 데이터 요청
	useEffect(() => {
		if (!isConnected) return;

		// API 명세서에 따른 구독 토픽 (/topic/ranking)
		const topic = '/topic/ranking';

		// 1. 토픽 구독 (데이터 수신)
		const subscription = subscribe(topic, (data: any) => {
			// 명세서상 데이터는 String 타입의 필드들을 가짐
			// 배열 형태로 온다고 가정하고 처리 (단일 객체일 경우 배열로 변환)
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

				// 클라이언트 측 정렬 및 제한
				if (type === 'VALUE') {
					parsedList.sort((a, b) => b.cumulativeAmount - a.cumulativeAmount);
				} else {
					parsedList.sort((a, b) => b.cumulativeVolume - a.cumulativeVolume);
				}

				setRankingData(parsedList.slice(0, limit));
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
