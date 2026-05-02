import { useState, useMemo, useRef, useEffect } from 'react';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import { useLatestSurgeAlert } from '../../hooks/stock/use-stock-alerts';
import { useStockStore } from '../../store/use-stock-store';
import type { RankingType, StockRow } from '../../types/stock';
import StockFilterGroup from './stock-filter-group';
import StockTable from './stock-table';
import Toast from '../common/toast';

export default function RankLayout() {
	const [rankingType, setRankingType] = useState<RankingType>('VALUE');
	const { stockCodes, isLoading, sortType } = useStockRankLogic(rankingType);
	const { latestAlert, clearAlert } = useLatestSurgeAlert();

	const stockMapRef = useRef(useStockStore.getState().stockMap);

	useEffect(() => {
		const unsub = useStockStore.subscribe((state) => {
			stockMapRef.current = state.stockMap;
		});
		return () => unsub();
	}, []);

	const rows: StockRow[] = useMemo(() => {
		return stockCodes
			.map((code, index) => {
				const stock = stockMapRef.current.get(code);
				if (!stock) return null;

				let buyRatio = 50 + stock.changeRate * 2;
				buyRatio = Math.max(10, Math.min(90, Math.floor(buyRatio)));

				const tickerState: StockRow['tickerState'] =
					stock.changeRate > 0 ? 'rise' : stock.changeRate < 0 ? 'fall' : 'idle';

				const row: StockRow = {
					id: stock.stockCode,
					rank: index + 1,
					isFavorite: false,
					name: stock.stockName,
					price: stock.currentPrice,
					changeRate: stock.changeRate,
					tradeAmount:
						rankingType === 'VOLUME'
							? stock.cumulativeVolume
							: stock.cumulativeAmount,
					buyRatio,
					tickerState,
				};
				return row;
			})
			.filter((row): row is StockRow => row !== null);
	}, [stockCodes, rankingType]);

	return (
		<div className='w-full max-w-6xl mx-auto px-4'>
			<StockFilterGroup activeType={rankingType} onTypeChange={setRankingType} />

			<div style={{ width: '100%', overflowX: 'auto' }}>
				{isLoading && rows.length === 0 ? (
					<div className='flex flex-col gap-2 py-2'>
						{Array.from({ length: 10 }).map((_, i) => (
							<div
								key={i}
								className='h-[60px] animate-pulse rounded-md'
								style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}
							/>
						))}
					</div>
				) : rows.length === 0 ? (
					<div className='py-20 text-center' style={{ color: '#9194A1' }}>
						데이터를 불러오는 중...
					</div>
				) : (
					<StockTable rows={rows} sortType={sortType} />
				)}
			</div>

			{latestAlert && (
				<Toast
					key={JSON.stringify(latestAlert)}
					duration={2500}
					onClose={clearAlert}
				>
					<div className='flex flex-col gap-1'>
						<div className='text-sm flex items-center gap-2'>
							<strong className='text-white text-base'>
								{latestAlert.stockName}
							</strong>
							<span
								style={{
									fontWeight: 600,
									color: latestAlert.changeRate.startsWith('-')
										? '#256AF4'
										: '#EA580C',
								}}
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