import React, { useState } from "react";
import { BuyIcon } from "../../../icons/BuyIcon";
import { MoonIcon } from "../../../icons/MoonIcon";
import { SparklineChart } from "./SparklineChart";
import type { SparklineDataPoint } from "./SparklineChart";
import { PredictionRangeBar } from "./PredictionRangeBar";
import {
  PredictionAnalysisWidget,
  type AnalysisData,
} from "./PredictionAnalysisWidget";

/* ── 타입 ── */
type PeriodTab = "1주" | "1개월" | "3개월";

export type PanelStatus = "default" | "skeleton" | "error" | "empty";

export interface AIPredictionPanelProps {
  /** 패널 상태 */
  status?: PanelStatus;
  onRetry?: () => void;
  /** 기간 탭 */
  period?: PeriodTab;
  onPeriodChange?: (period: PeriodTab) => void;
  onBuyClick?: () => void;
  /** SparklineChart */
  historicalData?: SparklineDataPoint[];
  forecastData?: SparklineDataPoint[];
  /** PredictionRangeBar */
  predictedPrice?: number;
  priceDiff?: number;
  changeRate?: number;
  baseDate?: string;
  upProbability?: number;
  downProbability?: number;
  /** PredictionAnalysisWidget */
  analysisData?: AnalysisData;
}

const PERIODS: PeriodTab[] = ["1주", "1개월", "3개월"];

/* ════════════════════════════════
   Skeleton 서브 컴포넌트
════════════════════════════════ */
const SkeletonBox: React.FC<{
  width?: string | number;
  height?: number;
  borderRadius?: number;
}> = ({ width = "100%", height = 16, borderRadius = 6 }) => (
  <div
    className="animate-[skeleton-pulse_700ms_ease-out_400ms_infinite]"
    style={{
      width,
      height: `${height}px`,
      borderRadius: `${borderRadius}px`,
      backgroundColor: "#21242C",
    }}
  />
);

const AIPredictionPanelSkeleton: React.FC = () => (
  <>
    {/* 차트 스켈레톤 */}
    <SkeletonBox height={140} borderRadius={8} />

    {/* AI 예측가 */}
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>
        AI 예측가
      </span>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <SkeletonBox width={140} height={32} borderRadius={6} />
        <SkeletonBox width={100} height={20} borderRadius={6} />
      </div>
    </div>

    {/* 방향성 확률 */}
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>
        방향성 확률
      </span>
      {(["상승", "하락"] as const).map((label, i) => (
        <div
          key={label}
          style={{ display: "flex", alignItems: "center", gap: "8px" }}
        >
          <span
            style={{
              fontSize: "12px",
              fontWeight: 700,
              color: i === 0 ? "#EA580C" : "#256AF4",
              width: "25px",
              flexShrink: 0,
            }}
          >
            {label}
          </span>
          <SkeletonBox height={8} borderRadius={9999} />
          <span
            style={{
              fontSize: "12px",
              fontWeight: 700,
              color: i === 0 ? "#EA580C" : "#256AF4",
              width: "25px",
              textAlign: "right",
              flexShrink: 0,
            }}
          >
            -
          </span>
        </div>
      ))}
    </div>

    {/* 분석 근거 */}
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>
        분석 근거
      </span>
      <div style={{ display: "flex", gap: "10px" }}>
        {[90, 80, 80].map((w, i) => (
          <SkeletonBox key={i} width={w} height={34} borderRadius={30} />
        ))}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          padding: "10px",
          backgroundColor: "#131316",
          borderRadius: "8px",
        }}
      >
        {[1, 2, 3, 4, 5].map((i) => (
          <SkeletonBox key={i} height={28} borderRadius={8} />
        ))}
      </div>
    </div>
  </>
);

