import { useCallback, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Client, type IMessage } from '@stomp/stompjs';
import { usePageVisibility } from '../common/use-page-visibility';

interface WebSocketOptions {
	reconnectInterval?: number;
	onConnect?: () => void;
	autoDisconnectInBackground?: boolean;
}

export const useWebSocket = (
	url: string,
	options: WebSocketOptions = {},
) => {
	const {
		reconnectInterval = 5000,
		onConnect,
		autoDisconnectInBackground = false,
	} = options;

	const queryClient = useQueryClient();
	const queryKey = ['websocket', 'status', url];
	const isVisible = usePageVisibility();

	const { data: status } = useQuery({
		queryKey,
		queryFn: () => ({ isConnected: false, error: null as Event | null }),
		staleTime: Infinity,
		gcTime: Infinity,
	});

	const isConnected = status?.isConnected ?? false;
	const error = status?.error ?? null;

	const client = useRef<Client | null>(null);
	const onConnectRef = useRef(onConnect);
	const isVisibleRef = useRef(isVisible);

	useEffect(() => { onConnectRef.current = onConnect; }, [onConnect]);
	useEffect(() => { isVisibleRef.current = isVisible; }, [isVisible]);

	const connect = useCallback(() => {
		if (client.current?.active) return;
		if (autoDisconnectInBackground && !isVisibleRef.current) return;

		// url이 ws:// 형태여야 함
		// ws://host/ws-stock → ws://host/ws-stock (그대로 사용)
		const brokerURL = url.startsWith('ws')
			? url
			: url.replace(/^http/, 'ws');

		const stompClient = new Client({
			brokerURL,
			reconnectDelay: reconnectInterval,
			onConnect: () => {
				queryClient.setQueryData(queryKey, { isConnected: true, error: null });
				console.log('STOMP Connected');
				onConnectRef.current?.();
			},
			onStompError: (frame) => {
				const errorEvent = new CustomEvent('stomp-error', { detail: frame });
				queryClient.setQueryData(queryKey, (prev: any) => ({
					...prev,
					error: errorEvent,
				}));
				console.error('STOMP Error:', frame);
			},
			onWebSocketClose: () => {
				queryClient.setQueryData(queryKey, (prev: any) => ({
					...prev,
					isConnected: false,
				}));
				console.log('STOMP Disconnected');
			},
		});

		stompClient.activate();
		client.current = stompClient;
	}, [url, reconnectInterval, queryClient, autoDisconnectInBackground]);

	const disconnect = useCallback(() => {
		if (client.current) {
			client.current.deactivate();
			client.current = null;
		}
		queryClient.setQueryData(['websocket', 'status', url], (prev: any) => ({
			...prev,
			isConnected: false,
		}));
	}, [url, queryClient]);

	useEffect(() => {
		if (!autoDisconnectInBackground) return;
		if (isVisible) {
			console.log('Tab became visible: Reconnecting STOMP...');
			connect();
		} else {
			console.log('Tab became hidden: Pausing STOMP...');
			disconnect();
		}
	}, [isVisible, autoDisconnectInBackground, connect, disconnect]);

	useEffect(() => {
		connect();
		return () => { disconnect(); };
	}, [connect, disconnect]);

	const sendMessage = useCallback((destination: string, body: unknown = {}) => {
		if (client.current?.connected) {
			client.current.publish({
				destination,
				body: typeof body === 'string' ? body : JSON.stringify(body),
			});
		} else {
			console.warn('STOMP client is not connected');
		}
	}, []);

	const subscribe = useCallback(
		(destination: string, callback?: (msg: unknown) => void) => {
			if (!client.current?.connected) return;
			return client.current.subscribe(destination, (message: IMessage) => {
				if (callback) {
					try { callback(JSON.parse(message.body)); }
					catch (e) { console.error('Failed to parse message body', e); }
				}
			});
		},
		[],
	);

	return { isConnected, error, sendMessage, subscribe, connect, disconnect };
};