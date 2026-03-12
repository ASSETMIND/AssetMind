import { useState } from 'react';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import type { RankingType } from '../../hooks/stock/use-stock-value-ranking';
import StockFilterGroup from './stock-filter-group';
import StockItem from './stock-item';
import TableHeader from './table-header';

// 랭킹 페이지의 전체 레이아웃 담당
export default function RankLayout() {
	const [rankingType, setRankingType] = useState<RankingType>('VALUE');
	const { stockList } = useStockRankLogic(rankingType);

	return (
		<div className='w-full max-w-6xl mx-auto px-4'>
			{/* 필터 영역 */}
			<StockFilterGroup
				activeType={rankingType}
				onTypeChange={setRankingType}
			/>

			{/* 랭킹 리스트 영역 */}
			<div className='rounded-lg'>
				<TableHeader sortType={rankingType} />
				<div className='flex flex-col'>
					{stockList.map((item) => (
						<StockItem key={item.stockCode} data={item} />
					))}
				</div>
			</div>
		</div>
	);
}
