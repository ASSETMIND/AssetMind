import { useEffect, useRef, useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import type { Time } from 'lightweight-charts';
import { getStockCandles } from '../../api/stock';
import type { CandleTimeframe, CandleDto } from '../../api/stock';

// ─── 색상 ─────────────────────────────────────────────────────

const CHART_COLORS = {
	bg:   'transparent',
	text: '#9194A1',
	grid: '#2F3037',
	rise: '#EA580C',
	fall: '#256AF4',
};

// ─── 기간 탭 정의 ─────────────────────────────────────────────

export type PeriodTab = '1분' | '5분' | '일' | '주' | '월';

export const PERIOD_TABS: PeriodTab[] = ['1분', '5분', '일', '주', '월'];

export const PERIOD_TO_TIMEFRAME: Record<PeriodTab, CandleTimeframe> = {
	'1분': '1m',
	'5분': '5m',
	'일':  '1d',
	'주':  '1w',
	'월':  '1mo',
};

// ─── 공통 차트 캔들 타입 ──────────────────────────────────────

interface ChartCandle {
	time:  Time;
	open:  number;
	high:  number;
	low:   number;
	close: number;
}

// ─── 데이터 변환 ──────────────────────────────────────────────
// 실제 API: timestamp(ISO-8601 string), open/high/low/close 모두 string

function candlesToChartData(raw: CandleDto[]): ChartCandle[] {
	const isIntraday = raw.length > 0 && raw[0].timestamp.includes('T') &&
		!raw[0].timestamp.endsWith('T00:00:00');

	return raw
		.map((d) => {
			const time = isIntraday
				? Math.floor(new Date(d.timestamp).getTime() / 1000) as unknown as Time
				: d.timestamp.slice(0, 10) as Time;

			return {
				time,
				open:  Number(d.open),
				high:  Number(d.high),
				low:   Number(d.low),
				close: Number(d.close),
			};
		})
		.filter((d) => !isNaN(d.open) && !isNaN(d.close))
		.sort((a, b) => {
			const ta = typeof a.time === 'number' ? a.time : new Date(a.time as string).getTime();
			const tb = typeof b.time === 'number' ? b.time : new Date(b.time as string).getTime();
			return ta - tb;
		});
}

// ─── useCandlestickChart ──────────────────────────────────────

export interface UseCandlestickChartReturn {
	chartContainerRef: React.RefObject<HTMLDivElement | null>;
	period:    PeriodTab;
	setPeriod: (p: PeriodTab) => void;
	isLoading: boolean;
	isError:   boolean;
}

export function useCandlestickChart(stockCode: string): UseCandlestickChartReturn {
	const chartContainerRef = useRef<HTMLDivElement>(null);
	const [period, setPeriod] = useState<PeriodTab>('일');

	const timeframe = PERIOD_TO_TIMEFRAME[period];

	// 모든 기간 → candles API 사용 (history는 체결 틱이라 차트에 부적합)
	const { data: candleData, isLoading, isError } = useQuery<CandleDto[]>({
		queryKey: ['stockCandles', stockCode, timeframe],
		queryFn:  () => getStockCandles(stockCode, timeframe, 200),
		enabled:  !!stockCode,
		staleTime: 1000 * 30,
	});

	const chartData: ChartCandle[] = useMemo(() =>
		candlesToChartData(candleData ?? []),
		[candleData],
	);

	useEffect(() => {
		if (!chartContainerRef.current) return;

		const chart = createChart(chartContainerRef.current, {
			layout: {
				background: { type: ColorType.Solid, color: CHART_COLORS.bg },
				textColor: CHART_COLORS.text,
			},
			grid: {
				vertLines: { color: CHART_COLORS.grid },
				horzLines: { color: CHART_COLORS.grid },
			},
			width:  chartContainerRef.current.clientWidth,
			height: chartContainerRef.current.clientHeight,
		});

		const candlestickSeries = chart.addSeries(CandlestickSeries, {
			upColor:       CHART_COLORS.rise,
			downColor:     CHART_COLORS.fall,
			borderVisible: false,
			wickUpColor:   CHART_COLORS.rise,
			wickDownColor: CHART_COLORS.fall,
		});

		if (chartData.length > 0) {
			candlestickSeries.setData(chartData);
			chart.timeScale().fitContent();
		}

		const handleResize = () => {
			if (chartContainerRef.current) {
				chart.applyOptions({ width: chartContainerRef.current.clientWidth });
			}
		};
		window.addEventListener('resize', handleResize);

		return () => {
			window.removeEventListener('resize', handleResize);
			chart.remove();
		};
	}, [chartData, period]);

	return { chartContainerRef, period, setPeriod, isLoading, isError };
}