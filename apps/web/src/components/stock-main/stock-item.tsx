import { memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStockItemLogic } from '../../hooks/stock/use-stock-item-logic';
import RatioBar from './ratio-bar';

// 개별 주식 아이템에 필요한 데이터 인터페이스

export interface StockItemData {
	stockCode: string;
	rank: number;
	stockName: string;
	price: string;
	changeRate: number;
	tradeVolume: string;
	buyRatio: number;
	sellRatio: number;
}

interface Props {
	data: StockItemData;
}

/**
 * 주식 목록의 개별 행(Row)을 렌더링하는 컴포넌트
 * @param data 주식 종목 데이터 객체
 */
function StockItem({ data }: Props) {
	const {
		rank,
		stockCode,
		stockName,
		price,
		changeRate,
		tradeVolume,
		buyRatio,
		sellRatio,
	} = data;

	// UI 렌더링에 필요한 포맷팅 데이터(문자열, 색상 클래스 등) 가공 로직
	const { name, formattedChangeRate, badgeClass } = useStockItemLogic({
		stockName,
		changeRate,
	});

	const navigate = useNavigate();

	const handleItemClick = () => {
		navigate(`/stock/${stockCode}`);
	};

	return (
		<div
			onClick={handleItemClick}
			className='grid grid-cols-[2.5fr_1fr_1fr_1fr_1.2fr] gap-4 items-center py-2 text-sm hover:bg-neutral-800 hover:rounded-md transition-colors cursor-pointer'
		>
			{/* 하트 + 순위 + 로고 + 이름 */}
			<div className='flex items-center gap-3 pl-2'>
				<button
					type='button'
					className='text-gray-300 hover:text-red-500 transition-colors'
					aria-label={`${name} 관심종목 추가`}
					onClick={(e) => e.stopPropagation()}
				>
					♥
				</button>
				<span className='w-5 text-center font-bold text-gray-500'>{rank}</span>
				<div
					className='w-8 h-8 rounded-full bg-blue-300 flex items-center justify-center text-[10px] font-bold'
					aria-hidden='true'
				>
					로고
				</div>
				<span className='font-semibold'>{name}</span>
			</div>

			{/* 현재가 */}
			<div className='text-right font-medium'>{price}원</div>

			{/* 등락률 */}
			<div className='text-right'>
				<span
					className={`font-semibold px-2 py-1 rounded transition-colors duration-300 ${badgeClass}`}
				>
					{formattedChangeRate}
				</span>
			</div>

			{/* 거래대금 순 / 거래량 순 */}
			<div className='text-right font-medium text-gray-600'>{tradeVolume}</div>

			{/* 비율 바 */}
			<div className='flex justify-end pr-2'>
				<RatioBar buy={buyRatio} sell={sellRatio} />
			</div>
		</div>
	);
}

/**
 * React.memo를 위한 커스텀 비교 함수
 * 참조 주소가 아닌 실제 렌더링에 영향을 주는 데이터 값들만 비교하여 불필요한 리렌더링을 차단합니다.
 */
const areEqual = (prevProps: Props, nextProps: Props) => {
	return (
		prevProps.data.stockCode === nextProps.data.stockCode &&
		prevProps.data.price === nextProps.data.price &&
		prevProps.data.changeRate === nextProps.data.changeRate &&
		prevProps.data.tradeVolume === nextProps.data.tradeVolume &&
		prevProps.data.buyRatio === nextProps.data.buyRatio &&
		prevProps.data.sellRatio === nextProps.data.sellRatio &&
		prevProps.data.rank === nextProps.data.rank &&
		prevProps.data.stockName === nextProps.data.stockName
	);
};

export default memo(StockItem, areEqual);
