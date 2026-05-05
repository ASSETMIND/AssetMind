import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useWebSocket } from '../web-socket/use-web-socket';
import {
	getOrderbook,
	getOrderbookTopic,
	STOCK_WS_URL,
} from '../../api/stock';
import type { OrderbookDto } from '../../api/stock';

export function useOrderbook(stockCode: string) {
	const [data, setData] = useState<OrderbookDto | null>(null);

	// 초기 REST API 로드
	const { data: queryData, isLoading, isError } = useQuery<OrderbookDto>({
		queryKey: ['orderbook', stockCode],
		queryFn: () => getOrderbook(stockCode),
		enabled: !!stockCode,
		staleTime: 1000 * 10,
	});

	// queryData가 오면 로컬 state에 반영
	useEffect(() => {
		if (queryData) setData(queryData);
	}, [queryData]);

	// WebSocket 실시간 업데이트
	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL);

	useEffect(() => {
		if (!isConnected || !stockCode) return;

		const topic = getOrderbookTopic(stockCode);
		const subscription = subscribe(topic, (raw: unknown) => {
			const update = raw as Partial<OrderbookDto>;
			setData((prev) => {
				if (!prev) return prev;
				return { ...prev, ...update };
			});
		});

		return () => {
			subscription?.unsubscribe();
		};
	}, [isConnected, stockCode, subscribe]);

	const status = isLoading
		? 'skeleton'
		: isError
			? 'error'
			: !data
				? 'skeleton'
				: 'default';

	return { data, status, isConnected };
}