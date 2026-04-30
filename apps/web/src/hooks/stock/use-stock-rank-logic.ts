import { useMemo } from 'react';
import { useStockRanking } from './use-stock-value-ranking';
import type { RankingType, StockRow } from '../../types/stock';

export const useStockRankLogic = (type: RankingType, limit = 20) => {
	const { rankingData, isConnected } = useStockRanking(type, limit);

	const stockList: StockRow[] = useMemo(() => {
		if (!rankingData) return [];

		return rankingData.map((stock, index) => {
			// 랭킹 타입에 따라 표시할 거래 데이터 결정
			// VALUE: 거래대금(원), VOLUME: 거래량(주) → tradeAmount에 통합
			const tradeAmount =
				type === 'VOLUME'
					? stock.cumulativeVolume
					: stock.cumulativeAmount;

			// 매수 비율 추정 (API 미제공 — 등락률 기반)
			// 등락률이 높을수록 매수세 강하다고 가정
			let buyRatio = 50 + stock.changeRate * 2;
			buyRatio = Math.max(10, Math.min(90, Math.floor(buyRatio)));

			// 등락 방향에 따라 ticker 상태 결정
			const tickerState: StockRow['tickerState'] =
				stock.changeRate > 0
					? 'rise'
					: stock.changeRate < 0
						? 'fall'
						: 'idle';

			return {
				id: stock.stockCode,
				rank: index + 1,
				isFavorite: false, // 즐겨찾기는 로컬 상태로 관리 (API 미제공)
				name: stock.stockName,
				price: stock.currentPrice,
				changeRate: stock.changeRate,
				tradeAmount,
				buyRatio,
				tickerState,
			};
		});
	}, [rankingData, type]);

	return {
		stockList,
		isConnected,
		sortType: (type === 'VALUE' ? 'value' : 'volume') as 'value' | 'volume',
	};
};