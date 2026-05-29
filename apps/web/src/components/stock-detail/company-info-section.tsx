import { useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useViewport } from '../../hooks/common/use-viewport';
import { DonutChart } from '../stock-detail/donut-chart';
import type { DonutSlice } from '../stock-detail/donut-chart';
import { CategoryModal } from '../stock-detail/category-modal';
import type { CategoryModalProps } from '../stock-detail/category-modal';
import CompanyNavSection from './company-nav-section';

// ─── Types ────────────────────────────────────────────────────

export interface CompanyInfo {
	name: string;
	market: string;
	ticker: string;
	exchange: string;
	homepageUrl?: string;
	source?: string;
	description?: string;
	marketCap: string;
	enterpriseValue: string;
	companyName: string;
	ceo: string;
	listingDate: string;
	listingDateSub?: string;
	shares: string;
	sharesSub?: string;
}

export interface BusinessItem {
	id: string;
	name: string;
	marketCap: string;
	logoUrl?: string;
	modalProps?: Omit<CategoryModalProps, 'isOpen' | 'onClose'>;
}

// ─── Mock 데이터 (API 연동 전 임시) ──────────────────────────

const MOCK_COMPANY: CompanyInfo = {
	name: '기업명',
	market: '국내',
	ticker: '000000',
	exchange: '코스피',
	homepageUrl: '',
	source: 'Reference',
	description: '동사는 0000년 설립되어 00도 00시에 본사를 두고 있으며, 0개의 생산기지와 0개의 연구개발법인, 다수의 해외 판매법인을 운영하는 000 000 기업입니다.',
	marketCap: '000조 0000억 원',
	enterpriseValue: '000조 0000억 원',
	companyName: 'Company Name',
	ceo: '이00, 김00',
	listingDate: '0000년 00월 00일',
	listingDateSub: '0000년 00월 00일 기준',
	shares: '00,000,000,000주',
	sharesSub: '0000년 00월 00일 기준',
};

const MOCK_DONUT_SLICES: DonutSlice[] = [
	{ label: 'TV, 모니터, 냉장고, 세탁기 등', value: 40, color: '#256AF4' },
	{ label: '스마트폰 OLED패널 등',           value: 35, color: '#6D4AE6' },
	{ label: '범례 3',                          value: 25, color: '#22C55E' },
];

const MOCK_BUSINESSES: BusinessItem[] = [
	{ id: '1', name: '주요 사업 1', marketCap: '000조 원' },
	{ id: '2', name: '주요 사업 2', marketCap: '000조 원' },
	{ id: '3', name: '주요 사업 3', marketCap: '000조 원' },
	{ id: '4', name: '주요 사업 4', marketCap: '000조 원' },
];

// ─── 색상 ─────────────────────────────────────────────────────

const DIVIDER = 'rgba(255,255,255,0.20)';
const BOX_BG = '#21242C';

// ─── 서브 컴포넌트 ────────────────────────────────────────────

const SkeletonBox = ({ w = '100%', h = 14 }: { w?: number | string; h?: number }) => (
	<div style={{ width: w, height: `${h}px`, borderRadius: '4px', backgroundColor: BOX_BG, flexShrink: 0 }} />
);

const HomepageButton = ({ url }: { url?: string }) => (
	<button onClick={() => url && window.open(url, '_blank')} style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'none', border: '1px solid #2F3037', cursor: 'pointer', padding: '4px 8px', borderRadius: '4px', flexShrink: 0 }}>
		<svg width="14" height="14" viewBox="0 0 16 16" fill="none">
			<path d="M6.66667 3.33333H3.33333C2.97971 3.33333 2.64057 3.47381 2.39052 3.72386C2.14048 3.97391 2 4.31304 2 4.66667V12.6667C2 13.0203 2.14048 13.3594 2.39052 13.6095C2.64057 13.8595 2.97971 14 3.33333 14H11.3333C11.687 14 12.0261 13.8595 12.2761 13.6095C12.5262 13.3594 12.6667 13.0203 12.6667 12.6667V9.33333" stroke="#9F9F9F" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
			<path d="M9.33333 2H14V6.66667" stroke="#9F9F9F" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
			<path d="M6.66667 9.33333L14 2" stroke="#9F9F9F" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
		</svg>
		<span style={{ fontSize: '14px', fontWeight: 400, color: '#9F9F9F' }}>홈페이지</span>
	</button>
);

