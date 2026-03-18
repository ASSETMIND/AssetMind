import { renderHook, act } from '@testing-library/react';
import { useStockRanking } from '../../hooks/stock/use-stock-value-ranking';
import { useWebSocket } from '../../hooks/web-socket/use-web-socket';
import type { StockRankingDto } from '../../types/stock';

// useWebSocket 훅 모킹
jest.mock('../../hooks/web-socket/use-web-socket');

const mockUseWebSocket = useWebSocket as jest.Mock;

// api 상수 모킹
jest.mock('../../api/stock.ts', () => ({
	STOCK_WS_URL: 'ws://localhost:8080/stocks',
	getStockRanking: jest.fn(() => new Promise(() => {})), // 무한 대기 Promise (비동기 업데이트로 인한 act 경고 방지)
}));

describe('useStockRanking Hook', () => {
	let mockSubscribe: jest.Mock;
	let mockSendMessage: jest.Mock;
	let mockUnsubscribe: jest.Mock;
	let isConnected = false;

	beforeEach(() => {
		// 각 테스트 전에 모킹 함수 및 상태 초기화
		mockSubscribe = jest.fn();
		mockSendMessage = jest.fn();
		mockUnsubscribe = jest.fn();
		isConnected = false;

		// useWebSocket 훅이 반환할 값 설정
		mockUseWebSocket.mockImplementation(() => {
			// subscribe 함수는 unsubscribe 함수를 포함하는 객체를 반환하도록 설정
			mockSubscribe.mockReturnValue({ unsubscribe: mockUnsubscribe });
			return {
				isConnected,
				subscribe: mockSubscribe,
				sendMessage: mockSendMessage,
			};
		});
	});

	afterEach(() => {
		jest.clearAllMocks();
	});

	it('연결되지 않았을 때는 구독이나 메시지 전송을 시도하지 않아야 한다', () => {
		renderHook(() => useStockRanking('VALUE', 10));
		expect(mockSubscribe).not.toHaveBeenCalled();
		expect(mockSendMessage).not.toHaveBeenCalled();
	});

	it('연결되었을 때 거래대금순(VALUE) 랭킹을 올바르게 구독하고 요청해야 한다', () => {
		isConnected = true; // 연결 상태로 변경
		const { rerender } = renderHook(() => useStockRanking('VALUE', 15));

		// isConnected가 true로 변경된 후 훅이 다시 실행되어야 useEffect가 동작
		rerender();

		expect(mockSubscribe).toHaveBeenCalledWith(
			'/topic/ranking/value',
			expect.any(Function),
		);
		expect(mockSendMessage).toHaveBeenCalledWith('/app/ranking/value', {
			limit: 15,
		});
	});

	it('연결되었을 때 거래량순(VOLUME) 랭킹을 올바르게 구독하고 요청해야 한다', () => {
		isConnected = true;
		const { rerender } = renderHook(() => useStockRanking('VOLUME', 20));

		rerender();

		expect(mockSubscribe).toHaveBeenCalledWith(
			'/topic/ranking/volume',
			expect.any(Function),
		);
		expect(mockSendMessage).toHaveBeenCalledWith('/app/ranking/volume', {
			limit: 20,
		});
	});

	it('웹소켓 메시지 수신 시 rankingData 상태를 업데이트해야 한다', () => {
		isConnected = true;
		const { result, rerender } = renderHook(() => useStockRanking('VALUE', 10));

		rerender();

		// subscribe 콜백 함수를 가져옴
		const subscribeCallback = mockSubscribe.mock.calls[0][1];

		const mockData: StockRankingDto[] = [
			{
				stockCode: '005930',
				stockName: '삼성전자',
				currentPrice: 80000,
				changeRate: 1.25,
				cumulativeAmount: 500000000000,
				cumulativeVolume: 6250000,
			},
		];

		// RANKING_VALUE_UPDATE 타입의 메시지 시뮬레이션
		act(() => {
			subscribeCallback({
				type: 'RANKING_VALUE_UPDATE',
				data: mockData,
			});
		});

		expect(result.current.rankingData).toEqual(mockData);
	});

	it('컴포넌트 언마운트 시 구독을 해지해야 한다', () => {
		isConnected = true;
		const { unmount, rerender } = renderHook(() =>
			useStockRanking('VALUE', 10),
		);

		rerender(); // isConnected 변경에 따른 재렌더링으로 구독 실행

		expect(mockSubscribe).toHaveBeenCalledTimes(1);

		// 언마운트
		unmount();

		expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
	});
});
