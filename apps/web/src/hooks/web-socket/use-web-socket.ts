import { useCallback, useEffect, useRef } from 'react';
import { Client, type IMessage } from '@stomp/stompjs';
import { useWebSocketStore } from '../../store/web-socket';

/*
 * STOMP 기반 웹소켓 연결 관리를 위한 커스텀 훅
 *
 * [반환 속성]
 * - isConnected: 웹소켓 연결 상태 (boolean)
 * - lastMessage: 최근 수신된 메시지 이벤트 객체
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
	const {
		isConnected,
		lastMessage,
		error,
		setIsConnected,
		setLastMessage,
		setError,
	} = useWebSocketStore();

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
			brokerURL: url,
			reconnectDelay: reconnectInterval, // 자동 재연결 간격 설정
			onConnect: () => {
				setIsConnected(true);
				setError(null);
				console.log('STOMP Connected');
				onConnectRef.current?.();
			},
			onStompError: (frame) => {
				// IFrame은 Event 타입이 아니므로 CustomEvent로 래핑하여 전달
				const errorEvent = new CustomEvent('stomp-error', { detail: frame });
				setError(errorEvent);
				console.error('STOMP Error:', frame);
			},
			onWebSocketClose: () => {
				setIsConnected(false);
				console.log('STOMP Disconnected');
			},
			// 디버그 로그가 필요하면 아래 주석 해제
			// debug: (str) => console.log(str),
		});

		stompClient.activate();
		client.current = stompClient;
	}, [url, reconnectInterval, setIsConnected, setError]);

	// connect 함수가 변경될 때마다 ref 업데이트 (재귀 호출 지원)
	useEffect(() => {
		connectRef.current = connect;
	}, [connect]);

	const disconnect = useCallback(() => {
		if (client.current) {
			client.current.deactivate();
			client.current = null;
		}
		setIsConnected(false);
	}, [setIsConnected]);

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
				// 기존 store와의 호환성을 위해 data 프로퍼티가 있는 객체로 변환하여 저장
				const eventLike = new MessageEvent('message', {
					data: message.body,
				});
				setLastMessage(eventLike);

				if (callback) {
					try {
						callback(JSON.parse(message.body));
					} catch (e) {
						console.error('Failed to parse message body', e);
					}
				}
			});
		},
		[setLastMessage],
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
		lastMessage,
		error,
		sendMessage,
		subscribe,
		connect,
		disconnect,
	};
};
