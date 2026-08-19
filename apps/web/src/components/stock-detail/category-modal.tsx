import { useState } from 'react';

export interface ReturnCard {
	label: string;
	value: string;
	isRise: boolean;
}

export interface MiniChartPoint {
	value: number;
}

export interface StockListItem {
	id: string;
	name: string;
	logoUrl?: string;
	chartData: MiniChartPoint[];
	currentPrice: string;
	changeRate: string;
	isRise: boolean | null;
}

export interface EtfItem {
	id: string;
	name: string;
	logoUrl?: string;
	currentPrice: string;
	changeRate: string;
	isRise: boolean | null;
}

export interface CategoryModalProps {
	isOpen: boolean;
	onClose: () => void;
	categoryName: string;
	categorySubtitle?: string;
	heroImageUrl?: string;
	returnCards?: ReturnCard[];
	returnBaseLabel?: string;
	stockList?: StockListItem[];
	etfList?: EtfItem[];
}

type MetricTab = 'returns' | 'marketCap' | 'sales' | 'operatingProfit';
type RegionFilter = 'all' | 'domestic' | 'overseas';

const RISE = '#EA580C';
const FALL = '#256AF4';
const NEUTRAL = '#9194A1';
const BOX_BG = '#21242C';
const PANEL_BG = '#1C1D21';
const DIVIDER = 'rgba(255,255,255,0.10)';

const rateColor = (isRise: boolean | null) =>
	isRise === true ? RISE : isRise === false ? FALL : NEUTRAL;

const MiniLineChart = ({ data, isRise, width = 80, height = 32 }: { data: MiniChartPoint[]; isRise: boolean | null; width?: number; height?: number }) => {
	if (data.length < 2) return <div style={{ width, height }} />;
	const values = data.map((d) => d.value);
	const minV = Math.min(...values);
	const maxV = Math.max(...values);
	const range = maxV - minV || 1;
	const PAD = 2;
	const toX = (i: number) => PAD + (i / (data.length - 1)) * (width - PAD * 2);
	const toY = (v: number) => PAD + (1 - (v - minV) / range) * (height - PAD * 2);
	const points = data.map((d, i) => `${toX(i).toFixed(1)},${toY(d.value).toFixed(1)}`).join(' ');
	const color = isRise === true ? RISE : isRise === false ? FALL : NEUTRAL;
	return (
		<svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ flexShrink: 0 }}>
			<polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
		</svg>
	);
};

const RegionDropdown = ({ value, onChange }: { value: RegionFilter; onChange: (v: RegionFilter) => void }) => {
	const [open, setOpen] = useState(false);
	const labels: Record<RegionFilter, string> = { all: '국내+해외', domestic: '국내', overseas: '해외' };
	return (
		<div style={{ position: 'relative' }}>
			<button onClick={() => setOpen((v) => !v)} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: BOX_BG, border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: 400, color: '#FFFFFF' }}>
				{labels[value]}<span style={{ fontSize: '10px', color: NEUTRAL }}>▾</span>
			</button>
			{open && (
				<div style={{ position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 20, backgroundColor: '#21242C', border: `1px solid ${DIVIDER}`, borderRadius: '8px', overflow: 'hidden', minWidth: '100px' }}>
					{(['all', 'domestic', 'overseas'] as RegionFilter[]).map((opt) => (
						<button key={opt} onClick={() => { onChange(opt); setOpen(false); }} style={{ display: 'block', width: '100%', padding: '8px 14px', backgroundColor: opt === value ? '#2C2C30' : 'transparent', border: 'none', cursor: 'pointer', fontSize: '12px', fontWeight: 400, color: '#FFFFFF', textAlign: 'left' }}>
							{labels[opt]}
						</button>
					))}
				</div>
			)}
		</div>
	);
};

