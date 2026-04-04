import React, { useState } from "react";
import { cn } from "../../../../lib/utils";
import { TradeTickerList } from "../TradeTickerList/TradeTickerList";
import type { TradeTickRow } from "../TradeTickerList/TradeTickerList";
import { ExternalLinkIcon } from "../../../icons/ExternalLinkIcon";
import { GlobalEmptyState } from "../../../common/GlobalEmptyState/GlobalEmptyState";

// ─── Types ────────────────────────────────────────────────────

export type OrderbookStatus = "default" | "skeleton" | "error" | "empty";
export type Viewport = "desktop" | "tablet" | "mobile";

export interface OrderbookRow {
  price: number;
  changeRate: number;
  quantity: number;
}

export interface MarketInfo {
  weekHigh: number;
  weekLow: number;
  upperLimit: number;
  lowerLimit: number;
  riseVI?: number;
  fallVI?: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  volumeUnit: string;
  changeFromYesterday: number;
  midPrice?: number;
}

interface OrderbookTableProps {
  status?: OrderbookStatus;
  viewport?: Viewport;
  /** @deprecated status="empty" 사용 권장 */
  isMarketClosed?: boolean;
  onRetry?: () => void;
  currentPrice?: number;
  currentChangeRate?: number;
  asks?: OrderbookRow[];
  bids?: OrderbookRow[];
  trades?: TradeTickRow[];
  tradeStrength?: number;
  marketInfo?: MarketInfo;
  onQuickOrder?: () => void;
  className?: string;
}

// ─── Helpers ──────────────────────────────────────────────────

const fmt = (v: number) => v.toLocaleString("ko-KR");
const fmtRate = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

// ─── Skeleton ─────────────────────────────────────────────────

const SkeletonBox: React.FC<{
  width?: string | number;
  height?: number;
  borderRadius?: number;
}> = ({ width = "100%", height = 16, borderRadius = 6 }) => (
  <div
    className="animate-[skeleton-pulse_700ms_ease-out_400ms_infinite]"
    style={{ width, height: `${height}px`, borderRadius: `${borderRadius}px`, backgroundColor: "#21242C", flexShrink: 0 }}
  />
);

// 우측 시세 정보 전용 스켈레톤
const SkeletonMarketInfo = () => {
  const D = <div style={{ height: "1px", background: "rgba(255,255,255,0.08)", margin: "6px 0" }} />;
  const R = ({ label }: { label: string }) => (
    <div style={{ display: "flex", justifyContent: "space-between", gap: "6px" }}>
      <span style={{ fontSize: "11px", fontWeight: 400, color: "#9F9F9F", whiteSpace: "nowrap" }}>{label}</span>
      <span style={{ fontSize: "11px", fontWeight: 400, color: "#9F9F9F", whiteSpace: "nowrap" }}>-</span>
    </div>
  );
  return (
    <div style={{ width: "110px", display: "flex", flexDirection: "column" }}>
      <R label="- 주 최고" />
      <R label="- 주 최저" />
      {D}
      <R label="상한가" />
      <R label="하한가" />
      <R label="상승VI" />
      <R label="하강VI" />
      {D}
      <R label="시작" />
      <R label="최고" />
      <R label="최저" />
      {D}
      <div style={{ fontSize: "11px", color: "#9F9F9F", whiteSpace: "nowrap" }}>거래량</div>
      <div style={{ fontSize: "11px", color: "#9F9F9F", whiteSpace: "nowrap" }}>-</div>
      <R label="어제보다" />
      {D}
      <R label="중간호가" />
    </div>
  );
};

