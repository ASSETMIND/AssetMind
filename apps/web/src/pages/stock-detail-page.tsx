import { useState } from 'react';
import { twMerge } from 'tailwind-merge';
import ChartSection from '../components/stock-detail/chart-section';
import OrderbookSection from '../components/stock-detail/orderbook-section';
import AIPredictionSection from '../components/stock-detail/ai-prediction-section';
import CombinedTradeInfoSection from '../components/stock-detail/combine-trade-info-section';
import CompanyNavSection from '../components/stock-detail/company-nav-section';
import CompanyInfoSection from '../components/stock-detail/company-info-section';
import StockHeaderCard from '../components/stock-detail/stock-header-card';

type TabType = '차트호가' | '종목정보' | '거래현황';

export default function StockDetailPage() {
	const [activeTab, setActiveTab] = useState<TabType>('차트호가');
	const tabs: TabType[] = ['차트호가', '종목정보', '거래현황'];

	return (
		<div className='w-full min-h-screen text-gray-200'>
			<div className='max-w-6xl mx-auto'>
				<div className='items-center pt-10'>
					<div>
						{/* 종목 카드 */}
						<StockHeaderCard />
						{/* 탭 네비게이션 */}
						<div className='pt-4'>
							{tabs.map((tab) => (
								<button
									key={tab}
									onClick={() => setActiveTab(tab)}
									className={twMerge(
										'pr-8 font-medium transition-colors',
										activeTab === tab
											? 'text-white'
											: 'text-gray-500 hover:text-gray-300',
									)}
								>
									{tab}
								</button>
							))}
						</div>
					</div>
				</div>

				{/* 탭 컨텐츠 영역 */}
				<div className='w-full mt-4'>
					{activeTab === '차트호가' && (
						<div className='grid grid-cols-12 gap-4'>
							<div className='col-span-12 xl:col-span-6 flex flex-col gap-4'>
								<ChartSection />
							</div>
							<div className='col-span-12 md:col-span-6 xl:col-span-3'>
								<OrderbookSection />
							</div>
							<div className='col-span-12 md:col-span-6 xl:col-span-3'>
								<AIPredictionSection />
							</div>
						</div>
					)}
					{activeTab === '종목정보' && (
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
					{activeTab === '거래현황' && (
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
