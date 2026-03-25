export default function OrderbookSection() {
	return (
		<div className='bg-gray-600 p-4 h-166.5 flex flex-col'>
			<div className='flex justify-between items-center mb-4'>
				<h3 className='font-bold text-gray-200'>호가</h3>
				<button className='text-xs px-2 py-1 text-gray-300 border'>
					빠른 주문
				</button>
			</div>

			{/* 호가 리스트 영역 */}
			<div className='flex-1 flex flex-col text-sm items-center justify-center'>
				호가리스트 영역
			</div>
		</div>
	);
}
