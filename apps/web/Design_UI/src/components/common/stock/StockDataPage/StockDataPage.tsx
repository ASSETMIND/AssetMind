import { useState, useEffect } from "react";
import { StockTable } from "../StockTable/StockTable";
import { TickerAnimation } from "../TickerAnimation/TickerAnimation";
import { LocalError } from "../../../common/LocalError/LocalError";
import { GlobalEmptyState } from "../../../common/GlobalEmptyState/GlobalEmptyState";
import { Skeleton } from "../../../common/Skeleton/Skeleton";
import { Tab } from "../../../common/Tab/Tab";
import type { StockRow } from "../StockTable/StockTable";
import type { Viewport } from "../StockTable/StockTable";

// ─── Types ────────────────────────────────────────────────────

export type PageState =
  | "default"       // 정상 데이터
  | "skeleton"      // 로딩 (Skeleton 애니메이션)
  | "realtime"      // 실시간 가격 갱신
  | "error"         // API 실패
  | "empty"         // 조회 결과 없음
  | "extreme";      // 극단값 (99:1, 1:99)

export interface StockDataPageProps {
  rows?: StockRow[];
  extremeRows?: StockRow[];
  pageState?: PageState;
  viewport?: Viewport;
  onRetry?: () => void;
  onFavoriteToggle?: (id: string) => void;
  onRowClick?: (id: string) => void;
}

// ─── Filter Tab Items ─────────────────────────────────────────

const MARKET_FILTER_ITEMS = [
  { label: "전체", value: "all" },
  { label: "국내", value: "domestic" },
  { label: "해외", value: "overseas" },
];

const SORT_FILTER_ITEMS = [
  { label: "증권 거래대금", value: "amount" },
  { label: "증권 거래량",   value: "volume" },
  { label: "거래대금",      value: "trade-amount" },
  { label: "거래량",        value: "trade-volume" },
];

// ─── Viewport Width ───────────────────────────────────────────

const VIEWPORT_WIDTH: Record<Viewport, string> = {
  desktop: "1200px",
  tablet:  "768px",
  mobile:  "393px",
};

// ─── StockDataPage ────────────────────────────────────────────

export const StockDataPage = ({
  rows: rowsProp,
  extremeRows,
  pageState = "default",
  viewport = "desktop",
  onRetry,
  onFavoriteToggle,
  onRowClick,
}: StockDataPageProps) => {
  const [rows, setRows] = useState<StockRow[]>(rowsProp ?? []);
  const containerWidth = VIEWPORT_WIDTH[viewport];

  // rows prop 변경 시 내부 state 동기화
  useEffect(() => {
    if (rowsProp) setRows(rowsProp);
  }, [rowsProp]);

  // 실시간 갱신 — realtime 상태에서만 활성화
  useEffect(() => {
    if (pageState !== "realtime" || !rowsProp) return;
    const timers = rowsProp.map((row) => {
      const interval = 1500 + Math.random() * 3000;
      return setInterval(() => {
        const delta = Math.floor((Math.random() - 0.5) * 2000);
        if (delta === 0) return;
        setRows((prev) =>
          prev.map((r) =>
            r.id === row.id ? { ...r, price: Math.max(1000, r.price + delta) } : r
          )
        );
      }, interval);
    });
    return () => timers.forEach(clearInterval);
  }, [pageState]);

  const isTableState =
    pageState === "default" ||
    pageState === "realtime" ||
    pageState === "extreme";

  return (
    <div
      style={{
        width: containerWidth,
        backgroundColor: "#131316",
        minHeight: "800px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* ── 필터 탭 영역 — 넘칠 경우 가로 스크롤 ── */}
      <div
        style={{
          padding: "16px",
          display: "flex",
          gap: "12px",
          overflowX: "auto",
          flexShrink: 0,
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
      >
        <div style={{ display: "flex", gap: "12px", flexShrink: 0 }}>
          <Tab items={MARKET_FILTER_ITEMS} defaultValue="all" />
          <Tab items={SORT_FILTER_ITEMS} defaultValue="amount" />
        </div>
      </div>

      {/* ── 콘텐츠 영역 ── */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: isTableState ? "flex-start" : "center",
          alignItems: isTableState ? "flex-start" : "center",
        }}
      >
        {pageState === "skeleton" && (
          <Skeleton variant="table-row" rows={10} />
        )}
        {pageState === "error" && (
          <LocalError
            message="데이터를 불러오는 데 실패했습니다."
            onRetry={onRetry}
          />
        )}
        {pageState === "empty" && (
          <GlobalEmptyState variant="no-data" display="inline" />
        )}
        {pageState === "extreme" && (
          <StockTable
            rows={extremeRows ?? []}
            viewport={viewport}
            onFavoriteToggle={onFavoriteToggle}
            onRowClick={onRowClick}
          />
        )}
        {pageState === "default" && (
          <StockTable
            rows={rows}
            viewport={viewport}
            onFavoriteToggle={onFavoriteToggle}
            onRowClick={onRowClick}
          />
        )}
        {pageState === "realtime" && (
          <div style={{ width: containerWidth }}>
            {rows.map((row) => (
              <TickerAnimation key={row.id} row={row} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default StockDataPage;