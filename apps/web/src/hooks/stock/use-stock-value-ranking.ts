import { useEffect, useState } from 'react';
import { useWebSocket } from '../web-socket/use-web-socket';
import { StockRankingResponseSchema } from '../../libs/schema/stock';
import type { StockRankingDto, RankingType } from '../../types/stock';
import { STOCK_WS_URL } from '../../api/stock';

export type { RankingType };

export const useStockRanking = (type: RankingType = 'VALUE', limit = 10) => {
	const [rankingData, setRankingData] = useState<StockRankingDto[]>([]);

	const { isConnected, subscribe, sendMessage } = useWebSocket(STOCK_WS_URL);

	useEffect(() => {
		if (!isConnected) return;

		const topic =
			type === 'VALUE' ? '/topic/ranking/value' : '/topic/ranking/volume';
		const appDestination =
			type === 'VALUE' ? '/app/ranking/value' : '/app/ranking/volume';
		const responseType =
			type === 'VALUE' ? 'RANKING_VALUE_UPDATE' : 'RANKING_VOLUME_UPDATE';

		const subscription = subscribe(topic, (data) => {
			const result = StockRankingResponseSchema.safeParse(data);
			if (result.success) {
				if (result.data.type === responseType) {
					setRankingData(result.data.data);
				}
			} else {
				console.warn('Invalid stock ranking data format:', result.error);
			}
		});

		sendMessage(appDestination, { limit });

		return () => {
			subscription?.unsubscribe();
		};
	}, [isConnected, subscribe, sendMessage, limit, type]);

	return { rankingData, isConnected };
};