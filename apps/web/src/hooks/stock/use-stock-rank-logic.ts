import { useStockStore } from '../../store/use-stock-store';
import { useStockRanking, type RankingType } from './use-stock-value-ranking';

export const useStockRankLogic = (type: RankingType, limit = 40) => {
	const { isConnected, isLoading } = useStockRanking(type, limit);

	const stockCodes = useStockStore((state) => state.stockCodes);
	const mapVersion = useStockStore((state) => state.mapVersion);

	return {
		stockCodes,
		mapVersion,
		isConnected,
		isLoading,
		sortType: (type === 'VALUE' ? 'value' : 'volume') as 'value' | 'volume',
	};
};