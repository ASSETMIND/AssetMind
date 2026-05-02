import { useCallback, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Client, type IMessage } from '@stomp/stompjs';
import SockJS from 'sockjs-client';
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
	// isVisible을 ref로 관리해서 connect 함수 재생성 방지
	const isVisibleRef = useRef(isVisible);

	useEffect(() => {
		onConnectRef.current = onConnect;
	}, [onConnect]);

	useEffect(() => {
		isVisibleRef.current = isVisible;
	}, [isVisible]);

	const connect = useCallback(() => {
		if (client.current?.active) return;

		// isVisible을 ref로 참조 (의존성 배열에서 제거)
		if (autoDisconnectInBackground && !isVisibleRef.current) return;

		const stompClient = new Client({
			webSocketFactory: () => {
				const isDev =
					typeof process !== 'undefined' &&
					process.env.NODE_ENV === 'development';
				const opts = isDev ? { transports: 'websocket' } : {};
				return new SockJS(url, undefined, opts);
			},
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
		// autoDisconnectInBackground, isVisibleRef는 ref라 의존성 불필요
		// eslint-disable-next-line react-hooks/exhaustive-deps
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

	// 탭 가시성 변경에 따른 자동 연결/해제
	useEffect(() => {
		if (!autoDisconnectInBackground) return;

		if (isVisible) {
			console.log('Tab became visible: Reconnecting STOMP...');
			connect();
		} else {
			console.log('Tab became hidden: Pausing STOMP...');
			disconnect();
		}
		// connect, disconnect는 안정적(stable)이므로 의존성 배열에 포함해도 무방
	}, [isVisible, autoDisconnectInBackground, connect, disconnect]);

	// 마운트 시 자동 연결, 언마운트 시 해제
	useEffect(() => {
		connect();
		return () => {
			disconnect();
		};
	}, [connect, disconnect]);

	const sendMessage = useCallback((destination: string, body: unknown = {}) => {
		if (client.current && client.current.connected) {
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
			if (!client.current || !client.current.connected) return;

			return client.current.subscribe(destination, (message: IMessage) => {
				if (callback) {
					try {
						callback(JSON.parse(message.body));
					} catch (e) {
						console.error('Failed to parse message body', e);
					}
				}
			});
		},
		[],
	);

	return {
		isConnected,
		error,
		sendMessage,
		subscribe,
		connect,
		disconnect,
	};
};