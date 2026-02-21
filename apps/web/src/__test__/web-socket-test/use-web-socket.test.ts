import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../../hooks/web-socket/use-web-socket';
import { useWebSocketStore } from '../../store/web-socket';

//웹소켓 커스텀 훅(useWebSocket)의 상태 관리, 연결, 메시지 송수신 및 예외 처리 로직을 검증하는 테스트 코드

describe('useWebSocket Hook', () => {
	let originalWebSocket: any;
	let mockSocket: any;

	beforeAll(() => {
		originalWebSocket = global.WebSocket;
	});

	afterAll(() => {
		global.WebSocket = originalWebSocket;
	});

	beforeEach(() => {
		// Zustand 스토어 상태 초기화
		useWebSocketStore.setState({
			isConnected: false,
			lastMessage: null,
			error: null,
		});

		// WebSocket Mock 객체 생성
		mockSocket = {
			send: jest.fn(),
			close: jest.fn(),
			readyState: 0, // CONNECTING
			onopen: null,
			onmessage: null,
			onerror: null,
			onclose: null,
		};

		// global.WebSocket을 Mock 함수로 대체
		global.WebSocket = jest.fn(() => mockSocket) as any;
		(global.WebSocket as any).OPEN = 1;
		(global.WebSocket as any).CONNECTING = 0;
		(global.WebSocket as any).CLOSING = 2;
		(global.WebSocket as any).CLOSED = 3;

		jest.useFakeTimers();
		jest.spyOn(console, 'log').mockImplementation(() => {});
		jest.spyOn(console, 'error').mockImplementation(() => {});
		jest.spyOn(console, 'warn').mockImplementation(() => {});
	});

	afterEach(() => {
		jest.clearAllMocks();
		jest.restoreAllMocks();
		jest.useRealTimers();
	});

	/*
	 * - 컴포넌트 마운트 시 초기 연결 동작 검증
	 * - 인자로 전달한 URL이 WebSocket 생성자에 정확히 전달되는지 확인
	 * - 불필요한 중복 연결 없이 최초 1회만 호출되는지 확인
	 */
	it('마운트 시 지정된 URL로 웹소켓 연결을 시도해야 한다', () => {
		const url = 'ws://test.com';
		renderHook(() => useWebSocket(url));

		expect(global.WebSocket).toHaveBeenCalledWith(url);
		expect(global.WebSocket).toHaveBeenCalledTimes(1);
	});

	/*
	 * - 웹소켓 연결 성공(onopen) 이벤트 발생 시 상태 변화 검증
	 * - 훅의 반환값(isConnected)이 true로 업데이트되는지 확인
	 * - Zustand 전역 스토어의 상태도 동일하게 동기화되는지 확인
	 */
	it('연결 성공 시 isConnected 상태가 true로 변경되어야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		act(() => {
			if (mockSocket.onopen) mockSocket.onopen();
		});

		expect(result.current.isConnected).toBe(true);
		expect(useWebSocketStore.getState().isConnected).toBe(true);
	});

	/*
	 * - 서버로부터 메시지 수신(onmessage) 이벤트 발생 시 동작 검증
	 * - 수신된 이벤트 데이터가 lastMessage 상태에 정상적으로 할당되는지 확인
	 * - 전역 스토어에도 동일하게 데이터가 업데이트되는지 확인
	 */
	it('메시지 수신 시 lastMessage 상태가 업데이트되어야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));
		const messageEvent = { data: 'test message' } as MessageEvent;

		act(() => {
			if (mockSocket.onmessage) mockSocket.onmessage(messageEvent);
		});

		expect(result.current.lastMessage).toBe(messageEvent);
		expect(useWebSocketStore.getState().lastMessage).toBe(messageEvent);
	});

	/*
	 * - 웹소켓 통신 중 에러(onerror) 발생 시 예외 처리 검증
	 * - 발생한 에러 객체가 error 상태에 정상적으로 할당되는지 확인
	 * - 전역 스토어의 에러 상태 동기화 확인
	 */
	it('에러 발생 시 error 상태가 업데이트되어야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));
		const errorEvent = new Event('error');

		act(() => {
			if (mockSocket.onerror) mockSocket.onerror(errorEvent);
		});

		expect(result.current.error).toBe(errorEvent);
		expect(useWebSocketStore.getState().error).toBe(errorEvent);
	});

	/*
	 * - 클라이언트에서 서버로 메시지를 전송하는 로직 검증
	 * - 연결이 완료된 상태(OPEN)일 때 내장 send 함수가 정상 호출되는지 확인
	 * - 전달한 메시지 페이로드가 정확하게 전송되는지 확인
	 */
	it('sendMessage 호출 시 웹소켓으로 메시지를 전송해야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		// 연결 상태를 OPEN으로 설정
		mockSocket.readyState = 1;

		const message = 'hello server';
		act(() => {
			result.current.sendMessage(message);
		});

		expect(mockSocket.send).toHaveBeenCalledWith(message);
	});

	/*
	 * - 불안정한 연결 상태에서의 예외 처리 검증
	 * - 연결 중(CONNECTING)이거나 끊어진 상태일 때 send 함수가 호출되지 않음을 확인
	 * - 개발자 도구 콘솔에 적절한 경고(warn) 로그가 출력되는지 확인
	 */
	it('연결되지 않은 상태에서 sendMessage 호출 시 전송하지 않고 경고를 출력해야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		// 연결 상태를 CONNECTING(0)으로 설정
		mockSocket.readyState = 0;

		act(() => {
			result.current.sendMessage('hello');
		});

		expect(mockSocket.send).not.toHaveBeenCalled();
		expect(console.warn).toHaveBeenCalledWith('WebSocket is not connected');
	});

	/*
	 * - 비정상적인 연결 종료 시 자동 재연결 로직 검증
	 * - 연결 종료(onclose) 이벤트 발생 시 isConnected 상태가 false로 변경되는지 확인
	 * - 지정된 재연결 대기 시간 경과 후 WebSocket 객체가 다시 생성(호출)되는지 확인
	 */
	it('연결이 끊어지면 지정된 시간 후 재연결을 시도해야 한다', () => {
		const reconnectInterval = 3000;
		renderHook(() => useWebSocket('ws://test.com', reconnectInterval));

		// 연결 종료 시뮬레이션 (상태를 CLOSED로 변경 후 이벤트 발생)
		mockSocket.readyState = 3;
		act(() => {
			if (mockSocket.onclose) mockSocket.onclose();
		});

		expect(useWebSocketStore.getState().isConnected).toBe(false);

		// 재연결 대기 시간만큼 진행
		act(() => {
			jest.advanceTimersByTime(reconnectInterval);
		});

		// 초기 연결(1) + 재연결(1) = 총 2회 호출
		expect(global.WebSocket).toHaveBeenCalledTimes(2);
	});

	/*
	 * - 사용자의 의도적인 연결 해제 동작 검증
	 * - 수동으로 disconnect 함수 호출 시 내장 close 함수가 실행되는지 확인
	 * - 지정된 시간이 지나도 자동 재연결 로직 타이머가 동작하지 않음을 명확히 검증
	 */
	it('disconnect 호출 시 연결을 종료하고 재연결하지 않아야 한다', () => {
		const reconnectInterval = 3000;
		const { result } = renderHook(() =>
			useWebSocket('ws://test.com', reconnectInterval),
		);

		act(() => {
			result.current.disconnect();
		});

		expect(mockSocket.close).toHaveBeenCalled();

		// 시간이 지나도 재연결이 시도되지 않음을 검증
		act(() => {
			jest.advanceTimersByTime(reconnectInterval);
		});

		// 초기 마운트 시 1번 호출된 것 외에 추가 호출이 없어야 함
		expect(global.WebSocket).toHaveBeenCalledTimes(1);
	});

	/*
	 * - 메모리 누수 방지를 위한 클린업 로직 검증
	 * - 컴포넌트가 화면에서 사라질 때 강제로 close 함수가 호출되어 자원이 정리되는지 확인
	 */
	it('컴포넌트 언마운트 시 웹소켓 연결을 종료해야 한다', () => {
		const { unmount } = renderHook(() => useWebSocket('ws://test.com'));

		unmount(); // 컴포넌트 강제 언마운트

		expect(mockSocket.close).toHaveBeenCalledTimes(1);
	});

	/*
	 * - 불필요한 네트워크 리소스 낭비 방지 로직 검증
	 * - 현재 상태가 연결 완료(OPEN)일 때 connect 함수를 수동으로 중복 호출해도 무시되는지 확인
	 */
	it('이미 연결 중이거나 연결된 상태에서는 중복으로 연결하지 않아야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		// 연결 상태를 OPEN(1)으로 강제 설정
		mockSocket.readyState = 1;

		act(() => {
			result.current.connect(); // 수동 연결 시도
		});

		// 최초 마운트 시 1번 호출된 것 외에, 수동 호출로 인한 추가 생성이 없어야 함
		expect(global.WebSocket).toHaveBeenCalledTimes(1);
	});
});
