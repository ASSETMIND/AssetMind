import { useState, useMemo } from 'react';
import { useStockRankLogic } from '../../hooks/stock/use-stock-rank-logic';
import { useLatestSurgeAlert } from '../../hooks/stock/use-stock-alerts';
import { useStockStore } from '../../store/use-stock-store';
import type { RankingType, StockRow } from '../../types/stock';
import StockFilterGroup from './stock-filter-group';
import StockTable from './stock-table';
import Toast from '../common/toast';

// ─── 스켈레톤 row ─────────────────────────────────────────────

const SkeletonRow = () => (
	<div
		style={{
			width: '100%',
			height: '60px',
			borderRadius: '6px',
			backgroundColor: 'rgba(255,255,255,0.04)',
			animation: 'rankPulse 1.5s ease-in-out infinite',
		}}
	/>
);

// ─── 빈 데이터 Fallback ───────────────────────────────────────

const EmptyState = () => (
	<div style={{
		display: 'flex',
		flexDirection: 'column',
		alignItems: 'center',
		justifyContent: 'center',
		padding: '80px 0',
		gap: '12px',
		color: '#9194A1',
	}}>
		<svg width='32' height='32' viewBox='0 0 24 24' fill='none'>
			<path d='M3 3h18v18H3V3z' stroke='#4B4B50' strokeWidth='1.5' strokeLinecap='round' />
			<path d='M9 9h6M9 13h4' stroke='#4B4B50' strokeWidth='1.5' strokeLinecap='round' />
		</svg>
		<p style={{ fontSize: '14px', margin: 0 }}>표시할 종목 데이터가 없습니다.</p>
	</div>
);

// ─── RankLayout ───────────────────────────────────────────────

export default function RankLayout() {
	const [rankingType, setRankingType] = useState<RankingType>('VALUE');
	const { stockCodes, isLoading, sortType, mapVersion } = useStockRankLogic(rankingType);
	const { latestAlert, clearAlert } = useLatestSurgeAlert();

	const stockMap = useStockStore.getState().stockMap;

	const rows: StockRow[] = useMemo(() => {
		return stockCodes
			.map((code, index) => {
				const stock = stockMap.get(code);
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
	}, [stockCodes, mapVersion, rankingType]);

	return (
		<div className='w-full max-w-6xl mx-auto px-4'>
			<style>{`@keyframes rankPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }`}</style>

			<StockFilterGroup activeType={rankingType} onTypeChange={setRankingType} />

			<div style={{ width: '100%', overflowX: 'auto' }}>
				{/* 초기 로딩 — 스켈레톤 */}
				{isLoading && rows.length === 0 && (
					<div style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '4px 0' }}>
						{Array.from({ length: 10 }).map((_, i) => (
							<SkeletonRow key={i} />
						))}
					</div>
				)}

				{/* 빈 데이터 — Fallback */}
				{!isLoading && rows.length === 0 && <EmptyState />}

				{/* 정상 데이터 */}
				{rows.length > 0 && <StockTable rows={rows} sortType={sortType} />}
			</div>

			{/* 급등락 Toast */}
			{latestAlert && (
				<Toast
					key={JSON.stringify(latestAlert)}
					duration={2500}
					onClose={clearAlert}
				>
					<span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
						<strong style={{ color: '#FFFFFF', fontSize: '15px' }}>
							{latestAlert.stockName}
						</strong>
						<span
							style={{
								fontWeight: 600,
								fontSize: '14px',
								color: latestAlert.changeRate.startsWith('-')
									? '#256AF4'
									: '#EA580C',
							}}
						>
							{latestAlert.changeRate}
						</span>
					</span>
				</Toast>
			)}
		</div>
	);
}