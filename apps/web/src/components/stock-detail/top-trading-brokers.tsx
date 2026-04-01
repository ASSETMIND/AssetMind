export default function TopTradingBrokers() {
	// 🌟 상단 매수/매도 상위 더미 데이터
	const buyTopList = [
		{ rank: 1, name: '삼성증권', volume: '416,095주', ratio: '100%' },
		{ rank: 2, name: '키움증권', volume: '412,968주', ratio: '95%' },
		{ rank: 3, name: 'KB증권', volume: '378,114주', ratio: '85%' },
		{ rank: 4, name: '미래에셋증권', volume: '364,072주', ratio: '80%' },
		{ rank: 5, name: 'BNK증권', volume: '287,197주', ratio: '60%' },
	];

	const sellTopList = [
		{ rank: 1, name: '모간서울', volume: '744,846주', ratio: '100%' },
		{ rank: 2, name: '골드만', volume: '342,419주', ratio: '50%' },
		{ rank: 3, name: 'KB증권', volume: '316,713주', ratio: '45%' },
		{ rank: 4, name: 'BNK증권', volume: '288,711주', ratio: '40%' },
		{ rank: 5, name: '씨엘', volume: '275,442주', ratio: '35%' },
	];

	return (
		<div className='flex flex-col'>
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

			<div className='flex gap-8 text-gray-200'>
				{/* 매수 상위 5 (빨간색) */}
				<div className='flex-1 flex flex-col'>
					<div className='font-bold text-white mb-6'>매수 상위 5</div>
					<div className='flex flex-col gap-3'>
						{buyTopList.map((item) => (
							<div key={item.rank} className='flex items-center text-sm'>
								<span className='w-8 text-gray-400'>{item.rank}</span>
								<span className='w-28 text-gray-200'>{item.name}</span>
								<div className='flex-1 relative h-8 flex items-center'>
									<div
										className='absolute inset-y-0 left-0 bg-red-500/20'
										style={{ width: item.ratio }}
									/>
									<span className='relative z-10 px-3 '>{item.volume}</span>
								</div>
							</div>
						))}
					</div>
				</div>

				{/* 매도 상위 5 (파란색) */}
				<div className='flex-1 flex flex-col'>
					<div className='font-bold text-white mb-6'>매도 상위 5</div>
					<div className='flex flex-col gap-3'>
						{sellTopList.map((item) => (
							<div key={item.rank} className='flex items-center text-sm'>
								<span className='w-8 text-gray-400'>{item.rank}</span>
								<span className='w-28 text-gray-200'>{item.name}</span>
								<div className='flex-1 relative h-8 flex items-center'>
									<div
										className='absolute inset-y-0 left-0 bg-blue-500/20 '
										style={{ width: item.ratio }}
									/>
									<span className='relative z-10 px-3 '>{item.volume}</span>
								</div>
							</div>
						))}
					</div>
				</div>
			</div>
		</div>
	);
}