const InfoTable = ({ company, isMobile }: { company: CompanyInfo; isMobile: boolean }) => {
	const rows = [
		[{ label: '시가총액', value: company.marketCap, sub: undefined }, { label: '실제 기업 가치', value: company.enterpriseValue, sub: undefined }],
		[{ label: '기업명', value: company.companyName, sub: undefined }, { label: '대표이사', value: company.ceo, sub: undefined }],
		[{ label: '상장일', value: company.listingDate, sub: company.listingDateSub }, { label: '발행주식수', value: company.shares, sub: company.sharesSub }],
	];

	if (isMobile) {
		const cells = rows.flat();
		return (
			<div style={{ width: '100%' }}>
				{cells.map((cell, i) => (
					<div key={i}>
						<div style={{ height: '1px', backgroundColor: DIVIDER }} />
						<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '12px 0', gap: '8px' }}>
							<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1', flexShrink: 0 }}>{cell.label}</span>
							<div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
								<span style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', textAlign: 'right' }}>{cell.value}</span>
								{cell.sub && <span style={{ fontSize: '12px', fontWeight: 400, color: '#9194A1', textAlign: 'right' }}>{cell.sub}</span>}
							</div>
						</div>
					</div>
				))}
				<div style={{ height: '1px', backgroundColor: DIVIDER }} />
			</div>
		);
	}

	return (
		<div style={{ width: '100%' }}>
			{rows.map((row, ri) => (
				<div key={ri}>
					<div style={{ height: '1px', backgroundColor: DIVIDER }} />
					<div style={{ display: 'flex' }}>
						{row.map((cell, ci) => (
							<div key={ci} style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '12px 0', borderRight: ci === 0 ? `1px solid ${DIVIDER}` : 'none', paddingLeft: ci === 1 ? '24px' : 0, paddingRight: ci === 0 ? '24px' : 0, gap: '8px' }}>
								<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1', flexShrink: 0 }}>{cell.label}</span>
								<div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
									<span style={{ fontSize: '14px', fontWeight: 700, color: '#FFFFFF', textAlign: 'right' }}>{cell.value}</span>
									{cell.sub && <span style={{ fontSize: '12px', fontWeight: 400, color: '#9194A1', textAlign: 'right' }}>{cell.sub}</span>}
								</div>
							</div>
						))}
					</div>
				</div>
			))}
			<div style={{ height: '1px', backgroundColor: DIVIDER }} />
		</div>
	);
};

const BusinessItemCard = ({ item, onClick }: { item: BusinessItem; onClick?: () => void }) => (
	<div onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: onClick ? 'pointer' : 'default', padding: '8px 0' }}>
		<div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: BOX_BG, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
			{item.logoUrl ? <img src={item.logoUrl} alt={item.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <div style={{ width: '100%', height: '100%', backgroundColor: '#2F3037', borderRadius: '8px' }} />}
		</div>
		<div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
			<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>{item.name}</span>
			<span style={{ fontSize: '12px', fontWeight: 400, color: '#9194A1' }}>시가총액 {item.marketCap}</span>
		</div>
	</div>
);

const PlaceholderSection = ({ title }: { title: string }) => (
	<div style={{ marginTop: '12px', padding: '24px', backgroundColor: BOX_BG, borderRadius: '8px' }}>
		<span style={{ fontSize: '14px', color: '#9194A1' }}>{title} — 추후 구현 예정</span>
	</div>
);

