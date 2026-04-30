interface Props {
	stockName: string;
	changeRate: number;
	currentPrice: number;
	cumulativeAmount: number;
	cumulativeVolume: number;
	rankingType?: 'VALUE' | 'VOLUME';
}

/**
 * 주식 아이템의 표시용 데이터를 가공하는 로직 (성능 최적화)
 */
export function useStockItemLogic({
	stockName,
	changeRate,
	currentPrice,
	cumulativeAmount,
	cumulativeVolume,
	rankingType = 'VALUE',
}: Props) {
	const isPositive = changeRate > 0;
	const isNegative = changeRate < 0;

	// 등락률 포맷팅
	const formattedChangeRate = isPositive
		? `+${changeRate.toFixed(2)}%`
		: `${changeRate.toFixed(2)}%`;

	// 가격 포맷팅 (천 단위 콤마)
	const formattedPrice = currentPrice.toLocaleString();

	// 거래량/거래대금 포맷팅 (타입에 따라 분기)
	const tradeVolumeStr =
		rankingType === 'VOLUME'
			? `${cumulativeVolume.toLocaleString()}주`
			: `${Math.floor(cumulativeAmount / 100000000).toLocaleString()}억원`;

	// 매수/매도 비율 계산 (등락률 가중치 부여 시뮬레이션)
	const buyRatio = Math.max(10, Math.min(90, Math.floor(50 + changeRate * 2)));
	const sellRatio = 100 - buyRatio;

	// 스타일 클래스 결정
	const textColorClass = isPositive
		? 'text-red-500'
		: isNegative
			? 'text-blue-500'
			: 'text-gray-400';

	return {
		name: stockName,
		formattedPrice,
		formattedChangeRate,
		tradeVolumeStr,
		buyRatio,
		sellRatio,
		textColorClass,
	};
}
