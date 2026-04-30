import { memo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStockItemLogic } from '../../hooks/stock/use-stock-item-logic';
import { useStockStore } from '../../store/use-stock-store';
import RatioBar from './ratio-bar';

interface Props {
	stockCode: string;
	rank: number;
	rankingType: 'VALUE' | 'VOLUME';
}

/**
 * 주식 목록의 개별 행(Row) 컴포넌트 (지점 업데이트 방식)
 * - 부모로부터 stockCode만 받고, 상세 데이터는 스토어에서 직접 구독합니다.
 * - 특정 종목의 데이터가 변해도 다른 종목은 리렌더링되지 않습니다.
 */
function StockItem({ stockCode, rank, rankingType }: Props) {
	// Selector 패턴: 이 종목의 데이터가 변경될 때만 리렌더링 발생
	const data = useStockStore((state) => state.stockMap.get(stockCode));
	const navigate = useNavigate();

	const handleItemClick = useCallback(() => {
		navigate(`/stock/${stockCode}`);
	}, [navigate, stockCode]);

	const handleFavoriteClick = useCallback((e: React.MouseEvent) => {
		e.stopPropagation();
	}, []);

	// 데이터가 아직 로드되지 않은 경우 (Skeleton 처리)
	if (!data)
		return (
			<div className='h-13 animate-pulse bg-neutral-900/50 rounded-md my-1' />
		);

	// UI 렌더링에 필요한 포맷팅 가공 (Dto의 원본 필드 사용)
	const {
		name,
		formattedPrice,
		formattedChangeRate,
		tradeVolumeStr,
		buyRatio,
		sellRatio,
		textColorClass,
	} = useStockItemLogic({
		stockName: data.stockName,
		changeRate: data.changeRate,
		currentPrice: data.currentPrice,
		cumulativeAmount: data.cumulativeAmount,
		cumulativeVolume: data.cumulativeVolume,
		rankingType,
	});

	return (
		<div
			onClick={handleItemClick}
			className='grid grid-cols-[2.5fr_1fr_1fr_1fr_1.2fr] gap-4 items-center py-2 text-sm hover:bg-neutral-800 hover:rounded-md transition-colors cursor-pointer group'
		>
			{/* 하트 + 순위 + 로고 + 이름 */}
			<div className='flex items-center gap-3 pl-2'>
				<button
					type='button'
					className='text-gray-300 hover:text-red-500 transition-colors'
					aria-label={`${name} 관심종목 추가`}
					onClick={handleFavoriteClick}
				>
					♥
				</button>
				<span className='w-5 text-center font-bold text-gray-500'>{rank}</span>
				<div
					className='w-8 h-8 rounded-full bg-neutral-700 flex items-center justify-center text-[10px] font-bold text-gray-400'
					aria-hidden='true'
				>
					로고
				</div>
				<span className='font-semibold group-hover:text-white transition-colors'>
					{name}
				</span>
			</div>

			{/* 현재가 */}
			<div className='text-right font-medium'>{formattedPrice}원</div>

			{/* 등락률 */}
			<div className='text-right'>
				<span
					className={`inline-block font-semibold px-2 py-1 rounded transition-colors ${textColorClass}`}
				>
					{formattedChangeRate}
				</span>
			</div>

			{/* 거래대금 순 / 거래량 순 (가공된 문자열 표시) */}
			<div className='text-right font-medium text-gray-500'>
				{tradeVolumeStr}
			</div>

			{/* 비율 바 (매수/매도 비율 시뮬레이션 적용) */}
			<div className='flex justify-end pr-2'>
				<RatioBar buy={buyRatio} sell={sellRatio} />
			</div>
		</div>
	);
}

export default memo(StockItem);
