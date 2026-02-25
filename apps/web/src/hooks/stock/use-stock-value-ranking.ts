import { useEffect, useState } from 'react';
import { useWebSocket } from '../web-socket/use-web-socket';
import { StockRankingResponseSchema } from '../../libs/schema/stock';
import type { StockRankingDto } from '../../types/stock';
import { STOCK_WS_URL } from '../../api/stock';

export type RankingType = 'VALUE' | 'VOLUME';

export const useStockRanking = (type: RankingType = 'VALUE', limit = 10) => {
	const [rankingData, setRankingData] = useState<StockRankingDto[]>([]);

	const { isConnected, subscribe, sendMessage } = useWebSocket(STOCK_WS_URL);

	// 연결(및 재연결) 시 STOMP 구독 및 초기 데이터 요청
	useEffect(() => {
		if (!isConnected) return;

		// 타입에 따른 토픽 및 메시지 타입 설정
		const topic =
			type === 'VALUE' ? '/topic/ranking/value' : '/topic/ranking/volume';
		const appDestination =
			type === 'VALUE' ? '/app/ranking/value' : '/app/ranking/volume';
		const responseType =
			type === 'VALUE' ? 'RANKING_VALUE_UPDATE' : 'RANKING_VOLUME_UPDATE';

		// 1. 토픽 구독 (데이터 수신)
		const subscription = subscribe(topic, (data) => {
			// Zod 스키마를 통한 런타임 데이터 검증
			const result = StockRankingResponseSchema.safeParse(data);

			if (result.success) {
				// 요청한 타입에 맞는 응답인지 확인
				if (result.data.type === responseType) {
					setRankingData(result.data.data);
				}
			} else {
				console.warn('Invalid stock ranking data format:', result.error);
			}
		});

		// 2. 파라미터 전송 (Limit 설정 등)
		sendMessage(appDestination, { limit });

		return () => {
			subscription?.unsubscribe();
		};
	}, [isConnected, subscribe, sendMessage, limit, type]);

	return { rankingData, isConnected };
};