// 데스크톱 & 태블릿 스켈레톤
const DesktopOrderbookSkeleton: React.FC = () => (
  <div style={{ display: "flex", position: "relative" }}>
    {/* 좌측: 매도 잔량 및 체결 내역 */}
    <div style={{ display: "flex", flexDirection: "column", width: "100px" }}>
      <div style={{ height: "32px" }} />
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={`ask-qty-${i}`} style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: "8px" }}>
          <SkeletonBox width={76} height={20} borderRadius={6} />
        </div>
      ))}
      <div style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 8px" }}>
        <span style={{ fontSize: "12px", color: "#FFFFFF", fontWeight: 400 }}>체결강도</span>
        <SkeletonBox width={32} height={18} borderRadius={9} />
      </div>
      {Array.from({ length: 14 }).map((_, i) => (
        <div key={`trade-${i}`} style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 8px" }}>
          <span style={{ fontSize: "13px", color: "#FFFFFF", fontWeight: 400 }}>-</span>
          <span style={{ fontSize: "13px", color: "#FFFFFF", fontWeight: 400 }}>-</span>
        </div>
      ))}
    </div>

    {/* 중앙: 호가 가격 */}
    <div style={{ display: "flex", flexDirection: "column", flex: 1, alignItems: "center" }}>
      {Array.from({ length: 21 }).map((_, i) => (
        <div key={`price-${i}`} style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "center", width: "100%" }}>
          <SkeletonBox width={76} height={20} borderRadius={6} />
        </div>
      ))}
    </div>

    {/* 우측: 시세 정보 및 매수 잔량 */}
    <div style={{ display: "flex", flexDirection: "column", width: "110px" }}>
      <div style={{ height: "32px" }} />
      <SkeletonMarketInfo />
      <div style={{ height: "50px" }} />
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={`bid-qty-${i}`} style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "flex-start", paddingLeft: "8px" }}>
          <SkeletonBox width={76} height={20} borderRadius={6} />
        </div>
      ))}
    </div>
  </div>
);

// 모바일 스켈레톤
const MobileOrderbookSkeleton: React.FC = () => (
  <div style={{ display: "flex", flexDirection: "column" }}>
    <div style={{ display: "flex", alignItems: "center", height: "32px" }}>
      <div style={{ flex: 1 }} />
      <div style={{ width: "110px", display: "flex", justifyContent: "center" }}>
        <SkeletonBox width={76} height={20} borderRadius={6} />
      </div>
      <div style={{ flex: 1 }} />
    </div>
    {Array.from({ length: 10 }).map((_, i) => (
      <div key={`mob-skel-${i}`} style={{ display: "flex", alignItems: "center", height: "32px", width: "100%" }}>
        <div style={{ flex: 1, display: "flex", justifyContent: "flex-end", paddingRight: "8px" }}>
          <SkeletonBox width="80%" height={20} borderRadius={6} />
        </div>
        <div style={{ width: "110px", display: "flex", justifyContent: "center" }}>
          <SkeletonBox width={76} height={20} borderRadius={6} />
        </div>
        <div style={{ flex: 1, display: "flex", justifyContent: "flex-start", paddingLeft: "8px" }}>
          <SkeletonBox width="80%" height={20} borderRadius={6} />
        </div>
      </div>
    ))}
  </div>
);

// ─── Error ────────────────────────────────────────────────────

const OrderbookError: React.FC<{ onRetry?: () => void }> = ({ onRetry }) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "600px" }}>
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "16px" }}>
      <svg width="30" height="28" viewBox="0 0 30 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M16.3261 0.724424C15.8071 -0.241475 14.1932 -0.241475 13.6742 0.724424L0.174404 25.8319C0.0533393 26.057 -0.0065451 26.3091 0.00056714 26.5637C0.00767938 26.8183 0.0815466 27.0668 0.214994 27.285C0.348442 27.5032 0.536934 27.6837 0.762161 27.809C0.987389 27.9343 1.2417 28.0001 1.50038 28H28.4999C28.7586 28.0005 29.013 27.935 29.2383 27.8099C29.4636 27.6848 29.6522 27.5044 29.7856 27.2862C29.919 27.0679 29.9927 26.8194 29.9995 26.5648C30.0063 26.3102 29.946 26.0582 29.8244 25.8334L16.3261 0.724424ZM16.5001 23.5693H13.5002V20.6154H16.5001V23.5693ZM13.5002 17.6616V10.2771H16.5001L16.5016 17.6616H13.5002Z" fill="#6B7280" />
      </svg>
      <p style={{ fontSize: "14px", fontWeight: 400, color: "#9F9F9F", textAlign: "center", lineHeight: "1.6", margin: 0 }}>
        호가 데이터를 불러오지 못했습니다.<br />잠시 후 다시 시도해 주세요.
      </p>
    </div>
    <div style={{ marginTop: "36px" }}>
      <button onClick={onRetry} style={{ width: "100px", height: "38px", backgroundColor: "#6B4EFF", border: "none", borderRadius: "8px", cursor: "pointer", fontSize: "14px", fontWeight: 500, color: "#FFFFFF" }}>
        다시 시도
      </button>
    </div>
  </div>
);

