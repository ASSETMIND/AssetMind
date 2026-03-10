import { renderHook, act } from '@testing-library/react';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import { useWebSocketStore } from '../../store/web-socket';
import { Client } from '@stomp/stompjs';
import type { StockRankingResponse } from '../../types/stock';

/**
 * [Mocking & Setup]
 * - STOMP 라이브러리 모킹: 실제 서버 연결 없이 인터페이스만 시뮬레이션
 * - 전역 상태 초기화: 테스트 간 상태 전이를 방지하기 위해 Zustand 상태 리셋
 */
jest.mock('@stomp/stompjs');
jest.mock('../../api/stock.ts', () => ({
	STOCK_WS_URL: 'ws://localhost:8080/stocks',
}));

describe('주식 실시간 랭킹 통합 테스트 (Integration)', () => {
	let mockClientInstance: any;
	let capturedConfig: any;

	beforeEach(() => {
		jest.clearAllMocks();
		useWebSocketStore.setState({
			isConnected: false,
			lastMessage: null,
			error: null,
		});

		mockClientInstance = {
			activate: jest.fn(),
			deactivate: jest.fn(),
			publish: jest.fn(),
			subscribe: jest.fn(),
			connected: false,
			active: false,
		};

		(Client as unknown as jest.Mock).mockImplementation((config) => {
			capturedConfig = config;
			return mockClientInstance;
		});
	});

	it('웹소켓 연결부터 서버 데이터 수신, UI 형식에 맞춘 최종 가공까지의 흐름이 정상 동작해야 한다', () => {
		/**
		 * @Given
		 * - useStockRankLogic 훅을 렌더링하여 STOMP 클라이언트 생성 유도
		 * - 서버에서 내려줄 Mock 데이터(삼성전자, 현대차) 준비
		 */
		const { result } = renderHook(() => useStockRankLogic('VALUE', 10));
		const mockServerData: StockRankingResponse[] = [
			{
				stockCode: '005930',
				stockName: '삼성전자',
				currentPrice: '217500',
				priceChange: '-500',
				changeRate: '-0.22',
				cumulativeAmount: '73200000000',
				cumulativeVolume: '15200000',
			},
			{
				stockCode: '005380',
				stockName: '현대차',
				currentPrice: '673000',
				priceChange: '64000',
				changeRate: '10.5',
				cumulativeAmount: '39300000000',
				cumulativeVolume: '420000',
			},
		];

		/**
		 * @When
		 * 1. 웹소켓 연결 성공 이벤트 트리거 (onConnect)
		 * 2. 서버로부터 메시지 수신 시뮬레이션 (stompSubscribeCallback 실행)
		 */
		act(() => {
			mockClientInstance.connected = true;
			capturedConfig.onConnect(); // 연결 트리거
		});

		const stompSubscribeCallback =
			mockClientInstance.subscribe.mock.calls[0][1];
		act(() => {
			stompSubscribeCallback({
				body: JSON.stringify(mockServerData),
			});
		});

		/**
		 * @Then
		 * - 상태 저장소의 연결태가 true인지 확인
		 * - 가공된 데이터가 UI 요구사항(콤마, '억원', 비율 계산)을 충족하는지 검증
		 */
		const { stockList, isConnected } = result.current;

		expect(isConnected).toBe(true);
		expect(stockList[0]).toEqual(
			expect.objectContaining({
				stockName: '삼성전자',
				price: '217,500', // 콤마 포맷팅 검증
				tradeVolume: '732억원', // 단위 변환 검증
				buyRatio: 49, // 비즈니스 로직(비율 계산) 검증
			}),
		);
		expect(stockList[1].tradeVolume).toBe('393억원');
	});

	it('컴포넌트 언마운트 시 구독 해지 및 웹소켓 비활성화가 순차적으로 이루어져야 한다', () => {
		/**
		 * @Given
		 * - 구독 해지(unsubscribe) 기능을 가진 객체를 반환하도록 모킹
		 * - 훅을 렌더링하고 연결 성공 상태로 만듦
		 */
		const mockUnsubscribe = jest.fn();
		mockClientInstance.subscribe.mockReturnValue({
			unsubscribe: mockUnsubscribe,
		});
		const { unmount } = renderHook(() => useStockRankLogic('VOLUME', 5));

		act(() => {
			mockClientInstance.connected = true;
			capturedConfig.onConnect();
		});

		/**
		 * @When
		 * - 컴포넌트(훅)를 언마운트(화면 이탈 시뮬레이션)
		 */
		unmount();

		/**
		 * @Then
		 * - 리소스 누수 방지를 위해 unsubscribe와 deactivate가 호출되었는지 확인
		 */
		expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
		expect(mockClientInstance.deactivate).toHaveBeenCalledTimes(1);
	});
});
