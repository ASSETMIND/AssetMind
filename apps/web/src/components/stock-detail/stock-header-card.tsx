export default function StockHeaderCard() {
	return (
		<div className='flex items-center gap-3 pr-8'>
			<div className='w-12 h-12 bg-gray-300 rounded-lg shrink-0' />

			{/* 텍스트 정보 영역 */}
			<div className='flex flex-col justify-center'>
				{/* 종목명 및 종목코드 */}
				<div className='flex items-baseline gap-2'>
					<h1 className='text-lg font-bold text-white'>종목명</h1>
					<span className='text-sm text-gray-400'>000000</span>
				</div>

				{/* 가격 및 등락률 정보 */}
				<div className='flex items-baseline gap-1.5'>
					<span className='text-xl font-bold text-white tracking-tight'>
						00,000원
					</span>
					<span className='text-xs text-gray-400'>어제보다</span>
					<span className='text-xs font-medium text-orange-500'>
						+00,000원 (00.00%)
					</span>
				</div>
			</div>
		</div>
	);
}
