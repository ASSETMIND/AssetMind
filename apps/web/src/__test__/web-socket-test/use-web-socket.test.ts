import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../../hooks/web-socket/use-web-socket';
import { useWebSocketStore } from '../../store/web-socket';
import { Client } from '@stomp/stompjs';

// @stomp/stompjs 모듈 모킹
jest.mock('@stomp/stompjs');

/*
 * STOMP 기반 useWebSocket 훅 테스트
 * - Client 객체 생성 및 설정 검증
 * - 연결(activate), 해제(deactivate) 동작 검증
 * - 메시지 발행(publish) 및 구독(subscribe) 검증
 * - 연결 상태 및 에러 상태 동기화 검증
 */
describe('useWebSocket Hook (STOMP)', () => {
	let mockClientInstance: any;
	let capturedConfig: any;

	beforeEach(() => {
		// 1. Zustand 스토어 초기화
		useWebSocketStore.setState({
			isConnected: false,
			lastMessage: null,
			error: null,
		});

		// 2. Mock Client 인스턴스 및 메서드 정의
		mockClientInstance = {
			activate: jest.fn(),
			deactivate: jest.fn(),
			publish: jest.fn(),
			subscribe: jest.fn(),
			connected: false,
			active: false,
		};

		// 3. Client 생성자 모킹 - 설정(config)을 캡처하여 콜백 테스트에 사용
		(Client as unknown as jest.Mock).mockImplementation((config) => {
			capturedConfig = config;
			return mockClientInstance;
		});

		// 4. 콘솔 로그 모킹 (테스트 출력 깔끔하게)
		jest.spyOn(console, 'log').mockImplementation(() => {});
		jest.spyOn(console, 'error').mockImplementation(() => {});
		jest.spyOn(console, 'warn').mockImplementation(() => {});
	});

	afterEach(() => {
		jest.clearAllMocks();
	});

	it('마운트 시 STOMP Client를 생성하고 연결(activate)해야 한다', () => {
		const url = 'ws://test.com';
		renderHook(() => useWebSocket(url));

		// Client 생성자가 호출되었는지 확인
		expect(Client).toHaveBeenCalledTimes(1);
		// 생성자에 전달된 설정 확인
		expect(capturedConfig.brokerURL).toBe(url);
		// activate 메서드 호출 확인
		expect(mockClientInstance.activate).toHaveBeenCalledTimes(1);
	});

	it('연결 성공(onConnect) 시 isConnected 상태가 true로 변경되어야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		// onConnect 콜백 실행 시뮬레이션
		act(() => {
			capturedConfig.onConnect();
		});

		expect(result.current.isConnected).toBe(true);
		expect(useWebSocketStore.getState().isConnected).toBe(true);
	});

	it('연결 종료(onWebSocketClose) 시 isConnected 상태가 false로 변경되어야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		// 먼저 연결 상태로 만듦
		act(() => {
			capturedConfig.onConnect();
		});
		expect(result.current.isConnected).toBe(true);

		// 연결 종료 콜백 실행 시뮬레이션
		act(() => {
			capturedConfig.onWebSocketClose();
		});

		expect(result.current.isConnected).toBe(false);
		expect(useWebSocketStore.getState().isConnected).toBe(false);
	});

	it('STOMP 에러(onStompError) 발생 시 error 상태가 업데이트되어야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));
		const mockFrame = { body: 'Error details' };

		// 에러 콜백 실행 시뮬레이션
		act(() => {
			capturedConfig.onStompError(mockFrame);
		});

		// CustomEvent로 래핑되어 저장되었는지 확인
		const storedError = useWebSocketStore.getState().error as CustomEvent;
		expect(storedError).toBeInstanceOf(CustomEvent);
		expect(storedError.type).toBe('stomp-error');
		expect(storedError.detail).toBe(mockFrame);
		expect(result.current.error).toBe(storedError);
	});

	it('sendMessage 호출 시 publish 메서드가 올바른 인자로 호출되어야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		// 연결 상태 시뮬레이션
		mockClientInstance.connected = true;

		const destination = '/app/test';
		const body = { key: 'value' };

		act(() => {
			result.current.sendMessage(destination, body);
		});

		expect(mockClientInstance.publish).toHaveBeenCalledWith({
			destination,
			body: JSON.stringify(body),
		});
	});

	it('연결되지 않은 상태에서 sendMessage 호출 시 publish를 실행하지 않고 경고를 출력해야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		// 연결 끊김 상태 시뮬레이션
		mockClientInstance.connected = false;

		act(() => {
			result.current.sendMessage('/app/test', 'hello');
		});

		expect(mockClientInstance.publish).not.toHaveBeenCalled();
		expect(console.warn).toHaveBeenCalledWith('STOMP client is not connected');
	});

	it('subscribe 호출 시 구독을 요청하고, 메시지 수신 시 상태와 콜백을 업데이트해야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));
		mockClientInstance.connected = true;

		const destination = '/topic/test';
		const mockCallback = jest.fn();
		const mockMessage = { body: JSON.stringify({ data: 'test' }) };

		// subscribe 모킹: 콜백을 즉시 실행하지 않고 저장해둠 (여기서는 간단히 mockSubscribe가 호출되는지만 확인 후 수동 트리거)
		let subscribeCallback: any;
		mockClientInstance.subscribe.mockImplementation(
			(_dest: string, cb: any) => {
				subscribeCallback = cb;
				return { unsubscribe: jest.fn() };
			},
		);

		act(() => {
			result.current.subscribe(destination, mockCallback);
		});

		// 1. subscribe 메서드 호출 확인
		expect(mockClientInstance.subscribe).toHaveBeenCalledWith(
			destination,
			expect.any(Function),
		);

		// 2. 메시지 수신 시뮬레이션 (저장된 콜백 실행)
		act(() => {
			if (subscribeCallback) {
				subscribeCallback(mockMessage);
			}
		});

		// 3. lastMessage 상태 업데이트 확인 (MessageEvent로 래핑됨)
		const lastMsg = useWebSocketStore.getState().lastMessage;
		expect(lastMsg).toBeInstanceOf(MessageEvent);
		expect(lastMsg?.data).toBe(mockMessage.body);

		// 4. 사용자 콜백 호출 확인 (파싱된 데이터 전달)
		expect(mockCallback).toHaveBeenCalledWith({ data: 'test' });
	});

	it('disconnect 호출 시 클라이언트를 비활성화(deactivate)해야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		act(() => {
			result.current.disconnect();
		});

		expect(mockClientInstance.deactivate).toHaveBeenCalled();
		expect(useWebSocketStore.getState().isConnected).toBe(false);
	});

	it('컴포넌트 언마운트 시 클라이언트를 비활성화해야 한다', () => {
		const { unmount } = renderHook(() => useWebSocket('ws://test.com'));

		unmount(); // 컴포넌트 강제 언마운트

		expect(mockClientInstance.deactivate).toHaveBeenCalled();
	});

	it('이미 연결 중이거나 연결된 상태에서는 중복으로 연결하지 않아야 한다', () => {
		const { result } = renderHook(() => useWebSocket('ws://test.com'));

		// 이미 활성화된 상태 시뮬레이션
		// mockClientInstance.active는 getter로 동작하도록 설정하거나 속성으로 설정
		// 여기서는 간단히 속성 변경
		Object.defineProperty(mockClientInstance, 'active', {
			get: () => true,
		});

		act(() => {
			result.current.connect(); // 수동 연결 시도
		});

		// 최초 마운트 시 1번 호출된 것 외에, 추가 호출이 없어야 함
		expect(Client).toHaveBeenCalledTimes(1);
	});
});
