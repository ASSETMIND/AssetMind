import { renderHook, act } from '@testing-library/react';
import { useStockItemLogic } from '../../hooks/stock/use-stock-item-logic';

describe('useStockItemLogic Hook', () => {
	beforeEach(() => {
		jest.useFakeTimers();
	});

	afterEach(() => {
		jest.useRealTimers();
	});

	it('양수 등락률일 때 "+" 부호와 빨간색 스타일을 반환해야 한다', () => {
		const { result } = renderHook(() => useStockItemLogic(1.23));
		expect(result.current.formattedChangeRate).toBe('+1.23%');
		expect(result.current.badgeClass).toContain('text-red-500');
	});

	it('음수 등락률일 때 파란색 스타일을 반환해야 한다', () => {
		const { result } = renderHook(() => useStockItemLogic(-4.56));
		expect(result.current.formattedChangeRate).toBe('-4.56%');
		expect(result.current.badgeClass).toContain('text-blue-500');
	});

	it('값이 변경되면 200ms 동안 배경색이 나타났다가 사라져야 한다', () => {
		const { result, rerender } = renderHook(
			({ rate }) => useStockItemLogic(rate),
			{ initialProps: { rate: 10 } },
		);

		// 초기 마운트 시 깜빡임
		expect(result.current.badgeClass).toContain('bg-red-500/50');

		// 200ms 후 투명해짐
		act(() => {
			jest.advanceTimersByTime(200);
		});
		expect(result.current.badgeClass).toContain('bg-transparent');

		// 값 변경 (하락)
		rerender({ rate: -10 });

		// 다시 깜빡임 (파란색)
		expect(result.current.badgeClass).toContain('bg-blue-500/50');

		// 200ms 후 투명해짐
		act(() => {
			jest.advanceTimersByTime(200);
		});
		expect(result.current.badgeClass).toContain('bg-transparent');
	});
});
