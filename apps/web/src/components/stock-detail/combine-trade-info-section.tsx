import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, LineSeries } from 'lightweight-charts';
import type { IChartApi, LineData } from 'lightweight-charts';
import { useViewport } from '../../hooks/common/use-viewport';

// ─── Types ────────────────────────────────────────────────────

type TrendPeriod = 'daily' | 'weekly';
type InvestorType = 'program' | 'credit' | 'lending' | 'short' | 'cfd';

export interface TraderRankItem { rank: number; name: string; quantity: number; }
export interface TrendDataPoint { time: string; individual: number; foreign: number; institution: number; }
export interface TrendTableRow { date: string; closePrice: number; changeRate: number; changeAmount: number; individualNet: number; foreignNet: number; foreignRatio: number; institutionNet: number; }
export interface ProgramTradeRow { date: string; netBuyChange: number; netBuy: number; buy: number; sell: number; nonArbitrageNet: number; }
export interface CreditTradeRow { date: string; type: '융자' | '대주'; changeQty: number; newQty: number; repayQty: number; balanceQty: number; balanceRate: number; }
export interface LendingTradeRow { date: string; changeQty: number; newQty: number; repayQty: number; balanceQty: number; }
export interface ShortTradeRow { date: string; tradeAmountRatio: number; shortQty: number; shortAmount: number; shortAvgPrice: number; tradeAmount: number; }
export interface CfdTradeRow { date: string; newBuyQty: number; repayBuyQty: number; balanceBuyQty: number; buyBalanceRate: number; newSellQty: number; repaySellQty: number; balanceSellQty: number; sellBalanceRate: number; }

// ─── 색상 & 스타일 ────────────────────────────────────────────

const RISE = '#EA580C';
const FALL = '#256AF4';
const IND_COLOR = '#C9A24D';
const FOR_COLOR = '#4FA3B8';
const INST_COLOR = '#8A6BBE';
const TABLE_BG1 = '#21242C';
const BOX_BG = '#21242C';

const fmt = (v: number) => v.toLocaleString('ko-KR');
const fmtRate = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
const fmtSigned = (v: number) => `${v >= 0 ? '+' : ''}${fmt(v)}`;
const signColor = (v: number) => v > 0 ? RISE : v < 0 ? FALL : '#9194A1';

const thStyle: React.CSSProperties = { padding: '8px 12px', textAlign: 'right', color: '#9194A1', fontWeight: 400, fontSize: '12px', borderBottom: '1px solid #2F3037', whiteSpace: 'nowrap' };
const tdBase: React.CSSProperties = { padding: '8px 12px', textAlign: 'right', fontSize: '12px', fontWeight: 400, whiteSpace: 'nowrap' };

// ─── Mock 데이터 ──────────────────────────────────────────────

