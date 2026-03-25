export default function CompanyInfoSection() {
	return (
		<div className='bg-gray-600 p-8 flex flex-col gap-12 h-166.5 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]'>
			{/* 1. 상단: 타이틀 및 기업 설명 */}
			<div>
				<div className='flex justify-between items-center mb-6'>
					<div className='flex items-baseline gap-4'>
						<h2 className='text-3xl font-bold text-white'>기업명</h2>
						<span className='text-gray-400 text-sm'>
							국내 · 000000 · 코스피
						</span>
					</div>
					<button className='text-sm text-gray-300 flex items-center gap-1'>
						<span>홈페이지 ↗</span>
					</button>
				</div>
				{/* 설명 박스 (모서리 둥글기 제거) */}
				<div className='bg-gray-700 p-6 text-sm text-gray-200 leading-relaxed'>
					동사는 0000년 설립되어 00도 00시에 본사를 두고 있으며, 0개의
					생산기지와 0개의 연구개발법인, 다수의 해외 판매법인을 운영하는 000 000
					기업입니다.
				</div>
			</div>

			{/* 2. 중앙: 기업 정보 요약 표 */}
			<div className='grid grid-cols-2 gap-x-12 gap-y-6 text-sm'>
				<div className='flex justify-between pb-2 shadow-[0_1px_0_0_rgba(107,114,128,0.5)]'>
					<span className='font-bold text-white'>시가총액</span>
					<span className='text-gray-200'>000조 0000억 원</span>
				</div>
				<div className='flex justify-between pb-2 shadow-[0_1px_0_0_rgba(107,114,128,0.5)]'>
					<span className='font-bold text-white'>실제 기업 가치</span>
					<span className='text-gray-200'>000조 0000억 원</span>
				</div>
				<div className='flex justify-between pb-2 shadow-[0_1px_0_0_rgba(107,114,128,0.5)]'>
					<span className='font-bold text-white'>기업명</span>
					<span className='text-gray-200'>Company Name</span>
				</div>
				<div className='flex justify-between pb-2 shadow-[0_1px_0_0_rgba(107,114,128,0.5)]'>
					<span className='font-bold text-white'>대표이사</span>
					<span className='text-gray-200'>이00, 김00</span>
				</div>
				<div className='flex justify-between items-center pb-2 shadow-[0_1px_0_0_rgba(107,114,128,0.5)]'>
					<span className='font-bold text-white'>상장일</span>
					<div className='text-right'>
						<div className='text-gray-200'>0000년 00월 00일</div>
						<div className='text-xs text-gray-400'>0000년 00월 00일 기준</div>
					</div>
				</div>
				<div className='flex justify-between items-center pb-2 shadow-[0_1px_0_0_rgba(107,114,128,0.5)]'>
					<span className='font-bold text-white'>발행주식수</span>
					<div className='text-right'>
						<div className='text-gray-200'>000,000,000주</div>
						<div className='text-xs text-gray-400'>0000년 00월 00일 기준</div>
					</div>
				</div>
			</div>

			{/* 3. 하단: 매출/산업 구성 (도넛 차트 영역) */}
			<div>
				<h3 className='text-xl font-bold text-white mb-2'>매출·산업 구성</h3>
				<p className='text-xs text-gray-400 mb-6'>
					0000년 00월 기준 (출처: Reference)
				</p>
				<div className='bg-gray-700 p-8 flex items-center gap-12'>
					{/* 도넛 차트 플레이스홀더 */}
					<div className='w-48 h-48 bg-gray-500 flex items-center justify-center'>
						<span className='text-gray-300 text-sm'>도넛 차트 영역</span>
					</div>

					{/* 범례 (Legend) */}
					<div className='flex flex-col gap-4 text-sm'>
						<div className='flex items-center gap-3'>
							<div className='w-3 h-3 bg-blue-400'></div>
							<span className='text-gray-200'>
								TV, 모니터, 냉장고, 세탁기 등
							</span>
							<span className='text-gray-400 text-xs ml-2'>00.00%</span>
						</div>
						<div className='flex items-center gap-3'>
							<div className='w-3 h-3 bg-purple-400'></div>
							<span className='text-gray-200'>스마트폰용 OLED패널 등</span>
							<span className='text-gray-400 text-xs ml-2'>00.00%</span>
						</div>
						<div className='flex items-center gap-3'>
							<div className='w-3 h-3 bg-yellow-400'></div>
							<span className='text-gray-200'>범례 3</span>
							<span className='text-gray-400 text-xs ml-2'>00.00%</span>
						</div>
						<div className='flex items-center gap-3'>
							<div className='w-3 h-3 bg-green-400'></div>
							<span className='text-gray-200'>범례 4</span>
							<span className='text-gray-400 text-xs ml-2'>00.00%</span>
						</div>
					</div>
				</div>
			</div>

			{/* 4. 최하단: 주요 사업 */}
			<div>
				<h3 className='text-xl font-bold text-white mb-6'>주요 사업</h3>
				<div className='grid grid-cols-2 gap-8'>
					{[1, 2, 3, 4].map((num) => (
						<div key={num} className='flex items-center gap-4'>
							{/* 아이콘 플레이스홀더 */}
							<div className='w-14 h-14 bg-gray-500'></div>
							<div>
								<div className='font-bold text-white text-base mb-1'>
									사업명 {num}
								</div>
								<div className='text-sm text-gray-400'>시가총액 0위</div>
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}