// ─── QuickOrderButton ─────────────────────────────────────────

const QuickOrderButton = ({ onClick }: { onClick?: () => void }) => (
  <button
    onClick={onClick}
    style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "4px", width: "79px", height: "24px", padding: "0", border: "1px solid rgba(255,255,255,0.25)", borderRadius: "8px", background: "transparent", cursor: "pointer", flexShrink: 0 }}
  >
    <ExternalLinkIcon color="#9F9F9F" />
    <span style={{ fontSize: "14px", fontWeight: 400, color: "#9F9F9F" }}>빠른 주문</span>
  </button>
);

// ─── Desktop: AskRow ─────────────────────────────────────────

const AskRow = ({ row, maxQty = 1, isEmpty }: { row?: OrderbookRow; maxQty?: number; isEmpty?: boolean }) => {
  const barWidth = isEmpty || !row ? 0 : Math.round((row.quantity / maxQty) * 100);
  return (
    <div style={{ position: "relative", width: "100px", height: "32px", display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: "8px", overflow: "hidden" }}>
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "1px", background: "linear-gradient(to left, rgba(255,255,255,0.15), transparent)" }} />
      {!isEmpty && row && (
        <>
          <div style={{ position: "absolute", top: "50%", transform: "translateY(-50%)", right: 0, width: `${barWidth}%`, height: "20px", background: "linear-gradient(to left, rgba(37,106,244,0.3), rgba(37,106,244,0.05))", borderRadius: "2px 0 0 2px" }} />
          <span style={{ position: "relative", fontSize: "13px", fontWeight: 400, color: "#256AF4" }}>{fmt(row.quantity)}</span>
        </>
      )}
    </div>
  );
};

// ─── Desktop: BidRow ─────────────────────────────────────────

const BidRow = ({ row, maxQty }: { row: OrderbookRow; maxQty: number }) => {
  const barWidth = Math.round((row.quantity / maxQty) * 100);
  return (
    <div style={{ position: "relative", width: "100px", height: "32px", display: "flex", alignItems: "center", justifyContent: "flex-start", paddingLeft: "8px", overflow: "hidden" }}>
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "1px", background: "linear-gradient(to right, rgba(255,255,255,0.15), transparent)" }} />
      <div style={{ position: "absolute", top: "50%", transform: "translateY(-50%)", left: 0, width: `${barWidth}%`, height: "20px", background: "linear-gradient(to right, rgba(234,88,12,0.3), rgba(234,88,12,0.05))", borderRadius: "0 2px 2px 0" }} />
      <span style={{ position: "relative", fontSize: "13px", fontWeight: 400, color: "#EA580C" }}>{fmt(row.quantity)}</span>
    </div>
  );
};

// ─── Desktop: PriceCell ───────────────────────────────────────

const PriceCell = ({ price, changeRate }: { price: number; changeRate: number }) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "100%", padding: "0 4px" }}>
    <span style={{ fontSize: "14px", fontWeight: 400, color: "#256AF4", lineHeight: 1.2 }}>{fmt(price)}</span>
    <span style={{ fontSize: "8px", fontWeight: 500, color: "#256AF4", lineHeight: 1.2 }}>{fmtRate(changeRate)}</span>
  </div>
);