const MOCK_BUY_LIST: TraderRankItem[] = [
	{ rank: 1, name: '미래에셋', quantity: 125000 },
	{ rank: 2, name: '삼성증권', quantity: 98000 },
	{ rank: 3, name: 'KB증권', quantity: 76000 },
	{ rank: 4, name: '키움증권', quantity: 54000 },
	{ rank: 5, name: '신한투자', quantity: 32000 },
];
const MOCK_SELL_LIST: TraderRankItem[] = [
	{ rank: 1, name: '외국계', quantity: 110000 },
	{ rank: 2, name: 'NH투자', quantity: 87000 },
	{ rank: 3, name: '한국투자', quantity: 65000 },
	{ rank: 4, name: '메리츠', quantity: 43000 },
	{ rank: 5, name: '대신증권', quantity: 21000 },
];
const MOCK_TREND_DATA: TrendDataPoint[] = Array.from({ length: 20 }, (_, i) => ({
	time: `2026-05-${String(i + 1).padStart(2, '0')}`,
	individual: Math.floor(Math.random() * 200000 - 100000),
	foreign: Math.floor(Math.random() * 200000 - 100000),
	institution: Math.floor(Math.random() * 200000 - 100000),
}));
const MOCK_TABLE_DATA: TrendTableRow[] = Array.from({ length: 20 }, (_, i) => ({
	date: `2026-05-${String(20 - i).padStart(2, '0')}`,
	closePrice: 75000 + Math.floor(Math.random() * 5000 - 2500),
	changeRate: parseFloat((Math.random() * 4 - 2).toFixed(2)),
	changeAmount: Math.floor(Math.random() * 2000 - 1000),
	individualNet: Math.floor(Math.random() * 100000 - 50000),
	foreignNet: Math.floor(Math.random() * 100000 - 50000),
	foreignRatio: parseFloat((50 + Math.random() * 10).toFixed(2)),
	institutionNet: Math.floor(Math.random() * 100000 - 50000),
}));
const MOCK_PROGRAM_DATA: ProgramTradeRow[] = Array.from({ length: 20 }, (_, i) => ({
	date: `2026-05-${String(20 - i).padStart(2, '0')}`,
	netBuyChange: Math.floor(Math.random() * 10000 - 5000),
	netBuy: Math.floor(Math.random() * 50000 - 25000),
	buy: Math.floor(Math.random() * 100000),
	sell: Math.floor(Math.random() * 100000),
	nonArbitrageNet: Math.floor(Math.random() * 50000 - 25000),
}));
const MOCK_CREDIT_DATA: CreditTradeRow[] = Array.from({ length: 20 }, (_, i) => ({
	date: `2026-05-${String(20 - i).padStart(2, '0')}`,
	type: i % 2 === 0 ? '융자' : '대주',
	changeQty: Math.floor(Math.random() * 10000 - 5000),
	newQty: Math.floor(Math.random() * 50000),
	repayQty: Math.floor(Math.random() * 50000),
	balanceQty: Math.floor(Math.random() * 200000),
	balanceRate: parseFloat((Math.random() * 5).toFixed(2)),
}));
const MOCK_LENDING_DATA: LendingTradeRow[] = Array.from({ length: 20 }, (_, i) => ({
	date: `2026-05-${String(20 - i).padStart(2, '0')}`,
	changeQty: Math.floor(Math.random() * 10000 - 5000),
	newQty: Math.floor(Math.random() * 50000),
	repayQty: Math.floor(Math.random() * 50000),
	balanceQty: Math.floor(Math.random() * 200000),
}));
const MOCK_SHORT_DATA: ShortTradeRow[] = Array.from({ length: 20 }, (_, i) => ({
	date: `2026-05-${String(20 - i).padStart(2, '0')}`,
	tradeAmountRatio: parseFloat((Math.random() * 10).toFixed(2)),
	shortQty: Math.floor(Math.random() * 100000),
	shortAmount: Math.floor(Math.random() * 10000000000),
	shortAvgPrice: Math.floor(70000 + Math.random() * 10000),
	tradeAmount: Math.floor(Math.random() * 100000000000),
}));
const MOCK_CFD_DATA: CfdTradeRow[] = Array.from({ length: 20 }, (_, i) => ({
	date: `2026-05-${String(20 - i).padStart(2, '0')}`,
	newBuyQty: Math.floor(Math.random() * 10000),
	repayBuyQty: Math.floor(Math.random() * 10000),
	balanceBuyQty: Math.floor(Math.random() * 50000),
	buyBalanceRate: parseFloat((Math.random() * 5).toFixed(2)),
	newSellQty: Math.floor(Math.random() * 10000),
	repaySellQty: Math.floor(Math.random() * 10000),
	balanceSellQty: Math.floor(Math.random() * 50000),
	sellBalanceRate: parseFloat((Math.random() * 5).toFixed(2)),
}));

// ─── 서브 컴포넌트 ────────────────────────────────────────────

const SkeletonBox = ({ w = '100%', h = 14 }: { w?: number | string; h?: number }) => (
	<div style={{ width: w, height: `${h}px`, borderRadius: '4px', backgroundColor: BOX_BG, flexShrink: 0 }} />
);

