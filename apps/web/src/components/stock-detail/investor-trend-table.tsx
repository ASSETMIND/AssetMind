export default function InvestorTrendTable() {
	// 하단 데이터 표 더미 데이터
	const tableData = [
		{
			date: '26년 3월 27일',
			price: '906,000원',
			rate: '-2.89%',
			amt: '-27,000원',
			retail: '+1,175,058주',
			foreign: '-1,336,696주',
			ratio: '53.05%',
			inst: '+141,266주',
		},
		{
			date: '26년 3월 26일',
			price: '933,000원',
			rate: '-6.23%',
			amt: '-62,000원',
			retail: '+1,575,366주',
			foreign: '-1,066,233주',
			ratio: '53.21%',
			inst: '-518,790주',
		},
		{
			date: '26년 3월 25일',
			price: '995,000원',
			rate: '+0.91%',
			amt: '+9,000원',
			retail: '-445,778주',
			foreign: '-375,419주',
			ratio: '53.35%',
			inst: '+846,742주',
		},
		{
			date: '26년 3월 24일',
			price: '986,000원',
			rate: '+5.68%',
			amt: '+53,000원',
			retail: '-418,860주',
			foreign: '-207,539주',
			ratio: '53.41%',
			inst: '+648,654주',
		},
		{
			date: '26년 3월 23일',
			price: '933,000원',
			rate: '-7.34%',
			amt: '-74,000원',
			retail: '+1,589,460주',
			foreign: '-152,891주',
			ratio: '53.43%',
			inst: '-1,526,039주',
		},
		{
			date: '26년 3월 20일',
			price: '1,007,000원',
			rate: '-0.59%',
			amt: '-6,000원',
			retail: '+761,183주',
			foreign: '-755,169주',
			ratio: '53.45%',
			inst: '-37,309주',
		},
		{
			date: '26년 3월 19일',
			price: '1,013,000원',
			rate: '-4.07%',
			amt: '-43,000원',
			retail: '+935,842주',
			foreign: '-696,577주',
			ratio: '53.55%',
			inst: '-286,381주',
		},
		{
			date: '26년 3월 18일',
			price: '1,056,000원',
			rate: '+8.86%',
			amt: '+86,000원',
			retail: '-1,626,652주',
			foreign: '+676,686주',
			ratio: '53.63%',
			inst: '+998,808주',
		},
	];

	const formatColor = (val: string) => {
		if (val.startsWith('+')) return 'text-red-500';
		if (val.startsWith('-')) return 'text-blue-500';
		return 'text-gray-200';
	};

	return (
		<div className='flex flex-col text-sm mt-4 bg-gray-800/40 overflow-hidden'>
			<div className='grid grid-cols-8 gap-4 px-4 py-4 text-gray-400 text-xs font-medium sticky top-0 z-20'>
				<span className='text-left'>일자</span>
				<span className='text-right'>종가</span>
				<span className='text-right'>등락률</span>
				<span className='text-right'>등락금액</span>
				<span className='text-right'>개인 순매수</span>
				<span className='text-right'>외국인 순매수</span>
				<span className='text-right'>외국인 지분율</span>
				<span className='text-right'>기관 순매수</span>
			</div>

			<div className='max-h-75 overflow-y-auto [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent'>
				{tableData.map((row, index) => (
					<div
						key={index}
						className='grid grid-cols-8 gap-4 px-4 py-4 transition-colors items-center'
					>
						<span className='text-left text-gray-300'>{row.date}</span>
						<span className='text-right text-gray-200'>{row.price}</span>
						<span className={`text-right font-medium ${formatColor(row.rate)}`}>
							{row.rate}
						</span>
						<span className={`text-right font-medium ${formatColor(row.amt)}`}>
							{row.amt}
						</span>
						<span
							className={`text-right font-medium ${formatColor(row.retail)}`}
						>
							{row.retail}
						</span>
						<span
							className={`text-right font-medium ${formatColor(row.foreign)}`}
						>
							{row.foreign}
						</span>
						<span className='text-right text-gray-200'>{row.ratio}</span>
						<span className={`text-right font-medium ${formatColor(row.inst)}`}>
							{row.inst}
						</span>
					</div>
				))}
			</div>
		</div>
	);
}
