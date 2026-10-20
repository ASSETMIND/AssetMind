import React, { useEffect, useRef, useState } from 'react';

// ─── Types ────────────────────────────────────────────────────

export type OrderbookStatus = 'default' | 'skeleton' | 'error' | 'empty';
export type Viewport = 'desktop' | 'tablet' | 'mobile';

export interface OrderbookRow {
	price: number;
	changeRate: number;
	quantity: number;
}

export interface TradeTickRow {
	id: string;
	price: number;
	quantity: number;
	isBuy: boolean;
}

export interface MarketInfo {
	weekHigh: number;
	weekLow: number;
	upperLimit: number;
	lowerLimit: number;
	riseVI?: number;
	fallVI?: number;
	open: number;
	high: number;
	low: number;
	volume: number;
	volumeUnit: string;
	changeFromYesterday: number;
	midPrice?: number;
}

interface OrderbookTableProps {
	status?: OrderbookStatus;
	viewport?: Viewport;
	isMarketClosed?: boolean;
	onRetry?: () => void;
	currentPrice?: number;
	currentChangeRate?: number;
	asks?: OrderbookRow[];
	bids?: OrderbookRow[];
	trades?: TradeTickRow[];
	tradeStrength?: number;
	marketInfo?: MarketInfo;
	onQuickOrder?: () => void;
	className?: string;
}

// ─── Helpers ──────────────────────────────────────────────────

const fmt = (v: number) => v.toLocaleString('ko-KR');
const fmtRate = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;

// ─── TradeTickerList (인라인) ─────────────────────────────────

const RISE_FLASH = 'rgba(234,88,12,0.18)';
const FALL_FLASH = 'rgba(37,106,244,0.18)';

const TradeTickItem = ({ trade, isNew }: { trade: TradeTickRow; isNew: boolean }) => {
	const [bg, setBg] = useState('transparent');
	const [slideIn, setSlideIn] = useState(false);
	const mountedRef = useRef(false);

	useEffect(() => {
		if (!isNew) return;
		if (!mountedRef.current) {
			mountedRef.current = true;
			const raf = requestAnimationFrame(() => setSlideIn(true));
			return () => cancelAnimationFrame(raf);
		}
	}, [isNew]);

	useEffect(() => {
		if (!isNew) return;
		setBg(trade.isBuy ? RISE_FLASH : FALL_FLASH);
		const t = setTimeout(() => setBg('transparent'), 150);
		return () => clearTimeout(t);
	}, [isNew, trade.isBuy]);

	return (
		<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', height: '32px', padding: '0 0 0 8px', backgroundColor: bg, transform: slideIn || !isNew ? 'translateY(0)' : 'translateY(-8px)', opacity: slideIn || !isNew ? 1 : 0, transition: isNew ? 'transform 120ms ease-out, opacity 120ms ease-out, background-color 150ms ease-out' : 'background-color 150ms ease-out', flexShrink: 0 }}>
			<span style={{ fontSize: '12px', fontWeight: 400, color: '#9F9F9F' }}>{fmt(trade.price)}</span>
			<span style={{ fontSize: '12px', fontWeight: 400, color: trade.isBuy ? '#EA580C' : '#256AF4', textAlign: 'right', minWidth: '32px' }}>{trade.quantity}</span>
		</div>
	);
};

const TradeTickerList = ({ trades, height = 320, tradeStrength }: { trades: TradeTickRow[]; height?: number; tradeStrength?: number }) => {
	const prevIdsRef = useRef<Set<string>>(new Set());
	const newIds = new Set<string>();
	for (const t of trades) {
		if (!prevIdsRef.current.has(t.id)) newIds.add(t.id);
	}
	useEffect(() => { prevIdsRef.current = new Set(trades.map((t) => t.id)); });

	return (
		<div style={{ display: 'flex', flexDirection: 'column' }}>
			<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0 4px 8px', height: '24px', flexShrink: 0 }}>
				<span style={{ fontSize: '12px', fontWeight: 400, color: '#9F9F9F' }}>체결강도</span>
				{tradeStrength !== undefined && <span style={{ fontSize: '12px', fontWeight: 400, color: '#256AF4' }}>{tradeStrength}%</span>}
			</div>
			<div style={{ height: `${height}px`, overflowY: 'auto', overflowX: 'hidden', display: 'flex', flexDirection: 'column', scrollbarWidth: 'none' }}>
				{trades.map((trade) => <TradeTickItem key={trade.id} trade={trade} isNew={newIds.has(trade.id)} />)}
			</div>
		</div>
	);
};

