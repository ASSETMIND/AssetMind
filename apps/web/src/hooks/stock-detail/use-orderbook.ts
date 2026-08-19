import { useEffect, useRef, useState } from 'react';
import { Client } from '@stomp/stompjs';
import SockJS from 'sockjs-client';
import { getOrderbook, getOrderbookTopic } from '../../api/stock';
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

function toViewModel(raw: OrderbookDto, basePrice: number): OrderbookViewModel {
	const ref = basePrice ?? 0;
	const sorted = [...raw.levels].sort((a, b) => a.level - b.level);
	return {
		asks: sorted.map((l: OrderbookLevelDto) => levelToRow(l.askPrice, l.askSize, ref)),
		bids: sorted.map((l: OrderbookLevelDto) => levelToRow(l.bidPrice, l.bidSize, ref)),
		totalAskSize: Number(raw.totalAskSize),
		totalBidSize: Number(raw.totalBidSize),
		marketTime:   raw.marketTime,
	};
}

export function useOrderbook(stockCode: string, basePrice?: number) {
	const [raw, setRaw] = useState<OrderbookDto | null>(null);
	const [status, setStatus] = useState<OrderbookStatus>('skeleton');
	const clientRef = useRef<Client | null>(null);
	const wsReceivedRef = useRef(false);

	// ── REST 스냅샷 선호출 ────────────────────────────────────
	useEffect(() => {
		if (!stockCode) return;
		wsReceivedRef.current = false;

		getOrderbook(stockCode).then((snapshot) => {
			if (wsReceivedRef.current) return;
			if (snapshot) {
				setRaw(snapshot);
				setStatus('default');
			}
		});
	}, [stockCode]);

	// ── SockJS WS 연결 ────────────────────────────────────────
	useEffect(() => {
		if (!stockCode) return;

		const client = new Client({
			webSocketFactory: () => new SockJS('http://localhost:9090/ws-stock'),
			reconnectDelay: 5000,
			onConnect: () => {
				client.subscribe(getOrderbookTopic(stockCode), (message) => {
					try {
						const dto = JSON.parse(message.body) as OrderbookDto;
						wsReceivedRef.current = true;
						setRaw(dto);
						setStatus('default');
					} catch {
						setStatus('error');
					}
				});
			},
			onStompError: () => {
				setStatus((prev) => prev === 'default' ? 'default' : 'error');
			},
			onDisconnect: () => {
			},
		});

		client.activate();
		clientRef.current = client;

		return () => {
			client.deactivate();
			clientRef.current = null;
		};
	}, [stockCode]);

	const viewModel: OrderbookViewModel | null =
		raw ? toViewModel(raw, basePrice ?? 0) : null;

	return { viewModel, status };
}