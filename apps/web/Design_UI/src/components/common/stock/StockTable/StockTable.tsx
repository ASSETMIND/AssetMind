import { useEffect, useRef, useState } from "react";
import { cn } from "../../../../lib/utils";
import { PriceChangeToken } from "../../PriceChangeToken/PriceChangeToken";
import { LinearGauge } from "../../stock/LinearGauge/LinearGauge";

// ─── Types ────────────────────────────────────────────────────

export type Viewport = "desktop" | "tablet" | "mobile";

export interface StockRow {
  id: string;
  rank: number;
  isFavorite: boolean;
  logoUrl?: string;
  name: string;
  price: number;
  changeRate: number;
  tradeAmount: number;
  buyRatio: number;
  tickerState?: "rise" | "fall" | "idle";
}

interface StockTableProps {
  rows: StockRow[];
  viewport?: Viewport;
  onFavoriteToggle?: (id: string) => void;
  onRowClick?: (id: string) => void;
  className?: string;
}

// ─── Layout config ────────────────────────────────────────────
// 프레임 크기: desktop=1200, tablet=768, mobile=393 (절대 변경 금지)
// 모든 뷰포트에서 폰트는 15px medium 통일
// 공간 부족 시 letterSpacing으로 조정

const LAYOUT = {
  desktop: {
    totalWidth: 1200,
    rankWidth: 60,
    nameWidth: 598,
    priceWidth: 100,
    changeRateWidth: 100,
    tradeAmountWidth: 130,
    buyRatioWidth: 180,
    showTradeAmount: true,
    showBuyRatio: true,
    nameFlex: false,
  },
  tablet: {
    totalWidth: 768,
    rankWidth: 56,
    nameWidth: 0,   // flex
    priceWidth: 100,
    changeRateWidth: 100,
    tradeAmountWidth: 120,
    buyRatioWidth: 0,
    showTradeAmount: true,
    showBuyRatio: false,
    nameFlex: true,
  },
  mobile: {
    totalWidth: 393,
    rankWidth: 48,
    nameWidth: 0,   // flex
    priceWidth: 90,
    changeRateWidth: 80,
    tradeAmountWidth: 0,
    buyRatioWidth: 0,
    showTradeAmount: false,
    showBuyRatio: false,
    nameFlex: true,
  },
} as const;

// ─── HeartIcon ────────────────────────────────────────────────

const HeartIcon = ({ active }: { active: boolean }) => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill={active ? "#EA580C" : "#4B4B50"}
    xmlns="http://www.w3.org/2000/svg"
  >
    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
  </svg>
);

// ─── SlotPrice ────────────────────────────────────────────────

const SlotPrice = ({
  value,
  letterSpacing = "normal",
}: {
  value: number;
  letterSpacing?: string;
}) => {
  const [display, setDisplay] = useState(value.toLocaleString("ko-KR") + "원");
  const [animating, setAnimating] = useState(false);
  const prevRef = useRef(value);

  useEffect(() => {
    if (prevRef.current === value) return;
    prevRef.current = value;
    setAnimating(true);
    const t = setTimeout(() => {
      setDisplay(value.toLocaleString("ko-KR") + "원");
      setAnimating(false);
    }, 200);
    return () => clearTimeout(t);
  }, [value]);

  return (
    <span
      style={{
        display: "inline-block",
        overflow: "hidden",
        height: "1.2em",
        fontSize: "15px",
        fontWeight: 500,
        fontVariantNumeric: "tabular-nums",
        whiteSpace: "nowrap",
        color: "#FFFFFF",
        position: "relative",
        letterSpacing,
      }}
    >
      <span
        style={{
          display: "inline-block",
          animation: animating ? "slotEnter 200ms ease-out forwards" : "none",
        }}
      >
        {display}
      </span>
      <style>{`
        @keyframes slotEnter {
          from { transform: translateY(100%); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
      `}</style>
    </span>
  );
};

// ─── StockTableRow ────────────────────────────────────────────

