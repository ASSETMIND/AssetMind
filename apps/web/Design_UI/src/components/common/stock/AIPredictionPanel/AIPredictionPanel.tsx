import React, { useState } from "react";
import { BuyIcon } from "../../../icons/BuyIcon";
import { SparklineChart } from "./SparklineChart";
import type { SparklineDataPoint } from "./SparklineChart";
import { PredictionRangeBar } from "./PredictionRangeBar";

type PeriodTab = "1주" | "1개월" | "3개월";

export interface AIPredictionPanelProps {
  period?: PeriodTab;
  onPeriodChange?: (period: PeriodTab) => void;
  onBuyClick?: () => void;
  historicalData: SparklineDataPoint[];
  forecastData: SparklineDataPoint[];
  predictedPrice: number;
  priceDiff: number;
  changeRate: number;
  baseDate: string;
  upProbability: number;
  downProbability: number;
}

const PERIODS: PeriodTab[] = ["1주", "1개월", "3개월"];

export const AIPredictionPanel: React.FC<AIPredictionPanelProps> = ({
  period: periodProp,
  onPeriodChange,
  onBuyClick,
  historicalData,
  forecastData,
  predictedPrice,
  priceDiff,
  changeRate,
  baseDate,
  upProbability,
  downProbability,
}) => {
  const [internalPeriod, setInternalPeriod] = useState<PeriodTab>("1주");
  const activePeriod = periodProp ?? internalPeriod;

  const handlePeriodClick = (p: PeriodTab) => {
    setInternalPeriod(p);
    onPeriodChange?.(p);
  };

  return (
    <div
      style={{
        width: "340px",
        backgroundColor: "#1C1D21",
        borderRadius: "12px",
        padding: "24px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        boxSizing: "border-box",
      }}
    >
      {/* ── 헤더 ── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>
          AI 가격 예측 패널
        </span>
        <button
          onClick={onBuyClick}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            background: "none",
            border: "1px solid #2F3037",
            cursor: "pointer",
            padding: "4px 8px",
            borderRadius: "4px",
          }}
        >
          <BuyIcon color="#9F9F9F" />
          <span style={{ fontSize: "14px", fontWeight: 400, color: "#9F9F9F" }}>
            매수하기
          </span>
        </button>
      </div>

      {/* ── 기간 탭 */}
      <div
        style={{
          display: "flex",
          borderRadius: "8px",
          gap: "4px",
          height: "48px",
          boxSizing: "border-box",
          alignItems: "center",
        }}
      >
        {PERIODS.map((p) => {
          const active = activePeriod === p;
          return (
            <button
              key={p}
              onClick={() => handlePeriodClick(p)}
              style={{
                flex: 1,
                height: "32px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: active ? "#2C2C30" : "transparent",
                border: "none",
                borderRadius: "6px",
                cursor: "pointer",
                fontSize: "16px",
                fontWeight: active ? 700 : 400,
                color: active ? "#FFFFFF" : "#9F9F9F",
                transition: "background-color 0.15s ease, color 0.15s ease",
              }}
            >
              {p}
            </button>
          );
        })}
      </div>

      {/* ── 스파크라인 차트 ── */}
      <SparklineChart
        historicalData={historicalData}
        forecastData={forecastData}
        width="100%"
      />

      {/* ── AI 예측가 + 방향성 확률 ── */}
      <PredictionRangeBar
        predictedPrice={predictedPrice}
        priceDiff={priceDiff}
        changeRate={changeRate}
        baseDate={baseDate}
        upProbability={upProbability}
        downProbability={downProbability}
      />
    </div>
  );
};

export default AIPredictionPanel;