const MoreButton = ({ expanded, onToggle }: { expanded: boolean; onToggle: () => void }) => (
	<div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0' }}>
		<button onClick={onToggle} style={{ backgroundColor: 'transparent', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#9194A1' }}>
			{expanded ? '접기 ▴' : '더 보기 ▾'}
		</button>
	</div>
);

const Dropdown = ({ value, options, onChange }: { value: string; options: { label: string; value: string }[]; onChange: (v: string) => void }) => {
	const [open, setOpen] = useState(false);
	const label = options.find((o) => o.value === value)?.label ?? value;
	return (
		<div style={{ position: 'relative' }}>
			<button onClick={() => setOpen((v) => !v)} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: '#2C2C30', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: 400, color: '#FFFFFF' }}>
				{label}<span style={{ fontSize: '10px', color: '#9194A1' }}>▾</span>
			</button>
			{open && (
				<div style={{ position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 10, backgroundColor: '#21242C', border: '1px solid #2F3037', borderRadius: '8px', overflow: 'hidden', minWidth: '130px' }}>
					{options.map((opt) => (
						<button key={opt.value} onClick={() => { onChange(opt.value); setOpen(false); }} style={{ display: 'block', width: '100%', padding: '8px 14px', backgroundColor: opt.value === value ? '#2C2C30' : 'transparent', border: 'none', cursor: 'pointer', fontSize: '12px', fontWeight: 400, color: '#FFFFFF', textAlign: 'left' }}>
							{opt.label}
						</button>
					))}
				</div>
			)}
		</div>
	);
};

const RankRow = ({ item, maxQty, side }: { item: TraderRankItem; maxQty: number; side: 'buy' | 'sell' }) => {
	const barPct = maxQty > 0 ? Math.round((item.quantity / maxQty) * 100) : 0;
	const color = side === 'buy' ? RISE : FALL;
	return (
		<div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
			<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1', width: '16px', flexShrink: 0, textAlign: 'center' }}>{item.rank}</span>
			<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF', width: '68px', flexShrink: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.name}</span>
			<div style={{ flex: 1, position: 'relative', height: '20px', display: 'flex', alignItems: 'center', borderRadius: '3px', overflow: 'hidden' }}>
				<div style={{ position: 'absolute', top: 0, left: 0, width: `${barPct}%`, height: '100%', backgroundColor: color, opacity: 0.2, borderRadius: '3px', transition: 'width 0.3s ease' }} />
				<span style={{ position: 'relative', zIndex: 1, width: '100%', fontSize: '12px', fontWeight: 400, color, textAlign: 'left', paddingLeft: '8px', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', boxSizing: 'border-box' }}>
					{fmt(item.quantity)} 주
				</span>
			</div>
		</div>
	);
};

const TrendLineChart = ({ data }: { data: TrendDataPoint[] }) => {
	const containerRef = useRef<HTMLDivElement>(null);
	useEffect(() => {
		if (!containerRef.current || data.length === 0) return;
		const chart = createChart(containerRef.current, {
			layout: { background: { type: ColorType.Solid, color: '#1C1D21' }, textColor: '#9194A1' },
			grid: { vertLines: { color: '#2F3037' }, horzLines: { color: '#2F3037' } },
			rightPriceScale: { borderColor: '#2F3037' },
			timeScale: { borderColor: '#2F3037', timeVisible: true },
			crosshair: { vertLine: { color: '#9194A1', width: 1, style: 3 }, horzLine: { color: '#9194A1', width: 1, style: 3 } },
			width: containerRef.current.clientWidth,
			height: 243,
		});
		const toLineData = (key: keyof Omit<TrendDataPoint, 'time'>): LineData[] =>
			data.map((d) => ({ time: d.time as any, value: d[key] }));
		chart.addSeries(LineSeries, { color: IND_COLOR, lineWidth: 2 }).setData(toLineData('individual'));
		chart.addSeries(LineSeries, { color: FOR_COLOR, lineWidth: 2 }).setData(toLineData('foreign'));
		chart.addSeries(LineSeries, { color: INST_COLOR, lineWidth: 2 }).setData(toLineData('institution'));
		chart.timeScale().fitContent();
		const ro = new ResizeObserver(() => {
			if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
		});
		ro.observe(containerRef.current);
		return () => { ro.disconnect(); chart.remove(); };
	}, [data]);
	return <div ref={containerRef} style={{ width: '100%', height: '243px' }} />;
};

const TrendDataTable = ({ rows }: { rows: TrendTableRow[] }) => {
	const [expanded, setExpanded] = useState(false);
	const displayed = expanded ? rows : rows.slice(0, 8);
	const HEADERS = ['일자', '종가', '등락률', '등락금액', '개인 순매수', '외국인 순매수', '외국인 지분율', '기관 순매수'];
	return (
		<div style={{ overflowX: 'auto' }}>
			<table style={{ width: '100%', borderCollapse: 'collapse' }}>
				<thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
				<tbody>
					{displayed.map((row, i) => (
						<tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : 'transparent' }}>
							<td style={{ ...tdBase, color: '#9194A1' }}>{row.date}</td>
							<td style={{ ...tdBase, color: '#FFFFFF', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.closePrice)}원</td>
							<td style={{ ...tdBase, color: signColor(row.changeRate) }}>{fmtRate(row.changeRate)}</td>
							<td style={{ ...tdBase, color: signColor(row.changeAmount) }}>{fmtSigned(row.changeAmount)}원</td>
							<td style={{ ...tdBase, color: signColor(row.individualNet) }}>{fmtSigned(row.individualNet)}주</td>
							<td style={{ ...tdBase, color: signColor(row.foreignNet) }}>{fmtSigned(row.foreignNet)}주</td>
							<td style={{ ...tdBase, color: '#9194A1' }}>{row.foreignRatio.toFixed(2)}%</td>
							<td style={{ ...tdBase, color: signColor(row.institutionNet) }}>{fmtSigned(row.institutionNet)}주</td>
						</tr>
					))}
				</tbody>
			</table>
			{rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
		</div>
	);
};

const ProgramTable = ({ rows }: { rows: ProgramTradeRow[] }) => {
	const [expanded, setExpanded] = useState(false);
	const [subFilter, setSubFilter] = useState('all');
	const displayed = expanded ? rows : rows.slice(0, 8);
	const HEADERS = ['일자', '순매수 증감', '순매수', '매수', '매도', '비차익 순매수'];
	return (
		<div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
			<Dropdown value={subFilter} options={[{ label: '전체', value: 'all' }, { label: '비차익·차익 거래', value: 'nonarbitrage' }]} onChange={setSubFilter} />
			<div style={{ overflowX: 'auto' }}>
				<table style={{ width: '100%', borderCollapse: 'collapse' }}>
					<thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
					<tbody>
						{displayed.map((row, i) => (
							<tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : 'transparent' }}>
								<td style={{ ...tdBase, color: '#9194A1' }}>{row.date}</td>
								<td style={{ ...tdBase, color: signColor(row.netBuyChange) }}>{fmtSigned(row.netBuyChange)}</td>
								<td style={{ ...tdBase, color: signColor(row.netBuy) }}>{fmtSigned(row.netBuy)}</td>
								<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.buy)}</td>
								<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.sell)}</td>
								<td style={{ ...tdBase, color: signColor(row.nonArbitrageNet) }}>{fmtSigned(row.nonArbitrageNet)}</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
			{rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
		</div>
	);
};

