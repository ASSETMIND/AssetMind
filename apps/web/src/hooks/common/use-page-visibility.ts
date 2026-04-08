import { useState, useEffect } from 'react';

/**
 * 브라우저 탭의 활성화/비활성화 상태를 감지하는 커스텀 훅
 */
export const usePageVisibility = () => {
	const [isVisible, setIsVisible] = useState(!document.hidden);

	useEffect(() => {
		const handleVisibilityChange = () => {
			setIsVisible(!document.hidden);
		};

		document.addEventListener('visibilitychange', handleVisibilityChange);

		return () => {
			document.removeEventListener('visibilitychange', handleVisibilityChange);
		};
	}, []);

	return isVisible;
};
