import { useMemo } from 'react';
import { useStockRanking, type RankingType } from './use-stock-value-ranking';
import type { StockItemData } from '../../components/stock-main/stock-item';

/**
 * 랭킹 리스트 데이터 처리 로직을 담당하는 훅
 * 데이터를 최소한으로 가공하여 렌더링 성능을 확보
 */
export const useStockRankLogic = (type: RankingType, limit = 40) => {
	const { rankingData, isConnected, isLoading } = useStockRanking(type, limit);

	const stockList: StockItemData[] = useMemo(() => {
		if (!rankingData) return [];

		// 필요한 데이터만 매핑하여 가벼운 객체 배열 유지
		return rankingData.map((stock, index) => {
			// 거래대금/거래량 텍스트 포맷팅 (데이터가 바뀔 때만 연산됨)
			const tradeVolumeStr =
				type === 'VOLUME'
					? `${stock.cumulativeVolume.toLocaleString()}주`
					: `${Math.floor(stock.cumulativeAmount / 100000000).toLocaleString()}억원`;

			// 매수/매도 비율 계산 (UI용 가중치 부여)
			let buyRatio = 50 + stock.changeRate * 2;
			buyRatio = Math.max(10, Math.min(90, Math.floor(buyRatio)));
			const sellRatio = 100 - buyRatio;

			return {
				stockCode: stock.stockCode,
				rank: index + 1,
				stockName: stock.stockName,
				price: stock.currentPrice.toLocaleString(),
				changeRate: stock.changeRate,
				tradeVolume: tradeVolumeStr,
				buyRatio,
				sellRatio,
			};
		});
	}, [rankingData, type]);

	// sortType을 메모이제이션하여 참조 무결성 유지
	const sortType = useMemo(
		() => (type === 'VALUE' ? 'value' : 'volume'),
		[type],
	) as 'value' | 'volume';

	return {
		stockList,
		isConnected,
		isLoading,
		sortType,
	};
};
