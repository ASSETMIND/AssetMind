import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { SurgeAlertPayload } from '../../types/stock';
import { useSurgeAlerts } from '../../hooks/stock/use-stock-alerts';

// STOMP 라이브러리 및 SockJS 모킹
let mockSubscribeCallback: (message: any) => void;
let mockActivate: jest.Mock;
let mockDeactivate: jest.Mock;

jest.mock('../../api/stock', () => ({
	STOCK_WS_URL: 'ws://localhost:8080/ws-stock',
	SURGE_ALERTS_TOPIC: '/topic/surge-alerts',
}));

jest.mock('sockjs-client', () => {
	return jest.fn().mockImplementation(() => ({}));
});

jest.mock('@stomp/stompjs', () => {
	return {
		Client: jest.fn().mockImplementation((config) => {
			mockActivate = jest.fn(() => {
				if (config.onConnect) config.onConnect();
			});
			mockDeactivate = jest.fn();

			return {
				activate: mockActivate,
				deactivate: mockDeactivate,
				subscribe: jest.fn((topic, callback) => {
					mockSubscribeCallback = callback;
				}),
			};
		}),
	};
});

describe('useSurgeAlerts 커스텀 훅 테스트', () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		queryClient = new QueryClient({
			defaultOptions: { queries: { retry: false } },
		});
		jest.clearAllMocks();
	});

	const wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);

	it('초기 상태에서는 빈 배열을 반환해야 한다.', () => {
		const { result } = renderHook(() => useSurgeAlerts(), { wrapper });
		expect(result.current.alerts).toEqual([]);
	});

	it('STOMP 메시지를 수신하면 alerts 배열 맨 앞에 새로운 데이터가 추가되어야 한다.', async () => {
		const { result } = renderHook(() => useSurgeAlerts(), { wrapper });

		// React Query의 초기 마운트 및 queryFn(() => []) 비동기 처리가 끝날 때까지 대기
		// 데이터 업데이트 직후 빈 배열로 다시 덮어씌워지는 Race Condition을 방지함
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 50));
		});
		const mockAlert: SurgeAlertPayload = {
			stockCode: '005930',
			stockName: '삼성전자',
			rate: '10.5',
			currentPrice: '85000',
			changeRate: '10.5',
			alertTime: '2023-10-27T10:00:00',
		};

		act(() => {
			mockSubscribeCallback({
				body: JSON.stringify(mockAlert),
			});
		});

		await waitFor(() => {
			expect(result.current.alerts).toHaveLength(1);
			expect(result.current.alerts[0]).toEqual(mockAlert);
		});
	});

	it('메시지가 10개를 초과하여 들어오면 최신 10개까지만 유지해야 한다.', async () => {
		const { result } = renderHook(() => useSurgeAlerts(), { wrapper });

		// 초기 마운트 대기
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 50));
		});

		act(() => {
			for (let i = 1; i <= 15; i++) {
				const alertPayload: SurgeAlertPayload = {
					stockCode: `CODE_${i}`,
					stockName: `주식_${i}`,
					rate: '10.0',
					currentPrice: '50000',
					changeRate: '10.0',
					alertTime: `2023-10-27T10:0${i}:00`,
				};

				mockSubscribeCallback({
					body: JSON.stringify(alertPayload),
				});
			}
		});

		await waitFor(() => {
			expect(result.current.alerts).toHaveLength(10);
			expect(result.current.alerts[0].stockCode).toBe('CODE_15');
			expect(result.current.alerts[9].stockCode).toBe('CODE_6');
		});
	});

	it('훅이 언마운트되면 STOMP 클라이언트의 deactivate가 호출되어야 한다.', () => {
		const { unmount } = renderHook(() => useSurgeAlerts(), { wrapper });
		unmount();
		expect(mockDeactivate).toHaveBeenCalledTimes(1);
	});
});