// ─── Desktop: MarketInfoPanel ─────────────────────────────────

const MarketInfoPanel = ({ info }: { info: MarketInfo }) => {
  const D = <div style={{ height: "1px", background: "rgba(255,255,255,0.08)", margin: "6px 0" }} />;
  const R = ({ label, value, color }: { label: string; value: string; color?: string }) => (
    <div style={{ display: "flex", justifyContent: "space-between", gap: "6px" }}>
      <span style={{ fontSize: "11px", fontWeight: 400, color: "#9F9F9F", whiteSpace: "nowrap" }}>{label}</span>
      <span style={{ fontSize: "11px", fontWeight: 400, color: color ?? "#9F9F9F", whiteSpace: "nowrap" }}>{value}</span>
    </div>
  );
  return (
    <div style={{ width: "110px", display: "flex", flexDirection: "column" }}>
      <R label="52주 최고" value={fmt(info.weekHigh)} />
      <R label="52주 최저" value={fmt(info.weekLow)} />
      {D}
      <R label="상한가" value={fmt(info.upperLimit)} />
      <R label="하한가" value={fmt(info.lowerLimit)} />
      <R label="상승VI" value={info.riseVI ? fmt(info.riseVI) : "-"} />
      <R label="하강VI" value={info.fallVI ? fmt(info.fallVI) : "-"} />
      {D}
      <R label="시작" value={fmt(info.open)} />
      <R label="최고" value={fmt(info.high)} color="#EA580C" />
      <R label="최저" value={fmt(info.low)} color="#256AF4" />
      {D}
      <div style={{ fontSize: "11px", color: "#9F9F9F", whiteSpace: "nowrap" }}>거래량</div>
      <div style={{ fontSize: "11px", color: "#9F9F9F", whiteSpace: "nowrap" }}>{info.volumeUnit}</div>
      <R label="어제보다" value={`${info.changeFromYesterday}%`} />
      {D}
      <R label="중간호가" value={info.midPrice ? fmt(info.midPrice) : "-"} />
    </div>
  );
};

// ─── Mobile: AskQuantityCell ──────────────────────────────────

const MobileAskQtyCell = ({ row, maxQty }: { row: OrderbookRow; maxQty: number }) => {
  const barWidth = Math.round((row.quantity / maxQty) * 100);
  return (
    <div style={{ position: "relative", flex: 1, height: "32px", display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: "8px", overflow: "hidden" }}>
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "1px", background: "linear-gradient(to left, rgba(255,255,255,0.15), transparent)" }} />
      <div style={{ position: "absolute", top: "50%", transform: "translateY(-50%)", right: 0, width: `${barWidth}%`, height: "20px", background: "linear-gradient(to left, rgba(37,106,244,0.3), rgba(37,106,244,0.05))", borderRadius: "2px 0 0 2px" }} />
      <span style={{ position: "relative", fontSize: "13px", fontWeight: 400, color: "#256AF4", fontVariantNumeric: "tabular-nums" }}>{fmt(row.quantity)}</span>
    </div>
  );
};

// ─── Mobile: BidQuantityCell ──────────────────────────────────

const MobileBidQtyCell = ({ row, maxQty }: { row: OrderbookRow; maxQty: number }) => {
  const barWidth = Math.round((row.quantity / maxQty) * 100);
  return (
    <div style={{ position: "relative", flex: 1, height: "32px", display: "flex", alignItems: "center", justifyContent: "flex-start", paddingLeft: "8px", overflow: "hidden" }}>
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "1px", background: "linear-gradient(to right, rgba(255,255,255,0.15), transparent)" }} />
      <div style={{ position: "absolute", top: "50%", transform: "translateY(-50%)", left: 0, width: `${barWidth}%`, height: "20px", background: "linear-gradient(to right, rgba(234,88,12,0.3), rgba(234,88,12,0.05))", borderRadius: "0 2px 2px 0" }} />
      <span style={{ position: "relative", fontSize: "13px", fontWeight: 400, color: "#EA580C", fontVariantNumeric: "tabular-nums" }}>{fmt(row.quantity)}</span>
    </div>
  );
};

