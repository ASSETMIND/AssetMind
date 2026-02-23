import { useEffect, useState } from 'react';
import { useWebSocket } from '../web-socket/use-web-socket';
import { StockRankingResponseSchema } from '../../libs/schema/stock';
import type { StockRankingDto } from '../../types/stock';

export const useStockValueRanking = (limit = 10) => {
	const [rankingData, setRankingData] = useState<StockRankingDto[]>([]);

	// 환경 변수에서 웹소켓 URL 로드 (없을 경우 기본값 처리)
	const WS_URL = import.meta.env.VITE_WS_URL
		? `${import.meta.env.VITE_WS_URL}/stocks`
		: 'ws://localhost:8080/stocks';

	const { lastMessage, sendMessage, isConnected } = useWebSocket(WS_URL);

	//  연결(및 재연결) 시 구독 메시지 전송
	// isConnected 상태를 감지하여 소켓이 연결되면 즉시 구독 요청을 보냄
	useEffect(() => {
		if (isConnected) {
			sendMessage(
				JSON.stringify({
					type: 'SUBSCRIBE',
					channel: 'RANKING_VALUE', // 거래대금순 랭킹 채널
					limit,
				}),
			);
		}
	}, [isConnected, sendMessage, limit]);

	// 메시지 수신 및 데이터 무결성 검증
	useEffect(() => {
		if (lastMessage?.data) {
			try {
				const parsed = JSON.parse(lastMessage.data);

				// Zod 스키마를 통한 런타임 데이터 검증
				const result = StockRankingResponseSchema.safeParse(parsed);

				if (result.success) {
					// 거래대금 랭킹 업데이트 메시지인지 확인 (채널/타입 필터링)
					if (result.data.type === 'RANKING_VALUE_UPDATE') {
						setRankingData(result.data.data);
					}
				} else {
					console.warn('Invalid stock ranking data format:', result.error);
				}
			} catch (error) {
				console.error('WebSocket message parsing error:', error);
			}
		}
	}, [lastMessage]);

	return { rankingData, isConnected };
};
