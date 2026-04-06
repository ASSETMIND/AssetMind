import { renderHook, act } from '@testing-library/react';
import { usePageVisibility } from '../../hooks/common/use-page-visibility';

describe('usePageVisibility Hook', () => {
	it('브라우저의 visibilitychange 이벤트에 따라 상태를 업데이트해야 한다', () => {
		const { result } = renderHook(() => usePageVisibility());

		// 초기 상태 확인 (기본값 visible)
		expect(result.current).toBe(true);

		// 탭이 숨겨진 상태 시뮬레이션 (document.hidden 조작)
		act(() => {
			Object.defineProperty(document, 'hidden', { value: true, configurable: true });
			document.dispatchEvent(new Event('visibilitychange'));
		});
		expect(result.current).toBe(false);

		// 탭이 다시 활성화된 상태 시뮬레이션
		act(() => {
			Object.defineProperty(document, 'hidden', { value: false, configurable: true });
			document.dispatchEvent(new Event('visibilitychange'));
		});
		expect(result.current).toBe(true);
	});
});
