import React, { useMemo, useId } from "react";

export interface SparklineDataPoint {
  time: string;
  value: number;
}

export interface SparklineChartProps {
  /** 과거 데이터 — 파란 실선 + 그라데이션 */
  historicalData: SparklineDataPoint[];
  /** 예측 데이터 — 초록 점선 + 그라데이션 */
  forecastData: SparklineDataPoint[];
  /** 컨테이너 너비 (기본값: 패널 전체 채우기) */
  width?: number | string;
}

const PADDING = { top: 28, right: 10, bottom: 8, left: 10 };
const CHART_HEIGHT = 140;
const W = 300;
const DIVIDER_COLOR = "#3A3A3F";
const HISTORICAL_COLOR = "#256AF4";
const FORECAST_COLOR = "#22C55E";
const MARKER_COLOR = "#FFFFFF";

function smoothPath(pts: { x: number; y: number }[]): string {
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1];
    const curr = pts[i];
    const cpX = (prev.x + curr.x) / 2;
    d += ` C ${cpX.toFixed(2)} ${prev.y.toFixed(2)}, ${cpX.toFixed(2)} ${curr.y.toFixed(2)}, ${curr.x.toFixed(2)} ${curr.y.toFixed(2)}`;
  }
  return d;
}

function fillPath(
  pts: { x: number; y: number }[],
  linePath: string,
  yBottom: number
): string {
  if (pts.length < 2) return "";
  const first = pts[0];
  const last = pts[pts.length - 1];
  return `${linePath} L ${last.x.toFixed(2)} ${yBottom.toFixed(2)} L ${first.x.toFixed(2)} ${yBottom.toFixed(2)} Z`;
}

export const SparklineChart: React.FC<SparklineChartProps> = ({
  historicalData,
  forecastData,
  width = "100%",
}) => {
  const uid = useId();

  const yTop = PADDING.top;
  const yBottom = CHART_HEIGHT - PADDING.bottom;

  const allValues = useMemo(
    () => [...historicalData, ...forecastData].map((d) => d.value),
    [historicalData, forecastData]
  );

  const minVal = useMemo(() => Math.min(...allValues), [allValues]);
  const maxVal = useMemo(() => {
    const raw = Math.max(...allValues);
    const range = raw - Math.min(...allValues) || 1;
    return raw + range * 0.08;
  }, [allValues]);

  const toY = (v: number) =>
    yBottom - ((v - minVal) / (maxVal - minVal || 1)) * (yBottom - yTop);

  const dividerX = useMemo(() => {
    const total = historicalData.length + forecastData.length - 1;
    if (total <= 0) return W / 2;
    return (
      PADDING.left +
      ((historicalData.length - 1) / total) *
        (W - PADDING.left - PADDING.right)
    );
  }, [historicalData.length, forecastData.length]);

  const histPts = useMemo(() => {
    if (historicalData.length === 0) return [];
    return historicalData.map((d, i) => ({
      x:
        PADDING.left +
        (i / (historicalData.length - 1 || 1)) * (dividerX - PADDING.left),
      y: toY(d.value),
    }));
  }, [historicalData, minVal, maxVal, dividerX]);

  const forecastPts = useMemo(() => {
    if (forecastData.length === 0) return [];
    const xEnd = W - PADDING.right;
    return forecastData.map((d, i) => ({
      x:
        dividerX +
        (i / (forecastData.length - 1 || 1)) * (xEnd - dividerX),
      y: toY(d.value),
    }));
  }, [forecastData, minVal, maxVal, dividerX]);

  const histLine = smoothPath(histPts);
  const forecastLine = smoothPath(forecastPts);
  const histFill = fillPath(histPts, histLine, yBottom);
  const forecastFill = fillPath(forecastPts, forecastLine, yBottom);

  const markerPt = histPts[histPts.length - 1];

  return (
    <div
      style={{
        width,
        height: `${CHART_HEIGHT}px`,
        backgroundColor: "#131316",
        borderRadius: "8px",
        position: "relative",
        overflow: "hidden",
        boxSizing: "border-box",
      }}
    >
      {/* 레이블 */}
      <span
        style={{
          position: "absolute",
          top: "10px",
          left: "12px",
          fontSize: "12px",
          fontWeight: 400,
          color: "#9F9F9F",
          pointerEvents: "none",
          zIndex: 1,
        }}
      >
        예측 가격 흐름
      </span>

      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${W} ${CHART_HEIGHT}`}
        preserveAspectRatio="none"
        style={{ display: "block" }}
      >
        <defs>
          {/* 과거 데이터 그라데이션 — 파란색 (고유 ID 적용) */}
          <linearGradient id={`grad-hist-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={HISTORICAL_COLOR} stopOpacity="0.25" />
            <stop offset="100%" stopColor={HISTORICAL_COLOR} stopOpacity="0" />
          </linearGradient>
          {/* 예측 데이터 그라데이션 — 초록색 (고유 ID 적용) */}
          <linearGradient id={`grad-forecast-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={FORECAST_COLOR} stopOpacity="0.20" />
            <stop offset="100%" stopColor={FORECAST_COLOR} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* 수직 구분선 */}
        <line
          x1={dividerX}
          y1={yTop - 8}
          x2={dividerX}
          y2={yBottom}
          stroke={DIVIDER_COLOR}
          strokeWidth="1"
          strokeDasharray="3 3"
        />

        {/* 과거 — 그라데이션 fill (고유 ID 참조) */}
        {histFill && (
          <path d={histFill} fill={`url(#grad-hist-${uid})`} />
        )}

        {/* 과거 — 파란 실선 */}
        {histLine && (
          <path
            d={histLine}
            fill="none"
            stroke={HISTORICAL_COLOR}
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* 예측 — 그라데이션 fill (고유 ID 참조) */}
        {forecastFill && (
          <path d={forecastFill} fill={`url(#grad-forecast-${uid})`} />
        )}

        {/* 예측 — 초록 점선 */}
        {forecastLine && (
          <path
            d={forecastLine}
            fill="none"
            stroke={FORECAST_COLOR}
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="5 3"
          />
        )}

        {/* 현재가 마커 — glow 효과 */}
        {markerPt && (
          <>
            {/* glow */}
            <circle
              cx={markerPt.x}
              cy={markerPt.y}
              r="7"
              fill={HISTORICAL_COLOR}
              opacity="0.15"
            />
            {/* 외곽 */}
            <circle
              cx={markerPt.x}
              cy={markerPt.y}
              r="4.5"
              fill="#131316"
              stroke={MARKER_COLOR}
              strokeWidth="1.5"
            />
            {/* 중심 */}
            <circle
              cx={markerPt.x}
              cy={markerPt.y}
              r="2"
              fill={MARKER_COLOR}
            />
          </>
        )}
      </svg>
    </div>
  );
};

export default SparklineChart;