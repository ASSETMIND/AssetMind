import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useWebSocket } from '../web-socket/use-web-socket';
import { useStockStore } from '../../store/use-stock-store';
import type { StockRankingDto } from '../../types/stock';
import { STOCK_WS_URL, getStockRanking } from '../../api/stock';

export type RankingType = 'VALUE' | 'VOLUME';

// 데이터 포맷팅 유틸리티
const formatStockData = (item: any): StockRankingDto => ({
	stockCode: item.stockCode,
	stockName: item.stockName,
	currentPrice: Number(item.currentPrice) || 0,
	priceChange: Number(item.priceChange) || 0,
	changeRate: Number(item.changeRate) || 0,
	cumulativeAmount: Number(item.cumulativeAmount) || 0,
	cumulativeVolume: Number(item.cumulativeVolume) || 0,
});

/**
 * 주식 랭킹 데이터를 관리하는 훅 (최적화 버전)
 * - Throttling & Batching: 300ms 주기로 일괄 업데이트하여 렌더링 부하 감소
 * - Zustand Store 연동: 전역 스토어를 업데이트하여 개별 아이템 지점 업데이트 지원
 */
export const useStockRanking = (type: RankingType = 'VALUE', limit = 40) => {
	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL);
	const { setInitialStocks, updateStocks } = useStockStore();
	
	const messageBuffer = useRef<StockRankingDto[]>([]);
	const queryKey = ['stockRanking', type, limit];

	// 초기 데이터 로드 (React Query)
	const { isLoading } = useQuery<StockRankingDto[]>({
		queryKey,
		queryFn: async () => {
			const data = await getStockRanking(type, limit);
			const formatted = data.map(formatStockData);
			// 초기 데이터를 전역 스토어에 동기화
			setInitialStocks(formatted);
			return formatted;
		},
		staleTime: 1000 * 60,
	});

	useEffect(() => {
		if (!isConnected) return;

		const topic = `/topic/ranking/${type.toLowerCase()}`;
		const subscription = subscribe(topic, (data: any) => {
			const rawList = Array.isArray(data) ? data : [data];
			const parsedList = rawList.map(formatStockData);
			
			// 버퍼에 데이터 추가
			messageBuffer.current.push(...parsedList);
		});

		// 배치 처리 타이머: 300ms마다 버퍼를 비우고 전역 스토어 업데이트
		const batchInterval = setInterval(() => {
			if (messageBuffer.current.length === 0) return;

			const currentBuffer = [...messageBuffer.current];
			messageBuffer.current = []; // 버퍼 비우기

			// 전역 스토어에 일괄 업데이트 요청
			// 이 시점에 스토어의 stockMap과 stockCodes가 갱신됩니다.
			updateStocks(currentBuffer, type, limit);
		}, 300);

		return () => {
			subscription?.unsubscribe();
			clearInterval(batchInterval);
		};
	}, [isConnected, subscribe, limit, type, updateStocks]);

	return { isConnected, isLoading };
};
