import { cn } from "../../../../lib/utils";
import { TradeTickerList } from "../TradeTickerList/TradeTickerList";
import type { TradeTickRow } from "../TradeTickerList/TradeTickerList";
import { ExternalLinkIcon } from "../../../icons/ExternalLinkIcon";
import { GlobalEmptyState } from "../../../common/GlobalEmptyState/GlobalEmptyState";

// ─── Types ────────────────────────────────────────────────────

export type OrderbookStatus = "default" | "skeleton" | "error" | "empty";

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
  /** @deprecated status="empty" */
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
    style={{
      width,
      height: `${height}px`,
      borderRadius: `${borderRadius}px`,
      backgroundColor: "#21242C",
      flexShrink: 0,
    }}
  />
);

const OrderbookSkeleton: React.FC = () => (
  <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
    {/* 헤더 */}
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>호가</span>
      <SkeletonBox width={79} height={24} borderRadius={8} />
    </div>

    {/* 호가 테이블 스켈레톤 */}
    <div style={{ display: "flex", gap: "4px" }}>
      {/* 좌측 잔량 */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", width: "100px" }}>
        {Array.from({ length: 12 }).map((_, i) => (
          <SkeletonBox key={i} width={100} height={28} borderRadius={4} />
        ))}
      </div>
      {/* 중앙 가격 */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
        <SkeletonBox height={28} borderRadius={4} />
        {Array.from({ length: 11 }).map((_, i) => (
          <SkeletonBox key={i} height={28} borderRadius={4} />
        ))}
      </div>
      {/* 우측 시세+잔량 */}
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", width: "100px" }}>
        {Array.from({ length: 12 }).map((_, i) => (
          <SkeletonBox key={i} width={100} height={28} borderRadius={4} />
        ))}
      </div>
    </div>
  </div>
);

// ─── Error ────────────────────────────────────────────────────

const OrderbookError: React.FC<{ onRetry?: () => void }> = ({ onRetry }) => (
  <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: "16px",
      minHeight: "480px",
    }}
  >
    <svg width="40" height="38" viewBox="0 0 30 28" fill="none" xmlns="http://www.w3.org/2000/svg">
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
      호가 데이터를 불러오지 못했습니다.
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

// ─── AskRow ───────────────────────────────────────────────────

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
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0, height: "1px",
        background: "linear-gradient(to left, rgba(255,255,255,0.15), transparent)",
      }} />
      {!isEmpty && row && (
        <>
          <div style={{
            position: "absolute", top: "50%", transform: "translateY(-50%)",
            right: 0, width: `${barWidth}%`, height: "20px",
            background: "linear-gradient(to left, rgba(37,106,244,0.3), rgba(37,106,244,0.05))",
            borderRadius: "2px 0 0 2px",
          }} />
          <span style={{ position: "relative", fontSize: "13px", fontWeight: 400, color: "#256AF4" }}>
            {fmt(row.quantity)}
          </span>
        </>
      )}
    </div>
  );
};

// ─── BidRow ───────────────────────────────────────────────────

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
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0, height: "1px",
        background: "linear-gradient(to right, rgba(255,255,255,0.15), transparent)",
      }} />
      <div style={{
        position: "absolute", top: "50%", transform: "translateY(-50%)",
        left: 0, width: `${barWidth}%`, height: "20px",
        background: "linear-gradient(to right, rgba(234,88,12,0.3), rgba(234,88,12,0.05))",
        borderRadius: "0 2px 2px 0",
      }} />
      <span style={{ position: "relative", fontSize: "13px", fontWeight: 400, color: "#EA580C" }}>
        {fmt(row.quantity)}
      </span>
    </div>
  );
};

// ─── PriceCell ────────────────────────────────────────────────

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
    display: "flex", flexDirection: "column", alignItems: "center",
    gap: "0px", width: "100%", padding: "0 4px",
  }}>
    <span style={{ fontSize: "14px", fontWeight: 400, color: "#256AF4", lineHeight: 1.2 }}>
      {fmt(price)}
    </span>
    <span style={{
      fontSize: "8px", fontWeight: 500,
      color: isCurrentPrice ? "#EA580C" : "#256AF4", lineHeight: 1.2,
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

// ─── HeaderAction ─────────────────────────────────────────────

const HeaderAction = ({
  status,
  onQuickOrder,
}: {
  status: OrderbookStatus;
  onQuickOrder?: () => void;
}) => {
  if (status === "empty") {
    return <GlobalEmptyState variant="market-closed" display="badge" />;
  }
  if (status === "error" || status === "skeleton") return null;
  return <QuickOrderButton onClick={onQuickOrder} />;
};

// ─── OrderbookTable ───────────────────────────────────────────

export const OrderbookTable = ({
  status: statusProp,
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
  // isMarketClosed 하위 호환 처리
  const status: OrderbookStatus = statusProp ?? (isMarketClosed ? "empty" : "default");

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
      {/* 방사형 그라데이션 배경 */}
      <div style={{
        position: "absolute", top: 0, left: 0, width: "200px", height: "200px",
        background: "radial-gradient(ellipse at top left, rgba(37,106,244,0.1) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />
      <div style={{
        position: "absolute", bottom: 0, right: 0, width: "200px", height: "200px",
        background: "radial-gradient(ellipse at bottom right, rgba(234,88,12,0.1) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />

      {/* 헤더 — 항상 표시 */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", position: "relative",
      }}>
        <span style={{ fontSize: "14px", fontWeight: 400, color: "#FFFFFF" }}>호가</span>
        <HeaderAction status={status} onQuickOrder={onQuickOrder} />
      </div>

      {/* 상태별 본문 */}
      {status === "skeleton" && <OrderbookSkeleton />}

      {status === "error" && <OrderbookError onRetry={onRetry} />}

      {(status === "default" || status === "empty") && marketInfo && (
        <div style={{ display: "flex", position: "relative" }}>
          {/* 좌측: 매도 잔량 + 체결 내역 */}
          <div style={{ display: "flex", flexDirection: "column" }}>
            <AskRow isEmpty />
            {asks.map((ask, i) => (
              <AskRow key={i} row={ask} maxQty={maxAskQty} />
            ))}
            <TradeTickerList
              trades={trades.map((t, i) => ({ ...t, id: `trade-${i}` }))}
              tradeStrength={tradeStrength}
              height={trades.length * 32 + 24}
            />
          </div>

          {/* 중앙: 현재가 + 호가 가격 */}
          <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
            <div style={{
              height: "32px", display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
            }}>
              <span style={{ fontSize: "14px", fontWeight: 400, color: "#256AF4", lineHeight: 1.2 }}>
                {fmt(currentPrice)}
              </span>
              <span style={{ fontSize: "8px", fontWeight: 500, color: "#EA580C", lineHeight: 1.2 }}>
                {fmtRate(currentChangeRate)}
              </span>
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

          {/* 우측: 시세 정보 + 매수 잔량 */}
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ height: "32px" }} />
            <MarketInfoPanel info={marketInfo} />
            <div style={{ height: "50px" }} />
            {bids.map((bid, i) => (
              <BidRow key={i} row={bid} maxQty={maxBidQty} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};