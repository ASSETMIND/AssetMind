import { useEffect, useRef, useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import type { Time } from 'lightweight-charts';
import { getStockCandles, getStockHistory } from '../../api/stock';
import type { CandleTimeframe, CandleDto, StockHistoryDto } from '../../api/stock';

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
	'월':  '1M',
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

function candlesToChartData(raw: CandleDto[]): ChartCandle[] {
	return raw
		.map((d) => ({
			time:  (typeof d.time === 'number' ? d.time : d.time.slice(0, 10)) as Time,
			open:  d.open,
			high:  d.high,
			low:   d.low,
			close: d.close,
		}))
		.sort((a, b) => {
			const ta = typeof a.time === 'number' ? a.time : new Date(a.time as string).getTime();
			const tb = typeof b.time === 'number' ? b.time : new Date(b.time as string).getTime();
			return ta - tb;
		});
}

function historyToChartData(raw: StockHistoryDto[]): ChartCandle[] {
	return raw
		.map((d) => ({
			time:  d.date.slice(0, 10) as Time,
			open:  d.open,
			high:  d.high,
			low:   d.low,
			close: d.close,
		}))
		.sort((a, b) => (a.time as string).localeCompare(b.time as string));
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

	const timeframe  = PERIOD_TO_TIMEFRAME[period];
	const isIntraday = period === '1분' || period === '5분';

	const candleQuery = useQuery<CandleDto[]>({
		queryKey: ['stockCandles', stockCode, timeframe],
		queryFn:  () => getStockCandles(stockCode, timeframe, 200),
		enabled:  !!stockCode && isIntraday,
		staleTime: 1000 * 30,
	});

	const historyQuery = useQuery<StockHistoryDto[]>({
		queryKey: ['stockHistory', stockCode, timeframe],
		queryFn:  () => getStockHistory(stockCode, 200),
		enabled:  !!stockCode && !isIntraday,
		staleTime: 1000 * 30,
	});

	const isLoading = isIntraday ? candleQuery.isLoading : historyQuery.isLoading;
	const isError   = isIntraday ? candleQuery.isError   : historyQuery.isError;

	const chartData: ChartCandle[] = useMemo(() =>
		isIntraday
			? candlesToChartData(candleQuery.data ?? [])
			: historyToChartData(historyQuery.data ?? []),
		[isIntraday, candleQuery.data, historyQuery.data],
	);

	useEffect(() => {
		if (!chartContainerRef.current || chartData.length === 0) return;

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

		candlestickSeries.setData(chartData);
		chart.timeScale().fitContent();

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
	}, [chartData]);

	return { chartContainerRef, period, setPeriod, isLoading, isError };
}