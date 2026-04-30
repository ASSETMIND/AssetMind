import React from 'react';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSurgeAlerts } from '../../hooks/stock/use-stock-alerts';
import { useWebSocket } from '../../hooks/web-socket/use-web-socket';

jest.mock('../../hooks/web-socket/use-web-socket');
jest.mock('../../api/stock', () => ({
	STOCK_WS_URL: 'ws://mock',
	SURGE_ALERTS_TOPIC: '/topic/mock',
}));

describe('useSurgeAlerts - 리팩토링 후 동작 테스트', () => {
	it('useWebSocket을 autoDisconnectInBackground 옵션과 함께 호출해야 한다', () => {
		const queryClient = new QueryClient();
		(useWebSocket as jest.Mock).mockReturnValue({
			isConnected: true,
			subscribe: jest.fn(),
		});

		renderHook(() => useSurgeAlerts(), {
			wrapper: ({ children }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		});

		// 백그라운드 최적화 옵션이 정확히 전달되었는지 검증
		expect(useWebSocket).toHaveBeenCalledWith(
			expect.any(String),
			expect.objectContaining({ autoDisconnectInBackground: true })
		);
	});
});