// ─── CompanyInfoSection ───────────────────────────────────────

export default function CompanyInfoSection() {
	const { id: stockCode = '' } = useParams<{ id: string }>();
	const viewport = useViewport();
	const isMobile = viewport === 'mobile';

	const [activeTab, setActiveTab] = useState('main');
	const [showAll, setShowAll] = useState(false);
	const [modalOpen, setModalOpen] = useState(false);
	const [selectedBusiness, setSelectedBusiness] = useState<BusinessItem | null>(null);

	const scrollContainerRef = useRef<HTMLDivElement>(null);
	const sectionRefs: Record<string, React.RefObject<HTMLDivElement>> = {
		main:     useRef<HTMLDivElement>(null),
		finance:  useRef<HTMLDivElement>(null),
		result:   useRef<HTMLDivElement>(null),
		dividend: useRef<HTMLDivElement>(null),
		peer:     useRef<HTMLDivElement>(null),
		analyst:  useRef<HTMLDivElement>(null),
	};

	const handleTabClick = (id: string) => {
		setActiveTab(id);
		const ref = sectionRefs[id];
		if (ref?.current && scrollContainerRef.current) {
			const containerTop = scrollContainerRef.current.getBoundingClientRect().top;
			const sectionTop = ref.current.getBoundingClientRect().top;
			scrollContainerRef.current.scrollTop += sectionTop - containerTop - 24;
		}
	};

	const handleBusinessClick = (item: BusinessItem) => {
		if (item.modalProps) {
			setSelectedBusiness(item);
			setModalOpen(true);
		}
	};

	const company = MOCK_COMPANY;
	const donutSlices = MOCK_DONUT_SLICES;
	const businesses = MOCK_BUSINESSES;
	const displayedMain = businesses.slice(0, 6);

	return (
		<div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: '0', width: '100%', backgroundColor: '#1C1D21', borderRadius: '12px', overflow: 'hidden' }}>

			{/* 좌측 내비 — 모바일에서는 상단 수평 스크롤 탭으로 전환 */}
			{isMobile ? (
				<div style={{ display: 'flex', overflowX: 'auto', scrollbarWidth: 'none', borderBottom: '1px solid #2F3037', padding: '0 16px' }}>
					{['주요 정보', '재무', '실적', '배당', '동종 업계 비교', '애널리스트 분석'].map((label, i) => {
						const id = ['main', 'finance', 'result', 'dividend', 'peer', 'analyst'][i];
						return (
							<button key={id} onClick={() => handleTabClick(id)} style={{ flexShrink: 0, padding: '12px 16px', background: 'none', border: 'none', borderBottom: activeTab === id ? '2px solid #FFFFFF' : '2px solid transparent', cursor: 'pointer', fontSize: '14px', fontWeight: activeTab === id ? 700 : 400, color: activeTab === id ? '#FFFFFF' : '#9194A1', whiteSpace: 'nowrap' }}>
								{label}
							</button>
						);
					})}
				</div>
			) : (
				<div style={{ width: '200px', flexShrink: 0, borderRight: '1px solid #2F3037' }}>
					<CompanyNavSection activeTab={activeTab} onTabClick={handleTabClick} />
				</div>
			)}

			{/* 우측 콘텐츠 */}
			<div ref={scrollContainerRef} style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', scrollbarWidth: 'none', padding: isMobile ? '16px' : '24px 30px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '24px', minHeight: isMobile ? 'auto' : '820px', maxHeight: isMobile ? 'none' : '820px' }}>

				{/* 주요 정보 */}
				<div ref={sectionRefs.main} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
					<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
						<div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
							<div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
								<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>{company.name}</span>
								<span style={{ fontSize: '13px', fontWeight: 400, color: '#9194A1' }}>{company.market} · {company.ticker} · {company.exchange}</span>
							</div>
							{company.source && <span style={{ fontSize: '12px', fontWeight: 400, color: '#9194A1' }}>출처: {company.source}</span>}
						</div>
						<HomepageButton url={company.homepageUrl} />
					</div>
					{company.description && (
						<div style={{ backgroundColor: BOX_BG, borderRadius: '8px', padding: '16px', fontSize: '14px', fontWeight: 400, color: '#FFFFFF', lineHeight: '1.6' }}>
							{company.description}
						</div>
					)}
					<InfoTable company={company} isMobile={isMobile} />
				</div>

				{/* 매출·산업 구성 */}
				<div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
					<div>
						<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>매출·산업 구성</span>
						<div><span style={{ fontSize: '12px', fontWeight: 400, color: '#9194A1' }}>0000년 00월 기준 (출처: Reference)</span></div>
					</div>
					<div style={{ backgroundColor: BOX_BG, borderRadius: '8px', padding: '32px 24px', display: 'flex', alignItems: 'center', gap: '40px', flexWrap: 'wrap' }}>
						<DonutChart slices={donutSlices} size={152} />
						<div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
							{donutSlices.map((slice, i) => (
								<div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
									<div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: slice.color, flexShrink: 0 }} />
									<span style={{ fontSize: '14px', fontWeight: 400, color: '#FFFFFF' }}>{slice.label}</span>
									<span style={{ fontSize: '14px', fontWeight: 400, color: '#9194A1', marginLeft: '4px' }}>{slice.value.toFixed(2)}%</span>
								</div>
							))}
						</div>
					</div>
				</div>

				{/* 주요 사업 */}
				<div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>주요 사업</span>
					<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0px' }}>
						{displayedMain.map((item) => <BusinessItemCard key={item.id} item={item} onClick={() => handleBusinessClick(item)} />)}
					</div>
					{showAll && (
						<>
							<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF', marginTop: '8px' }}>그 외 사업</span>
							<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0px' }}>
								{MOCK_BUSINESSES.slice(6).map((item) => <BusinessItemCard key={item.id} item={item} onClick={() => handleBusinessClick(item)} />)}
							</div>
						</>
					)}
					<div style={{ display: 'flex', justifyContent: 'center', paddingTop: '8px' }}>
						<button onClick={() => setShowAll((v) => !v)} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: 'transparent', border: 'none', cursor: 'pointer', fontSize: '14px', fontWeight: 400, color: '#9194A1' }}>
							{showAll ? '접기 ▴' : '더 보기 ▾'}
						</button>
					</div>
				</div>

				{/* 재무 */}
				<div ref={sectionRefs.finance} style={{ paddingTop: '8px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>재무</span>
					<PlaceholderSection title="재무 데이터" />
				</div>

				{/* 실적 */}
				<div ref={sectionRefs.result} style={{ paddingTop: '8px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>실적</span>
					<PlaceholderSection title="실적 데이터" />
				</div>

				{/* 배당 */}
				<div ref={sectionRefs.dividend} style={{ paddingTop: '8px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>배당</span>
					<PlaceholderSection title="배당 데이터" />
				</div>

				{/* 동종 업계 비교 */}
				<div ref={sectionRefs.peer} style={{ paddingTop: '8px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>동종 업계 비교</span>
					<PlaceholderSection title="동종 업계 비교" />
				</div>

				{/* 애널리스트 분석 */}
				<div ref={sectionRefs.analyst} style={{ paddingTop: '8px' }}>
					<span style={{ fontSize: '18px', fontWeight: 700, color: '#FFFFFF' }}>애널리스트 분석</span>
					<PlaceholderSection title="애널리스트 분석" />
				</div>
			</div>

			{/* CategoryModal */}
			{selectedBusiness?.modalProps && (
				<CategoryModal
					isOpen={modalOpen}
					onClose={() => { setModalOpen(false); setSelectedBusiness(null); }}
					{...selectedBusiness.modalProps}
				/>
			)}
		</div>
	);
}