export const StockTableRow = ({
  row,
  viewport = "desktop",
  onFavoriteToggle,
  onRowClick,
}: {
  row: StockRow;
  viewport?: Viewport;
  onFavoriteToggle?: (id: string) => void;
  onRowClick?: (id: string) => void;
}) => {
  const L = LAYOUT[viewport];
  const isMobile = viewport === "mobile";
  const isTablet = viewport === "tablet";

  // 공간 절약을 위한 letterSpacing: mobile/tablet에서 약간 좁힘
  const numericLetterSpacing = isMobile ? "-0.3px" : isTablet ? "-0.2px" : "normal";

  const bgColor =
    row.tickerState === "rise"
      ? "rgba(234,88,12,0.1)"
      : row.tickerState === "fall"
      ? "rgba(37,106,244,0.1)"
      : "transparent";

  return (
    <div
      onClick={() => onRowClick?.(row.id)}
      style={{
        width: `${L.totalWidth}px`,
        height: "60px",
        display: "flex",
        alignItems: "center",
        paddingLeft: "16px",
        paddingRight: "16px",
        paddingTop: "12px",
        paddingBottom: "12px",
        backgroundColor: bgColor,
        transition: "background-color 150ms ease-out",
        cursor: "pointer",
        boxSizing: "border-box",
      }}
    >
      {/* 하트 + 순위 */}
      <div
        style={{
          width: `${L.rankWidth}px`,
          height: "21px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: isMobile ? "10px" : "14px",
          flexShrink: 0,
        }}
      >
        <button
          onClick={(e) => { e.stopPropagation(); onFavoriteToggle?.(row.id); }}
          aria-label={row.isFavorite ? "즐겨찾기 해제" : "즐겨찾기 추가"}
          style={{ background: "none", border: "none", padding: 0, cursor: "pointer", display: "flex", alignItems: "center" }}
        >
          <HeartIcon active={row.isFavorite} />
        </button>
        <span
          style={{
            fontSize: "15px",
            fontWeight: 700,
            color: "#9194A1",
            fontVariantNumeric: "tabular-nums",
            minWidth: "16px",
            textAlign: "center",
            flexShrink: 0,
            letterSpacing: numericLetterSpacing,
          }}
        >
          {row.rank}
        </span>
      </div>

      {/* 로고 + 종목명 */}
      <div
        style={{
          width: L.nameFlex ? undefined : `${L.nameWidth}px`,
          flex: L.nameFlex ? 1 : undefined,
          height: "36px",
          display: "flex",
          alignItems: "center",
          gap: isMobile ? "10px" : "14px",
          flexShrink: L.nameFlex ? undefined : 0,
          overflow: "hidden",
          minWidth: 0,
        }}
      >
        {row.logoUrl ? (
          <img
            src={row.logoUrl}
            alt={row.name}
            style={{
              width: isMobile ? "28px" : "36px",
              height: isMobile ? "28px" : "36px",
              borderRadius: "50%",
              objectFit: "cover",
              flexShrink: 0,
            }}
          />
        ) : (
          <div
            style={{
              width: isMobile ? "28px" : "36px",
              height: isMobile ? "28px" : "36px",
              borderRadius: "50%",
              backgroundColor: "#21242C",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: "12px", fontWeight: 400, color: "#9194A1" }}>
              {row.name[0]}
            </span>
          </div>
        )}
        <span
          style={{
            fontSize: "15px",
            fontWeight: 500,
            color: "#FFFFFF",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            letterSpacing: isMobile ? "-0.2px" : "normal",
          }}
        >
          {row.name}
        </span>
      </div>

      {/* 현재가 */}
      <div
        style={{
          width: `${L.priceWidth}px`,
          height: "21px",
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          flexShrink: 0,
        }}
      >
        <SlotPrice value={row.price} letterSpacing={numericLetterSpacing} />
      </div>

      {/* 등락률 */}
      <div
        style={{
          width: `${L.changeRateWidth}px`,
          height: "21px",
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          flexShrink: 0,
          paddingLeft: isMobile ? "6px" : "11px",
          paddingRight: isMobile ? "4px" : "11px",
          boxSizing: "border-box",
        }}
      >
        <PriceChangeToken value={row.changeRate} />
      </div>

      {/* 거래대금 — tablet/desktop */}
      {L.showTradeAmount && (
        <div
          style={{
            width: `${L.tradeAmountWidth}px`,
            height: "21px",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontSize: "15px",
              fontWeight: 500,
              color: "#FFFFFF",
              fontVariantNumeric: "tabular-nums",
              whiteSpace: "nowrap",
              letterSpacing: isTablet ? "-0.2px" : "normal",
            }}
          >
            {row.tradeAmount.toLocaleString("ko-KR")}원
          </span>
        </div>
      )}

      {/* 거래 비율 — desktop */}
      {L.showBuyRatio && (
        <div
          style={{
            width: `${L.buyRatioWidth}px`,
            height: "18px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <LinearGauge buyRatio={row.buyRatio} />
        </div>
      )}
    </div>
  );
};

// ─── StockTable ───────────────────────────────────────────────

export const StockTable = ({
  rows,
  viewport = "desktop",
  onFavoriteToggle,
  onRowClick,
  className,
}: StockTableProps) => {
  const L = LAYOUT[viewport];
  const isMobile = viewport === "mobile";
  const isTablet = viewport === "tablet";

  return (
    <div className={cn("", className)} style={{ width: `${L.totalWidth}px` }}>
      {/* 헤더 */}
      <div
        style={{
          width: `${L.totalWidth}px`,
          height: "26px",
          display: "flex",
          alignItems: "center",
          paddingLeft: "16px",
          paddingRight: "16px",
          paddingTop: "3px",
          paddingBottom: "3px",
          boxSizing: "border-box",
        }}
      >
        {/* 순위+종목명 묶음 */}
        <div
          style={{
            width: L.nameFlex ? undefined : `${L.rankWidth + L.nameWidth}px`,
            flex: L.nameFlex ? 1 : undefined,
            height: "20px",
            display: "flex",
            alignItems: "center",
            flexShrink: L.nameFlex ? undefined : 0,
          }}
        >
          <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1", whiteSpace: "nowrap" }}>
            순위 · 오늘 00:00 기준
          </span>
        </div>

        {/* 현재가 */}
        <div
          style={{
            width: `${L.priceWidth}px`,
            height: "20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1" }}>현재가</span>
        </div>

        {/* 등락률 */}
        <div
          style={{
            width: `${L.changeRateWidth}px`,
            height: "20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1" }}>등락률</span>
        </div>

        {/* 거래대금 */}
        {L.showTradeAmount && (
          <div
            style={{
              width: `${L.tradeAmountWidth}px`,
              height: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1", whiteSpace: "nowrap" }}>
              거래대금 순
            </span>
          </div>
        )}

        {/* 거래 비율 */}
        {L.showBuyRatio && (
          <div
            style={{
              width: `${L.buyRatioWidth}px`,
              height: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1", whiteSpace: "nowrap" }}>
              거래 비율
            </span>
          </div>
        )}
      </div>

      {/* 행 */}
      {rows.map((row) => (
        <StockTableRow
          key={row.id}
          row={row}
          viewport={viewport}
          onFavoriteToggle={onFavoriteToggle}
          onRowClick={onRowClick}
        />
      ))}
    </div>
  );
};