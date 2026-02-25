import { useMemo } from 'react';
import { useStockRanking, type RankingType } from './use-stock-value-ranking';
import type { StockItemData } from '../../components/stock/stock-item';

export const useStockRankLogic = (type: RankingType, limit = 20) => {
	const { rankingData, isConnected } = useStockRanking(type, limit);

	const stockList: StockItemData[] = useMemo(() => {
		if (!rankingData) return [];

		return rankingData.map((stock, index) => {
			// 거래대금 포맷팅: 원 단위 -> 억원 단위 절삭
			const tradeVolume = Math.floor(stock.cumulativeAmount / 100000000);

			// 매수/매도 비율 시뮬레이션 (데이터 부재로 인한 등락률 기반 추정)
			// 등락률이 높을수록 매수세가 강하다고 가정 (기본 50% + 등락률 가중치)
			let buyRatio = 50 + stock.changeRate * 2;
			buyRatio = Math.max(10, Math.min(90, Math.floor(buyRatio)));
			const sellRatio = 100 - buyRatio;

			return {
				id: stock.stockCode,
				rank: index + 1,
				name: stock.stockName,
				price: stock.currentPrice.toLocaleString(),
				changeRate: stock.changeRate,
				tradeVolume: `${tradeVolume.toLocaleString()}억원`,
				buyRatio,
				sellRatio,
			};
		});
	}, [rankingData]);

	return { stockList, isConnected };
};
