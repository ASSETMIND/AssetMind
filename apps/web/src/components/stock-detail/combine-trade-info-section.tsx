import TopTradingBrokers from './top-trading-brokers';
import InvestorTrendTable from './investor-trend-table';

export default function CombinedTradeInfoSection() {
	// SVG 차트 좌표 및 레이블 데이터
	const personalPoints = '0,75 100,125 200,15 300,150 400,100';
	const foreignerPoints = '0,35 100,150 200,25 300,150 400,150';
	const institutionPoints = '0,50 100,65 200,35 300,50 400,25';

	const yAxisLabels = [
		'15,000,000',
		'10,000,000',
		'5,000,000',
		'0',
		'-5,000,000',
		'-10,000,000',
		'-15,000,000',
		'-20,000,000',
		'-25,000,000',
	];
	const xAxisLabels = ['00.00', '00.00', '00.00', '00.00', '00.00'];

	return (
		<div className='bg-gray-600 p-6 flex flex-col gap-16 h-166.5 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]'>
			{/* 거래원 매매 상위 */}
			<TopTradingBrokers />

			{/* 투자자별 매매 동향 */}
			<div className='flex flex-col'>
				<div className='mb-6'>
					<h3 className='font-bold text-white text-lg mb-1'>
						투자자별 매매 동향
					</h3>
					<p className='text-sm text-gray-300'>
						외국인 순매수량은 장외거래를 포함한 매매수량입니다.
					</p>
				</div>

				<div className='flex justify-between items-end mb-8'>
					<div className='flex flex-col gap-4'>
						<div className='flex gap-2 text-sm text-gray-200'>
							<span className='cursor-pointer bg-gray-700/50 px-3 py-1 rounded hover:text-white transition-colors'>
								일별 ▾
							</span>
							<span className='cursor-pointer bg-gray-700/50 px-3 py-1 rounded hover:text-white transition-colors'>
								1주일 ▾
							</span>
						</div>
						<div className='flex gap-4 text-xs text-gray-300 pl-1'>
							<div className='flex items-center gap-1.5'>
								<div className='w-2 h-2 rounded-full bg-yellow-500'></div>
								<span>개인</span>
							</div>
							<div className='flex items-center gap-1.5'>
								<div className='w-2 h-2 rounded-full bg-blue-500'></div>
								<span>외국인</span>
							</div>
							<div className='flex items-center gap-1.5'>
								<div className='w-2 h-2 rounded-full bg-purple-500'></div>
								<span>기관</span>
							</div>
						</div>
					</div>
					<div className='flex flex-col items-end gap-2'>
						<span className='text-xs text-gray-300'>
							기준 : 0000.00.00 00:00
						</span>
						<button className='text-white border border-gray-400 hover:bg-gray-500 px-3 py-1 text-sm rounded transition-colors'>
							투자자별 순매수 보기
						</button>
					</div>
				</div>

				{/* 차트 영역 */}
				<div className='flex mb-8 h-64'>
					<div className='flex-1 relative'>
						<div className='absolute inset-0 flex flex-col justify-between z-0'>
							{yAxisLabels.map((_, i) => (
								<div
									key={i}
									className='w-full border-t border-gray-500/50'
								></div>
							))}
						</div>
						<svg
							viewBox='0 0 400 200'
							className='absolute inset-0 w-full h-full z-10'
							preserveAspectRatio='none'
						>
							<polyline
								points={personalPoints}
								fill='none'
								stroke='#eab308'
								strokeWidth='2'
							/>
							<polyline
								points={foreignerPoints}
								fill='none'
								stroke='#3b82f6'
								strokeWidth='2'
							/>
							<polyline
								points={institutionPoints}
								fill='none'
								stroke='#a855f7'
								strokeWidth='2'
							/>
						</svg>
						<div className='absolute top-full left-0 right-0 flex justify-between text-xs text-gray-400 mt-3'>
							{xAxisLabels.map((lbl, i) => (
								<span key={i}>{lbl}</span>
							))}
						</div>
					</div>
					<div className='w-24 flex flex-col justify-between items-end pl-4 text-xs text-gray-400 h-full'>
						{yAxisLabels.map((label, i) => (
							<span key={i} className='-translate-y-1/2 leading-none'>
								{label}
							</span>
						))}
					</div>
				</div>

				{/* 스크롤 가능 데이터 표 영역 */}
				<InvestorTrendTable />
			</div>
		</div>
	);
}
