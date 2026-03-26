import { useState } from 'react';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import { useLatestSurgeAlert } from '../../hooks/stock/use-stock-alerts';
import type { RankingType } from '../../hooks/stock/use-stock-value-ranking';
import StockFilterGroup from './stock-filter-group';
import StockItem from './stock-item';
import TableHeader from './table-header';
import Toast from '../common/toast';

// 랭킹 페이지의 전체 레이아웃 담당
export default function RankLayout() {
	const [rankingType, setRankingType] = useState<RankingType>('VALUE');
	const { stockList } = useStockRankLogic(rankingType);

	// 실시간 급등 알림 데이터 가져오기
	const { latestAlert, clearAlert } = useLatestSurgeAlert();

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

			{/* 급등 알림 토스트 시각화 */}
			{latestAlert && (
				<Toast
					key={JSON.stringify(latestAlert)}
					duration={2500}
					onClose={clearAlert}
				>
					<div className='flex flex-col gap-1'>
						<span className='text-xs text-gray-400'>실시간 급등락 포착</span>
						<div className='text-sm flex items-center gap-2'>
							<strong className='text-white text-base'>
								{latestAlert.stockName}
							</strong>
							<span
								className={`font-semibold ${latestAlert.changeRate.startsWith('-') ? 'text-blue-500' : 'text-red-500'}`}
							>
								{latestAlert.changeRate.includes('%')
									? latestAlert.changeRate
									: `${latestAlert.changeRate}%`}
							</span>
						</div>
					</div>
				</Toast>
			)}
		</div>
	);
}
