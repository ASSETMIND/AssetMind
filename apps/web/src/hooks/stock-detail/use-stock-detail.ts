import { useEffect, useState } from 'react';
import { useWebSocket } from '../web-socket/use-web-socket';
import { STOCK_WS_URL } from '../../api/stock';

export interface StockDetailData {
	stockCode:        string;
	currentPrice:     number;
	priceChange:      number;
	changeRate:       number;
	openPrice:        number;
	highPrice:        number;
	lowPrice:         number;
	cumulativeVolume: number;
	cumulativeAmount: number;
}

/**
 * 개별 종목 실시간 데이터 훅
 * - STOMP /topic/stocks/{stockCode} 구독
 * - 연결 전까지는 null 반환
 */
export function useStockDetail(stockCode: string) {
	const [data, setData] = useState<StockDetailData | null>(null);

	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL, {
		autoDisconnectInBackground: true,
	});

	useEffect(() => {
		if (!isConnected || !stockCode) return;

		const topic = `/topic/stocks/${stockCode}`;
		const subscription = subscribe(topic, (raw: unknown) => {
			const d = raw as Record<string, string>;
			setData({
				stockCode:        d.stockCode,
				currentPrice:     Number(d.currentPrice) || 0,
				priceChange:      Number(d.priceChange)  || 0,
				changeRate:       Number(d.changeRate)   || 0,
				openPrice:        Number(d.openPrice)    || 0,
				highPrice:        Number(d.highPrice)    || 0,
				lowPrice:         Number(d.lowPrice)     || 0,
				cumulativeVolume: Number(d.cumulativeVolume) || 0,
				cumulativeAmount: Number(d.cumulativeAmount) || 0,
			});
		});

		return () => {
			subscription?.unsubscribe();
		};
	}, [isConnected, stockCode, subscribe]);

	return { data, isConnected };
}