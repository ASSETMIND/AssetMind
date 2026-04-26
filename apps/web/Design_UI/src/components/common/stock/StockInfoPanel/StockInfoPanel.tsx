import React, { useRef, useState } from "react";
import { DonutChart } from "../DonutChart/DonutChart";
import type { DonutSlice } from "../DonutChart/DonutChart";
import { CategoryModal } from "../CategoryModal/CategoryModal";
import type { CategoryModalProps } from "../CategoryModal/CategoryModal";

// ─── Types ────────────────────────────────────────────────────

export interface CompanyInfo {
  name: string;
  market: string;
  ticker: string;
  exchange: string;
  homepageUrl?: string;
  source?: string;
  description?: string;
  marketCap: string;
  enterpriseValue: string;
  companyName: string;
  ceo: string;
  listingDate: string;
  listingDateSub?: string;
  shares: string;
  sharesSub?: string;
}

export interface BusinessItem {
  id: string;
  name: string;
  marketCap: string;
  logoUrl?: string;
  // CategoryModal에 전달할 데이터
  modalProps?: Omit<CategoryModalProps, "isOpen" | "onClose">;
}

export interface StockInfoPanelProps {
  status?: "default" | "skeleton" | "error";
  company?: CompanyInfo;
  donutSlices?: DonutSlice[];
  donutBaseDate?: string;
  donutNote?: string;
  mainBusinesses?: BusinessItem[];
  otherBusinesses?: BusinessItem[];
  onRetry?: () => void;
}

// ─── 색상 ─────────────────────────────────────────────────────

const DIVIDER = "rgba(255,255,255,0.20)";
const PANEL_BG = "#1C1D21";
const BOX_BG = "#21242C";

// ─── Helpers ──────────────────────────────────────────────────

const SkeletonBox = ({ w, h = 14 }: { w: number | string; h?: number }) => (
  <div
    className="animate-[skeleton-pulse_700ms_ease-out_400ms_infinite]"
    style={{ width: w, height: `${h}px`, borderRadius: "4px", backgroundColor: "#21242C", flexShrink: 0 }}
  />
);

// ─── 좌측 탭 ──────────────────────────────────────────────────

const LEFT_TABS = [
  { id: "main",     label: "주요 정보",     bold: true },
  { id: "finance",  label: "재무",          bold: false },
  { id: "result",   label: "실적",          bold: false },
  { id: "dividend", label: "배당",          bold: false },
  { id: "peer",     label: "동종 업계 비교", bold: false },
  { id: "analyst",  label: "애널리스트 분석", bold: false },
];

// ─── 홈페이지 버튼 ────────────────────────────────────────────

const HomepageButton: React.FC<{ url?: string }> = ({ url }) => (
  <button
    onClick={() => url && window.open(url, "_blank")}
    style={{
      display: "flex", alignItems: "center", gap: "4px",
      background: "none", border: "1px solid #2F3037",
      cursor: "pointer", padding: "4px 8px", borderRadius: "4px",
      flexShrink: 0,
    }}
  >
    {/* ExternalLink 아이콘 인라인 */}
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M6.66667 3.33333H3.33333C2.97971 3.33333 2.64057 3.47381 2.39052 3.72386C2.14048 3.97391 2 4.31304 2 4.66667V12.6667C2 13.0203 2.14048 13.3594 2.39052 13.6095C2.64057 13.8595 2.97971 14 3.33333 14H11.3333C11.687 14 12.0261 13.8595 12.2761 13.6095C12.5262 13.3594 12.6667 13.0203 12.6667 12.6667V9.33333" stroke="#9F9F9F" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M9.33333 2H14V6.66667" stroke="#9F9F9F" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M6.66667 9.33333L14 2" stroke="#9F9F9F" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
    <span style={{ fontSize: "14px", fontWeight: 400, color: "#9F9F9F" }}>홈페이지</span>
  </button>
);

// ─── 기업 정보 테이블 ─────────────────────────────────────────