const CreditTable = ({ rows }: { rows: CreditTradeRow[] }) => {
	const [expanded, setExpanded] = useState(false);
	const [creditFilter, setCreditFilter] = useState('융자');
	const filtered = rows.filter((r) => r.type === creditFilter);
	const displayed = expanded ? filtered : filtered.slice(0, 8);
	const HEADERS = ['일자', '증감수량', '신규수량', '상환수량', '잔고수량', '잔고율'];
	return (
		<div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
			<Dropdown value={creditFilter} options={[{ label: '신용융자', value: '융자' }, { label: '신용대주', value: '대주' }]} onChange={setCreditFilter} />
			<div style={{ overflowX: 'auto' }}>
				<table style={{ width: '100%', borderCollapse: 'collapse' }}>
					<thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
					<tbody>
						{displayed.map((row, i) => (
							<tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : 'transparent' }}>
								<td style={{ ...tdBase, color: '#9194A1' }}>{row.date}</td>
								<td style={{ ...tdBase, color: signColor(row.changeQty) }}>{fmtSigned(row.changeQty)}</td>
								<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.newQty)}</td>
								<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.repayQty)}</td>
								<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.balanceQty)}</td>
								<td style={{ ...tdBase, color: '#9194A1' }}>{row.balanceRate.toFixed(2)}%</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
			{filtered.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
		</div>
	);
};

