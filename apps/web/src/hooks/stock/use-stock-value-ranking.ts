import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useWebSocket } from '../web-socket/use-web-socket';
import { useStockStore } from '../../store/use-stock-store';
import type { StockRankingDto, RankingType } from '../../types/stock';
import { STOCK_WS_URL, getStockRanking } from '../../api/stock';
import { usePageVisibility } from '../common/use-page-visibility';

export type { RankingType };

// 데이터 포맷팅 유틸리티
const formatStockData = (item: StockRankingDto): StockRankingDto => ({
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
 * - Page Visibility API: 탭 비활성화 시 소켓 연결 해제 및 연산 중지
 * - Throttling & Batching: 300ms 주기로 일괄 업데이트하여 렌더링 부하 감소
 * - Resume Sync: 포그라운드 전환 시 최신 데이터 재조회
 */
export const useStockRanking = (type: RankingType = 'VALUE', limit = 40) => {
	const isVisible = usePageVisibility();

	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL, {
		autoDisconnectInBackground: true,
	});

	const { setInitialStocks, updateStocks } = useStockStore();

	const messageBuffer = useRef<StockRankingDto[]>([]);
	const queryKey = ['stockRanking', type, limit];

	// 초기 데이터 로드 (React Query)
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

	// 탭이 다시 활성화될 때 최신 데이터 동기화 (Resume logic)
	useEffect(() => {
		if (isVisible) {
			console.log('Tab visible: Refreshing stock ranking data...');
			refetch();
		}
	}, [isVisible, refetch]);

	useEffect(() => {
		if (!isConnected || !isVisible) return;

		const topic = `/topic/ranking/${type.toLowerCase()}`;
		const subscription = subscribe(topic, (data: unknown) => {
			const rawList = Array.isArray(data) ? data : [data];
			const parsedList = (rawList as StockRankingDto[]).map(formatStockData);
			messageBuffer.current.push(...parsedList);
		});

		// 배치 처리 타이머: 300ms마다 버퍼를 비우고 전역 스토어 업데이트
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