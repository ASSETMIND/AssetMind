import RatioBar from './ratio-bar';

export interface StockItemData {
	id: string;
	rank: number;
	name: string;
	price: string;
	changeRate: number;
	tradeVolume: string;
	buyRatio: number;
	sellRatio: number;
}

interface Props {
	data: StockItemData;
}

// 각 개별 종목 행 렌더링
export default function StockItem({ data }: Props) {
	const isPositive = data.changeRate > 0;
	const changeColor = isPositive ? 'text-red-500' : 'text-blue-500';
	const changeSign = isPositive ? '+' : '';

	return (
		<div className='grid grid-cols-[2.5fr_1fr_1fr_1fr_1.2fr] gap-4 items-center py-2 text-sm hover:bg-neutral-800 hover:rounded-md transition-colors '>
			{/* 하트 + 순위 + 로고 + 이름 */}
			<div className='flex items-center gap-3 pl-2'>
				<button className='text-gray-300 hover:text-red-400'>♥</button>
				<span className='w-5 text-center font-bold text-gray-500'>
					{data.rank}
				</span>
				<div className='w-8 h-8 rounded-full bg-blue-300 flex items-center justify-center text-[10px] font-bold'>
					로고
				</div>
				<span className='font-semibold'>{data.name}</span>
			</div>

			{/* 현재가 */}
			<div className='text-right font-medium'>{data.price}원</div>

			{/* 등락률 */}
			<div className={`text-right font-semibold ${changeColor}`}>
				{changeSign}
				{data.changeRate.toFixed(2)}%
			</div>

			{/* 거래대금 순 */}
			<div className='text-right font-medium text-gray-600'>
				{data.tradeVolume}
			</div>

			{/* 비율 바 */}
			<div className='flex justify-end pr-2'>
				<RatioBar buy={data.buyRatio} sell={data.sellRatio} />
			</div>
		</div>
	);
}
