import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PriceChangeToken } from './price-change-token';
import { LinearGauge } from './linear-gauge';
import type { StockRow } from '../../types/stock';

// ─── HeartIcon ────────────────────────────────────────────────

const HeartIcon = ({ active }: { active: boolean }) => (
	<svg width='14' height='14' viewBox='0 0 24 24' fill={active ? '#EA580C' : '#4B4B50'} xmlns='http://www.w3.org/2000/svg'>
		<path d='M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z' />
	</svg>
);

// ─── SlotPrice ────────────────────────────────────────────────

const SlotPrice = ({ value }: { value: number }) => {
	const [display, setDisplay] = useState(value.toLocaleString('ko-KR') + '원');
	const [animating, setAnimating] = useState(false);
	const prevRef = useRef(value);

	useEffect(() => {
		if (prevRef.current === value) return;
		prevRef.current = value;
		setAnimating(true);
		const t = setTimeout(() => {
			setDisplay(value.toLocaleString('ko-KR') + '원');
			setAnimating(false);
		}, 200);
		return () => clearTimeout(t);
	}, [value]);

	return (
		<span style={{ display: 'inline-block', overflow: 'hidden', height: '1.2em', fontSize: '15px', fontWeight: 500, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', color: '#FFFFFF', position: 'relative' }}>
			<span style={{ display: 'inline-block', animation: animating ? 'slotEnter 200ms ease-out forwards' : 'none' }}>
				{display}
			</span>
			<style>{`@keyframes slotEnter { from { transform: translateY(100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }`}</style>
		</span>
	);
};

// ─── StockTableRow ────────────────────────────────────────────

interface RowProps {
	row: StockRow;
	sortType: 'value' | 'volume';
	onFavoriteToggle?: (id: string) => void;
}

const StockTableRow = ({ row, sortType, onFavoriteToggle }: RowProps) => {
	const navigate = useNavigate();

	// tickerState는 일시적으로만 배경색을 켜야 함
	// 외부에서 받은 tickerState를 500ms 후 자동 해제
	const [activeTicker, setActiveTicker] = useState<StockRow['tickerState']>('idle');
	const prevTickerRef = useRef(row.tickerState);

	useEffect(() => {
		if (prevTickerRef.current === row.tickerState) return;
		prevTickerRef.current = row.tickerState;
		setActiveTicker(row.tickerState);
		const t = setTimeout(() => setActiveTicker('idle'), 500);
		return () => clearTimeout(t);
	}, [row.tickerState]);

	const bgColor =
		activeTicker === 'rise'
			? 'rgba(234,88,12,0.1)'
			: activeTicker === 'fall'
				? 'rgba(37,106,244,0.1)'
				: 'transparent';

	const tradeAmountStr =
		sortType === 'volume'
			? `${row.tradeAmount.toLocaleString('ko-KR')}주`
			: `${Math.floor(row.tradeAmount / 100000000).toLocaleString('ko-KR')}억원`;

	return (
		<div
			onClick={() => navigate(`/stock/${row.id}`)}
			style={{ width: '100%', height: '60px', display: 'flex', alignItems: 'center', paddingLeft: '16px', paddingRight: '16px', paddingTop: '12px', paddingBottom: '12px', backgroundColor: bgColor, transition: 'background-color 150ms ease-out', cursor: 'pointer', boxSizing: 'border-box' }}
		>
			{/* 하트 + 순위 — 60px */}
			<div style={{ width: '60px', height: '21px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '14px', flexShrink: 0 }}>
				<button
					onClick={(e) => { e.stopPropagation(); onFavoriteToggle?.(row.id); }}
					aria-label={row.isFavorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}
					style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', display: 'flex', alignItems: 'center' }}
				>
					<HeartIcon active={row.isFavorite} />
				</button>
				<span style={{ fontSize: '15px', fontWeight: 700, color: '#9194A1', fontVariantNumeric: 'tabular-nums', minWidth: '16px', textAlign: 'center', flexShrink: 0 }}>
					{row.rank}
				</span>
			</div>

			{/* 로고 + 종목명 — 나머지 공간 */}
			<div style={{ flex: 1, height: '36px', display: 'flex', alignItems: 'center', gap: '14px', overflow: 'hidden' }}>
				{row.logoUrl ? (
					<img src={row.logoUrl} alt={row.name} style={{ width: '36px', height: '36px', borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
				) : (
					<div style={{ width: '36px', height: '36px', borderRadius: '50%', backgroundColor: '#21242C', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
						<span style={{ fontSize: '12px', fontWeight: 400, color: '#9194A1' }}>{row.name[0]}</span>
					</div>
				)}
				<span style={{ fontSize: '15px', fontWeight: 500, color: '#FFFFFF', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
					{row.name}
				</span>
			</div>

			{/* 현재가 — 100px */}
			<div style={{ width: '100px', height: '21px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', flexShrink: 0 }}>
				<SlotPrice value={row.price} />
			</div>

			{/* 등락률 — 100px */}
			<div style={{ width: '100px', height: '21px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', flexShrink: 0, paddingLeft: '11px', paddingRight: '11px', boxSizing: 'border-box' }}>
				<PriceChangeToken value={row.changeRate} />
			</div>

			{/* 거래대금/거래량 — 130px */}
			<div style={{ width: '130px', height: '21px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', flexShrink: 0 }}>
				<span style={{ fontSize: '15px', fontWeight: 500, color: '#FFFFFF', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
					{tradeAmountStr}
				</span>
			</div>

			{/* 거래 비율 바 — 160px */}
			<div style={{ width: '160px', height: '18px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
				<LinearGauge buyRatio={row.buyRatio} />
			</div>
		</div>
	);
};

// ─── StockTable ───────────────────────────────────────────────

interface StockTableProps {
	rows: StockRow[];
	sortType: 'value' | 'volume';
	onFavoriteToggle?: (id: string) => void;
	className?: string;
}

export const StockTable = ({ rows, sortType, onFavoriteToggle, className }: StockTableProps) => {
	return (
		<div className={className ?? ''} style={{ width: '100%' }}>
			{/* 헤더 */}
			<div style={{ width: '100%', height: '26px', display: 'flex', alignItems: 'center', paddingLeft: '16px', paddingRight: '16px', paddingTop: '3px', paddingBottom: '3px', boxSizing: 'border-box' }}>
				<div style={{ flex: 1, height: '20px', display: 'flex', alignItems: 'center' }}>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1', whiteSpace: 'nowrap' }}>순위</span>
				</div>
				<div style={{ width: '100px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', flexShrink: 0 }}>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1' }}>현재가</span>
				</div>
				<div style={{ width: '100px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', flexShrink: 0 }}>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1' }}>등락률</span>
				</div>
				<div style={{ width: '130px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', flexShrink: 0 }}>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1', whiteSpace: 'nowrap' }}>
						{sortType === 'volume' ? '거래량 순' : '거래대금 순'}
					</span>
				</div>
				<div style={{ width: '160px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1', whiteSpace: 'nowrap' }}>거래 비율</span>
				</div>
			</div>

			{/* 행 */}
			{rows.map((row) => (
				<StockTableRow
					key={row.id}
					row={row}
					sortType={sortType}
					onFavoriteToggle={onFavoriteToggle}
				/>
			))}
		</div>
	);
};

export default StockTable;