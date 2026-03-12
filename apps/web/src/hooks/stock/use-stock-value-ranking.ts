import { useEffect, useState } from 'react';
import { useWebSocket } from '../web-socket/use-web-socket';
import type { StockRankingDto, StockRankingResponse } from '../../types/stock';
import { STOCK_WS_URL, getStockRanking } from '../../api/stock';

export type RankingType = 'VALUE' | 'VOLUME';

export const useStockRanking = (type: RankingType = 'VALUE', limit = 40) => {
	const [rankingData, setRankingData] = useState<StockRankingDto[]>([]);

	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL);

	// 랭킹 타입이 변경되면 기존 데이터 초기화 후 HTTP 요청으로 초기 데이터 로드
	useEffect(() => {
		setRankingData([]);

		const fetchInitialData = async () => {
			try {
				const data = await getStockRanking(type, limit);
				// HTTP 응답 데이터를 내부 상태 포맷에 맞게 변환 (안전한 숫자형 변환 적용)
				const formattedData = data.map((item: any) => ({
					stockCode: item.stockCode,
					stockName: item.stockName,
					currentPrice: Number(item.currentPrice) || 0,
					priceChange: Number(item.priceChange) || 0,
					changeRate: Number(item.changeRate) || 0,
					cumulativeAmount: Number(item.cumulativeAmount) || 0,
					cumulativeVolume: Number(item.cumulativeVolume) || 0,
				}));
				setRankingData(formattedData);
			} catch (error) {
				console.error('Failed to fetch initial stock ranking:', error);
			}
		};

		fetchInitialData();
	}, [type, limit]);

	// 연결(및 재연결) 시 STOMP 구독 및 초기 데이터 요청
	useEffect(() => {
		if (!isConnected) return;

		// API 명세서에 따른 구독 토픽 (/topic/ranking)
		const topic = '/topic/ranking';

		// 토픽 구독 (데이터 수신)
		const subscription = subscribe(topic, (data: any) => {
			// console.log('웹소켓 수신 데이터:', data);
			const rawList = Array.isArray(data) ? data : [data];

			try {
				const parsedList: StockRankingDto[] = rawList.map(
					(item: StockRankingResponse) => ({
						stockCode: item.stockCode,
						stockName: item.stockName,
						currentPrice: Number(item.currentPrice) || 0,
						priceChange: Number(item.priceChange) || 0,
						changeRate: Number(item.changeRate) || 0,
						cumulativeAmount: Number(item.cumulativeAmount) || 0,
						cumulativeVolume: Number(item.cumulativeVolume) || 0,
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
