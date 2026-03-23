import { cn } from "../../../../lib/utils";
import { ExternalLinkIcon } from "../../../icons/ExternalLinkIcon";
import { GlobalEmptyState } from "../../../common/GlobalEmptyState/GlobalEmptyState";

// ─── Types ────────────────────────────────────────────────────

export interface OrderbookRow {
  price: number;
  changeRate: number;
  quantity: number;
}

export interface TradeTickRow {
  price: number;
  quantity: number;
  isBuy: boolean;
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
  currentPrice: number;
  currentChangeRate: number;
  asks: OrderbookRow[];
  bids: OrderbookRow[];
  trades: TradeTickRow[];
  tradeStrength: number;
  marketInfo: MarketInfo;
  isMarketClosed?: boolean;
  onQuickOrder?: () => void;
  className?: string;
}

// ─── Helpers ──────────────────────────────────────────────────

const fmt = (v: number) => v.toLocaleString("ko-KR");
const fmtRate = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

// ─── QuickOrderButton — 79x24 ─────────────────────────────────

const QuickOrderButton = ({ onClick }: { onClick?: () => void }) => (
  <button
    onClick={onClick}
    style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: "4px",
      width: "79px",
      height: "24px",
      padding: "0",
      border: "1px solid rgba(255,255,255,0.25)",
      borderRadius: "8px",
      background: "transparent",
      cursor: "pointer",
      flexShrink: 0,
    }}
  >
    <ExternalLinkIcon color="#9F9F9F" />
    <span style={{ fontSize: "14px", fontWeight: 400, color: "#9F9F9F" }}>빠른 주문</span>
  </button>
);

// ─── AskRow (매도 잔량 — 좌측상단) ───────────────────────────

const AskRow = ({
  row,
  maxQty = 1,
  isEmpty,
}: {
  row?: OrderbookRow;
  maxQty?: number;
  isEmpty?: boolean;
}) => {
  const barWidth = isEmpty || !row ? 0 : Math.round((row.quantity / maxQty) * 100);

  return (
    <div
      style={{
        position: "relative",
        width: "100px",
        height: "32px",
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-end",
        paddingRight: "8px",
        overflow: "hidden",
      }}
    >
      {/* 구분선: 오른쪽 진하게 → 왼쪽 페이드 */}
      <div style={{
        position: "absolute",
        bottom: 0, left: 0, right: 0,
        height: "1px",
        background: "linear-gradient(to left, rgba(255,255,255,0.15), transparent)",
      }} />

      {!isEmpty && row && (
        <>
          {/* 잔량 바: 오른쪽 기준 왼쪽으로 채워짐 */}
          <div style={{
            position: "absolute",
            top: "50%",
            transform: "translateY(-50%)",
            right: 0,
            width: `${barWidth}%`,
            height: "20px",
            background: "linear-gradient(to left, rgba(37,106,244,0.3), rgba(37,106,244,0.05))",
            borderRadius: "2px 0 0 2px",
          }} />
          {/* 잔량 숫자 */}
          <span style={{ position: "relative", fontSize: "13px", fontWeight: 400, color: "#256AF4" }}>
            {fmt(row.quantity)}
          </span>
        </>
      )}
    </div>
  );
};

// ─── BidRow (매수 잔량 — 우측하단) ───────────────────────────

const BidRow = ({ row, maxQty }: { row: OrderbookRow; maxQty: number }) => {
  const barWidth = Math.round((row.quantity / maxQty) * 100);

  return (
    <div
      style={{
        position: "relative",
        width: "100px",
        height: "32px",
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-start",
        paddingLeft: "8px",
        overflow: "hidden",
      }}
    >
      {/* 구분선: 왼쪽 진하게 → 오른쪽 페이드 */}
      <div style={{
        position: "absolute",
        bottom: 0, left: 0, right: 0,
        height: "1px",
        background: "linear-gradient(to right, rgba(255,255,255,0.15), transparent)",
      }} />

      {/* 잔량 바: 왼쪽 기준 오른쪽으로 채워짐 */}
      <div style={{
        position: "absolute",
        top: "50%",
        transform: "translateY(-50%)",
        left: 0,
        width: `${barWidth}%`,
        height: "20px",
        background: "linear-gradient(to right, rgba(234,88,12,0.3), rgba(234,88,12,0.05))",
        borderRadius: "0 2px 2px 0",
      }} />

      <span style={{ position: "relative", fontSize: "13px", fontWeight: 400, color: "#EA580C" }}>
        {fmt(row.quantity)}
      </span>
    </div>
  );
};

// ─── PriceCell (중앙 가격+등락률) ────────────────────────────

const PriceCell = ({
  price,
  changeRate,
  isCurrentPrice,
}: {
  price: number;
  changeRate: number;
  isCurrentPrice?: boolean;
}) => (
  <div style={{
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "0px",
    width: "100%",
    padding: "0 4px",
  }}>
    <span style={{
      fontSize: "14px",
      fontWeight: 400,
      color: "#256AF4",
      lineHeight: 1.2,
    }}>
      {fmt(price)}
    </span>
    <span style={{
      fontSize: "8px",
      fontWeight: 500,
      color: isCurrentPrice ? "#EA580C" : "#256AF4",
      lineHeight: 1.2,
    }}>
      {fmtRate(changeRate)}
    </span>
  </div>
);

// ─── MarketInfoPanel ──────────────────────────────────────────

