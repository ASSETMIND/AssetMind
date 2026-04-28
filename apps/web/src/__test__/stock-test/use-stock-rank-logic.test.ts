import { renderHook } from '@testing-library/react';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import { useStockRanking } from '../../hooks/stock/use-stock-value-ranking';
import type { StockRankingDto } from '../../types/stock';

// useStockRanking 훅 모킹
jest.mock('../../hooks/stock/use-stock-value-ranking');

const mockUseStockRanking = useStockRanking as jest.Mock;

describe('useStockRankLogic Hook', () => {
	beforeEach(() => {
		// 각 테스트 전에 모킹 함수 초기화
		mockUseStockRanking.mockClear();
	});

	it('useStockRanking에서 받은 데이터를 UI에 맞게 가공해야 한다', () => {
		const mockRankingData: StockRankingDto[] = [
			{
				stockCode: '005930',
				stockName: '삼성전자',
				currentPrice: 82500,
				changeRate: 1.25,
				priceChange: 1000,
				cumulativeAmount: 587600000000, // 5,876억원
				cumulativeVolume: 7122424,
			},
			{
				stockCode: '000660',
				stockName: 'SK하이닉스',
				currentPrice: 131000,
				changeRate: -2.5,
				priceChange: -3500,
				cumulativeAmount: 432100000000, // 4,321억원
				cumulativeVolume: 3300000,
			},
		];

		// useStockRanking이 mock 데이터를 반환하도록 설정
		mockUseStockRanking.mockReturnValue({
			rankingData: mockRankingData,
			isConnected: true,
			isLoading: false,
		});

		const { result } = renderHook(() => useStockRankLogic('VALUE', 2));

		// 1. useStockRanking이 올바른 인자로 호출되었는지 확인
		expect(mockUseStockRanking).toHaveBeenCalledWith('VALUE', 2);

		// 2. 반환된 상태값 확인
		const { stockList, isConnected, isLoading, sortType } = result.current;

		expect(isConnected).toBe(true);
		expect(isLoading).toBe(false);
		expect(sortType).toBe('value');
		expect(stockList).toHaveLength(2);

		// 첫 번째 아이템 (삼성전자) 검증 - 필드명 변경 반영 (stockCode, stockName)
		expect(stockList[0]).toEqual({
			stockCode: '005930',
			rank: 1,
			stockName: '삼성전자',
			price: '82,500',
			changeRate: 1.25,
			tradeVolume: '5,876억원',
			buyRatio: 52, // 50 + 1.25 * 2 = 52.5 -> floor(52)
			sellRatio: 48, // 100 - 52
		});

		// 두 번째 아이템 (SK하이닉스) 검증
		expect(stockList[1]).toEqual({
			stockCode: '000660',
			rank: 2,
			stockName: 'SK하이닉스',
			price: '131,000',
			changeRate: -2.5,
			tradeVolume: '4,321억원',
			buyRatio: 45, // 50 - 2.5 * 2 = 45
			sellRatio: 55, // 100 - 45
		});
	});

	it('거래량(VOLUME) 타입일 때 tradeVolume 포맷이 변경되어야 한다', () => {
		const mockRankingData: StockRankingDto[] = [
			{
				stockCode: '005930',
				stockName: '삼성전자',
				currentPrice: 82500,
				changeRate: 0,
				priceChange: 0,
				cumulativeAmount: 100000000,
				cumulativeVolume: 1234567,
			},
		];

		mockUseStockRanking.mockReturnValue({
			rankingData: mockRankingData,
			isConnected: true,
			isLoading: false,
		});

		const { result } = renderHook(() => useStockRankLogic('VOLUME'));

		expect(result.current.stockList[0].tradeVolume).toBe('1,234,567주');
		expect(result.current.sortType).toBe('volume');
	});

	it('rankingData가 없거나 비어있을 때 빈 배열을 반환해야 한다', () => {
		// rankingData가 null일 때
		mockUseStockRanking.mockReturnValue({
			rankingData: null,
			isConnected: true,
			isLoading: false,
		});
		const { result: resultNull } = renderHook(() => useStockRankLogic('VALUE'));
		expect(resultNull.current.stockList).toEqual([]);

		// rankingData가 빈 배열일 때
		mockUseStockRanking.mockReturnValue({
			rankingData: [],
			isConnected: true,
			isLoading: false,
		});
		const { result: resultEmpty } = renderHook(() =>
			useStockRankLogic('VALUE'),
		);
		expect(resultEmpty.current.stockList).toEqual([]);
	});

	it('buyRatio가 10 미만 또는 90 초과가 되지 않도록 제한해야 한다', () => {
		const mockRankingData: StockRankingDto[] = [
			{
				stockCode: 'UP',
				stockName: '초급등주',
				currentPrice: 10000,
				changeRate: 30, // 50 + 30 * 2 = 110 -> 90으로 제한되어야 함
				priceChange: 3000,
				cumulativeAmount: 100000000,
				cumulativeVolume: 10000,
			},
			{
				stockCode: 'DOWN',
				stockName: '초급락주',
				currentPrice: 10000,
				changeRate: -25, // 50 - 25 * 2 = 0 -> 10으로 제한되어야 함
				priceChange: -2500,
				cumulativeAmount: 100000000,
				cumulativeVolume: 10000,
			},
		];

		mockUseStockRanking.mockReturnValue({
			rankingData: mockRankingData,
			isConnected: true,
			isLoading: false,
		});

		const { result } = renderHook(() => useStockRankLogic('VALUE'));
		const { stockList } = result.current;

		expect(stockList[0].buyRatio).toBe(90);
		expect(stockList[0].sellRatio).toBe(10);

		expect(stockList[1].buyRatio).toBe(10);
		expect(stockList[1].sellRatio).toBe(90);
	});
});
