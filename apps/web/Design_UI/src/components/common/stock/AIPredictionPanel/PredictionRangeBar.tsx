import React from "react";

export interface PredictionRangeBarProps {
  /** AI 예측 가격 (원) */
  predictedPrice: number;
  /** 현재가 대비 변동액 (양수=상승, 음수=하락) */
  priceDiff: number;
  /** 변동률 (%) */
  changeRate: number;
  /** 기준일 (예: "2025년 03월 26일") */
  baseDate: string;
  /** 상승 확률 0~100 */
  upProbability: number;
  /** 하락 확률 0~100 */
  downProbability: number;
}

const RISE_COLOR = "#EA580C";
const FALL_COLOR = "#256AF4";
const BAR_BG = "#2A2A2E";
const MIN_BAR_PCT = 4;

function formatPrice(value: number): string {
  return Math.abs(value).toLocaleString("ko-KR");
}

function clampBar(pct: number): number {
  if (pct <= 0) return 0;
  return Math.max(pct, MIN_BAR_PCT);
}

export const PredictionRangeBar: React.FC<PredictionRangeBarProps> = ({
  predictedPrice,
  priceDiff,
  changeRate,
  baseDate,
  upProbability,
  downProbability,
}) => {
  const isRise = priceDiff >= 0;
  const diffColor = isRise ? RISE_COLOR : FALL_COLOR;
  const diffSign = isRise ? "+" : "-";

  const upBarPct = clampBar(upProbability);
  const downBarPct = clampBar(downProbability);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {/* AI 예측가 섹션 */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        {/* 헤더 행: AI 예측가 레이블 + 기준일 */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>
            AI 예측가
          </span>
          <span style={{ fontSize: "10px", fontWeight: 400, color: "#9F9F9F" }}>
            {baseDate} 기준
          </span>
        </div>

        {/* 예측 가격 + 변동 */}
        <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
          <span
            style={{
              fontSize: "24px",
              fontWeight: 700,
              color: "#FFFFFF",
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "-0.5px",
            }}
          >
            {formatPrice(predictedPrice)}원
          </span>
          <span
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: diffColor,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {diffSign}
            {formatPrice(priceDiff)}원 ({isRise ? "+" : "-"}
            {Math.abs(changeRate).toFixed(2)}%)
          </span>
        </div>
      </div>

      {/* 방향성 확률 섹션 */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>
          방향성 확률
        </span>

        {/* 상승 바 */}
        <DirectionBar
          label="상승"
          probability={upProbability}
          barPct={upBarPct}
          color={RISE_COLOR}
        />

        {/* 하락 바 */}
        <DirectionBar
          label="하락"
          probability={downProbability}
          barPct={downBarPct}
          color={FALL_COLOR}
        />
      </div>
    </div>
  );
};

/* ── 내부 서브 컴포넌트 ── */

interface DirectionBarProps {
  label: string;
  probability: number;
  barPct: number;
  color: string;
}

const DirectionBar: React.FC<DirectionBarProps> = ({
  label,
  probability,
  barPct,
  color,
}) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: "8px",
    }}
  >
    {/* 레이블 — bold 12, 25x18 고정 */}
    <span
      style={{
        width: "25px",
        height: "18px",
        fontSize: "12px",
        fontWeight: 700,
        color,
        display: "flex",
        alignItems: "center",
        flexShrink: 0,
      }}
    >
      {label}
    </span>

    {/* 바 — flex-grow로 패널 채우기 */}
    <div
      style={{
        flex: 1,
        height: "10px",
        backgroundColor: BAR_BG,
        borderRadius: "9999px",
        overflow: "hidden",
        position: "relative",
      }}
    >
      <div
        style={{
          width: `${barPct}%`,
          height: "100%",
          backgroundColor: color,
          borderRadius: "9999px",
          transition: "width 0.4s ease",
        }}
      />
    </div>

    {/* 퍼센트 — bold 12, 25x18 고정 */}
    <span
      style={{
        width: "25px",
        height: "18px",
        fontSize: "12px",
        fontWeight: 700,
        color,
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-end",
        flexShrink: 0,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {probability}%
    </span>
  </div>
);

export default PredictionRangeBar;