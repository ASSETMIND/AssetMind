import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import StockFilterGroup from './stock-filter-group';
import StockItem from './stock-item';
import TableHeader from './table-header';

// 랭킹 페이지의 전체 레이아웃 담당
export default function RankLayout() {
	const { stockList } = useStockRankLogic();

	return (
		<div className='w-full max-w-6xl mx-auto px-4'>
			{/* 필터 영역 */}
			<StockFilterGroup />

			{/* 랭킹 리스트 영역 */}
			<div className='rounded-lg'>
				<TableHeader />
				<div className='flex flex-col'>
					{stockList.map((item) => (
						<StockItem key={item.id} data={item} />
					))}
				</div>
			</div>
		</div>
	);
}
