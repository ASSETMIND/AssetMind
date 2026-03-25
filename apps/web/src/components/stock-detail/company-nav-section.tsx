/*
	기업 상세정보 네브창
*/
export default function CompanyNavSection() {
	const navItems = [
		'주요 정보',
		'재무',
		'실적',
		'배당',
		'동종 업계 비교',
		'애널리스트 분석',
	];

	return (
		<div className='bg-gray-600 p-4 flex flex-col gap-2 min-h-166.5'>
			{navItems.map((item, idx) => (
				<button
					key={item}
					className={`p-4 text-left ${
						idx === 0
							? 'bg-gray-700 text-white font-bold'
							: 'text-gray-300 hover:text-white'
					}`}
				>
					{item}
				</button>
			))}
		</div>
	);
}