const LendingTable = ({ rows }: { rows: LendingTradeRow[] }) => {
	const [expanded, setExpanded] = useState(false);
	const displayed = expanded ? rows : rows.slice(0, 8);
	const HEADERS = ['일자', '증감수량', '신규수량', '상환수량', '잔고수량'];
	return (
		<div style={{ overflowX: 'auto' }}>
			<table style={{ width: '100%', borderCollapse: 'collapse' }}>
				<thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
				<tbody>
					{displayed.map((row, i) => (
						<tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : 'transparent' }}>
							<td style={{ ...tdBase, color: '#9194A1' }}>{row.date}</td>
							<td style={{ ...tdBase, color: signColor(row.changeQty) }}>{fmtSigned(row.changeQty)}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.newQty)}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.repayQty)}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.balanceQty)}</td>
						</tr>
					))}
				</tbody>
			</table>
			{rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
		</div>
	);
};

const ShortTable = ({ rows }: { rows: ShortTradeRow[] }) => {
	const [expanded, setExpanded] = useState(false);
	const displayed = expanded ? rows : rows.slice(0, 8);
	const HEADERS = ['일자', '거래대금대비 비율', '공매도 수량', '공매도 금액', '공매도 평균가', '거래대금'];
	return (
		<div style={{ overflowX: 'auto' }}>
			<table style={{ width: '100%', borderCollapse: 'collapse' }}>
				<thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
				<tbody>
					{displayed.map((row, i) => (
						<tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : 'transparent' }}>
							<td style={{ ...tdBase, color: '#9194A1' }}>{row.date}</td>
							<td style={{ ...tdBase, color: '#9194A1' }}>{row.tradeAmountRatio.toFixed(2)}%</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.shortQty)}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.shortAmount)}원</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.shortAvgPrice)}원</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.tradeAmount)}원</td>
						</tr>
					))}
				</tbody>
			</table>
			{rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
		</div>
	);
};

const CfdTable = ({ rows }: { rows: CfdTradeRow[] }) => {
	const [expanded, setExpanded] = useState(false);
	const displayed = expanded ? rows : rows.slice(0, 8);
	const HEADERS = ['일자', '신규 매수', '상환 매수', '잔고 매수', '매수 잔고율', '신규 매도', '상환 매도', '잔고 매도', '매도 잔고율'];
	return (
		<div style={{ overflowX: 'auto' }}>
			<table style={{ width: '100%', borderCollapse: 'collapse' }}>
				<thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
				<tbody>
					{displayed.map((row, i) => (
						<tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : 'transparent' }}>
							<td style={{ ...tdBase, color: '#9194A1' }}>{row.date}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.newBuyQty)}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.repayBuyQty)}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.balanceBuyQty)}</td>
							<td style={{ ...tdBase, color: '#9194A1' }}>{row.buyBalanceRate.toFixed(2)}%</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.newSellQty)}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.repaySellQty)}</td>
							<td style={{ ...tdBase, color: '#FFFFFF' }}>{fmt(row.balanceSellQty)}</td>
							<td style={{ ...tdBase, color: '#9194A1' }}>{row.sellBalanceRate.toFixed(2)}%</td>
						</tr>
					))}
				</tbody>
			</table>
			{rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
		</div>
	);
};

// ─── CombinedTradeInfoSection ─────────────────────────────────

