import { useCallback, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Client, type IMessage } from '@stomp/stompjs';
import SockJS from 'sockjs-client';

/*
 * STOMP 기반 웹소켓 연결 관리를 위한 커스텀 훅
 *
 * [반환 속성]
 * - isConnected: 웹소켓 연결 상태 (boolean)
 * - lastMessage: (성능 최적화를 위해 전역 상태에서 제거됨)
 * - error: 발생한 에러 이벤트 객체
 * - sendMessage: STOMP 메시지 발행 (publish) 함수
 * - subscribe: 특정 채널 구독 함수
 * - connect: 수동 연결 함수
 * - disconnect: 수동 연결 해제 함수
 */

export const useWebSocket = (
	url: string,
	reconnectInterval = 5000,
	onConnect?: () => void,
) => {
	const queryClient = useQueryClient();
	const queryKey = ['websocket', 'status', url];

	// React Query를 전역 상태 저장소처럼 사용하여 연결 상태 관리 (Zustand 대체)
	const { data: status } = useQuery({
		queryKey,
		queryFn: () => ({ isConnected: false, error: null as Event | null }),
		staleTime: Infinity, // 상태 자동 만료 방지
		gcTime: Infinity, // 언마운트 후에도 상태 유지
	});

	const isConnected = status?.isConnected ?? false;
	const error = status?.error ?? null;

	const client = useRef<Client | null>(null);
	const connectRef = useRef<() => void>(() => {});

	// onConnect 콜백을 ref로 관리하여 의존성 배열 문제 해결
	const onConnectRef = useRef(onConnect);
	useEffect(() => {
		onConnectRef.current = onConnect;
	}, [onConnect]);

	const connect = useCallback(() => {
		// 이미 활성화된 클라이언트가 있으면 중단
		if (client.current?.active) return;

		const stompClient = new Client({
			webSocketFactory: () => new SockJS(url),
			reconnectDelay: reconnectInterval, // 자동 재연결 간격 설정
			onConnect: () => {
				queryClient.setQueryData(queryKey, { isConnected: true, error: null });
				console.log('STOMP Connected');
				onConnectRef.current?.();
			},
			onStompError: (frame) => {
				// IFrame은 Event 타입이 아니므로 CustomEvent로 래핑하여 전달
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
			// 디버그 로그가 필요하면 아래 주석 해제
			debug: (str) => console.log(str),
		});

		stompClient.activate();
		client.current = stompClient;
	}, [url, reconnectInterval, queryClient]);

	// connect 함수가 변경될 때마다 ref 업데이트 (재귀 호출 지원)
	useEffect(() => {
		connectRef.current = connect;
	}, [connect]);

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

	// STOMP 메시지 발행 (Publish)
	const sendMessage = useCallback((destination: string, body: any = {}) => {
		if (client.current && client.current.connected) {
			client.current.publish({
				destination,
				body: typeof body === 'string' ? body : JSON.stringify(body),
			});
		} else {
			console.warn('STOMP client is not connected');
		}
	}, []);

	// STOMP 구독 (Subscribe)
	const subscribe = useCallback(
		(destination: string, callback?: (msg: any) => void) => {
			if (!client.current || !client.current.connected) return;

			return client.current.subscribe(destination, (message: IMessage) => {
				// 💡 lastMessage 전역 상태 업데이트 제거 (성능 최적화)
				// 데이터를 소비하는 곳(개별 훅)에서 callback을 통해 즉시 처리하도록 강제합니다.
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

	// 생명주기 관리
	// - 마운트 시: 자동 연결 (connect)
	// - 언마운트 시: 연결 해제 (disconnect)
	useEffect(() => {
		connect();
		return () => {
			disconnect();
		};
	}, [connect, disconnect]);

	return {
		isConnected,
		error,
		sendMessage,
		subscribe,
		connect,
		disconnect,
	};
};
