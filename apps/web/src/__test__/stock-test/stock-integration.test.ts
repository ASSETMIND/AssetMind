import { renderHook, act, waitFor } from '@testing-library/react';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import { useWebSocket } from '../../hooks/web-socket/use-web-socket';

// WebSocket 훅 모킹: 실제 네트워크 연결 없이 동작 시뮬레이션
jest.mock('../../hooks/web-socket/use-web-socket');
jest.mock('../../api/stock', () => ({
	__esModule: true,
	STOCK_WS_URL: 'ws://localhost:8080/stocks',
	getStockRanking: jest.fn().mockResolvedValue([]), // 초기 API 호출 모킹 (TypeError 방지)
}));

describe('주식 랭킹 시스템 통합 테스트 (Hooks & WebSocket)', () => {
	let mockSubscribe: jest.Mock;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let messageCallback: (data: any) => void;

	beforeEach(() => {
		jest.clearAllMocks();
		jest.spyOn(console, 'log').mockImplementation(() => {}); // 콘솔 로그 숨김 처리

		// subscribe 함수가 호출될 때, 내부 콜백 함수를 캡처하여 테스트에서 호출할 수 있도록 설정
		mockSubscribe = jest.fn((_topic, callback) => {
			messageCallback = callback;
			return { unsubscribe: jest.fn() };
		});

		// useWebSocket 훅이 항상 '연결됨(isConnected: true)' 상태를 반환하도록 모킹
		(useWebSocket as jest.Mock).mockReturnValue({
			isConnected: true,
			subscribe: mockSubscribe,
		});
	});

	it('웹소켓을 통해 데이터를 수신하면 랭킹 리스트가 업데이트되고 거래대금순(VALUE)으로 정렬되어야 한다', async () => {
		const { result } = renderHook(() => useStockRankLogic('VALUE', 10));

		// 초기 API 데이터 패치 대기 (act 경고 및 빈 배열 덮어쓰기 방지)
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 0));
		});

		// 초기 상태 확인
		expect(result.current.stockList).toEqual([]);
		expect(result.current.isConnected).toBe(true);

		// 웹소켓 메시지 시뮬레이션 데이터 (모든 필드는 String 타입 - API 명세 준수)
		const samsung = {
			stockCode: '005930',
			stockName: '삼성전자',
			currentPrice: '70000',
			priceChange: '1000',
			changeRate: '1.5',
			cumulativeAmount: '200000000000', // 2,000억
			cumulativeVolume: '3000000',
		};

		const hynix = {
			stockCode: '000660',
			stockName: 'SK하이닉스',
			currentPrice: '120000',
			priceChange: '-500',
			changeRate: '-0.4',
			cumulativeAmount: '150000000000', // 1,500억
			cumulativeVolume: '1000000',
		};

		// act를 사용하여 비동기 상태 업데이트 유발
		await act(async () => {
			// 실제 환경과 동일하게 정렬된 배열로 한 번에 전달
			if (messageCallback) messageCallback([samsung, hynix]);
		});

		// 검증: 삼성전자가 거래대금이 더 많으므로 1위, 하이닉스가 2위여야 함
		await waitFor(() => {
			expect(result.current.stockList).toHaveLength(2);
			expect(result.current.stockList[0].stockName).toBe('삼성전자');
			expect(result.current.stockList[1].stockName).toBe('SK하이닉스');
		});

		// 데이터 포맷팅 검증 (거래대금은 억 단위 변환, 가격 콤마 처리)
		expect(result.current.stockList[0].tradeVolume).toContain('2,000억원');
		expect(result.current.stockList[0].price).toBe('70,000');
	});

	it('랭킹 타입이 VOLUME(거래량)일 때는 거래량 순으로 정렬되고 단위가 "주"로 표시되어야 한다', async () => {
		const { result } = renderHook(() => useStockRankLogic('VOLUME', 10));

		// 초기 API 데이터 패치 완료 대기
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 0));
		});

		// 거래량: A(100주) < B(200주)
		const stockA = {
			stockCode: 'A',
			stockName: 'Stock A',
			currentPrice: '1000',
			priceChange: '0',
			changeRate: '0',
			cumulativeAmount: '10000',
			cumulativeVolume: '100',
		};

		const stockB = {
			stockCode: 'B',
			stockName: 'Stock B',
			currentPrice: '2000',
			priceChange: '0',
			changeRate: '0',
			cumulativeAmount: '20000',
			cumulativeVolume: '200',
		};

		await act(async () => {
			// 배열 형태로 한 번에 들어오는 경우도 처리 가능한지 확인
			if (messageCallback) messageCallback([stockB, stockA]);
		});

		await waitFor(() => {
			expect(result.current.stockList).toHaveLength(2);
			// 거래량이 많은 Stock B가 1위
			expect(result.current.stockList[0].stockName).toBe('Stock B');
			expect(result.current.stockList[1].stockName).toBe('Stock A');
			// 단위 확인
			expect(result.current.stockList[0].tradeVolume).toBe('200주');
		});
	});

	it('서버로부터 새로운 랭킹 배열이 수신되면 기존 데이터가 최신 데이터로 대체(업데이트)되어야 한다', async () => {
		const { result } = renderHook(() => useStockRankLogic('VALUE', 10));

		// 초기 API 데이터 패치 완료 대기
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 0));
		});

		// 1. 초기 데이터 (삼성전자 7만원)
		const initialData = {
			stockCode: '005930',
			stockName: '삼성전자',
			currentPrice: '70000',
			priceChange: '0',
			changeRate: '0',
			cumulativeAmount: '100000000000',
			cumulativeVolume: '1000000',
		};

		await act(async () => {
			if (messageCallback) messageCallback([initialData]);
		});

		expect(result.current.stockList[0].price).toBe('70,000');

		// 2. 업데이트 데이터 (삼성전자 7만5천원, 거래대금 증가)
		const updatedData = {
			...initialData,
			currentPrice: '75000',
			cumulativeAmount: '150000000000', // 거래대금 증가
		};
		const newData = {
			stockCode: '000660',
			stockName: 'SK하이닉스',
			currentPrice: '120000',
			priceChange: '0',
			changeRate: '0',
			cumulativeAmount: '100000000000',
			cumulativeVolume: '1000000',
		};

		await act(async () => {
			if (messageCallback) messageCallback([updatedData, newData]);
		});

		// 리스트가 새로운 배열로 대체되었는지 확인
		await waitFor(() => {
			expect(result.current.stockList).toHaveLength(2);
			expect(result.current.stockList[0].price).toBe('75,000');
			expect(result.current.stockList[0].stockName).toBe('삼성전자');
			expect(result.current.stockList[1].stockName).toBe('SK하이닉스');
		});
	});

	it('랭킹 타입(VALUE <-> VOLUME)이 변경되면 기존 데이터 목록이 초기화되어야 한다', async () => {
		// 초기 렌더링: VALUE 타입
		const { result, rerender } = renderHook(
			({ type }) => useStockRankLogic(type, 10),
			{
				initialProps: { type: 'VALUE' as const },
			},
		);

		// 초기 API 데이터 패치 완료 대기
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 0));
		});

		const mockData = {
			stockCode: '005930',
			stockName: '삼성전자',
			currentPrice: '70000',
			priceChange: '0',
			changeRate: '0',
			cumulativeAmount: '100000000000',
			cumulativeVolume: '1000000',
		};

		// 데이터 주입
		await act(async () => {
			if (messageCallback) messageCallback([mockData]);
		});

		expect(result.current.stockList).toHaveLength(1);

		// 타입 변경: VALUE -> VOLUME
		await act(async () => {
			// @ts-ignore - 테스트 편의상 타입 캐스팅 생략
			rerender({ type: 'VOLUME' });
			await new Promise((resolve) => setTimeout(resolve, 0)); // 재호출된 API 대기
		});

		// 데이터가 초기화되었는지 비동기 대기
		await waitFor(() => {
			expect(result.current.stockList).toEqual([]);
		});
	});

	it('고빈도 소켓 메시지가 수신될 때 시스템이 뻗지 않고 마지막 상태를 잘 렌더링해야 한다 (Stress Test)', async () => {
		const LIMIT = 20;
		const { result } = renderHook(() => useStockRankLogic('VALUE', LIMIT));

		// 초기 API 데이터 패치 완료 대기
		await act(async () => {
			await new Promise((resolve) => setTimeout(resolve, 0));
		});

		const BATCH_SIZE = LIMIT;
		const ITERATIONS = 100; // 100번의 메시지 수신 시뮬레이션

		// 서버가 항상 LIMIT 개수만큼의 랭킹을 통째로 갱신해서 보내준다고 가정
		await act(async () => {
			for (let i = 0; i < ITERATIONS; i++) {
				const batch = Array.from({ length: BATCH_SIZE }, (_, j) => ({
					stockCode: `CODE_${j}`,
					stockName: `Stock ${j}`,
					currentPrice: (1000 + i).toString(), // 가격이 매번 오름
					priceChange: '0',
					changeRate: '0',
					cumulativeAmount: (100000000 * j).toString(),
					cumulativeVolume: '1000',
				}));
				if (messageCallback) messageCallback(batch);
			}
		});

		await waitFor(() => {
			// 1. 리스트 크기는 제한(LIMIT)과 정확히 일치해야 한다
			expect(result.current.stockList.length).toBe(LIMIT);

			// 2. 순위(rank)가 1부터 순차적으로 부여되었는지 확인
			result.current.stockList.forEach((stock, index) => {
				expect(stock.rank).toBe(index + 1);
			});

			// 3. 마지막으로 보낸 99번째 값(1000 + 99 = 1099)이 정상적으로 반영되었는지 확인
			expect(result.current.stockList[0].price).toBe('1,099');
		});
	});
});