// ─── Mobile: PriceCell ───────────────────

const MobilePriceCell = ({ price, changeRate, isCurrent }: { price: number; changeRate: number; isCurrent?: boolean }) => (
  <div style={{ width: "110px", flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "32px" }}>
    <span style={{ fontSize: isCurrent ? "14px" : "13px", fontWeight: 400, color: isCurrent ? "#FFFFFF" : "#256AF4", fontVariantNumeric: "tabular-nums", lineHeight: 1.2 }}>
      {fmt(price)}
    </span>
    <span style={{ fontSize: "8px", fontWeight: 500, color: isCurrent ? "#EA580C" : "#256AF4", lineHeight: 1.2 }}>
      {fmtRate(changeRate)}
    </span>
  </div>
);

// ─── Mobile: EmptyCell ───────────────────────────────────────

const MobileEmptyCell = ({ direction }: { direction: "ask" | "bid" }) => (
  <div style={{ position: "relative", flex: 1, height: "32px", overflow: "hidden" }}>
    <div style={{
      position: "absolute", bottom: 0, left: 0, right: 0, height: "1px",
      background: direction === "ask"
        ? "linear-gradient(to right, rgba(255,255,255,0.15), transparent)"
        : "linear-gradient(to left, rgba(255,255,255,0.15), transparent)",
    }} />
  </div>
);

// ─── Mobile: CurrentPriceRow ──────────────────────────────────

const MobileCurrentPriceRow = ({ price, changeRate }: { price: number; changeRate: number }) => (
  <div style={{ display: "flex", alignItems: "center", height: "32px" }}>
    <div style={{ flex: 1 }} />
    <MobilePriceCell price={price} changeRate={changeRate} isCurrent />
    <div style={{ flex: 1 }} />
  </div>
);

// ─── Mobile Orderbook Body ────────────────────────────────────

const MobileOrderbookBody: React.FC<{
  currentPrice: number;
  currentChangeRate: number;
  asks: OrderbookRow[];
  bids: OrderbookRow[];
  maxAskQty: number;
  maxBidQty: number;
}> = ({ currentPrice, currentChangeRate, asks, bids, maxAskQty, maxBidQty }) => {
  const displayAsks = asks.slice(0, 10);
  const displayBids = bids.slice(0, 10);

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {/* 1. 상단 현재가 헤더 */}
      <MobileCurrentPriceRow price={currentPrice} changeRate={currentChangeRate} />

      {/* 2. 매도/매수 좌우 정렬 및 중앙 단일 가격 열 적용 (10행) */}
      {Array.from({ length: 10 }).map((_, i) => {
        const ask = displayAsks[i];
        const bid = displayBids[i];
        
        const price = ask ? ask.price : (bid ? bid.price : 0);
        const changeRate = ask ? ask.changeRate : (bid ? bid.changeRate : 0);

        return (
          <div key={i} style={{ display: "flex", alignItems: "center", height: "32px", width: "100%" }}>
            
            {/* 좌측: 매도 잔량 (없으면 빈 셀) */}
            {ask ? <MobileAskQtyCell row={ask} maxQty={maxAskQty} /> : <MobileEmptyCell direction="ask" />}

            {/* 중앙: 단일 가격 셀 */}
            <MobilePriceCell price={price} changeRate={changeRate} />

            {/* 우측: 매수 잔량 (없으면 빈 셀) */}
            {bid ? <MobileBidQtyCell row={bid} maxQty={maxBidQty} /> : <MobileEmptyCell direction="bid" />}
            
          </div>
        );
      })}
    </div>
  );
};

// ─── OrderbookTable ───────────────────────────────────────────

