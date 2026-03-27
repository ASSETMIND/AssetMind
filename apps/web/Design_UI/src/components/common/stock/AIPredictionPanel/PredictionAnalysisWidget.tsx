import React, { useState } from "react";
import { WarningIcon } from "../../../icons/WarningIcon";
import { CheckIcon } from "../../../icons/CheckIcon";

/* ── 타입 ── */
export type AnalysisTab = "기술적 지표" | "시장 심리" | "수급 동향";

export type SignalType = "warning" | "positive" | "neutral";

export interface AnalysisItem {
  type: SignalType;
  text: string;
}

export interface AnalysisData {
  "기술적 지표": AnalysisItem[];
  "시장 심리": AnalysisItem[];
  "수급 동향": AnalysisItem[];
}

export interface PredictionAnalysisWidgetProps {
  data: AnalysisData;
  defaultTab?: AnalysisTab;
}

/* ── 상수 ── */
const TABS: AnalysisTab[] = ["기술적 지표", "시장 심리", "수급 동향"];

const SIGNAL_STYLE: Record<
  SignalType,
  { bg: string; color: string; showIcon: boolean }
> = {
  warning: {
    bg: "rgba(245, 158, 11, 0.10)",
    color: "#F59E0B",
    showIcon: true,
  },
  positive: {
    bg: "rgba(0, 200, 83, 0.10)",
    color: "#00C853",
    showIcon: true,
  },
  neutral: {
    bg: "transparent",
    color: "#FFFFFF",
    showIcon: false,
  },
};

/* ── 서브 컴포넌트: 분석 아이템 행 ── */
const AnalysisItemRow: React.FC<{ item: AnalysisItem }> = ({ item }) => {
  const style = SIGNAL_STYLE[item.type];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "5px",
        padding: "6px 10px",
        backgroundColor: style.bg,
        borderRadius: "8px",
        minHeight: "28px",
        boxSizing: "border-box",
      }}
    >
      {/* 아이콘 영역 — 20x20 고정 */}
      {style.showIcon && (
        <div
          style={{
            width: "20px",
            height: "20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {item.type === "warning" ? (
            /* WarningIcon 30x28 viewBox → 20x20 영역에 맞춤 */
            <svg
              width="16"
              height="15"
              viewBox="0 0 30 28"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M16.3261 0.724424C15.8071 -0.241475 14.1932 -0.241475 13.6742 0.724424L0.174404 25.8319C0.0533393 26.057 -0.0065451 26.3091 0.00056714 26.5637C0.00767938 26.8183 0.0815466 27.0668 0.214994 27.285C0.348442 27.5032 0.536934 27.6837 0.762161 27.809C0.987389 27.9343 1.2417 28.0001 1.50038 28H28.4999C28.7586 28.0005 29.013 27.935 29.2383 27.8099C29.4636 27.6848 29.6522 27.5044 29.7856 27.2862C29.919 27.0679 29.9927 26.8194 29.9995 26.5648C30.0063 26.3102 29.946 26.0582 29.8244 25.8334L16.3261 0.724424ZM16.5001 23.5693H13.5002V20.6154H16.5001V23.5693ZM13.5002 17.6616V10.2771H16.5001L16.5016 17.6616H13.5002Z"
                fill="#F59E0B"
              />
            </svg>
          ) : (
            <CheckIcon color={style.color} />
          )}
        </div>
      )}

      {/* 텍스트 */}
      <span
        style={{
          fontSize: "14px",
          fontWeight: 400,
          color: style.color,
          lineHeight: "1.4",
        }}
      >
        {item.text}
      </span>
    </div>
  );
};

/* ── 메인 컴포넌트 ── */
export const PredictionAnalysisWidget: React.FC<
  PredictionAnalysisWidgetProps
> = ({ data, defaultTab = "기술적 지표" }) => {
  const [activeTab, setActiveTab] = useState<AnalysisTab>(defaultTab);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {/* 섹션 레이블 */}
      <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>
        분석 근거
      </span>

      {/* 탭 — 높이 34, 좌우패딩 14, 상하패딩 5, 간격 10 */}
      <div style={{ display: "flex", gap: "10px" }}>
        {TABS.map((tab) => {
          const active = activeTab === tab;
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                height: "34px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "5px 14px",
                backgroundColor: active ? "#2C2C30" : "transparent",
                border: "none",
                borderRadius: "30px",
                cursor: "pointer",
                fontSize: "16px",
                fontWeight: active ? 700 : 400,
                color: active ? "#FFFFFF" : "#9F9F9F",
                whiteSpace: "nowrap",
                transition: "background-color 0.15s ease, color 0.15s ease",
                boxSizing: "border-box",
              }}
            >
              {tab}
            </button>
          );
        })}
      </div>

      {/* 분석 아이템 컨테이너 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          borderRadius: "8px",
          padding: "10px",
          backgroundColor: "#131316",
          boxSizing: "border-box",
        }}
      >
        {data[activeTab].map((item, idx) => (
          <AnalysisItemRow key={idx} item={item} />
        ))}
      </div>
    </div>
  );
};

export default PredictionAnalysisWidget;