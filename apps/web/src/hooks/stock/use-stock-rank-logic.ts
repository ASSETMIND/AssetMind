import { useMemo } from 'react';
import { useStockRanking, type RankingType } from './use-stock-value-ranking';
import type { StockItemData } from '../../components/stock/stock-item';

export const useStockRankLogic = (type: RankingType, limit = 40) => {
	const { rankingData, isConnected, isLoading } = useStockRanking(type, limit);

	const stockList: StockItemData[] = useMemo(() => {
		if (!rankingData) return [];

		return rankingData.map((stock, index) => {
			// 거래대금/거래량 텍스트 포맷팅 분기 처리
			let tradeVolumeStr = '';
			if (type === 'VOLUME') {
				tradeVolumeStr = `${stock.cumulativeVolume.toLocaleString()}주`;
			} else {
				tradeVolumeStr = `${Math.floor(stock.cumulativeAmount / 100000000).toLocaleString()}억원`;
			}

			// 매수/매도 비율 시뮬레이션 (등락률 가중치 부여)
			let buyRatio = 50 + stock.changeRate * 2;
			buyRatio = Math.max(10, Math.min(90, Math.floor(buyRatio))); // 10~90 사이로 제한
			const sellRatio = 100 - buyRatio;

			return {
				stockCode: stock.stockCode,
				rank: index + 1,
				stockName: stock.stockName,
				price: stock.currentPrice.toLocaleString(), // 천 단위 콤마 추가
				changeRate: stock.changeRate,
				tradeVolume: tradeVolumeStr,
				buyRatio,
				sellRatio,
			};
		});
	}, [rankingData, type]);

	return {
		stockList,
		isConnected,
		isLoading,
		sortType: (type === 'VALUE' ? 'value' : 'volume') as 'value' | 'volume',
	};
};
