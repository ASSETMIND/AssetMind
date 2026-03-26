/*
	각종 차트들 
*/
export default function ChartSection() {
	return (
		<>
			{/* 상단 캔들스틱 차트 영역 */}
			<div className='bg-gray-600 h-100 p-4 flex flex-col'>
				<div className='flex gap-4 text-sm text-gray-300 mb-4'>
					<span className='cursor-pointer'>1분</span>
					<span className='text-white font-bold cursor-pointer'>일</span>
					<span className='cursor-pointer'>주</span>
					<span className='cursor-pointer'>월</span>
					<span className='cursor-pointer'>년</span>
				</div>
				<div className='flex-1 flex items-center justify-center'>
					<span className='text-gray-200'>캔들스틱 및 거래량 차트 영역</span>
				</div>
			</div>

			{/* 하단 보조 지표 영역 */}
			<div className='bg-gray-600 h-62.5 p-4 flex items-center justify-center'>
				<span className='text-gray-200'>추가 정보 / 보조 지표 영역</span>
			</div>
		</>
	);
}
