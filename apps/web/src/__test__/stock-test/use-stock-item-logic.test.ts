import { renderHook } from '@testing-library/react';
import { useStockItemLogic } from '../../hooks/stock/use-stock-item-logic';

describe('useStockItemLogic Hook', () => {
	it('양수 등락률일 때 "+" 부호와 빨간색 스타일 클래스를 반환해야 한다', () => {
		const { result } = renderHook(() =>
			useStockItemLogic({ stockName: '삼성전자', changeRate: 1.23 }),
		);

		expect(result.current.name).toBe('삼성전자');
		expect(result.current.formattedChangeRate).toBe('+1.23%');
		expect(result.current.textColorClass).toBe('text-red-500');
		expect(result.current.flashBgClass).toBe('bg-red-500/20');
		expect(result.current.isPositive).toBe(true);
	});

	it('음수 등락률일 때 파란색 스타일 클래스를 반환해야 한다', () => {
		const { result } = renderHook(() =>
			useStockItemLogic({ stockName: 'SK하이닉스', changeRate: -4.56 }),
		);

		expect(result.current.name).toBe('SK하이닉스');
		expect(result.current.formattedChangeRate).toBe('-4.56%');
		expect(result.current.textColorClass).toBe('text-blue-500');
		expect(result.current.flashBgClass).toBe('bg-blue-500/20');
		expect(result.current.isNegative).toBe(true);
	});

	it('등락률이 0일 때 무채색 스타일을 반환해야 한다', () => {
		const { result } = renderHook(() =>
			useStockItemLogic({ stockName: '보합주', changeRate: 0 }),
		);

		expect(result.current.formattedChangeRate).toBe('0.00%');
		expect(result.current.textColorClass).toBe('text-gray-400');
		expect(result.current.flashBgClass).toBe('bg-transparent');
	});
});