export const CategoryModal = ({ isOpen, onClose, categoryName, categorySubtitle = '0개 회사 · 0개 ETF', heroImageUrl, returnCards = [], returnBaseLabel = '기준 : 전일 종가', stockList = [], etfList = [] }: CategoryModalProps) => {
	const [activeMetric, setActiveMetric] = useState<MetricTab>('returns');
	const [regionFilter, setRegionFilter] = useState<RegionFilter>('all');

	if (!isOpen) return null;

	const METRIC_TABS: { label: string; value: MetricTab }[] = [
		{ label: '수익률', value: 'returns' },
		{ label: '시가총액', value: 'marketCap' },
		{ label: '매출', value: 'sales' },
		{ label: '영업이익률', value: 'operatingProfit' },
	];

	return (
		<div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 100, backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
			<div onClick={(e) => e.stopPropagation()} style={{ width: 'min(600px, calc(100vw - 32px))', maxHeight: '90dvh', backgroundColor: PANEL_BG, borderRadius: '16px', overflow: 'clip', display: 'flex', flexDirection: 'column', position: 'relative' }}>
				<button onClick={onClose} style={{ position: 'absolute', top: '16px', right: '16px', zIndex: 10, width: '32px', height: '32px', borderRadius: '50%', backgroundColor: 'rgba(0,0,0,0.3)', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
					<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M1 1L13 13M13 1L1 13" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round"/></svg>
				</button>
				<div style={{ height: '200px', flexShrink: 0, backgroundColor: '#3A3D45', position: 'relative', display: 'flex', alignItems: 'flex-end', padding: '24px', boxSizing: 'border-box', overflow: 'hidden' }}>
					{heroImageUrl && <img src={heroImageUrl} alt="" style={{ position: 'absolute', right: '24px', top: '50%', transform: 'translateY(-50%)', height: '140px', objectFit: 'contain' }} />}
					<div style={{ display: 'flex', flexDirection: 'column', gap: '4px', zIndex: 1 }}>
						<span style={{ fontSize: '12px', fontWeight: 400, color: 'rgba(255,255,255,0.7)' }}>지금 뜨는 카테고리 /</span>
						<span style={{ fontSize: '26px', fontWeight: 700, color: '#FFFFFF' }}>{categoryName}</span>
						<span style={{ fontSize: '13px', fontWeight: 400, color: 'rgba(255,255,255,0.7)' }}>{categorySubtitle}</span>
					</div>
				</div>
				<div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', scrollbarWidth: 'none', padding: '20px 24px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '24px' }}>
					<div style={{ display: 'flex', gap: '8px' }}>
						{METRIC_TABS.map((tab) => (
							<button key={tab.value} onClick={() => setActiveMetric(tab.value)} style={{ padding: '6px 16px', border: 'none', borderRadius: '20px', cursor: 'pointer', fontSize: '14px', fontWeight: activeMetric === tab.value ? 700 : 400, backgroundColor: activeMetric === tab.value ? BOX_BG : 'transparent', color: activeMetric === tab.value ? '#FFFFFF' : NEUTRAL, transition: 'background-color 0.15s' }}>
								{tab.label}
							</button>
						))}
					</div>
					<div style={{ display: 'flex', justifyContent: 'flex-end' }}>
						<span style={{ fontSize: '12px', fontWeight: 400, color: NEUTRAL }}>{returnBaseLabel}</span>
					</div>
					{returnCards.length > 0 && (
						<div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
							{returnCards.map((card, i) => (
								<div key={i} style={{ backgroundColor: BOX_BG, borderRadius: '12px', padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
									<span style={{ fontSize: '12px', fontWeight: 400, color: NEUTRAL }}>{card.label}</span>
									<span style={{ fontSize: '20px', fontWeight: 700, color: rateColor(card.isRise), fontVariantNumeric: 'tabular-nums' }}>{card.value}</span>
								</div>
							))}
						</div>
					)}
					<div style={{ display: 'flex', flexDirection: 'column', gap: '0px' }}>
						<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '8px' }}>
							<RegionDropdown value={regionFilter} onChange={setRegionFilter} />
							<div style={{ display: 'flex', gap: '32px' }}>
								<span style={{ fontSize: '12px', fontWeight: 400, color: NEUTRAL, width: '80px', textAlign: 'center' }}>차트</span>
								<span style={{ fontSize: '12px', fontWeight: 400, color: NEUTRAL, width: '60px', textAlign: 'right' }}>현재가</span>
								<span style={{ fontSize: '12px', fontWeight: 400, color: NEUTRAL, width: '60px', textAlign: 'right' }}>어제보다</span>
							</div>
						</div>
						{stockList.map((stock) => (
							<div key={stock.id} style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderTop: `1px solid ${DIVIDER}` }}>
								<div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
									<div style={{ width: '32px', height: '32px', borderRadius: '50%', backgroundColor: BOX_BG, flexShrink: 0, overflow: 'hidden' }}>
										{stock.logoUrl && <img src={stock.logoUrl} alt={stock.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
									</div>
									<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>{stock.name}</span>
								</div>
								<div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
									<MiniLineChart data={stock.chartData} isRise={stock.isRise} width={80} height={32} />
									<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF', width: '60px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{stock.currentPrice}</span>
									<span style={{ fontSize: '14px', fontWeight: 400, color: rateColor(stock.isRise), width: '60px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{stock.changeRate}</span>
								</div>
							</div>
						))}
					</div>
				</div>
			</div>
		</div>
	);
};

export default CategoryModal;