export const OrderbookTable = ({
  status: statusProp,
  viewport = "desktop",
  isMarketClosed,
  onRetry,
  currentPrice = 0,
  currentChangeRate = 0,
  asks = [],
  bids = [],
  trades = [],
  tradeStrength = 0,
  marketInfo,
  onQuickOrder,
  className,
}: OrderbookTableProps) => {
  const status: OrderbookStatus = statusProp ?? (isMarketClosed ? "empty" : "default");
  const isMobile = viewport === "mobile";

  const maxAskQty = Math.max(...asks.map((a) => a.quantity), 1);
  const maxBidQty = Math.max(...bids.map((b) => b.quantity), 1);

  return (
    <div
      className={cn(className)}
      style={{
        width: isMobile ? "345px" : "340px",
        height: isMobile ? "454px" : "820px", 
        backgroundColor: "#1C1D21",
        borderRadius: "12px",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        position: "relative",
        overflow: "hidden",
        boxSizing: "border-box",
      }}
    >
      {/* 방사형 그라데이션 배경 */}
      <div style={{ position: "absolute", top: 0, left: 0, width: "200px", height: "200px", background: "radial-gradient(ellipse at top left, rgba(37,106,244,0.1) 0%, transparent 70%)", pointerEvents: "none" }} />
      <div style={{ position: "absolute", bottom: 0, right: 0, width: "200px", height: "200px", background: "radial-gradient(ellipse at bottom right, rgba(234,88,12,0.1) 0%, transparent 70%)", pointerEvents: "none" }} />

      {/* 헤더 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", position: "relative" }}>
        <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>호가</span>
        {status === "empty" && <GlobalEmptyState variant="market-closed" display="badge" />}
        
        {/* 스켈레톤 상태일 때도 버튼이 보이도록 변경 */}
        {(status === "default" || status === "skeleton") && !isMobile && <QuickOrderButton onClick={onQuickOrder} />}
        {(status === "default" || status === "skeleton") && isMobile && (
          <button
            onClick={onQuickOrder}
            style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "4px 12px", backgroundColor: "transparent", border: "1px solid rgba(255,255,255,0.2)", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: 400, color: "#9F9F9F" }}
          >
            전체 보기
          </button>
        )}
      </div>

      {/* 상태별 본문 */}
      {status === "skeleton" && (isMobile ? <MobileOrderbookSkeleton /> : <DesktopOrderbookSkeleton />)}
      {status === "error" && <OrderbookError onRetry={onRetry} />}

      {(status === "default" || status === "empty") && marketInfo && (
        <>
          {/* Mobile */}
          {isMobile && (
            <MobileOrderbookBody
              currentPrice={currentPrice}
              currentChangeRate={currentChangeRate}
              asks={asks}
              bids={bids}
              maxAskQty={maxAskQty}
              maxBidQty={maxBidQty}
            />
          )}

          {/* Desktop/Tablet */}
          {!isMobile && (
            <div style={{ display: "flex", position: "relative" }}>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <AskRow isEmpty />
                {asks.map((ask, i) => <AskRow key={i} row={ask} maxQty={maxAskQty} />)}
                <TradeTickerList
                  trades={trades.map((t, i) => ({ ...t, id: `trade-${i}` }))}
                  tradeStrength={tradeStrength}
                  height={trades.length * 32 + 24}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
                <div style={{ height: "32px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: "14px", fontWeight: 400, color: "#256AF4", lineHeight: 1.2 }}>{fmt(currentPrice)}</span>
                  <span style={{ fontSize: "8px", fontWeight: 500, color: "#EA580C", lineHeight: 1.2 }}>{fmtRate(currentChangeRate)}</span>
                </div>
                {asks.map((ask, i) => (
                  <div key={i} style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <PriceCell price={ask.price} changeRate={ask.changeRate} />
                  </div>
                ))}
                {bids.map((bid, i) => (
                  <div key={i} style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <PriceCell price={bid.price} changeRate={bid.changeRate} />
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <div style={{ height: "32px" }} />
                <MarketInfoPanel info={marketInfo} />
                <div style={{ height: "50px" }} />
                {bids.map((bid, i) => <BidRow key={i} row={bid} maxQty={maxBidQty} />)}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};