export default function CombinedTradeInfoSection() {
	const viewport = useViewport();
	const isMobile = viewport === 'mobile';
	const [period, setPeriod] = useState<TrendPeriod>('daily');
	const [activeTab, setActiveTab] = useState<InvestorType>('program');

	const maxBuyQty = Math.max(...MOCK_BUY_LIST.map((i) => i.quantity), 1);
	const maxSellQty = Math.max(...MOCK_SELL_LIST.map((i) => i.quantity), 1);

	const INVESTOR_TABS: { label: string; value: InvestorType }[] = [
		{ label: '프로그램 매매', value: 'program' },
		{ label: '신용거래',     value: 'credit'  },
		{ label: '대차거래',     value: 'lending' },
		{ label: '공매도',       value: 'short'   },
		{ label: 'CFD',          value: 'cfd'     },
	];

	return (
		<div style={{ width: '100%', backgroundColor: '#1C1D21', borderRadius: '12px', padding: isMobile ? '16px' : '24px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '32px' }}>

			{/* ── 거래원 매매 상위 ── */}
			<div>
				<div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '16px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>거래원 매매 상위</span>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1' }}>거래소에서 제공하는 주요 거래원의 실시간 데이터입니다.</span>
				</div>
				<div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1' }}>기준 : 0000.00.00 00:00:00</span>
				</div>
				<div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: isMobile ? '24px' : '40px' }}>
					<div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
						<span style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF' }}>매수 상위 5</span>
						{MOCK_BUY_LIST.map((item) => <RankRow key={item.rank} item={item} maxQty={maxBuyQty} side="buy" />)}
					</div>
					<div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
						<span style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF' }}>매도 상위 5</span>
						{MOCK_SELL_LIST.map((item) => <RankRow key={item.rank} item={item} maxQty={maxSellQty} side="sell" />)}
					</div>
				</div>
			</div>

			<div style={{ height: '1px', backgroundColor: '#2F3037', flexShrink: 0 }} />

			{/* ── 투자자별 매매 동향 ── */}
			<div>
				<div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '16px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>투자자별 매매 동향</span>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1' }}>외국인 순매수량은 장외거래를 포함한 매매수량입니다.</span>
				</div>
				<div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
					<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1' }}>기준 : 0000.00.00 00:00:00</span>
				</div>
				<div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
					<Dropdown value={period} options={[{ label: '일별', value: 'daily' }, { label: '1주일', value: 'weekly' }]} onChange={(v) => setPeriod(v as TrendPeriod)} />
					<div style={{ flex: 1 }} />
					{!isMobile && (
						<button style={{ width: '152px', height: '32px', backgroundColor: '#2C2C30', border: 'none', borderRadius: '5px', cursor: 'pointer', fontSize: '12px', fontWeight: 400, color: '#FFFFFF' }}>
							투자자별 순매수 보기
						</button>
					)}
				</div>
				<div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '12px' }}>
					{[{ color: IND_COLOR, label: '개인' }, { color: FOR_COLOR, label: '외국인' }, { color: INST_COLOR, label: '기관' }].map((item) => (
						<div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
							<div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: item.color, flexShrink: 0 }} />
							<span style={{ fontSize: '12px', fontWeight: 700, color: '#FFFFFF' }}>{item.label}</span>
						</div>
					))}
				</div>
				<TrendLineChart data={MOCK_TREND_DATA} />
				<div style={{ marginTop: '16px' }}>
					<TrendDataTable rows={MOCK_TABLE_DATA} />
				</div>
				<div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>투자 유형별 현황</span>
					<div style={{ display: 'flex', overflowX: 'auto', scrollbarWidth: 'none', borderBottom: '1px solid #2F3037' }}>
						{INVESTOR_TABS.map((tab) => (
							<button key={tab.value} onClick={() => setActiveTab(tab.value)} style={{ padding: '8px 16px', backgroundColor: 'transparent', border: 'none', borderBottom: activeTab === tab.value ? '2px solid #FFFFFF' : '2px solid transparent', cursor: 'pointer', fontSize: '14px', fontWeight: activeTab === tab.value ? 700 : 400, color: activeTab === tab.value ? '#FFFFFF' : '#9194A1', marginBottom: '-1px', whiteSpace: 'nowrap' }}>
								{tab.label}
							</button>
						))}
					</div>
					{activeTab === 'program' && <ProgramTable rows={MOCK_PROGRAM_DATA} />}
					{activeTab === 'credit'  && <CreditTable rows={MOCK_CREDIT_DATA} />}
					{activeTab === 'lending' && <LendingTable rows={MOCK_LENDING_DATA} />}
					{activeTab === 'short'   && <ShortTable rows={MOCK_SHORT_DATA} />}
					{activeTab === 'cfd'     && <CfdTable rows={MOCK_CFD_DATA} />}
				</div>
			</div>
		</div>
	);
}