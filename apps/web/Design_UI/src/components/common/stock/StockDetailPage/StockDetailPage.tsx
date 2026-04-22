import { useState } from "react";
import { Tab } from "../../../common/Tab/Tab";
import { MobileTabSwitcher } from "../../../common/MobileTabSwitcher/MobileTabSwitcher";
import { TradingViewWrapper } from "../TradingViewWrapper/TradingViewWrapper";
import { OrderbookTable } from "../OrderbookTable/OrderbookTable";
import { AIPredictionPanel } from "../AIPredictionPanel/AIPredictionPanel";
import { InvestorTradePanel } from "../InvestorTradePanel/InvestorTradePanel";
import { ChartIcon } from "../../../icons/ChartIcon";
import { StockInfoIcon } from "../../../icons/StockInfoIcon";
import { TradeStatusIcon } from "../../../icons/TradeStatusIcon";
import { AIPredictionIcon } from "../../../icons/AIPredictionIcon";
import type { CandlestickData, ChartPeriod } from "../TradingViewWrapper/TradingViewWrapper";
import type { OrderbookRow, MarketInfo } from "../OrderbookTable/OrderbookTable";
import type { TradeTickRow } from "../TradeTickerList/TradeTickerList";
import type { Viewport } from "../StockTable/StockTable";
import type { SparklineDataPoint } from "../AIPredictionPanel/SparklineChart";
import type { AnalysisData } from "../AIPredictionPanel/PredictionAnalysisWidget";
import type {
  TraderRankItem,
  TrendDataPoint,
  TrendTableRow,
  ProgramTradeRow,
  CreditTradeRow,
  LendingTradeRow,
  ShortTradeRow,
  CfdTradeRow,
} from "../InvestorTradePanel/InvestorTradePanel";

// ─── Types ────────────────────────────────────────────────────

export type DetailTab = "chart" | "orderbook" | "trade" | "ai";
export type PanelState = "default" | "skeleton" | "error" | "empty";

export interface StockMeta {
  ticker: string;
  name: string;
  price: number;
  changeFromYesterday: number;
  changeRate: number;
  logoUrl?: string;
}

export interface StockDetailPageProps {
  stock?: StockMeta;
  activeTab?: DetailTab;
  onTabChange?: (tab: DetailTab) => void;
  viewport?: Viewport;
  onRetry?: () => void;
  isMarketClosed?: boolean;

  // ── 패널별 독립 상태 ──────────────────────────────────────
  chartState?: PanelState;
  orderbookState?: PanelState;
  aiState?: PanelState;

  // ── 차트 ─────────────────────────────────────────────────
  chartData?: CandlestickData[];
  chartPeriod?: ChartPeriod;
  onChartPeriodChange?: (period: ChartPeriod) => void;

  // ── 호가창 ───────────────────────────────────────────────
  currentPrice?: number;
  currentChangeRate?: number;
  asks?: OrderbookRow[];
  bids?: OrderbookRow[];
  trades?: TradeTickRow[];
  tradeStrength?: number;
  marketInfo?: MarketInfo;
  onQuickOrder?: () => void;

  // ── AI 예측 패널 ──────────────────────────────────────────
  aiPeriod?: "1주" | "1개월" | "3개월";
  onAIPeriodChange?: (period: "1주" | "1개월" | "3개월") => void;
  onBuyClick?: () => void;
  aiHistoricalData?: SparklineDataPoint[];
  aiForecastData?: SparklineDataPoint[];
  aiPredictedPrice?: number;
  aiPriceDiff?: number;
  aiChangeRate?: number;
  aiBaseDate?: string;
  aiUpProbability?: number;
  aiDownProbability?: number;
  aiAnalysisData?: AnalysisData;

