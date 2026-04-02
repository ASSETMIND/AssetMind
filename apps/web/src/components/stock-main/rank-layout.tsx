import { useState } from 'react';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import { useLatestSurgeAlert } from '../../hooks/stock/use-stock-alerts';
import type { RankingType } from '../../hooks/stock/use-stock-value-ranking';
import StockFilterGroup from './stock-filter-group';
import StockItem from './stock-item';
import TableHeader from './table-header';
import Toast from '../common/toast';

/**
 * 랭킹 페이지의 전체 레이아웃
 * - 최적화: stockCodes 리스트만 가지고 루프를 돌며, 개별 아이템은 직접 스토어에서 데이터를 가져옴
 */
export default function RankLayout() {
	const [rankingType, setRankingType] = useState<RankingType>('VALUE');
	const { stockCodes, isLoading } = useStockRankLogic(rankingType);

	// 실시간 급등 알림 데이터 가져오기
	const { latestAlert, clearAlert } = useLatestSurgeAlert();

	return (
		<div className='w-full max-w-6xl mx-auto px-4 overflow-hidden'>
			{/* 필터 영역 */}
			<StockFilterGroup
				activeType={rankingType}
				onTypeChange={setRankingType}
			/>

			{/* 랭킹 리스트 영역 */}
			<div className='rounded-lg min-h-100'>
				<TableHeader sortType={rankingType} />
				<div className='flex flex-col'>
					{/* stockCodes가 바뀔 때만(즉, 순위 정렬이 바뀔 때만) 리스트가 재정렬됨 */}
					{stockCodes.map((code, index) => (
						<StockItem
							key={code}
							stockCode={code}
							rank={index + 1}
							rankingType={rankingType}
						/>
					))}

					{!isLoading && stockCodes.length === 0 && (
						<div className='py-20 text-center text-gray-500'>
							데이터를 불러오는 중입니다...
						</div>
					)}
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
								{latestAlert.changeRate}
							</span>
						</div>
					</div>
				</Toast>
			)}
		</div>
	);
}