/* ════════════════════════════════
   ErrorState 서브 컴포넌트
════════════════════════════════ */
const AIPredictionPanelError: React.FC<{ onRetry?: () => void }> = ({
  onRetry,
}) => (
  <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: "16px",
      minHeight: "600px",
    }}
  >
    <svg
      width="40"
      height="38"
      viewBox="0 0 30 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M16.3261 0.724424C15.8071 -0.241475 14.1932 -0.241475 13.6742 0.724424L0.174404 25.8319C0.0533393 26.057 -0.0065451 26.3091 0.00056714 26.5637C0.00767938 26.8183 0.0815466 27.0668 0.214994 27.285C0.348442 27.5032 0.536934 27.6837 0.762161 27.809C0.987389 27.9343 1.2417 28.0001 1.50038 28H28.4999C28.7586 28.0005 29.013 27.935 29.2383 27.8099C29.4636 27.6848 29.6522 27.5044 29.7856 27.2862C29.919 27.0679 29.9927 26.8194 29.9995 26.5648C30.0063 26.3102 29.946 26.0582 29.8244 25.8334L16.3261 0.724424ZM16.5001 23.5693H13.5002V20.6154H16.5001V23.5693ZM13.5002 17.6616V10.2771H16.5001L16.5016 17.6616H13.5002Z"
        fill="#6B7280"
      />
    </svg>
    <p
      style={{
        fontSize: "14px",
        fontWeight: 400,
        color: "#9F9F9F",
        textAlign: "center",
        lineHeight: "1.6",
        margin: 0,
      }}
    >
      예측 데이터를 불러오지 못했습니다.
      <br />
      잠시 후 다시 시도해 주세요.
    </p>
    <button
      onClick={onRetry}
      style={{
        padding: "12px 32px",
        backgroundColor: "#6B4EFF",
        border: "none",
        borderRadius: "8px",
        cursor: "pointer",
        fontSize: "14px",
        fontWeight: 500,
        color: "#FFFFFF",
      }}
    >
      다시 시도
    </button>
  </div>
);

/* ════════════════════════════════
   헤더 우측 액션 영역
════════════════════════════════ */
const HeaderAction: React.FC<{
  status: PanelStatus;
  onBuyClick?: () => void;
}> = ({ status, onBuyClick }) => {
  if (status === "empty") {
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "5px",
          padding: "5px",
          backgroundColor: "#2C2C30",
          borderRadius: "4px",
          width: "64px",
          height: "25px",
          boxSizing: "border-box",
        }}
      >
        <MoonIcon color="#FFFFFF" />
        <span
          style={{
            fontSize: "10px",
            fontWeight: 500,
            color: "#FFFFFF",
            whiteSpace: "nowrap",
          }}
        >
          휴장 시간
        </span>
      </div>
    );
  }

  if (status === "error") return null;

  return (
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
  );
};

/* ════════════════════════════════
   메인 패널
════════════════════════════════ */
export const AIPredictionPanel: React.FC<AIPredictionPanelProps> = ({
  status = "default",
  onRetry,
  period: periodProp,
  onPeriodChange,
  onBuyClick,
  historicalData = [],
  forecastData = [],
  predictedPrice = 0,
  priceDiff = 0,
  changeRate = 0,
  baseDate = "",
  upProbability = 0,
  downProbability = 0,
  analysisData,
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
      {/* 헤더 */}
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
        <HeaderAction status={status} onBuyClick={onBuyClick} />
      </div>

      {/* ErrorState */}
      {status === "error" ? (
        <AIPredictionPanelError onRetry={onRetry} />
      ) : (
        <>
          {/* 기간 탭 */}
          <div
            style={{
              display: "flex",
              gap: "4px",
              height: "48px",
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

          {/* Skeleton or 실제 콘텐츠 */}
          {status === "skeleton" ? (
            <AIPredictionPanelSkeleton />
          ) : (
            <>
              <SparklineChart
                historicalData={historicalData}
                forecastData={forecastData}
                width="100%"
              />

              <PredictionRangeBar
                predictedPrice={predictedPrice}
                priceDiff={priceDiff}
                changeRate={changeRate}
                baseDate={baseDate}
                upProbability={upProbability}
                downProbability={downProbability}
              />

              {analysisData && (
                <PredictionAnalysisWidget data={analysisData} />
              )}

              {/* 면책 고지 */}
              <p
                style={{
                  fontSize: "11px",
                  fontWeight: 400,
                  color: "#9F9F9F",
                  lineHeight: "1.6",
                  margin: 0,
                  paddingTop: "4px",
                }}
              >
                ※ AI 예측은 참고로만 이용하며 투자 판단의 방적 근거가 될 수
                없습니다. 투자 손실의 책임은 투자자 본인에게 있습니다.
              </p>
            </>
          )}
        </>
      )}
    </div>
  );
};

export default AIPredictionPanel;