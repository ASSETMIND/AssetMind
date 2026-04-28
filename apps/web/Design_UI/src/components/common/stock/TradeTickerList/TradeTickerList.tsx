import { useEffect, useRef, useState } from "react";

export interface TradeTickRow {
  id: string;
  price: number;
  quantity: number;
  isBuy: boolean;
}

interface TradeTickerListProps {
  trades: TradeTickRow[];
  height?: number;
  tradeStrength?: number;
  className?: string;
}

const fmt = (v: number) => v.toLocaleString("ko-KR");

const RISE_FLASH = "rgba(234,88,12,0.18)";
const FALL_FLASH = "rgba(37,106,244,0.18)";
const IDLE_BG = "transparent";

const TradeTickItem = ({
  trade,
  isNew,
}: {
  trade: TradeTickRow;
  isNew: boolean;
}) => {
  const [bg, setBg] = useState<string>(IDLE_BG);
  const [slideIn, setSlideIn] = useState(false);
  const mountedRef = useRef(false);

  useEffect(() => {
    if (!isNew) return;
    if (!mountedRef.current) {
      mountedRef.current = true;
      const raf = requestAnimationFrame(() => setSlideIn(true));
      return () => cancelAnimationFrame(raf);
    }
  }, [isNew]);

  useEffect(() => {
    if (!isNew) return;
    const flashColor = trade.isBuy ? RISE_FLASH : FALL_FLASH;
    setBg(flashColor);
    const timer = setTimeout(() => setBg(IDLE_BG), 150);
    return () => clearTimeout(timer);
  }, [isNew, trade.isBuy]);

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        height: "32px",
        padding: "0 0 0 8px",
        backgroundColor: bg,
        transform: slideIn || !isNew ? "translateY(0)" : "translateY(-8px)",
        opacity: slideIn || !isNew ? 1 : 0,
        transition: isNew
          ? "transform 120ms ease-out, opacity 120ms ease-out, background-color 150ms ease-out"
          : "background-color 150ms ease-out",
        flexShrink: 0,
      }}
    >
      <span style={{ fontSize: "12px", fontWeight: 400, color: "#9F9F9F" }}>
        {fmt(trade.price)}
      </span>
      <span
        style={{
          fontSize: "12px",
          fontWeight: 400,
          color: trade.isBuy ? "#EA580C" : "#256AF4",
          textAlign: "right",
          minWidth: "32px",
        }}
      >
        {trade.quantity}
      </span>
    </div>
  );
};

export const TradeTickerList = ({
  trades,
  height = 320,
  tradeStrength,
  className,
}: TradeTickerListProps) => {
  const prevIdsRef = useRef<Set<string>>(new Set());
  const newIds = new Set<string>();

  for (const t of trades) {
    if (!prevIdsRef.current.has(t.id)) {
      newIds.add(t.id);
    }
  }

  useEffect(() => {
    prevIdsRef.current = new Set(trades.map((t) => t.id));
  });

  return (
    <div
      className={className ?? undefined}
      style={{ display: "flex", flexDirection: "column" }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "4px 0 4px 8px",
          height: "24px",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: "12px", fontWeight: 400, color: "#9F9F9F" }}>
          체결강도
        </span>
        {tradeStrength !== undefined && (
          <span style={{ fontSize: "12px", fontWeight: 400, color: "#256AF4" }}>
            {tradeStrength}%
          </span>
        )}
      </div>

      <div
        style={{
          height: `${height}px`,
          overflowY: "auto",
          overflowX: "hidden",
          display: "flex",
          flexDirection: "column",
          scrollbarWidth: "none",
        }}
      >
        {trades.map((trade) => (
          <TradeTickItem
            key={trade.id}
            trade={trade}
            isNew={newIds.has(trade.id)}
          />
        ))}
      </div>
    </div>
  );
};