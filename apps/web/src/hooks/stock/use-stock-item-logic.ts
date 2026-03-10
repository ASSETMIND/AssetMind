import { useState, useEffect } from 'react';

interface Props {
	stockName: string;
	changeRate: number;
}

export function useStockItemLogic({ stockName, changeRate }: Props) {
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

	return { name: stockName, formattedChangeRate, badgeClass };
}
