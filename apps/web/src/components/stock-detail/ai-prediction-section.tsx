export default function AIPredictionSection() {
	return (
		<div className='bg-gray-600 p-4 h-166.5 flex flex-col'>
			<div className='flex justify-between items-center mb-4'>
				<h3 className='font-bold text-gray-200'>AI 가격 예측 패널</h3>
				<button className='text-xs  px-2 py-1 rounded text-gray-300'>
					매수하기
				</button>
			</div>

			{/* 기간 탭 */}
			<div className='flex rounded-lg p-1 mb-4'>
				<button className='flex-1 py-1 text-white border text-sm'>1주</button>
				<button className='flex-1 py-1 text-gray-500 text-sm hover:text-gray-300'>
					1개월
				</button>
				<button className='flex-1 py-1 text-gray-500 text-sm hover:text-gray-300'>
					3개월
				</button>
			</div>

			{/* 예측 차트 영역 */}
			<div className='h-32  mb-4 flex items-center justify-center'>
				<span className='text-gray-600 text-sm'>예측 라인 차트 영역</span>
			</div>

			{/* 예측가 정보 */}
			<div className='mb-6'>AI 예측가</div>

			{/* 방향성 확률 (프로그레스 바) */}
			<div className='mb-8'>방향성 확률</div>

			{/* 분석 근거 */}
			<div className='flex-1'>
				<p className='text-sm mb-3'>분석 근거</p>
				<div className='flex gap-2 mb-4 pb-2'>
					<span className='text-sm'>기술적 지표</span>
					<span className='text-sm px-2'>시장 심리</span>
					<span className='text-sm px-2'>수급 동향</span>
				</div>

				<div className='flex flex-col gap-2 text-sm'>분석근거 영역</div>
			</div>
		</div>
	);
}
