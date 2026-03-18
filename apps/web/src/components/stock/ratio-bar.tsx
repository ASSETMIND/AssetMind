import { memo } from 'react';

interface Props {
	buy: number;
	sell: number;
}

// 매수, 매도 비율 시각화 바
function RatioBar({ buy, sell }: Props) {
	return (
		<div className='flex flex-col gap-1 w-full max-w-30'>
			{/* 바 그래프 영역 */}
			<div className='flex h-1.5 w-full overflow-hidden rounded-full bg-gray-200'>
				<div className='bg-blue-500' style={{ width: `${buy}%` }} />
				<div className='bg-red-500' style={{ width: `${sell}%` }} />
			</div>
			{/* 텍스트 수치 영역 */}
			<div className='flex w-full justify-between text-[11px] text-gray-400'>
				<span className='text-blue-500'>{buy}</span>
				<span className='text-red-500'>{sell}</span>
			</div>
		</div>
	);
}

export default memo(RatioBar);
