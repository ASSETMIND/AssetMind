import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useStockRanking } from '../../hooks/stock/use-stock-value-ranking';
import { useWebSocket } from '../../hooks/web-socket/use-web-socket';
import { usePageVisibility } from '../../hooks/common/use-page-visibility';
import { getStockRanking } from '../../api/stock';

jest.mock('../../hooks/web-socket/use-web-socket');
jest.mock('../../hooks/common/use-page-visibility');
jest.mock('../../api/stock', () => ({
	STOCK_WS_URL: 'ws://mock',
	getStockRanking: jest.fn(),
}));
jest.mock('../../store/use-stock-store', () => ({
	useStockStore: () => ({
		setInitialStocks: jest.fn(),
		updateStocks: jest.fn(),
	}),
}));

describe('useStockRanking - Visibility 최적화 테스트', () => {
	let queryClient: QueryClient;
	const mockSubscribe = jest.fn();

	beforeEach(() => {
		queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
		jest.clearAllMocks();

		(useWebSocket as jest.Mock).mockReturnValue({
			isConnected: true,
			subscribe: mockSubscribe.mockReturnValue({ unsubscribe: jest.fn() }),
		});
		(getStockRanking as jest.Mock).mockResolvedValue([]);
	});

	const wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);

	it('탭이 비활성화(hidden)되면 소켓 구독 및 배칭 작업을 수행하지 않아야 한다', () => {
		// 가시성 상태를 false로 모킹하여 백그라운드 환경 조성
		(usePageVisibility as jest.Mock).mockReturnValue(false);

		renderHook(() => useStockRanking('VALUE', 10), { wrapper });

		// 비활성 상태에서는 구독 함수가 호출되지 않아야 함
		expect(mockSubscribe).not.toHaveBeenCalled();
	});

	it('탭이 다시 활성화(visible)되면 데이터를 재조회(refetch)해야 한다', async () => {
		// 비활성화 상태로 시작
		(usePageVisibility as jest.Mock).mockReturnValueOnce(false).mockReturnValue(true);

		renderHook(() => useStockRanking('VALUE', 10), { wrapper });

		// 포그라운드 복귀 시 최신 데이터 동기화를 위한 API 호출 여부 검증
		await waitFor(() => {
			expect(getStockRanking).toHaveBeenCalled();
		});
	});
});
