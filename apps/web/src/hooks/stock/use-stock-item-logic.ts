import { useState, useEffect } from 'react';

export function useStockItemLogic(changeRate: number) {
	const [isBlinking, setIsBlinking] = useState(false);

	useEffect(() => {
		setIsBlinking(true);
		const timer = setTimeout(() => setIsBlinking(false), 200);
		return () => clearTimeout(timer);
	}, [changeRate]);

	const isPositive = changeRate > 0;
	const formattedChangeRate = isPositive
		? `+${changeRate.toFixed(2)}%`
		: `${changeRate.toFixed(2)}%`;

	const badgeClass = isPositive
		? `text-red-500 ${isBlinking ? 'bg-red-500/50' : 'bg-transparent'}`
		: `text-blue-500 ${isBlinking ? 'bg-blue-500/50' : 'bg-transparent'}`;

	return { formattedChangeRate, badgeClass };
}