const InfoTable: React.FC<{ company: CompanyInfo }> = ({ company }) => {
  const rows = [
    [
      { label: "시가총액",     value: company.marketCap,       subValue: undefined },
      { label: "실제 기업 가치", value: company.enterpriseValue, subValue: undefined },
    ],
    [
      { label: "기업명",  value: company.companyName, subValue: undefined },
      { label: "대표이사", value: company.ceo,         subValue: undefined },
    ],
    [
      { label: "상장일",    value: company.listingDate, subValue: company.listingDateSub },
      { label: "발행주식수", value: company.shares,      subValue: company.sharesSub },
    ],
  ];

  return (
    <div style={{ width: "100%" }}>
      {rows.map((row, ri) => (
        <div key={ri}>
          {/* 구분선 */}
          <div style={{ height: "1px", backgroundColor: DIVIDER }} />
          <div style={{ display: "flex" }}>
            {row.map((cell, ci) => (
              <div
                key={ci}
                style={{
                  flex: 1,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  padding: "12px 0",
                  borderRight: ci === 0 ? `1px solid ${DIVIDER}` : "none",
                  paddingLeft: ci === 1 ? "24px" : 0,
                  paddingRight: ci === 0 ? "24px" : 0,
                  gap: "8px",
                }}
              >
                <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1", flexShrink: 0 }}>
                  {cell.label}
                </span>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
                  <span style={{ fontSize: "14px", fontWeight: 700, color: "#FFFFFF", textAlign: "right" }}>
                    {cell.value}
                  </span>
                  {cell.subValue && (
                    <span style={{ fontSize: "12px", fontWeight: 400, color: "#9194A1", textAlign: "right" }}>
                      {cell.subValue}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {/* 마지막 구분선 */}
      <div style={{ height: "1px", backgroundColor: DIVIDER }} />
    </div>
  );
};

// ─── 사업 아이템 ──────────────────────────────────────────────

const BusinessItemCard: React.FC<{ item: BusinessItem; onClick?: () => void }> = ({ item, onClick }) => (
  <div
    onClick={onClick}
    style={{
      display: "flex", alignItems: "center", gap: "12px",
      cursor: onClick ? "pointer" : "default",
      padding: "8px 0",
    }}
  >
    {/* 로고 */}
    <div style={{
      width: "40px", height: "40px", borderRadius: "8px",
      backgroundColor: BOX_BG, flexShrink: 0,
      display: "flex", alignItems: "center", justifyContent: "center",
      overflow: "hidden",
    }}>
      {item.logoUrl ? (
        <img src={item.logoUrl} alt={item.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : (
        <div style={{ width: "100%", height: "100%", backgroundColor: "#2F3037", borderRadius: "8px" }} />
      )}
    </div>
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>{item.name}</span>
      <span style={{ fontSize: "12px", fontWeight: 400, color: "#9194A1" }}>시가총액 {item.marketCap}</span>
    </div>
  </div>
);

// ─── 에러 ─────────────────────────────────────────────────────

const ErrorBlock: React.FC<{ onRetry?: () => void }> = ({ onRetry }) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, gap: "16px" }}>
    <svg width="30" height="28" viewBox="0 0 30 28" fill="none">
      <path d="M16.3261 0.724424C15.8071 -0.241475 14.1932 -0.241475 13.6742 0.724424L0.174404 25.8319C0.0533393 26.057 -0.0065451 26.3091 0.00056714 26.5637C0.00767938 26.8183 0.0815466 27.0668 0.214994 27.285C0.348442 27.5032 0.536934 27.6837 0.762161 27.809C0.987389 27.9343 1.2417 28.0001 1.50038 28H28.4999C28.7586 28.0005 29.013 27.935 29.2383 27.8099C29.4636 27.6848 29.6522 27.5044 29.7856 27.2862C29.919 27.0679 29.9927 26.8194 29.9995 26.5648C30.0063 26.3102 29.946 26.0582 29.8244 25.8334L16.3261 0.724424ZM16.5001 23.5693H13.5002V20.6154H16.5001V23.5693ZM13.5002 17.6616V10.2771H16.5001L16.5016 17.6616H13.5002Z" fill="#6B7280" />
    </svg>
    <p style={{ fontSize: "14px", color: "#9F9F9F", textAlign: "center", margin: 0 }}>
      데이터를 불러오지 못했습니다.<br />잠시 후 다시 시도해 주세요.
    </p>
    <button onClick={onRetry} style={{ width: "100px", height: "38px", backgroundColor: "#6D4AE6", border: "none", borderRadius: "8px", cursor: "pointer", fontSize: "14px", fontWeight: 500, color: "#FFFFFF" }}>
      다시 시도
    </button>
  </div>
);

// ─── StockInfoPanel ───────────────────────────────────────────

export const StockInfoPanel: React.FC<StockInfoPanelProps> = ({
  status = "default",
  company,
  donutSlices = [],
  donutBaseDate = "",
  donutNote = "",
  mainBusinesses = [],
  otherBusinesses = [],
  onRetry,
}) => {
  const [activeTab, setActiveTab] = useState("main");
  const [showAll, setShowAll] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedBusiness, setSelectedBusiness] = useState<BusinessItem | null>(null);

  const handleBusinessClick = (item: BusinessItem) => {
    if (item.modalProps) {
      setSelectedBusiness(item);
      setModalOpen(true);
    }
  };

  // 각 섹션 ref (스크롤 책갈피)
  const sectionRefs: Record<string, React.RefObject<HTMLDivElement>> = {
    main:     useRef<HTMLDivElement>(null),
    finance:  useRef<HTMLDivElement>(null),
    result:   useRef<HTMLDivElement>(null),
    dividend: useRef<HTMLDivElement>(null),
    peer:     useRef<HTMLDivElement>(null),
    analyst:  useRef<HTMLDivElement>(null),
  };
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const handleTabClick = (id: string) => {
    setActiveTab(id);
    const ref = sectionRefs[id];
    if (ref?.current && scrollContainerRef.current) {
      const containerTop = scrollContainerRef.current.getBoundingClientRect().top;
      const sectionTop = ref.current.getBoundingClientRect().top;
      scrollContainerRef.current.scrollTop += sectionTop - containerTop - 24;
    }
  };

  // 더 보기: 기본 6개 → 전체(주요 6 + 그 외 전체)
  const displayedMain = mainBusinesses.slice(0, 6);
  const displayedOther = showAll ? otherBusinesses : [];

  return (
    <div
      style={{
        width: "1036px",
        height: "820px",
        backgroundColor: PANEL_BG,
        borderRadius: "12px",
        display: "flex",
        overflow: "hidden",
        boxSizing: "border-box",
      }}
    >
      {/* ── 좌측 탭 ── */}
      <div
        style={{
          width: "250px",
          height: "820px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          gap: "4px",
          padding: "24px 0",
          borderRight: "none",
          boxSizing: "border-box",
        }}
      >
        {LEFT_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab.id)}
            style={{
              width: "100%",
              padding: "10px 24px",
              backgroundColor: activeTab === tab.id ? BOX_BG : "transparent",
              border: "none",
              borderRadius: activeTab === tab.id ? "8px" : 0,
              cursor: "pointer",
              textAlign: "left",
              fontSize: "16px",
              fontWeight: activeTab === tab.id ? 700 : 400,
              color: activeTab === tab.id ? "#FFFFFF" : "#9194A1",
              transition: "background-color 0.15s ease",
              marginLeft: tab.bold ? 0 : "8px",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── 우측 콘텐츠 ── */}
      {status === "error" && <ErrorBlock onRetry={onRetry} />}

      {status === "skeleton" && (
        <div style={{ flex: 1, padding: "24px 30px", display: "flex", flexDirection: "column", gap: "16px" }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonBox key={i} w="100%" h={i === 0 ? 20 : 28} />
          ))}
        </div>
      )}

      {status === "default" && company && (
        <div
          ref={scrollContainerRef}
          style={{
            flex: 1,
            overflowY: "auto",
            overflowX: "hidden",
            scrollbarWidth: "none",
            padding: "24px 30px",
            boxSizing: "border-box",
            display: "flex",
            flexDirection: "column",
            gap: "24px",
          }}
        >
          {/* ── 주요 정보 섹션 ── */}
          <div ref={sectionRefs.main} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {/* 헤더 */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>{company.name}</span>
                  <span style={{ fontSize: "13px", fontWeight: 400, color: "#9194A1" }}>
                    {company.market} · {company.ticker} · {company.exchange}
                  </span>
                </div>
                {company.source !== undefined && (
                  <span style={{ fontSize: "12px", fontWeight: 400, color: "#9194A1" }}>
                    출처: {company.source}
                  </span>
                )}
              </div>
              <HomepageButton url={company.homepageUrl} />
            </div>

            {/* 기업 소개 텍스트 박스 */}
            {company.description && (
              <div style={{
                backgroundColor: BOX_BG,
                borderRadius: "8px",
                padding: "16px",
                fontSize: "14px",
                fontWeight: 400,
                color: "#FFFFFF",
                lineHeight: "1.6",
              }}>
                {company.description}
              </div>
            )}

            {/* 기업 정보 테이블 */}
            <InfoTable company={company} />
          </div>

          {/* ── 매출·산업 구성 섹션 ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <div>
              <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>매출·산업 구성</span>
              {donutBaseDate && (
                <div>
                  <span style={{ fontSize: "12px", fontWeight: 400, color: "#9194A1" }}>{donutBaseDate} (출처: Reference)</span>
                </div>
              )}
            </div>

            {/* 도넛 차트 박스 */}
            <div style={{
              backgroundColor: BOX_BG,
              borderRadius: "8px",
              padding: "32px 24px",
              display: "flex",
              alignItems: "center",
              gap: "40px",
            }}>
              {/* 도넛 차트 */}
              <DonutChart slices={donutSlices} size={152} />

              {/* 범례 */}
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {donutSlices.map((slice, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: slice.color, flexShrink: 0 }} />
                    <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>{slice.label}</span>
                    <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1", marginLeft: "4px" }}>
                      {slice.value.toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* 주석 */}
            {donutNote && (
              <span style={{ fontSize: "11px", fontWeight: 400, color: "#9194A1" }}>{donutNote}</span>
            )}
          </div>

          {/* ── 주요 사업 섹션 ── */}
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>주요 사업</span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0px" }}>
              {displayedMain.map((item) => (
                <BusinessItemCard
                  key={item.id}
                  item={item}
                  onClick={() => handleBusinessClick(item)}
                />
              ))}
            </div>

            {/* 그 외 사업 — 더 보기 시 표시 */}
            {showAll && otherBusinesses.length > 0 && (
              <>
                <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF", marginTop: "8px" }}>그 외 사업</span>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0px" }}>
                  {otherBusinesses.map((item) => (
                    <BusinessItemCard
                      key={item.id}
                      item={item}
                      onClick={() => handleBusinessClick(item)}
                    />
                  ))}
                </div>
              </>
            )}

            {/* 더 보기 / 접기 버튼 */}
            <div style={{ display: "flex", justifyContent: "center", paddingTop: "8px" }}>
              <button
                onClick={() => setShowAll((v) => !v)}
                style={{
                  display: "inline-flex", alignItems: "center", gap: "4px",
                  backgroundColor: "transparent", border: "none",
                  cursor: "pointer", fontSize: "14px", fontWeight: 400, color: "#9194A1",
                }}
              >
                {showAll ? "접기 ▴" : "더 보기 ▾"}
              </button>
            </div>
          </div>

          {/* ── CategoryModal ── */}
          {selectedBusiness?.modalProps && (
            <CategoryModal
              isOpen={modalOpen}
              onClose={() => { setModalOpen(false); setSelectedBusiness(null); }}
              {...selectedBusiness.modalProps}
            />
          )}

          {/* ── 재무 섹션 placeholder ── */}
          <div ref={sectionRefs.finance} style={{ paddingTop: "8px" }}>
            <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>재무</span>
            <div style={{ marginTop: "12px", padding: "24px", backgroundColor: BOX_BG, borderRadius: "8px" }}>
              <span style={{ fontSize: "14px", color: "#9194A1" }}>재무 데이터 — 추후 구현 예정</span>
            </div>
          </div>

          {/* ── 실적 섹션 placeholder ── */}
          <div ref={sectionRefs.result} style={{ paddingTop: "8px" }}>
            <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>실적</span>
            <div style={{ marginTop: "12px", padding: "24px", backgroundColor: BOX_BG, borderRadius: "8px" }}>
              <span style={{ fontSize: "14px", color: "#9194A1" }}>실적 데이터 — 추후 구현 예정</span>
            </div>
          </div>

          {/* ── 배당 섹션 placeholder ── */}
          <div ref={sectionRefs.dividend} style={{ paddingTop: "8px" }}>
            <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>배당</span>
            <div style={{ marginTop: "12px", padding: "24px", backgroundColor: BOX_BG, borderRadius: "8px" }}>
              <span style={{ fontSize: "14px", color: "#9194A1" }}>배당 데이터 — 추후 구현 예정</span>
            </div>
          </div>

          {/* ── 동종 업계 비교 섹션 placeholder ── */}
          <div ref={sectionRefs.peer} style={{ paddingTop: "8px" }}>
            <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>동종 업계 비교</span>
            <div style={{ marginTop: "12px", padding: "24px", backgroundColor: BOX_BG, borderRadius: "8px" }}>
              <span style={{ fontSize: "14px", color: "#9194A1" }}>동종 업계 비교 — 추후 구현 예정</span>
            </div>
          </div>

          {/* ── 애널리스트 분석 섹션 placeholder ── */}
          <div ref={sectionRefs.analyst} style={{ paddingTop: "8px" }}>
            <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>애널리스트 분석</span>
            <div style={{ marginTop: "12px", padding: "24px", backgroundColor: BOX_BG, borderRadius: "8px" }}>
              <span style={{ fontSize: "14px", color: "#9194A1" }}>애널리스트 분석 — 추후 구현 예정</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StockInfoPanel;