// 랭킹 필터 버튼 그룹
export default function StockFilterGroup() {
	const wrapperClass = 'flex items-center rounded-xl bg-[#282932] p-1';
	const activeBtnClass =
		'rounded-lg bg-[#41434D] px-3 py-1.5 text-[13px] font-semibold text-white shadow-sm whitespace-nowrap';
	const inactiveBtnClass =
		'rounded-lg px-3 py-1.5 text-[13px] font-medium text-gray-400 transition-colors hover:text-gray-200 hover:bg-[#343540] whitespace-nowrap';

	return (
		<div className='flex gap-3 py-4 overflow-x-auto w-full scrollbar-hide'>
			{/* 지역 필터 */}
			<div className={wrapperClass}>
				<button className={activeBtnClass}>전체</button>
				<button className={inactiveBtnClass}>국내</button>
				<button className={inactiveBtnClass}>해외</button>
			</div>

			{/* 정렬 기준 필터 */}
			<div className={wrapperClass}>
				<button className={activeBtnClass}>증권 거래대금</button>
				<button className={inactiveBtnClass}>증권 거래량</button>
				<button className={inactiveBtnClass}>거래대금</button>
				<button className={inactiveBtnClass}>거래량</button>
				<button className={inactiveBtnClass}>급상승</button>
				<button className={inactiveBtnClass}>급하락</button>
			</div>

			{/* 시간 필터 */}
			<div className={wrapperClass}>
				<button className={activeBtnClass}>실시간</button>
				<button className={inactiveBtnClass}>1일</button>
				<button className={inactiveBtnClass}>1주일</button>
				<button className={inactiveBtnClass}>1개월</button>
				<button className={inactiveBtnClass}>3개월</button>
				<button className={inactiveBtnClass}>6개월</button>
				<button className={inactiveBtnClass}>1년</button>
			</div>
		</div>
	);
}
