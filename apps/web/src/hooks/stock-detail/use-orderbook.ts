import { useEffect, useRef, useState } from 'react';
import { Client } from '@stomp/stompjs';
import SockJS from 'sockjs-client';
import { getOrderbookTopic } from '../../api/stock';
import type { OrderbookDto, OrderbookLevelDto } from '../../api/stock';
import type { OrderbookRow } from '../../components/stock-detail/orderbook-table';

function levelToRow(price: string, size: string, baseRef: number): OrderbookRow {
	const priceNum = Number(price);
	const changeRate = baseRef > 0
		? Number((((priceNum - baseRef) / baseRef) * 100).toFixed(2))
		: 0;
	return { price: priceNum, changeRate, quantity: Number(size) };
}

export interface OrderbookViewModel {
	asks:         OrderbookRow[];
	bids:         OrderbookRow[];
	totalAskSize: number;
	totalBidSize: number;
	marketTime:   string;
}

export type OrderbookStatus = 'skeleton' | 'error' | 'default';

export function useOrderbook(stockCode: string, basePrice?: number) {
	const [raw, setRaw] = useState<OrderbookDto | null>(null);
	const [status, setStatus] = useState<OrderbookStatus>('skeleton');
	const clientRef = useRef<Client | null>(null);

	console.log('[useOrderbook] render - stockCode:', stockCode, 'basePrice:', basePrice);

	useEffect(() => {
		if (!stockCode) return;

		console.log('[useOrderbook] connecting to SockJS...');

		const client = new Client({
			webSocketFactory: () => new SockJS('http://localhost:9090/ws-stock'),
			reconnectDelay: 5000,
			onConnect: () => {
				console.log('[useOrderbook] STOMP connected!');
				client.subscribe(getOrderbookTopic(stockCode), (message) => {
					try {
						const dto = JSON.parse(message.body) as OrderbookDto;
						console.log('[useOrderbook] received:', dto);
						setRaw(dto);
						setStatus('default');
					} catch {
						setStatus('error');
					}
				});
			},
			onStompError: (frame) => {
				console.error('[useOrderbook] STOMP error:', frame);
				setStatus('error');
			},
			onDisconnect: () => {
				console.log('[useOrderbook] disconnected');
				setStatus('skeleton');
			},
			onWebSocketError: (e) => console.error('[useOrderbook] WS error:', e),
		});

		client.activate();
		clientRef.current = client;

		return () => {
			client.deactivate();
			clientRef.current = null;
		};
	}, [stockCode]);

	const viewModel: OrderbookViewModel | null = raw
		? (() => {
				const ref = basePrice ?? 0;
				const sorted = [...raw.levels].sort((a, b) => a.level - b.level);
				const asks: OrderbookRow[] = sorted.map((l: OrderbookLevelDto) =>
					levelToRow(l.askPrice, l.askSize, ref),
				);
				const bids: OrderbookRow[] = sorted.map((l: OrderbookLevelDto) =>
					levelToRow(l.bidPrice, l.bidSize, ref),
				);
				return {
					asks,
					bids,
					totalAskSize: Number(raw.totalAskSize),
					totalBidSize: Number(raw.totalBidSize),
					marketTime:   raw.marketTime,
				};
			})()
		: null;

	return { viewModel, status };
}