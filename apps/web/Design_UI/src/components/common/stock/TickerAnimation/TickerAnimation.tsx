import { useEffect, useRef, useState } from "react";
import { StockTableRow } from "../StockTable/StockTable";
import type { StockRow } from "../StockTable/StockTable";

/**
 * TickerAnimation 컴포넌트
 *
 * 실시간 가격 갱신 시 배경색 깜빡임 처리
 * - 상승: rgba(234,88,12,0.1) — status.rise 10% 불투명도
 * - 하락: rgba(37,106,244,0.1) — status.fall 10% 불투명도
 * - 150ms ease-out 후 idle 복귀
 */
export const TickerAnimation = ({
  row,
  onFavoriteToggle,
  onRowClick,
}: {
  row: StockRow;
  onFavoriteToggle?: (id: string) => void;
  onRowClick?: (id: string) => void;
}) => {
  const [tickerState, setTickerState] = useState<"rise" | "fall" | "idle">("idle");
  const prevPriceRef = useRef<number | null>(null);

  useEffect(() => {
    // 최초 렌더링 시 기준값만 저장
    if (prevPriceRef.current === null) {
      prevPriceRef.current = row.price;
      return;
    }

    if (prevPriceRef.current === row.price) return;

    const state = row.price > prevPriceRef.current ? "rise" : "fall";
    prevPriceRef.current = row.price;

    setTickerState(state);

    const timer = setTimeout(() => setTickerState("idle"), 150);
    return () => clearTimeout(timer);
  }, [row.price]);

  return (
    <StockTableRow
      row={{ ...row, tickerState }}
      onFavoriteToggle={onFavoriteToggle}
      onRowClick={onRowClick}
    />
  );
};