  // ── 거래현황 패널 ─────────────────────────────────────────
  tradeState?: PanelState;
  buyList?: TraderRankItem[];
  sellList?: TraderRankItem[];
  rankBaseDateTime?: string;
  trendData?: TrendDataPoint[];
  trendBaseDateTime?: string;
  tradeTableData?: TrendTableRow[];
  programData?: ProgramTradeRow[];
  creditData?: CreditTradeRow[];
  lendingData?: LendingTradeRow[];
  shortData?: ShortTradeRow[];
  cfdData?: CfdTradeRow[];
  onViewNetBuy?: () => void;
}

// ─── 탭 정의 ──────────────────────────────────────────────────

const DESKTOP_TAB_ITEMS = [
  { label: "차트·호가", value: "chart" },
  { label: "종목정보",  value: "orderbook" },
  { label: "거래현황",  value: "trade" },
];

const MOBILE_TAB_ITEMS = [
  { label: "차트",     value: "chart",     icon: <ChartIcon /> },
  { label: "종목 정보", value: "orderbook", icon: <StockInfoIcon /> },
  { label: "거래 현황", value: "trade",     icon: <TradeStatusIcon /> },
  { label: "AI 예측",  value: "ai",        icon: <AIPredictionIcon /> },
];

// ─── Viewport 전체 너비 ───────────────────────────────────────

const VIEWPORT_WIDTH: Record<Viewport, string> = {
  desktop: "1440px",
  tablet:  "768px",
  mobile:  "393px",
};

// ─── 헤더 ─────────────────────────────────────────────────────

