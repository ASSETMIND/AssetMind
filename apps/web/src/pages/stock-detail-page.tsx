import { useState } from 'react';
import { useParams } from 'react-router-dom';
import ChartSection from '../components/stock-detail/chart-section';
import OrderbookSection from '../components/stock-detail/orderbook-section';
import AIPredictionSection from '../components/stock-detail/ai-prediction-section';
import CombinedTradeInfoSection from '../components/stock-detail/combine-trade-info-section';
import CompanyNavSection from '../components/stock-detail/company-nav-section';
import CompanyInfoSection from '../components/stock-detail/company-info-section';
import StockHeaderCard from '../components/stock-detail/stock-header-card';
import ErrorBoundary from '../components/common/error-boundary';
import { useViewport } from '../hooks/common/use-viewport';

// ─── 탭 정의 ──────────────────────────────────────────────────

type TabType = 'chart' | 'info' | 'trade' | 'ai';

// 데스크톱/태블릿: 3탭 (AI는 각 탭에 사이드로 표시)
const TABS_DESKTOP: { value: TabType; label: string }[] = [
	{ value: 'chart', label: '차트·호가' },
	{ value: 'info',  label: '종목정보' },
	{ value: 'trade', label: '거래현황' },
];

// 모바일: 4탭 (AI 별도 탭)
const TABS_MOBILE: { value: TabType; label: string }[] = [
	{ value: 'chart', label: '차트·호가' },
	{ value: 'info',  label: '종목정보' },
	{ value: 'trade', label: '거래현황' },
	{ value: 'ai',    label: 'AI 예측' },
];

// ─── StockDetailPage ───────────────────────────────────────────

export default function StockDetailPage() {
	const { id: stockCode } = useParams<{ id: string }>();
	const [activeTab, setActiveTab] = useState<TabType>('chart');
	const viewport = useViewport();
	const isMobile = viewport === 'mobile';
	const isTablet = viewport === 'tablet';

	const tabs = isMobile ? TABS_MOBILE : TABS_DESKTOP;

	return (
		<div className='w-full min-h-screen text-gray-200'>
			<div style={{
				maxWidth: isMobile || isTablet ? '100%' : '1400px',
				margin: '0 auto',
				padding: isMobile ? '0 12px' : '0 16px',
			}}>
				<div style={{ paddingTop: isMobile ? '16px' : '40px' }}>
					{/* 종목 헤더 */}
					<StockHeaderCard />

					{/* 탭 */}
					<div style={{
						display: 'flex',
						gap: isMobile ? '12px' : '32px',
						paddingTop: '16px',
						paddingBottom: '8px',
						borderBottom: '1px solid #2F3037',
						overflowX: 'auto',
						scrollbarWidth: 'none',
					}}>
						{tabs.map((tab) => (
							<button
								key={tab.value}
								onClick={() => setActiveTab(tab.value)}
								style={{
									background: 'none',
									border: 'none',
									cursor: 'pointer',
									paddingBottom: '8px',
									fontSize: isMobile ? '14px' : '16px',
									fontWeight: activeTab === tab.value ? 700 : 400,
									color: activeTab === tab.value ? '#FFFFFF' : '#9194A1',
									borderBottom: activeTab === tab.value
										? '2px solid #FFFFFF'
										: '2px solid transparent',
									transition: 'color 0.15s, border-color 0.15s',
									whiteSpace: 'nowrap',
									flexShrink: 0,
								}}
							>
								{tab.label}
							</button>
						))}
					</div>
				</div>

				{/* 탭 콘텐츠 */}
				<div style={{ width: '100%', marginTop: '16px' }}>

					{/* ── 차트·호가 탭 ── */}
					{activeTab === 'chart' && (
						<>
							{/* 데스크톱 */}
							{!isMobile && !isTablet && (
								<div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
									<div style={{ flex: 1, minWidth: 0 }}>
										<ErrorBoundary><ChartSection /></ErrorBoundary>
									</div>
									<div style={{ flexShrink: 0 }}>
										<ErrorBoundary><OrderbookSection /></ErrorBoundary>
									</div>
									<div style={{ flexShrink: 0 }}>
										<ErrorBoundary><AIPredictionSection /></ErrorBoundary>
									</div>
								</div>
							)}
							{/* 태블릿 */}
							{isTablet && (
								<div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
									<div style={{ flex: 1, minWidth: 0 }}>
										<ErrorBoundary><ChartSection /></ErrorBoundary>
									</div>
									<div style={{ width: '300px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '16px' }}>
										<ErrorBoundary><OrderbookSection /></ErrorBoundary>
										<ErrorBoundary><AIPredictionSection /></ErrorBoundary>
									</div>
								</div>
							)}
							{/* 모바일: 차트 + 호가만 (AI는 별도 탭) */}
							{isMobile && (
								<div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
									<ErrorBoundary><ChartSection /></ErrorBoundary>
									<ErrorBoundary><OrderbookSection /></ErrorBoundary>
								</div>
							)}
						</>
					)}

					{/* ── 종목정보 탭 ── */}
					{activeTab === 'info' && (
						<>
							{!isMobile ? (
								<div className='grid grid-cols-12 gap-4'>
									<div className={isTablet ? 'col-span-12' : 'col-span-2'}>
										<ErrorBoundary><CompanyNavSection /></ErrorBoundary>
									</div>
									<div className={isTablet ? 'col-span-12' : 'col-span-7'}>
										<ErrorBoundary><CompanyInfoSection /></ErrorBoundary>
									</div>
									{!isTablet && (
										<div className='col-span-3'>
											<ErrorBoundary><AIPredictionSection /></ErrorBoundary>
										</div>
									)}
								</div>
							) : (
								<div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
									<ErrorBoundary><CompanyNavSection /></ErrorBoundary>
									<ErrorBoundary><CompanyInfoSection /></ErrorBoundary>
								</div>
							)}
						</>
					)}

					{/* ── 거래현황 탭 ── */}
					{activeTab === 'trade' && (
						<>
							{!isMobile ? (
								<div className='grid grid-cols-12 gap-4'>
									<div className={isTablet ? 'col-span-12' : 'col-span-9'}>
										<ErrorBoundary><CombinedTradeInfoSection /></ErrorBoundary>
									</div>
									{!isTablet && (
										<div className='col-span-3'>
											<ErrorBoundary><AIPredictionSection /></ErrorBoundary>
										</div>
									)}
								</div>
							) : (
								<ErrorBoundary><CombinedTradeInfoSection /></ErrorBoundary>
							)}
						</>
					)}

					{/* ── AI 예측 탭 (모바일 전용) ── */}
					{activeTab === 'ai' && isMobile && (
						<ErrorBoundary><AIPredictionSection /></ErrorBoundary>
					)}
				</div>
			</div>
		</div>
	);
}