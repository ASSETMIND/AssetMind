import { useState } from 'react';
import { useParams } from 'react-router-dom';
import ChartSection from '../components/stock-detail/chart-section';
import OrderbookSection from '../components/stock-detail/orderbook-section';
import AIPredictionSection from '../components/stock-detail/ai-prediction-section';
import CombinedTradeInfoSection from '../components/stock-detail/combine-trade-info-section';
import CompanyNavSection from '../components/stock-detail/company-nav-section';
import CompanyInfoSection from '../components/stock-detail/company-info-section';
import StockHeaderCard from '../components/stock-detail/stock-header-card';

type TabType = 'chart' | 'info' | 'trade';

const TABS: { value: TabType; label: string }[] = [
	{ value: 'chart', label: '차트·호가' },
	{ value: 'info',  label: '종목정보' },
	{ value: 'trade', label: '거래현황' },
];

export default function StockDetailPage() {
	const { id: stockCode } = useParams<{ id: string }>();
	const [activeTab, setActiveTab] = useState<TabType>('chart');

	return (
		<div className='w-full min-h-screen text-gray-200'>
			<div className='max-w-[1400px] mx-auto px-4'>
				<div className='pt-10'>
					{/* 종목 헤더 */}
					<StockHeaderCard />

					{/* 탭 */}
					<div className='flex gap-8 pt-6 pb-2 border-b border-gray-800'>
						{TABS.map((tab) => (
							<button
								key={tab.value}
								onClick={() => setActiveTab(tab.value)}
								style={{
									background: 'none',
									border: 'none',
									cursor: 'pointer',
									paddingBottom: '8px',
									fontSize: '16px',
									fontWeight: activeTab === tab.value ? 700 : 400,
									color: activeTab === tab.value ? '#FFFFFF' : '#9194A1',
									borderBottom: activeTab === tab.value
										? '2px solid #FFFFFF'
										: '2px solid transparent',
									transition: 'color 0.15s, border-color 0.15s',
								}}
							>
								{tab.label}
							</button>
						))}
					</div>
				</div>

				{/* 탭 콘텐츠 */}
				<div className='w-full mt-6'>

					{/* ── 차트·호가 탭 ── */}
					{activeTab === 'chart' && (
						<div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
							{/* 차트 — 나머지 공간 */}
							<div style={{ flex: 1, minWidth: 0 }}>
								<ChartSection />
							</div>
							{/* 호가창 — 340px 고정 */}
							<div style={{ flexShrink: 0 }}>
								<OrderbookSection />
							</div>
							{/* AI 예측 — 340px 고정 */}
							<div style={{ flexShrink: 0 }}>
								<AIPredictionSection />
							</div>
						</div>
					)}

					{/* ── 종목정보 탭 ── */}
					{activeTab === 'info' && (
						<div className='grid grid-cols-12 gap-4'>
							<div className='col-span-12 md:col-span-3 xl:col-span-2'>
								<CompanyNavSection />
							</div>
							<div className='col-span-12 md:col-span-9 xl:col-span-7 flex flex-col gap-4'>
								<CompanyInfoSection />
							</div>
							<div className='col-span-12 xl:col-span-3'>
								<AIPredictionSection />
							</div>
						</div>
					)}

					{/* ── 거래현황 탭 ── */}
					{activeTab === 'trade' && (
						<div className='grid grid-cols-12 gap-4'>
							<div className='col-span-12 xl:col-span-9 flex flex-col gap-4'>
								<CombinedTradeInfoSection />
							</div>
							<div className='col-span-12 xl:col-span-3'>
								<AIPredictionSection />
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}