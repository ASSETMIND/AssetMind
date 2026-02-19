// 테이블의 헤더를 담당
export default function TableHeader() {
	return (
		<div className='grid grid-cols-[2.5fr_1fr_1fr_1fr_1.2fr] gap-4 py-3 text-sm'>
			<div className='pl-2'>순위 · 오늘 13:25 기준</div>
			<div className='text-right'>현재가</div>
			<div className='text-right'>등락률</div>
			<div className='text-right'>거래대금 순</div>
			<div className='text-right pr-2'>증권 거래 비율 ⓘ</div>
		</div>
	);
}