// ─── Skeleton ─────────────────────────────────────────────────

const SkeletonBox = ({ width = '100%', height = 16 }: { width?: string | number; height?: number }) => (
	<div style={{ width, height: `${height}px`, borderRadius: '6px', backgroundColor: '#21242C', flexShrink: 0 }} />
);

const DesktopOrderbookSkeleton = () => (
	<div style={{ display: 'flex', position: 'relative' }}>
		<div style={{ display: 'flex', flexDirection: 'column', width: '100px' }}>
			<div style={{ height: '32px' }} />
			{Array.from({ length: 10 }).map((_, i) => (
				<div key={i} style={{ height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: '8px' }}>
					<SkeletonBox width={76} height={20} />
				</div>
			))}
		</div>
		<div style={{ display: 'flex', flexDirection: 'column', flex: 1, alignItems: 'center' }}>
			{Array.from({ length: 21 }).map((_, i) => (
				<div key={i} style={{ height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%' }}>
					<SkeletonBox width={76} height={20} />
				</div>
			))}
		</div>
		<div style={{ display: 'flex', flexDirection: 'column', width: '110px' }}>
			<div style={{ height: '32px' }} />
			{Array.from({ length: 10 }).map((_, i) => (
				<div key={i} style={{ height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'flex-start', paddingLeft: '8px' }}>
					<SkeletonBox width={76} height={20} />
				</div>
			))}
		</div>
	</div>
);

const MobileOrderbookSkeleton = () => (
	<div style={{ display: 'flex', flexDirection: 'column' }}>
		<div style={{ display: 'flex', alignItems: 'center', height: '32px' }}>
			<div style={{ flex: 1 }} />
			<div style={{ width: '110px', display: 'flex', justifyContent: 'center' }}>
				<SkeletonBox width={76} height={20} />
			</div>
			<div style={{ flex: 1 }} />
		</div>
		{Array.from({ length: 10 }).map((_, i) => (
			<div key={i} style={{ display: 'flex', alignItems: 'center', height: '32px', width: '100%' }}>
				<div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end', paddingRight: '8px' }}>
					<SkeletonBox width='80%' height={20} />
				</div>
				<div style={{ width: '110px', display: 'flex', justifyContent: 'center' }}>
					<SkeletonBox width={76} height={20} />
				</div>
				<div style={{ flex: 1, display: 'flex', justifyContent: 'flex-start', paddingLeft: '8px' }}>
					<SkeletonBox width='80%' height={20} />
				</div>
			</div>
		))}
	</div>
);

// ─── Error ────────────────────────────────────────────────────

const OrderbookError = ({ onRetry }: { onRetry?: () => void }) => (
	<div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '600px', gap: '16px' }}>
		<p style={{ fontSize: '14px', color: '#9F9F9F', textAlign: 'center', lineHeight: '1.6', margin: 0 }}>
			호가 데이터를 불러오지 못했습니다.<br />잠시 후 다시 시도해 주세요.
		</p>
		<button onClick={onRetry} style={{ width: '100px', height: '38px', backgroundColor: '#6B4EFF', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: 500, color: '#FFFFFF' }}>
			다시 시도
		</button>
	</div>
);

// ─── Desktop: AskRow ──────────────────────────────────────────