const MarketInfoPanel = ({ info }: { info: MarketInfo }) => {
  const divider = (
    <div style={{ height: "1px", background: "rgba(255,255,255,0.08)", margin: "6px 0" }} />
  );
  const Row = ({ label, value, color }: { label: string; value: string; color?: string }) => (
    <div style={{ display: "flex", justifyContent: "space-between", gap: "6px" }}>
      <span style={{ fontSize: "11px", fontWeight: 400, color: "#9F9F9F", whiteSpace: "nowrap" }}>{label}</span>
      <span style={{ fontSize: "11px", fontWeight: 400, color: color ?? "#9F9F9F", whiteSpace: "nowrap" }}>{value}</span>
    </div>
  );

  return (
    <div style={{ width: "110px", display: "flex", flexDirection: "column" }}>
      <Row label="52주 최고" value={fmt(info.weekHigh)} />
      <Row label="52주 최저" value={fmt(info.weekLow)} />
      {divider}
      <Row label="상한가" value={fmt(info.upperLimit)} />
      <Row label="하한가" value={fmt(info.lowerLimit)} />
      <Row label="상승VI" value={info.riseVI ? fmt(info.riseVI) : "-"} />
      <Row label="하강VI" value={info.fallVI ? fmt(info.fallVI) : "-"} />
      {divider}
      <Row label="시작" value={fmt(info.open)} />
      <Row label="최고" value={fmt(info.high)} color="#EA580C" />
      <Row label="최저" value={fmt(info.low)} color="#256AF4" />
      {divider}
      <div style={{ fontSize: "11px", color: "#9F9F9F", whiteSpace: "nowrap" }}>거래량</div>
      <div style={{ fontSize: "11px", color: "#9F9F9F", whiteSpace: "nowrap" }}>{info.volumeUnit}</div>
      <Row label="어제보다" value={`${info.changeFromYesterday}%`} />
      {divider}
      <Row label="중간호가" value={info.midPrice ? fmt(info.midPrice) : "-"} />
    </div>
  );
};

// ─── OrderbookTable ───────────────────────────────────────────

export const OrderbookTable = ({
  currentPrice,
  currentChangeRate,
  asks,
  bids,
  trades,
  tradeStrength,
  marketInfo,
  isMarketClosed = false,
  onQuickOrder,
  className,
}: OrderbookTableProps) => {
  const maxAskQty = Math.max(...asks.map((a) => a.quantity), 1);
  const maxBidQty = Math.max(...bids.map((b) => b.quantity), 1);

  return (
    <div
      className={cn(className)}
      style={{
        width: "340px",
        backgroundColor: "#1C1D21",
        borderRadius: "12px",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 좌측상단 방사형 그라데이션 — opacity 10% */}
      <div style={{
        position: "absolute",
        top: 0, left: 0,
        width: "200px",
        height: "200px",
        background: "radial-gradient(ellipse at top left, rgba(37,106,244,0.1) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />
      {/* 우측하단 방사형 그라데이션 — opacity 10% */}
      <div style={{
        position: "absolute",
        bottom: 0, right: 0,
        width: "200px",
        height: "200px",
        background: "radial-gradient(ellipse at bottom right, rgba(234,88,12,0.1) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />

      {/* 헤더 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", position: "relative" }}>
        <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>호가</span>
        {isMarketClosed
          ? <GlobalEmptyState variant="market-closed" display="badge" />
          : <QuickOrderButton onClick={onQuickOrder} />
        }
      </div>

      {/* 호가 본문 */}
      <div style={{ display: "flex", position: "relative" }}>

        {/* 좌측: 매도 잔량 + 체결강도 + 체결내역 */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          {/* 현재가 행 비움 */}
          <AskRow isEmpty />
          {asks.map((ask, i) => (
            <AskRow key={i} row={ask} maxQty={maxAskQty} />
          ))}
          {/* 체결강도 */}
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "4px 8px 4px 0",
            gap: "10px",
            height: "24px",
          }}>
            <span style={{ fontSize: "12px", fontWeight: 400, color: "#9F9F9F" }}>체결강도</span>
            <span style={{ fontSize: "12px", fontWeight: 400, color: "#256AF4" }}>{tradeStrength}%</span>
          </div>
          {/* 체결 내역 */}
          {trades.map((trade, i) => (
            <div key={i} style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              height: "32px",
              padding: "0 8px 0 0",
              gap: "10px",
            }}>
              <span style={{ fontSize: "12px", fontWeight: 400, color: "#9F9F9F" }}>{fmt(trade.price)}</span>
              <span style={{ fontSize: "12px", fontWeight: 400, color: trade.isBuy ? "#EA580C" : "#256AF4" }}>
                {trade.quantity}
              </span>
            </div>
          ))}
        </div>

        {/* 중앙: 현재가 + 호가 가격 */}
        <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
          {/* 현재가 강조 */}
          <div style={{
            height: "32px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0px",
          }}>
            <span style={{ fontSize: "14px", fontWeight: 400, color: "#256AF4", lineHeight: 1.2 }}>
              {fmt(currentPrice)}
            </span>
            <span style={{ fontSize: "8px", fontWeight: 500, color: "#EA580C", lineHeight: 1.2 }}>
              {fmtRate(currentChangeRate)}
            </span>
          </div>
          {/* 매도 호가 */}
          {asks.map((ask, i) => (
            <div key={i} style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <PriceCell price={ask.price} changeRate={ask.changeRate} />
            </div>
          ))}
          {/* 매수 호가 */}
          {bids.map((bid, i) => (
            <div key={i} style={{ height: "32px", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <PriceCell price={bid.price} changeRate={bid.changeRate} />
            </div>
          ))}
        </div>

        {/* 우측: 시세 정보 패널 + 매수 잔량 */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          {/* 현재가 강조 행 비움 */}
          <div style={{ height: "32px" }} />
          <MarketInfoPanel info={marketInfo} />
          <div style={{ height: "50px" }} />
          {bids.map((bid, i) => (
            <BidRow key={i} row={bid} maxQty={maxBidQty} />
          ))}
        </div>
      </div>
    </div>
  );
};