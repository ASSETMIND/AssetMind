interface Props {
	stockName: string;
	changeRate: number;
}

/**
 * 주식 아이템의 표시용 데이터를 가공하는 로직
 * 상태(State)를 제거하여 불필요한 리렌더링을 방지
 */
export function useStockItemLogic({ stockName, changeRate }: Props) {
	const isPositive = changeRate > 0;
	const isNegative = changeRate < 0;

	const formattedChangeRate = isPositive
		? `+${changeRate.toFixed(2)}%`
		: `${changeRate.toFixed(2)}%`;

	const textColorClass = isPositive
		? 'text-red-500'
		: isNegative
			? 'text-blue-500'
			: 'text-gray-400';

	const flashBgClass = isPositive
		? 'bg-red-500/20'
		: isNegative
			? 'bg-blue-500/20'
			: 'bg-transparent';

	return {
		name: stockName,
		formattedChangeRate,
		textColorClass,
		flashBgClass,
		isPositive,
		isNegative,
	};
}
