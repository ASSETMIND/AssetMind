import { useCallback, useEffect, useRef } from 'react';
import type { UseWebSocketReturn } from '../../types/web-socket';
import { useWebSocketStore } from '../../store/web-socket';

/*
 * 웹소켓 연결 관리를 위한 커스텀 훅
 *
 * [반환 속성]
 * - isConnected: 웹소켓 연결 상태 (boolean)
 * - lastMessage: 최근 수신된 메시지 이벤트 객체
 * - error: 발생한 에러 이벤트 객체
 * - sendMessage: 서버로 메시지 전송 함수
 * - connect: 수동 연결 함수
 * - disconnect: 수동 연결 해제 함수
 */

export const useWebSocket = (
	url: string,
	reconnectInterval = 3000,
	onConnect?: () => void,
): UseWebSocketReturn => {
	const {
		isConnected,
		lastMessage,
		error,
		setIsConnected,
		setLastMessage,
		setError,
	} = useWebSocketStore();

	const ws = useRef<WebSocket | null>(null);
	const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
		null,
	);
	const shouldReconnect = useRef(true);
	const connectRef = useRef<() => void>(() => {});

	// onConnect 콜백을 ref로 관리하여 의존성 배열 문제 해결
	const onConnectRef = useRef(onConnect);
	useEffect(() => {
		onConnectRef.current = onConnect;
	}, [onConnect]);

	const connect = useCallback(() => {
		// 연결 검증
		// - 현재 상태가 OPEN 또는 CONNECTING인 경우 실행 중단
		// - 중복 연결 방지
		if (
			ws.current?.readyState === WebSocket.OPEN ||
			ws.current?.readyState === WebSocket.CONNECTING
		) {
			return;
		}

		// 재연결 타이머 초기화
		if (reconnectTimeoutRef.current) {
			clearTimeout(reconnectTimeoutRef.current);
			reconnectTimeoutRef.current = null;
		}

		shouldReconnect.current = true;
		const socket = new WebSocket(url);

		// 이벤트 핸들러 등록: 연결 성공
		// - 연결 상태 활성화 및 에러 초기화
		socket.onopen = () => {
			setIsConnected(true);
			setError(null);
			console.log('WebSocket Connected');
			// 연결 성공 시 주입된 콜백(구독 로직 등) 실행
			onConnectRef.current?.();
		};

		// 이벤트 핸들러 등록: 메시지 수신
		// - 최신 메시지 상태 업데이트
		socket.onmessage = (event) => {
			setLastMessage(event);
		};

		// 이벤트 핸들러 등록: 에러 발생
		// - 에러 상태 업데이트
		socket.onerror = (event) => {
			setError(event);
			console.error('WebSocket Error:', event);
		};

		// 이벤트 핸들러 등록: 연결 종료
		// - 연결 상태 비활성화
		socket.onclose = () => {
			setIsConnected(false);
			console.log('WebSocket Disconnected');

			// 자동 재연결 로직
			if (shouldReconnect.current) {
				console.log(`Reconnecting in ${reconnectInterval}ms...`);
				reconnectTimeoutRef.current = setTimeout(() => {
					connectRef.current();
				}, reconnectInterval);
			}
		};

		ws.current = socket;
	}, [url, reconnectInterval, setIsConnected, setLastMessage, setError]);

	// connect 함수가 변경될 때마다 ref 업데이트 (재귀 호출 지원)
	useEffect(() => {
		connectRef.current = connect;
	}, [connect]);

	const disconnect = useCallback(() => {
		shouldReconnect.current = false;
		if (reconnectTimeoutRef.current) {
			clearTimeout(reconnectTimeoutRef.current);
			reconnectTimeoutRef.current = null;
		}
		// 연결 종료 처리
		// - 웹소켓 객체가 존재할 경우 close 호출 및 참조 초기화
		if (ws.current) {
			ws.current.close();
			ws.current = null;
		}
	}, []);

	const sendMessage = useCallback((message: string | ArrayBuffer | Blob) => {
		// 메시지 전송 처리
		// - 정상 연결(OPEN) 상태에서만 메시지 전송
		// - 미연결 상태일 경우 경고 로그 출력
		if (ws.current && ws.current.readyState === WebSocket.OPEN) {
			ws.current.send(message);
		} else {
			console.warn('WebSocket is not connected');
		}
	}, []);

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
		connect,
		disconnect,
	};
};
