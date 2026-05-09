import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PriceChangeToken } from './price-change-token';
import { LinearGauge } from './linear-gauge';
import type { StockRow } from '../../types/stock';
import { useViewport } from '../../hooks/common/use-viewport';

// ─── HeartIcon ────────────────────────────────────────────────

const HeartIcon = ({ active }: { active: boolean }) => (
	<svg width='14' height='14' viewBox='0 0 24 24' fill={active ? '#EA580C' : '#4B4B50'} xmlns='http://www.w3.org/2000/svg'>
		<path d='M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z' />
	</svg>
);

// ─── SlotPrice ────────────────────────────────────────────────

const SlotPrice = ({ value, fontSize = '15px' }: { value: number; fontSize?: string }) => {
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
		<span style={{ display: 'inline-block', overflow: 'hidden', height: '1.2em', fontSize, fontWeight: 500, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', color: '#FFFFFF', position: 'relative' }}>
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
	isMobile?: boolean;
	isTablet?: boolean;
	onFavoriteToggle?: (id: string) => void;
}

const StockTableRow = ({ row, sortType, isMobile, isTablet, onFavoriteToggle }: RowProps) => {
	const navigate = useNavigate();

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
		activeTicker === 'rise' ? 'rgba(234,88,12,0.1)' :
		activeTicker === 'fall' ? 'rgba(37,106,244,0.1)' : 'transparent';

	const tradeAmountStr =
		sortType === 'volume'
			? `${row.tradeAmount.toLocaleString('ko-KR')}주`
			: `${Math.floor(row.tradeAmount / 100000000).toLocaleString('ko-KR')}억원`;

	// ── 모바일: 순위 / 종목명 / 현재가 / 등락률 가로 배치 ────
	if (isMobile) {
		return (
			<div
				onClick={() => navigate(`/stock/${row.id}`)}
				style={{ display: 'flex', alignItems: 'center', height: '56px', paddingLeft: '12px', paddingRight: '12px', backgroundColor: bgColor, transition: 'background-color 150ms', cursor: 'pointer', boxSizing: 'border-box' }}
			>
				{/* 즐겨찾기 + 순위 — 40px */}
				<div style={{ width: '40px', display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
					<button onClick={(e) => { e.stopPropagation(); onFavoriteToggle?.(row.id); }} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', flexShrink: 0 }}>
						<HeartIcon active={row.isFavorite} />
					</button>
					<span style={{ fontSize: '13px', fontWeight: 700, color: '#9194A1' }}>{row.rank}</span>
				</div>

				{/* 로고 + 종목명 — 나머지 공간 */}
				<div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
					{row.logoUrl ? (
						<img src={row.logoUrl} alt={row.name} style={{ width: '28px', height: '28px', borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
					) : (
						<div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: '#21242C', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
							<span style={{ fontSize: '10px', color: '#9194A1' }}>{row.name[0]}</span>
						</div>
					)}
					<span style={{ fontSize: '14px', fontWeight: 500, color: '#FFFFFF', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
						{row.name}
					</span>
				</div>

				{/* 현재가 — 80px */}
				<div style={{ width: '80px', flexShrink: 0, textAlign: 'right' }}>
					<SlotPrice value={row.price} fontSize='14px' />
				</div>

				{/* 등락률 — 60px */}
				<div style={{ width: '60px', flexShrink: 0, textAlign: 'right' }}>
					<PriceChangeToken value={row.changeRate} />
				</div>
			</div>
		);
	}

	// ── 태블릿: 거래비율 바 숨김 ──────────────────────────────
	if (isTablet) {
		return (
			<div
				onClick={() => navigate(`/stock/${row.id}`)}
				style={{ width: '100%', height: '60px', display: 'flex', alignItems: 'center', paddingLeft: '12px', paddingRight: '12px', backgroundColor: bgColor, transition: 'background-color 150ms', cursor: 'pointer', boxSizing: 'border-box' }}
			>
				<div style={{ width: '52px', display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
					<button onClick={(e) => { e.stopPropagation(); onFavoriteToggle?.(row.id); }} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}>
						<HeartIcon active={row.isFavorite} />
					</button>
					<span style={{ fontSize: '13px', fontWeight: 700, color: '#9194A1' }}>{row.rank}</span>
				</div>
				<div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
					<div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: '#21242C', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
						<span style={{ fontSize: '10px', color: '#9194A1' }}>{row.name[0]}</span>
					</div>
					<span style={{ fontSize: '14px', fontWeight: 500, color: '#FFFFFF', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.name}</span>
				</div>
				<div style={{ width: '90px', display: 'flex', justifyContent: 'flex-end' }}><SlotPrice value={row.price} fontSize='14px' /></div>
				<div style={{ width: '80px', display: 'flex', justifyContent: 'flex-end' }}><PriceChangeToken value={row.changeRate} /></div>
				<div style={{ width: '100px', display: 'flex', justifyContent: 'flex-end' }}>
					<span style={{ fontSize: '13px', fontWeight: 500, color: '#FFFFFF', fontVariantNumeric: 'tabular-nums' }}>{tradeAmountStr}</span>
				</div>
			</div>
		);
	}

	// ── 데스크톱 ──────────────────────────────────────────────
	return (
		<div
			onClick={() => navigate(`/stock/${row.id}`)}
			style={{ width: '100%', height: '60px', display: 'flex', alignItems: 'center', paddingLeft: '16px', paddingRight: '16px', backgroundColor: bgColor, transition: 'background-color 150ms ease-out', cursor: 'pointer', boxSizing: 'border-box' }}
		>
			<div style={{ width: '60px', display: 'flex', alignItems: 'center', gap: '14px', flexShrink: 0 }}>
				<button onClick={(e) => { e.stopPropagation(); onFavoriteToggle?.(row.id); }} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
					<HeartIcon active={row.isFavorite} />
				</button>
				<span style={{ fontSize: '15px', fontWeight: 700, color: '#9194A1', minWidth: '16px', textAlign: 'center' }}>{row.rank}</span>
			</div>
			<div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '14px', overflow: 'hidden' }}>
				{row.logoUrl ? (
					<img src={row.logoUrl} alt={row.name} style={{ width: '36px', height: '36px', borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
				) : (
					<div style={{ width: '36px', height: '36px', borderRadius: '50%', backgroundColor: '#21242C', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
						<span style={{ fontSize: '12px', color: '#9194A1' }}>{row.name[0]}</span>
					</div>
				)}
				<span style={{ fontSize: '15px', fontWeight: 500, color: '#FFFFFF', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{row.name}</span>
			</div>
			<div style={{ width: '100px', display: 'flex', justifyContent: 'flex-end' }}><SlotPrice value={row.price} /></div>
			<div style={{ width: '100px', display: 'flex', justifyContent: 'flex-end', paddingLeft: '11px', paddingRight: '11px', boxSizing: 'border-box' }}><PriceChangeToken value={row.changeRate} /></div>
			<div style={{ width: '130px', display: 'flex', justifyContent: 'flex-end' }}>
				<span style={{ fontSize: '15px', fontWeight: 500, color: '#FFFFFF', fontVariantNumeric: 'tabular-nums' }}>{tradeAmountStr}</span>
			</div>
			<div style={{ width: '160px', display: 'flex', justifyContent: 'center' }}>
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

export default function StockTable({ rows, sortType, onFavoriteToggle, className }: StockTableProps) {
	const viewport = useViewport();
	const isMobile = viewport === 'mobile';
	const isTablet = viewport === 'tablet';

	return (
		<div className={className ?? ''} style={{ width: '100%' }}>
			{/* 헤더 */}
			{isMobile ? (
				// 모바일 헤더 — 순위 / 종목명 / 현재가 / 등락률 각각 별도 컬럼
				<div style={{ display: 'flex', alignItems: 'center', padding: '0 12px 4px', boxSizing: 'border-box' }}>
					{/* 순위 — 40px */}
					<div style={{ width: '40px', flexShrink: 0 }}>
						<span style={{ fontSize: '12px', color: '#9194A1' }}>순위</span>
					</div>
					{/* 종목명 — 나머지 */}
					<div style={{ flex: 1 }}>
						<span style={{ fontSize: '12px', color: '#9194A1' }}>종목명</span>
					</div>
					{/* 현재가 — 80px */}
					<div style={{ width: '80px', flexShrink: 0, textAlign: 'right' }}>
						<span style={{ fontSize: '12px', color: '#9194A1' }}>현재가</span>
					</div>
					{/* 등락률 — 60px */}
					<div style={{ width: '60px', flexShrink: 0, textAlign: 'right' }}>
						<span style={{ fontSize: '12px', color: '#9194A1' }}>등락률</span>
					</div>
				</div>
			) : (
				// 태블릿/데스크톱 헤더
				<div style={{ width: '100%', height: '26px', display: 'flex', alignItems: 'center', paddingLeft: isTablet ? '12px' : '16px', paddingRight: isTablet ? '12px' : '16px', boxSizing: 'border-box' }}>
					<div style={{ flex: 1 }}>
						<span style={{ fontSize: '13px', color: '#9194A1' }}>순위</span>
					</div>
					<div style={{ width: isTablet ? '90px' : '100px', display: 'flex', justifyContent: 'flex-end' }}>
						<span style={{ fontSize: '13px', color: '#9194A1' }}>현재가</span>
					</div>
					<div style={{ width: isTablet ? '80px' : '100px', display: 'flex', justifyContent: 'flex-end' }}>
						<span style={{ fontSize: '13px', color: '#9194A1' }}>등락률</span>
					</div>
					<div style={{ width: isTablet ? '100px' : '130px', display: 'flex', justifyContent: 'flex-end' }}>
						<span style={{ fontSize: '13px', color: '#9194A1' }}>{sortType === 'volume' ? '거래량 순' : '거래대금 순'}</span>
					</div>
					{!isTablet && (
						<div style={{ width: '160px', display: 'flex', justifyContent: 'center' }}>
							<span style={{ fontSize: '13px', color: '#9194A1' }}>거래 비율</span>
						</div>
					)}
				</div>
			)}

			{rows.map((row) => (
				<StockTableRow
					key={row.id}
					row={row}
					sortType={sortType}
					isMobile={isMobile}
					isTablet={isTablet}
					onFavoriteToggle={onFavoriteToggle}
				/>
			))}
		</div>
	);
}

export { StockTable };