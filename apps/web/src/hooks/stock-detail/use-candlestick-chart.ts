import { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';

const TW_COLORS = {
	gray300: '#d1d5db',
	gray600: '#4b5563',
	red500: '#ef4444',
	blue500: '#3b82f6',
};

export function useCandlestickChart(data: any[]) {
	const chartContainerRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!chartContainerRef.current) return;

		const chart = createChart(chartContainerRef.current, {
			layout: {
				background: { type: ColorType.Solid, color: 'transparent' },
				textColor: TW_COLORS.gray300,
			},
			grid: {
				vertLines: { color: TW_COLORS.gray600 },
				horzLines: { color: TW_COLORS.gray600 },
			},
			width: chartContainerRef.current.clientWidth,
			height: chartContainerRef.current.clientHeight,
		});

		// 캔들스틱 시리즈 설정
		const candlestickSeries = chart.addSeries(CandlestickSeries, {
			upColor: TW_COLORS.red500,
			downColor: TW_COLORS.blue500,
			borderVisible: false,
			wickUpColor: TW_COLORS.red500,
			wickDownColor: TW_COLORS.blue500,
		});

		// 데이터 주입
		candlestickSeries.setData(data);
		chart.timeScale().fitContent();

		// 반응형(Resize) 이벤트 처리
		const handleResize = () => {
			chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
		};
		window.addEventListener('resize', handleResize);

		return () => {
			window.removeEventListener('resize', handleResize);
			chart.remove();
		};
	}, [data]);

	return chartContainerRef;
}
