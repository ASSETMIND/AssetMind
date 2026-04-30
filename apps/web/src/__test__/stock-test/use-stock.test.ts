import { renderHook, waitFor, act } from '@testing-library/react';
import {
	useStockRanking,
	type RankingType,
} from '../../hooks/stock/use-stock-value-ranking';
import { getStockRanking } from '../../api/stock';
import { useWebSocket } from '../../hooks/web-socket/use-web-socket';

// API 모듈 모킹
jest.mock('../../api/stock', () => ({
	STOCK_WS_URL: 'ws://localhost:8080/ws-stock',
	getStockRanking: jest.fn(),
}));

// WebSocket 훅 모킹
jest.mock('../../hooks/web-socket/use-web-socket');

describe('useStockRanking Hook Tests', () => {
	let mockSubscribe: jest.Mock;
	let socketCallback: (data: any) => void;
	let mockUnsubscribe: jest.Mock;

	beforeEach(() => {
		jest.clearAllMocks();

		mockUnsubscribe = jest.fn();
		// WebSocket 구독 시 콜백 함수를 캡처하여 테스트에서 호출할 수 있도록 설정
		mockSubscribe = jest.fn((_topic, callback) => {
			socketCallback = callback;
			return { unsubscribe: mockUnsubscribe };
		});

		// useWebSocket 훅이 항상 연결된 상태를 반환하도록 설정
		(useWebSocket as jest.Mock).mockReturnValue({
			isConnected: true,
			subscribe: mockSubscribe,
		});

		// console.error 스파이 (에러 로그 검증용)
		jest.spyOn(console, 'error').mockImplementation(() => {});
	});

	// 초기 데이터 로딩 (REST API) 테스트
	it('마운트 시 REST API를 호출하여 초기 데이터를 로드하고 숫자형으로 변환해야 한다', async () => {
		// Mock 데이터 설정 (API 응답은 주로 문자열로 옴)
		const mockHttpData = [
			{
				stockCode: '005930',
				stockName: '삼성전자',
				currentPrice: '70000',
				priceChange: '0',
				changeRate: '0',
				cumulativeAmount: '100000', // String
				cumulativeVolume: '100',
			},
		];

		(getStockRanking as jest.Mock).mockResolvedValue(mockHttpData);

		const { result } = renderHook(() => useStockRanking('VALUE', 10));

		// 초기 상태는 빈 배열
		expect(result.current.rankingData).toEqual([]);

		// 비동기 API 호출 후 데이터 업데이트 확인
		await waitFor(() => {
			expect(result.current.rankingData).toHaveLength(1);
		});

		// 데이터 변환 확인 (String -> Number, Hook 내부 로직 검증)
		expect(result.current.rankingData[0].stockName).toBe('삼성전자');
		expect(result.current.rankingData[0].currentPrice).toBe(70000);
		expect(result.current.rankingData[0].cumulativeAmount).toBe(100000);
		expect(getStockRanking).toHaveBeenCalledWith('VALUE', 10);
	});

	it('API 호출 실패 시 에러를 로깅하고 빈 배열을 유지해야 한다', async () => {
		(getStockRanking as jest.Mock).mockRejectedValue(new Error('API Error'));

		const { result } = renderHook(() => useStockRanking('VALUE', 10));

		await waitFor(() => {
			expect(console.error).toHaveBeenCalledWith(
				'Failed to fetch initial stock ranking:',
				expect.any(Error),
			);
		});

		expect(result.current.rankingData).toEqual([]);
	});

	// 실시간 업데이트 및 로직 (WebSocket) 테스트
	it('실시간 데이터 수신 시 기존 목록을 업데이트하고 거래대금(VALUE) 순으로 재정렬해야 한다', async () => {
		// 초기 데이터: A(100억), B(50억) -> 순서: A, B
		const initialData = [
			{
				stockCode: 'A',
				stockName: 'Stock A',
				currentPrice: '1000',
				priceChange: '0',
				changeRate: '0',
				cumulativeAmount: '10000', // 1위
				cumulativeVolume: '10',
			},
			{
				stockCode: 'B',
				stockName: 'Stock B',
				currentPrice: '500',
				priceChange: '0',
				changeRate: '0',
				cumulativeAmount: '5000', // 2위
				cumulativeVolume: '5',
			},
		];
		(getStockRanking as jest.Mock).mockResolvedValue(initialData);

		const { result } = renderHook(() => useStockRanking('VALUE', 10));

		await waitFor(() => {
			expect(result.current.rankingData).toHaveLength(2);
			// limit 10이지만 초기데이터가 2개
			expect(result.current.rankingData[0].stockCode).toBe('A');
		});

		// 웹소켓 이벤트: B의 거래대금이 급증하여 A를 추월 (20000 > 10000)
		const wsData = {
			stockCode: 'B',
			stockName: 'Stock B',
			currentPrice: '600',
			cumulativeAmount: '20000',
			cumulativeVolume: '20',
		};

		act(() => {
			if (socketCallback) {
				socketCallback(wsData);
			}
		});

		// 결과 검증: B가 1위가 되어야 함
		await waitFor(() => {
			expect(result.current.rankingData[0].stockCode).toBe('B');
			expect(result.current.rankingData[1].stockCode).toBe('A');
		});

		// 값 업데이트 확인
		expect(result.current.rankingData[0].cumulativeAmount).toBe(20000);
	});

	it('데이터 수신 시 limit 개수만큼만 데이터를 유지해야 한다', async () => {
		// limit을 2로 설정
		const { result } = renderHook(() => useStockRanking('VALUE', 2));

		// 3개의 데이터가 웹소켓으로 들어옴 (배열 형태)
		const wsDataList = [
			{ stockCode: 'A', cumulativeAmount: '3000' }, // 1등
			{ stockCode: 'B', cumulativeAmount: '2000' }, // 2등
			{ stockCode: 'C', cumulativeAmount: '1000' }, // 3등 (잘려야 함)
		];

		act(() => {
			if (socketCallback) {
				socketCallback(wsDataList);
			}
		});

		await waitFor(() => {
			expect(result.current.rankingData).toHaveLength(2);
			// 상위 2개만 남아야 함
			expect(result.current.rankingData.map((d) => d.stockCode)).toEqual([
				'A',
				'B',
			]);
		});
	});

	// 상태 변경 및 구독 관리 테스트
	it('웹소켓 연결 시 올바른 토픽을 구독하고 언마운트 시 구독을 해지해야 한다', () => {
		const { unmount } = renderHook(() => useStockRanking('VALUE', 10));

		expect(mockSubscribe).toHaveBeenCalledWith(
			'/topic/ranking',
			expect.any(Function),
		);

		unmount();

		expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
	});

	it('랭킹 타입이 변경되면 데이터를 초기화하고 API를 다시 호출해야 한다', async () => {
		// 초기 호출 (VALUE)
		(getStockRanking as jest.Mock).mockResolvedValue([]);
		const { rerender } = renderHook(
			({ type }: { type: RankingType }) => useStockRanking(type, 10),
			{
				initialProps: { type: 'VALUE' },
			},
		);

		// 타입 변경 (VOLUME)
		rerender({ type: 'VOLUME' });

		// API가 VOLUME으로 다시 호출되었는지 확인
		await waitFor(() => {
			expect(getStockRanking).toHaveBeenCalledWith('VOLUME', 10);
		});
	});

	// 예외 처리 (방어 코드) 테스트
	it('숫자가 아닌 데이터(빈 문자열, null 등)가 수신되면 0으로 처리하여 앱이 크래시되지 않아야 한다', async () => {
		const { result } = renderHook(() => useStockRanking('VALUE', 10));

		const malformedData = {
			stockCode: 'ERR',
			stockName: 'Error Stock',
			currentPrice: '', // 빈 문자열
			priceChange: null, // null
			changeRate: 'invalid', // 숫자가 아닌 문자열
			cumulativeAmount: undefined, // undefined
		};

		act(() => {
			if (socketCallback) {
				socketCallback(malformedData);
			}
		});

		await waitFor(() => {
			expect(result.current.rankingData).toHaveLength(1);
		});

		const item = result.current.rankingData[0];
		// Hook 내부의 || 0 로직 검증
		expect(item.currentPrice).toBe(0);
		expect(item.priceChange).toBe(0);
		expect(item.changeRate).toBe(0);
		expect(item.cumulativeAmount).toBe(0);

		// 에러 로그가 찍히지 않아야 함 (try-catch 내의 파싱 에러가 아님, 파싱은 성공하고 값만 0)
		expect(console.error).not.toHaveBeenCalledWith(
			'Failed to parse stock ranking data:',
			expect.any(Error),
		);
	});
});
