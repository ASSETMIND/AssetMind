import { useState } from 'react';
import { useCandlestickChart } from '../../hooks/stock-detail/use-candlestick-chart';

type TimeFrame = '1분' | '일' | '주' | '월' | '년';
const TABS: TimeFrame[] = ['1분', '일', '주', '월', '년'];

// 더미 데이터 정의
const MOCK_DATA: Record<TimeFrame, any[]> = {
	'1분': [
		// 1분봉처럼 장중 시간 단위 데이터 (Unix Timestamp 사용: 초 단위)
		{ time: 1711670400, open: 80000, high: 80500, low: 79800, close: 80200 },
		{ time: 1711670460, open: 80200, high: 81000, low: 80100, close: 80800 },
		{ time: 1711670520, open: 80800, high: 80900, low: 80000, close: 80100 },
		{ time: 1711670580, open: 80100, high: 80500, low: 79500, close: 79600 },
		{ time: 1711670640, open: 79600, high: 81500, low: 79500, close: 81000 },
	],
	일: [
		{ time: '2026-03-15', open: 80000, high: 82000, low: 79000, close: 81500 },
		{ time: '2026-03-16', open: 81500, high: 83000, low: 80500, close: 82500 },
		{ time: '2026-03-17', open: 82500, high: 84000, low: 81000, close: 81500 },
		{ time: '2026-03-18', open: 81500, high: 82000, low: 78000, close: 78500 },
		{ time: '2026-03-19', open: 78500, high: 81000, low: 78000, close: 80500 },
	],
	주: [
		// 주봉 (일주일 간격)
		{ time: '2026-02-16', open: 75000, high: 79000, low: 74000, close: 78000 },
		{ time: '2026-02-23', open: 78000, high: 81000, low: 77000, close: 80500 },
		{ time: '2026-03-02', open: 80500, high: 82000, low: 79000, close: 79500 },
		{ time: '2026-03-09', open: 79500, high: 85000, low: 79000, close: 84000 },
	],
	월: [
		// 월봉 (한 달 간격)
		{ time: '2025-12-01', open: 65000, high: 70000, low: 64000, close: 69000 },
		{ time: '2026-01-01', open: 69000, high: 75000, low: 68000, close: 74000 },
		{ time: '2026-02-01', open: 74000, high: 81000, low: 73000, close: 80500 },
		{ time: '2026-03-01', open: 80500, high: 87000, low: 78000, close: 86500 },
	],
	년: [
		// 연봉 (1년 간격)
		{ time: '2023-01-01', open: 55000, high: 65000, low: 50000, close: 60000 },
		{ time: '2024-01-01', open: 60000, high: 75000, low: 58000, close: 72000 },
		{ time: '2025-01-01', open: 72000, high: 80000, low: 65000, close: 69000 },
		{ time: '2026-01-01', open: 69000, high: 90000, low: 68000, close: 86500 },
	],
};

export default function ChartSection() {
	const [selectedTab, setSelectedTab] = useState<TimeFrame>('일');
	const chartContainerRef = useCandlestickChart(MOCK_DATA[selectedTab]);

	return (
		<>
			<div className='bg-gray-600 h-100 p-4 flex flex-col'>
				<div className='flex gap-4 text-sm text-gray-300 mb-4'>
					{TABS.map((tab) => (
						<span
							key={tab}
							onClick={() => setSelectedTab(tab)}
							className={`cursor-pointer pb-1 ${
								selectedTab === tab
									? 'text-white font-bold' // 선택된 탭 스타일
									: 'hover:text-white' // 선택되지 않은 탭 스타일
							}`}
						>
							{tab}
						</span>
					))}
				</div>

				<div ref={chartContainerRef} className='flex-1 w-full relative' />
			</div>

			<div className='bg-gray-600 h-62.5 p-4 flex items-center justify-center'>
				<span className='text-gray-200'>추가 정보 / 보조 지표 영역</span>
			</div>
		</>
	);
}
