/*
	매매동향
 */
export default function CombinedTradeInfoSection() {
	return (
		<div className='bg-gray-600 p-6 flex flex-col gap-16 h-166.5 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]'>
			<div className='flex flex-col'>
				{/* 헤더 영역 */}
				<div className='flex justify-between items-end mb-8'>
					<div>
						<h3 className='font-bold text-white text-lg mb-1'>
							거래원 매매 상위
						</h3>
						<p className='text-sm text-gray-300'>
							거래소에서 제공하는 주요 거래원의 실시간 데이터입니다.
						</p>
					</div>
					<div className='text-xs text-gray-300'>기준 : 0000.00.00 00:00</div>
				</div>

				{/* 매수/매도 리스트 영역 */}
				<div className='flex gap-8 text-gray-200'>
					{/* 매수 상위 5 */}
					<div className='flex-1 flex flex-col'>
						<div className='font-bold text-white mb-4'>매수 상위 5</div>
						<div className='h-32 flex items-center justify-center'>
							매수 상위 리스트 목업 영역
						</div>
					</div>

					{/* 매도 상위 5 */}
					<div className='flex-1 flex flex-col'>
						<div className='font-bold text-white mb-4'>매도 상위 5</div>
						<div className='h-32 flex items-center justify-center'>
							매도 상위 리스트 목업 영역
						</div>
					</div>
				</div>
			</div>

			<div className='flex flex-col'>
				{/* 헤더 영역 */}
				<div className='mb-6'>
					<h3 className='font-bold text-white text-lg mb-1'>
						투자자별 매매 동향
					</h3>
					<p className='text-sm text-gray-300'>
						외국인 순매수량은 장외거래를 포함한 매매수량입니다.
					</p>
				</div>

				{/* 필터 및 기준시간 영역 */}
				<div className='flex justify-between items-end mb-6'>
					<div className='flex gap-4 text-sm text-gray-200'>
						<span className='cursor-pointer'>일별 ▾</span>
						<span className='cursor-pointer'>1주일 ▾</span>
					</div>
					<div className='flex flex-col items-end gap-2'>
						<span className='text-xs text-gray-300'>
							기준 : 0000.00.00 00:00
						</span>
						<button className='text-white bg-gray-500 px-3 py-1 text-sm'>
							투자자별 순매수 보기
						</button>
					</div>
				</div>

				{/* 차트 영역 */}
				<div className='h-60 flex items-center justify-center text-gray-200 mb-6'>
					투자자별 매매 동향 선 차트 목업 영역
				</div>

				{/* 하단 데이터 표 영역 */}
				<div className='h-12 flex items-center justify-center text-gray-300 text-sm'>
					일자 / 종가 / 등락률 / 등락금액 / 개인 순매수 등 데이터 표 영역
				</div>
			</div>
		</div>
	);
}