const StockHeader = ({
  stock,
  viewport,
}: {
  stock: StockMeta;
  viewport: Viewport;
}) => {
  const isMobile = viewport === "mobile";
  const isRise = stock.changeRate >= 0;
  const changeColor = isRise ? "#EA580C" : "#256AF4";
  const sign = isRise ? "+" : "";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: isMobile ? "12px" : "16px",
        padding: isMobile ? "16px" : "20px 24px",
      }}
    >
      <div
        style={{
          width: isMobile ? "48px" : "56px",
          height: isMobile ? "48px" : "56px",
          borderRadius: "12px",
          backgroundColor: "#21242C",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          overflow: "hidden",
        }}
      >
        {stock.logoUrl ? (
          <img
            src={stock.logoUrl}
            alt={stock.name}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <span style={{ fontSize: isMobile ? "16px" : "18px", fontWeight: 500, color: "#9194A1" }}>
            {stock.name[0]}
          </span>
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
          <span style={{ fontSize: isMobile ? "16px" : "18px", fontWeight: 700, color: "#FFFFFF" }}>
            {stock.name}
          </span>
          <span style={{ fontSize: "13px", fontWeight: 400, color: "#9194A1" }}>
            {stock.ticker}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
          <span
            style={{
              fontSize: isMobile ? "22px" : "26px",
              fontWeight: 700,
              color: "#FFFFFF",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {stock.price.toLocaleString("ko-KR")}원
          </span>
          <span
            style={{
              fontSize: "14px",
              fontWeight: 500,
              color: changeColor,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            어제보다 {sign}{stock.changeFromYesterday.toLocaleString("ko-KR")}원 ({sign}{stock.changeRate.toFixed(2)}%)
          </span>
        </div>
      </div>
    </div>
  );
};

// ─── StockDetailPage ──────────────────────────────────────────

export const StockDetailPage = ({
  stock = {
    ticker: "005930",
    name: "삼성전자",
    price: 75000,
    changeFromYesterday: 1720,
    changeRate: 2.35,
  },
  activeTab: activeTabProp,
  onTabChange,
  viewport = "desktop",
  onRetry,
  isMarketClosed = false,

  chartState = "default",
  orderbookState = "default",
  aiState = "default",

  chartData = [],
  chartPeriod = "1d",
  onChartPeriodChange,

  currentPrice = 0,
  currentChangeRate = 0,
  asks = [],
  bids = [],
  trades = [],
  tradeStrength = 0,
  marketInfo,
  onQuickOrder,

  aiPeriod,
  onAIPeriodChange,
  onBuyClick,
  aiHistoricalData = [],
  aiForecastData = [],
  aiPredictedPrice = 0,
  aiPriceDiff = 0,
  aiChangeRate = 0,
  aiBaseDate = "",
  aiUpProbability = 0,
  aiDownProbability = 0,
  aiAnalysisData,

  tradeState = "default",
  buyList = [],
  sellList = [],
  rankBaseDateTime = "",
  trendData = [],
  trendBaseDateTime = "",
  tradeTableData = [],
  programData = [],
  creditData = [],
  lendingData = [],
  shortData = [],
  cfdData = [],
  onViewNetBuy,
}: StockDetailPageProps) => {
  const [internalTab, setInternalTab] = useState<DetailTab>("chart");
  const activeTab = activeTabProp ?? internalTab;
  const isMobile = viewport === "mobile";
  const isTablet = viewport === "tablet";
  const containerWidth = VIEWPORT_WIDTH[viewport];

  const handleTabChange = (tab: string) => {
    setInternalTab(tab as DetailTab);
    onTabChange?.(tab as DetailTab);
  };

  // isMarketClosed → 호가창·AI 패널 모두 empty 강제
  const resolvedOrderbookStatus: PanelState =
    isMarketClosed ? "empty" : orderbookState;

  const resolvedAIStatus: PanelState =
    isMarketClosed ? "empty" : aiState;

  // ── 차트 패널 ─────────────────────────────────────────────
  const renderChart = (width: number, height: number) => (
    <div
      style={{
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: "#1C1D21",
        borderRadius: "12px",
        overflow: "hidden",
        padding: "12px",
        boxSizing: "border-box",
        flexShrink: 0,
      }}
    >
      <TradingViewWrapper
        data={chartData}
        period={chartPeriod}
        onPeriodChange={onChartPeriodChange}
        isMarketClosed={isMarketClosed}
      />
    </div>
  );

  // ── 호가창 ────────────────────────────────────────────────
  const renderOrderbook = (vp: Viewport) => (
    <OrderbookTable
      status={resolvedOrderbookStatus}
      viewport={vp}
      onRetry={onRetry}
      currentPrice={currentPrice}
      currentChangeRate={currentChangeRate}
      asks={asks}
      bids={bids}
      trades={trades}
      tradeStrength={tradeStrength}
      marketInfo={marketInfo}
      onQuickOrder={onQuickOrder}
    />
  );

  // ── AI 예측 패널 — isMarketClosed 시 status="empty" 전달 ──
  const renderAI = () => (
    <AIPredictionPanel
      status={resolvedAIStatus}
      viewport={viewport}
      onRetry={onRetry}
      period={aiPeriod}
      onPeriodChange={onAIPeriodChange}
      onBuyClick={onBuyClick}
      historicalData={aiHistoricalData}
      forecastData={aiForecastData}
      predictedPrice={aiPredictedPrice}
      priceDiff={aiPriceDiff}
      changeRate={aiChangeRate}
      baseDate={aiBaseDate}
      upProbability={aiUpProbability}
      downProbability={aiDownProbability}
      analysisData={aiAnalysisData}
    />
  );

  // ── 거래현황 패널 ─────────────────────────────────────────
  // desktop: 1036x820 / tablet: 710x820 / mobile: 345x657
  const TRADE_PANEL_SIZE: Record<Viewport, { width: number; height: number }> = {
    desktop: { width: 1036, height: 820 },
    tablet:  { width: 710,  height: 820 },
    mobile:  { width: 345,  height: 657 },
  };

  const renderTrade = () => {
    const { width, height } = TRADE_PANEL_SIZE[viewport];
    return (
      <InvestorTradePanel
        status={tradeState === "skeleton" ? "skeleton" : tradeState === "error" ? "error" : "default"}
        buyList={buyList}
        sellList={sellList}
        rankBaseDateTime={rankBaseDateTime}
        trendData={trendData}
        trendBaseDateTime={trendBaseDateTime}
        tableData={tradeTableData}
        programData={programData}
        creditData={creditData}
        lendingData={lendingData}
        shortData={shortData}
        cfdData={cfdData}
        onRetry={onRetry}
        onViewNetBuy={onViewNetBuy}
        panelWidth={width}
        panelHeight={height}
      />
    );
  };

  return (
    <div
      style={{
        width: containerWidth,
        backgroundColor: "#131316",
        height: isMobile ? "852px" : isTablet ? "1024px" : "auto",
        minHeight: isMobile || isTablet ? undefined : "100vh",
        display: "flex",
        flexDirection: "column",
        boxSizing: "border-box",
        overflow: isMobile || isTablet ? "hidden" : undefined,
      }}
    >
      {/* ── 헤더 ── */}
      <StockHeader stock={stock} viewport={viewport} />

      {/* ── 탭 (구분선 없음) ── */}
      {!isMobile && (
        <div style={{ padding: "0 24px" }}>
          <Tab
            items={DESKTOP_TAB_ITEMS}
            value={activeTab}
            onChange={handleTabChange}
          />
        </div>
      )}

      <div style={{ flex: 1 }}>

        {/* ══ 차트·호가 탭 — 데스크톱 ══════════════════════════ */}
        {activeTab === "chart" && !isMobile && !isTablet && (
          <div
            style={{
              padding: "16px 24px",
              display: "flex",
              gap: "12px",
              alignItems: "flex-start",
              boxSizing: "border-box",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {renderChart(680, 400)}
              <div
                style={{
                  width: "680px",
                  height: "400px",
                  backgroundColor: "#1C1D21",
                  borderRadius: "12px",
                  flexShrink: 0,
                }}
              />
            </div>
            {renderOrderbook("desktop")}
            {renderAI()}
          </div>
        )}

        {/* ══ 차트·호가 탭 — 태블릿 ══════════════════════════ */}
        {activeTab === "chart" && isTablet && (
          <div
            style={{
              padding: "16px 24px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              boxSizing: "border-box",
            }}
          >
            {renderChart(710, 400)}
            <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
              <div style={{ width: "347px", flexShrink: 0 }}>
                {renderAI()}
              </div>
              {renderOrderbook("desktop")}
            </div>
          </div>
        )}

        {/* ══ 차트·호가 탭 — 모바일 ══════════════════════════ */}
        {activeTab === "chart" && isMobile && (
          <div
            style={{
              padding: "12px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "12px",
              boxSizing: "border-box",
            }}
          >
            {renderChart(345, 407)}
            {renderOrderbook("mobile")}
          </div>
        )}

        {/* ══ 종목정보 탭 ══════════════════════════════════════ */}
        {activeTab === "orderbook" && (
          <div
            style={{
              padding: "40px 24px",
              color: "#9194A1",
              fontSize: "14px",
              textAlign: "center",
            }}
          >
            종목정보 탭 — 추후 구현 예정
          </div>
        )}

        {/* ══ 거래현황 탭 ══════════════════════════════════════ */}
        {activeTab === "trade" && (
          <div style={{ padding: isMobile ? "12px" : "16px 24px", boxSizing: "border-box" }}>
            {renderTrade()}
          </div>
        )}

        {/* ══ AI 예측 탭 — 모바일 전용 ════════════════════════ */}
        {activeTab === "ai" && isMobile && (
          <div style={{
            padding: "12px",
            display: "flex",
            justifyContent: "center",
          }}>
            {renderAI()}
          </div>
        )}
      </div>

      {/* ── 모바일 하단 탭 ── */}
      {isMobile && (
        <MobileTabSwitcher
          items={MOBILE_TAB_ITEMS}
          value={activeTab}
          onChange={handleTabChange}
        />
      )}
    </div>
  );
};

export default StockDetailPage;