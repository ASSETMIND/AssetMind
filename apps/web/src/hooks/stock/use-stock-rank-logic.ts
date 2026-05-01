import { useStockStore } from '../../store/use-stock-store';
import { useStockRanking, type RankingType } from './use-stock-value-ranking';

/**
 * 랭킹 리스트 데이터 처리 로직을 담당하는 훅
 * - Zustand Store의 stockCodes를 구독하여 리스트 순서 관리
 */
export const useStockRankLogic = (type: RankingType, limit = 40) => {
	const { isConnected, isLoading } = useStockRanking(type, limit);

	// 전체 맵이 아닌 정렬된 코드 리스트만 구독 (순서 변경 시에만 리렌더링)
	const stockCodes = useStockStore((state) => state.stockCodes);

	return {
		stockCodes,
		isConnected,
		isLoading,
		sortType: (type === 'VALUE' ? 'value' : 'volume') as 'value' | 'volume',
	};
};