const AskRow = ({ row, maxQty = 1, isEmpty }: { row?: OrderbookRow; maxQty?: number; isEmpty?: boolean }) => {
	const barWidth = isEmpty || !row ? 0 : Math.round((row.quantity / maxQty) * 100);
	return (
		<div style={{ position: 'relative', width: '100px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: '8px', overflow: 'hidden' }}>
			<div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px', background: 'linear-gradient(to left, rgba(255,255,255,0.15), transparent)' }} />
			{!isEmpty && row && (
				<>
					<div style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', right: 0, width: `${barWidth}%`, height: '20px', background: 'linear-gradient(to left, rgba(37,106,244,0.3), rgba(37,106,244,0.05))', borderRadius: '2px 0 0 2px' }} />
					<span style={{ position: 'relative', fontSize: '13px', fontWeight: 400, color: '#256AF4' }}>{fmt(row.quantity)}</span>
				</>
			)}
		</div>
	);
};

// ─── Desktop: BidRow ──────────────────────────────────────────

const BidRow = ({ row, maxQty }: { row: OrderbookRow; maxQty: number }) => {
	const barWidth = Math.round((row.quantity / maxQty) * 100);
	return (
		<div style={{ position: 'relative', width: '100px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'flex-start', paddingLeft: '8px', overflow: 'hidden' }}>
			<div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px', background: 'linear-gradient(to right, rgba(255,255,255,0.15), transparent)' }} />
			<div style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', left: 0, width: `${barWidth}%`, height: '20px', background: 'linear-gradient(to right, rgba(234,88,12,0.3), rgba(234,88,12,0.05))', borderRadius: '0 2px 2px 0' }} />
			<span style={{ position: 'relative', fontSize: '13px', fontWeight: 400, color: '#EA580C' }}>{fmt(row.quantity)}</span>
		</div>
	);
};

// ─── Desktop: PriceCell ───────────────────────────────────────

const PriceCell = ({ price, changeRate }: { price: number; changeRate: number }) => (
	<div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', padding: '0 4px' }}>
		<span style={{ fontSize: '14px', fontWeight: 400, color: '#256AF4', lineHeight: 1.2 }}>{fmt(price)}</span>
		<span style={{ fontSize: '8px', fontWeight: 500, color: '#256AF4', lineHeight: 1.2 }}>{fmtRate(changeRate)}</span>
	</div>
);

// ─── Desktop: MarketInfoPanel ─────────────────────────────────

const MarketInfoPanel = ({ info }: { info: MarketInfo }) => {
	const D = <div style={{ height: '1px', background: 'rgba(255,255,255,0.08)', margin: '6px 0' }} />;
	const R = ({ label, value, color }: { label: string; value: string; color?: string }) => (
		<div style={{ display: 'flex', justifyContent: 'space-between', gap: '6px' }}>
			<span style={{ fontSize: '11px', fontWeight: 400, color: '#9F9F9F', whiteSpace: 'nowrap' }}>{label}</span>
			<span style={{ fontSize: '11px', fontWeight: 400, color: color ?? '#9F9F9F', whiteSpace: 'nowrap' }}>{value}</span>
		</div>
	);
	return (
		<div style={{ width: '110px', display: 'flex', flexDirection: 'column' }}>
			<R label='52주최고' value={fmt(info.weekHigh)} />
			<R label='52주최저' value={fmt(info.weekLow)} />
			{D}
			<R label='상한가' value={fmt(info.upperLimit)} />
			<R label='하한가' value={fmt(info.lowerLimit)} />
			<R label='상승VI' value={info.riseVI ? fmt(info.riseVI) : '-'} />
			<R label='하락VI' value={info.fallVI ? fmt(info.fallVI) : '-'} />
			{D}
			<R label='시가' value={fmt(info.open)} />
			<R label='고가' value={fmt(info.high)} color='#EA580C' />
			<R label='저가' value={fmt(info.low)} color='#256AF4' />
			{D}
			<div style={{ fontSize: '11px', color: '#9F9F9F', whiteSpace: 'nowrap' }}>거래량</div>
			<div style={{ fontSize: '11px', color: '#9F9F9F', whiteSpace: 'nowrap' }}>{info.volumeUnit}</div>
			<R label='전일대비' value={`${info.changeFromYesterday}%`} />
			{D}
			<R label='예상체결가' value={info.midPrice ? fmt(info.midPrice) : '-'} />
		</div>
	);
};

// ─── Mobile: AskQuantityCell ──────────────────────────────────

const MobileAskQtyCell = ({ row, maxQty }: { row: OrderbookRow; maxQty: number }) => {
	const barWidth = Math.round((row.quantity / maxQty) * 100);
	return (
		<div style={{ position: 'relative', flex: 1, height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: '8px', overflow: 'hidden' }}>
			<div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px', background: 'linear-gradient(to left, rgba(255,255,255,0.15), transparent)' }} />
			<div style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', right: 0, width: `${barWidth}%`, height: '20px', background: 'linear-gradient(to left, rgba(37,106,244,0.3), rgba(37,106,244,0.05))', borderRadius: '2px 0 0 2px' }} />
			<span style={{ position: 'relative', fontSize: '13px', fontWeight: 400, color: '#256AF4', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.quantity)}</span>
		</div>
	);
};

// ─── Mobile: BidQuantityCell ──────────────────────────────────

const MobileBidQtyCell = ({ row, maxQty }: { row: OrderbookRow; maxQty: number }) => {
	const barWidth = Math.round((row.quantity / maxQty) * 100);
	return (
		<div style={{ position: 'relative', flex: 1, height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'flex-start', paddingLeft: '8px', overflow: 'hidden' }}>
			<div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px', background: 'linear-gradient(to right, rgba(255,255,255,0.15), transparent)' }} />
			<div style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', left: 0, width: `${barWidth}%`, height: '20px', background: 'linear-gradient(to right, rgba(234,88,12,0.3), rgba(234,88,12,0.05))', borderRadius: '0 2px 2px 0' }} />
			<span style={{ position: 'relative', fontSize: '13px', fontWeight: 400, color: '#EA580C', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.quantity)}</span>
		</div>
	);
};

// ─── Mobile: PriceCell ───────────────────────────────────────

const MobilePriceCell = ({ price, changeRate, isCurrent }: { price: number; changeRate: number; isCurrent?: boolean }) => (
	<div style={{ width: '110px', flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '32px' }}>
		<span style={{ fontSize: isCurrent ? '14px' : '13px', fontWeight: 400, color: isCurrent ? '#FFFFFF' : '#256AF4', fontVariantNumeric: 'tabular-nums', lineHeight: 1.2 }}>
			{fmt(price)}
		</span>
		<span style={{ fontSize: '8px', fontWeight: 500, color: isCurrent ? '#EA580C' : '#256AF4', lineHeight: 1.2 }}>
			{fmtRate(changeRate)}
		</span>
	</div>
);

// ─── Mobile: EmptyCell ───────────────────────────────────────

const MobileEmptyCell = ({ direction }: { direction: 'ask' | 'bid' }) => (
	<div style={{ position: 'relative', flex: 1, height: '32px', overflow: 'hidden' }}>
		<div style={{
			position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px',
			background: direction === 'ask'
				? 'linear-gradient(to right, rgba(255,255,255,0.15), transparent)'
				: 'linear-gradient(to left, rgba(255,255,255,0.15), transparent)',
		}} />
	</div>
);

// ─── Mobile: CurrentPriceRow ──────────────────────────────────

const MobileCurrentPriceRow = ({ price, changeRate }: { price: number; changeRate: number }) => (
	<div style={{ display: 'flex', alignItems: 'center', height: '32px' }}>
		<div style={{ flex: 1 }} />
		<MobilePriceCell price={price} changeRate={changeRate} isCurrent />
		<div style={{ flex: 1 }} />
	</div>
);

// ─── Mobile Orderbook Body ────────────────────────────────────

const MobileOrderbookBody: React.FC<{
	currentPrice: number;
	currentChangeRate: number;
	asks: OrderbookRow[];
	bids: OrderbookRow[];
	maxAskQty: number;
	maxBidQty: number;
}> = ({ currentPrice, currentChangeRate, asks, bids, maxAskQty, maxBidQty }) => {
	const displayAsks = asks.slice(0, 10);
	const displayBids = bids.slice(0, 10);

	return (
		<div style={{ display: 'flex', flexDirection: 'column' }}>
			<MobileCurrentPriceRow price={currentPrice} changeRate={currentChangeRate} />
			{Array.from({ length: 10 }).map((_, i) => {
				const ask = displayAsks[i];
				const bid = displayBids[i];
				const price = ask ? ask.price : (bid ? bid.price : 0);
				const changeRate = ask ? ask.changeRate : (bid ? bid.changeRate : 0);

				return (
					<div key={i} style={{ display: 'flex', alignItems: 'center', height: '32px', width: '100%' }}>
						{ask ? <MobileAskQtyCell row={ask} maxQty={maxAskQty} /> : <MobileEmptyCell direction='ask' />}
						<MobilePriceCell price={price} changeRate={changeRate} />
						{bid ? <MobileBidQtyCell row={bid} maxQty={maxBidQty} /> : <MobileEmptyCell direction='bid' />}
					</div>
				);
			})}
		</div>
	);
};

// ─── OrderbookTable ───────────────────────────────────────────

export const OrderbookTable = ({
	status: statusProp,
	viewport = 'desktop',
	isMarketClosed,
	onRetry,
	currentPrice = 0,
	currentChangeRate = 0,
	asks = [],
	bids = [],
	trades = [],
	tradeStrength = 0,
	marketInfo,
	onQuickOrder,
	className,
}: OrderbookTableProps) => {
	const status: OrderbookStatus = statusProp ?? (isMarketClosed ? 'empty' : 'default');
	const isMobile = viewport === 'mobile';
	const isTablet = viewport === 'tablet';

	const maxAskQty = Math.max(...asks.map((a) => a.quantity), 1);
	const maxBidQty = Math.max(...bids.map((b) => b.quantity), 1);

	const containerWidth = isMobile || isTablet ? '100%' : '340px';
	const containerHeight = isMobile ? 'auto' : '820px';

	return (
		<div
			className={className}
			style={{ width: containerWidth, height: containerHeight, backgroundColor: '#1C1D21', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative', overflow: 'hidden', boxSizing: 'border-box' }}
		>
			{/* 배경 그라디언트 */}
			<div style={{ position: 'absolute', top: 0, left: 0, width: '200px', height: '200px', background: 'radial-gradient(ellipse at top left, rgba(37,106,244,0.1) 0%, transparent 70%)', pointerEvents: 'none' }} />
			<div style={{ position: 'absolute', bottom: 0, right: 0, width: '200px', height: '200px', background: 'radial-gradient(ellipse at bottom right, rgba(234,88,12,0.1) 0%, transparent 70%)', pointerEvents: 'none' }} />

			{/* 헤더 */}
			<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative' }}>
				<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>호가</span>
				{(status === 'default' || status === 'skeleton') && !isMobile && (
					<button onClick={onQuickOrder} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '4px', width: '79px', height: '24px', border: '1px solid rgba(255,255,255,0.25)', borderRadius: '8px', background: 'transparent', cursor: 'pointer' }}>
						<span style={{ fontSize: '14px', fontWeight: 400, color: '#9F9F9F' }}>빠른 주문</span>
					</button>
				)}
				{(status === 'default' || status === 'skeleton') && isMobile && (
					<button onClick={onQuickOrder} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 12px', backgroundColor: 'transparent', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: 400, color: '#9F9F9F' }}>
						전체 보기
					</button>
				)}
			</div>

			{/* 상태별 렌더링 */}
			{status === 'skeleton' && (isMobile ? <MobileOrderbookSkeleton /> : <DesktopOrderbookSkeleton />)}
			{status === 'error' && <OrderbookError onRetry={onRetry} />}
			{status === 'empty' && (
				<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: '#9F9F9F', fontSize: '14px' }}>
					장이 휴장 중입니다.
				</div>
			)}

			{status === 'default' && marketInfo && (
				<>
					{/* Mobile */}
					{isMobile && (
						<MobileOrderbookBody
							currentPrice={currentPrice}
							currentChangeRate={currentChangeRate}
							asks={asks}
							bids={bids}
							maxAskQty={maxAskQty}
							maxBidQty={maxBidQty}
						/>
					)}

					{/* Desktop/Tablet */}
					{!isMobile && (
						<div style={{ display: 'flex', position: 'relative' }}>
							<div style={{ display: 'flex', flexDirection: 'column' }}>
								<AskRow isEmpty />
								{asks.map((ask, i) => <AskRow key={i} row={ask} maxQty={maxAskQty} />)}
								<TradeTickerList
									trades={trades}
									tradeStrength={tradeStrength}
									height={trades.length * 32 + 24}
								/>
							</div>
							<div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
								<div style={{ height: '32px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
									<span style={{ fontSize: '14px', fontWeight: 400, color: '#256AF4', lineHeight: 1.2 }}>{fmt(currentPrice)}</span>
									<span style={{ fontSize: '8px', fontWeight: 500, color: '#EA580C', lineHeight: 1.2 }}>{fmtRate(currentChangeRate)}</span>
								</div>
								{asks.map((ask, i) => (
									<div key={i} style={{ height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
										<PriceCell price={ask.price} changeRate={ask.changeRate} />
									</div>
								))}
								{bids.map((bid, i) => (
									<div key={i} style={{ height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
										<PriceCell price={bid.price} changeRate={bid.changeRate} />
									</div>
								))}
							</div>
							<div style={{ display: 'flex', flexDirection: 'column' }}>
								<div style={{ height: '32px' }} />
								<MarketInfoPanel info={marketInfo} />
								<div style={{ height: '50px' }} />
								{bids.map((bid, i) => <BidRow key={i} row={bid} maxQty={maxBidQty} />)}
							</div>
						</div>
					)}
				</>
			)}
		</div>
	);
};

export default OrderbookTable;