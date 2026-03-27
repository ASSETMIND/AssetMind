import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CandlestickSeries, HistogramSeries } from "lightweight-charts";
import { GlobalEmptyState } from "../../../common/GlobalEmptyState/GlobalEmptyState";

export type ChartPeriod = "1m" | "1d" | "1w" | "1mo" | "1y";

export interface CandlestickData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface OHLCInfo {
  open: number;
  high: number;
  low: number;
  close: number;
}

interface TradingViewWrapperProps {
  data?: CandlestickData[];
  period?: ChartPeriod;
  onPeriodChange?: (period: ChartPeriod) => void;
  isMarketClosed?: boolean;
  className?: string;
}

const PERIOD_ITEMS: { label: string; value: ChartPeriod }[] = [
  { label: "1분", value: "1m" },
  { label: "일",  value: "1d" },
  { label: "주",  value: "1w" },
  { label: "월",  value: "1mo" },
  { label: "년",  value: "1y" },
];

// ─── 차트 전용 필터 탭 ────────────────────────────────────────

const ChartFilterTab = ({
  items,
  value,
  onChange,
}: {
  items: { label: string; value: ChartPeriod }[];
  value: ChartPeriod;
  onChange: (v: ChartPeriod) => void;
}) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "8px",
      width: "233px",
      paddingTop: "8px",
      paddingBottom: "8px",
      paddingLeft: "0",
      paddingRight: "0",
    }}
  >
    {items.map((item) => {
      const isActive = value === item.value;
      return (
        <button
          key={item.value}
          onClick={() => onChange(item.value)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "4px 11px",
            gap: "10px",
            background: isActive ? "#383A42" : "transparent",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: 400,
            color: isActive ? "#FFFFFF" : "#9194A1",
            whiteSpace: "nowrap",
          }}
        >
          {item.label}
        </button>
      );
    })}
  </div>
);

/**
 * TradingViewWrapper 컴포넌트
 *
 * Lightweight Charts 기반 캔들스틱 차트 래퍼
 * - 차트 전용 기간 필터 탭 (233x허그, 칩 좌우패딩 11 상하패딩 4)
 * - 크로스헤어 OHLC 표시
 * - 거래량 히스토그램
 * - 시장 휴장 뱃지
 */
export const TradingViewWrapper = ({
  data = [],
  period = "1d",
  onPeriodChange,
  isMarketClosed = false,
  className,
}: TradingViewWrapperProps) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  const [ohlc, setOhlc] = useState<OHLCInfo | null>(null);
  const [internalPeriod, setInternalPeriod] = useState<ChartPeriod>(period);

  const handlePeriodChange = (v: ChartPeriod) => {
    setInternalPeriod(v);
    onPeriodChange?.(v);
  };

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#131316" },
        textColor: "#9194A1",
      },
      grid: {
        vertLines: { color: "#2F3037" },
        horzLines: { color: "#2F3037" },
      },
      crosshair: {
        vertLine: { color: "#9194A1", width: 1, style: 3 },
        horzLine: { color: "#9194A1", width: 1, style: 3 },
      },
      rightPriceScale: {
        borderColor: "#2F3037",
      },
      timeScale: {
        borderColor: "#2F3037",
        timeVisible: true,
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
    });

    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#EA580C",
      downColor: "#256AF4",
      borderUpColor: "#EA580C",
      borderDownColor: "#256AF4",
      wickUpColor: "#EA580C",
      wickDownColor: "#256AF4",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#256AF4",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    if (data.length > 0) {
      candleSeries.setData(
        data.map((d) => ({
          time: d.time as any,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        }))
      );

      volumeSeries.setData(
        data.map((d) => ({
          time: d.time as any,
          value: d.volume ?? 0,
          color: d.close >= d.open ? "#EA580C" : "#256AF4",
        }))
      );

      chart.timeScale().fitContent();
    }

    // 크로스헤어 OHLC 표시
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) {
        setOhlc(null);
        return;
      }
      const candle = param.seriesData.get(candleSeries) as any;
      if (candle) {
        setOhlc({
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
        });
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data]);

  const fmt = (v: number) => v.toLocaleString("ko-KR");

  return (
    <div
      className={className}
      style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%" }}
    >
      {/* 기간 필터 탭 + 휴장 뱃지 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <ChartFilterTab
          items={PERIOD_ITEMS}
          value={internalPeriod}
          onChange={handlePeriodChange}
        />
        {isMarketClosed && (
          <GlobalEmptyState variant="market-closed" display="badge" />
        )}
      </div>

      {/* OHLC 표시 */}
      {ohlc && (
        <div style={{ display: "flex", gap: "12px", padding: "4px 0", fontSize: "12px" }}>
          <span style={{ color: "#9194A1" }}>시작 <span style={{ color: "#FFFFFF" }}>{fmt(ohlc.open)}</span></span>
          <span style={{ color: "#9194A1" }}>고가 <span style={{ color: "#EA580C" }}>{fmt(ohlc.high)}</span></span>
          <span style={{ color: "#9194A1" }}>저가 <span style={{ color: "#256AF4" }}>{fmt(ohlc.low)}</span></span>
          <span style={{ color: "#9194A1" }}>종가 <span style={{ color: "#FFFFFF" }}>{fmt(ohlc.close)}</span></span>
        </div>
      )}

      {/* 차트 영역 */}
      <div ref={chartContainerRef} style={{ flex: 1, minHeight: 0 }} />
    </div>
  );
};