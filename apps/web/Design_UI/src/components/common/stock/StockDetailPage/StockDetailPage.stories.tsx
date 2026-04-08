import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { StockDetailPage } from "./StockDetailPage";
import type { CandlestickData } from "../TradingViewWrapper/TradingViewWrapper";
import type { OrderbookRow, MarketInfo } from "../OrderbookTable/OrderbookTable";
import type { TradeTickRow } from "../TradeTickerList/TradeTickerList";
import type { SparklineDataPoint } from "../AIPredictionPanel/SparklineChart";
import type { AnalysisData } from "../AIPredictionPanel/PredictionAnalysisWidget";

// ════════════════════════════════════════════════════════════════
// Mock Data
// ════════════════════════════════════════════════════════════════

// ─── 종목 메타 ────────────────────────────────────────────────

const MOCK_STOCK = {
  ticker: "005930",
  name: "삼성전자",
  price: 75000,
  changeFromYesterday: 1720,
  changeRate: 2.35,
};

const MOCK_STOCK_DOWN = {
  ticker: "000660",
  name: "SK하이닉스",
  price: 182000,
  changeFromYesterday: -2200,
  changeRate: -1.20,
};

// ─── 차트 데이터 ──────────────────────────────────────────────

const generateChartData = (days: number): CandlestickData[] => {
  const data: CandlestickData[] = [];
  let price = 75000;
  const startDate = new Date("2025-10-01");
  for (let i = 0; i < days; i++) {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + i);
    if (date.getDay() === 0 || date.getDay() === 6) continue;
    const open = price;
    const change = (Math.random() - 0.48) * 3000;
    const close = Math.max(50000, open + change);
    const high = Math.max(open, close) + Math.random() * 1500;
    const low = Math.min(open, close) - Math.random() * 1500;
    const volume = Math.floor(Math.random() * 200000000 + 50000000);
    data.push({
      time: date.toISOString().split("T")[0],
      open: Math.round(open),
      high: Math.round(high),
      low: Math.round(low),
      close: Math.round(close),
      volume,
    });
    price = close;
  }
  return data;
};

const MOCK_CHART_DATA = generateChartData(180);

// ─── 호가 데이터 ──────────────────────────────────────────────

const MOCK_ASKS: OrderbookRow[] = [
  { price: 76000, changeRate: -9.52,  quantity: 1200 },
  { price: 75500, changeRate: -9.52,  quantity: 800  },
  { price: 75000, changeRate: -10.71, quantity: 2100 },
  { price: 74500, changeRate: -11.31, quantity: 500  },
  { price: 74000, changeRate: -11.90, quantity: 1800 },
  { price: 73500, changeRate: -12.50, quantity: 900  },
  { price: 73000, changeRate: -13.10, quantity: 3200 },
  { price: 72500, changeRate: -13.69, quantity: 700  },
  { price: 72000, changeRate: -14.29, quantity: 1500 },
  { price: 71500, changeRate: -14.88, quantity: 600  },
];

const MOCK_BIDS: OrderbookRow[] = [
  { price: 74800, changeRate: -11.55, quantity: 2500 },
  { price: 74300, changeRate: -12.14, quantity: 1300 },
  { price: 73800, changeRate: -12.74, quantity: 800  },
  { price: 73300, changeRate: -13.33, quantity: 3500 },
  { price: 72800, changeRate: -13.93, quantity: 600  },
  { price: 72300, changeRate: -14.52, quantity: 1900 },
  { price: 71800, changeRate: -15.12, quantity: 700  },
  { price: 71300, changeRate: -15.71, quantity: 2200 },
  { price: 70800, changeRate: -16.31, quantity: 400  },
  { price: 70300, changeRate: -16.90, quantity: 1600 },
];

const MOCK_TRADES: TradeTickRow[] = Array.from({ length: 14 }, (_, i) => ({
  id: `t${i + 1}`,
  price: 75000 + Math.floor((Math.random() - 0.5) * 500),
  quantity: Math.floor(Math.random() * 10) + 1,
  isBuy: Math.random() > 0.5,
}));

const MOCK_MARKET_INFO: MarketInfo = {
  weekHigh: 98000,
  weekLow: 62000,
  upperLimit: 97500,
  lowerLimit: 52500,
  riseVI: undefined,
  fallVI: undefined,
  open: 74000,
  high: 76500,
  low: 73200,
  volume: 15234567,
  volumeUnit: "1,523만",
  changeFromYesterday: 2.35,
  midPrice: 75200,
};

// ─── AI 예측 패널 Mock 데이터 ─────────────────────────────────

const MOCK_AI_HISTORICAL: SparklineDataPoint[] = [
  { time: "2025-10-01", value: 63000 },
  { time: "2025-11-01", value: 58000 },
  { time: "2025-12-01", value: 61000 },
  { time: "2026-01-01", value: 55000 },
  { time: "2026-02-01", value: 59000 },
  { time: "2026-03-01", value: 57000 },
  { time: "2026-03-15", value: 63000 },
];

const MOCK_AI_FORECAST: SparklineDataPoint[] = [
  { time: "2026-03-15", value: 63000 },
  { time: "2026-03-22", value: 70000 },
  { time: "2026-03-29", value: 80000 },
];

// AnalysisData 타입 그대로 사용 — 불필요한 tabs/activeTab/items 필드 제거
const MOCK_AI_ANALYSIS: AnalysisData = {
  "기술적 지표": [
    { type: "warning",  text: "경고 또는 위험 신호가 있는 내용" },
    { type: "neutral",  text: "중립이거나 추가 확인이 필요한 내용" },
    { type: "positive", text: "긍정적 신호가 있는 내용" },
    { type: "neutral",  text: "중립이거나 추가 확인이 필요한 내용" },
    { type: "neutral",  text: "중립이거나 추가 확인이 필요한 내용" },
  ],
  "시장 심리": [
    { type: "positive", text: "투자자 심리 지수 낙관 구간 진입" },
    { type: "neutral",  text: "외국인 순매수 흐름 지속 중" },
    { type: "warning",  text: "공매도 비율 단기 급등 감지" },
  ],
  "수급 동향": [
    { type: "neutral",  text: "기관 순매수 전환 신호 감지" },
    { type: "positive", text: "외국인 대규모 매수 유입" },
    { type: "warning",  text: "개인 투자자 과매도 구간 진입" },
    { type: "neutral",  text: "프로그램 매매 비중 중립" },
  ],
};

// ─── 공통 args ────────────────────────────────────────────────

const COMMON_ARGS = {
  stock: MOCK_STOCK,
  chartData: MOCK_CHART_DATA,
  chartPeriod: "1d" as const,
  currentPrice: 75000,
  currentChangeRate: 2.35,
  asks: MOCK_ASKS,
  bids: MOCK_BIDS,
  trades: MOCK_TRADES,
  tradeStrength: 72,
  marketInfo: MOCK_MARKET_INFO,
  onQuickOrder: () => alert("빠른 주문"),
  onRetry: () => alert("Retry"),
  onBuyClick: () => alert("매수하기"),

  // 패널 상태
  chartState: "default" as const,
  orderbookState: "default" as const,
  aiState: "default" as const,

  // AI 패널 데이터
  aiHistoricalData: MOCK_AI_HISTORICAL,
  aiForecastData: MOCK_AI_FORECAST,
  aiPredictedPrice: 80000,
  aiPriceDiff: 17000,
  aiChangeRate: 26.98,
  aiBaseDate: "2026년 03월 26일",
  aiUpProbability: 72,
  aiDownProbability: 28,
  aiAnalysisData: MOCK_AI_ANALYSIS,
};

// ════════════════════════════════════════════════════════════════
// Meta
// ════════════════════════════════════════════════════════════════

const meta: Meta<typeof StockDetailPage> = {
  title: "Components/Stock/StockDetailPage",
  component: StockDetailPage,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
    layout: "fullscreen",
    docs: {
      description: {
        component: `
종목 세부 페이지 통합 Story.

**레이아웃**
- Desktop (1440px): 좌(차트 680×400 + 빈패널 680×400) / 중(호가 340) / 우(AI 340) 고정 3열
- Tablet (768px): 차트 710×400 상단 / AI 347px + 호가 340px 하단 2열, 페이지 전체 스크롤
- Mobile (393px): 차트 탭에서 차트 345×407 + 호가창 345×454 수직 나열, AI는 AI탭에서만 표시

**패널별 독립 상태**
\`chartState\`, \`orderbookState\`, \`aiState\` prop으로 각 패널 상태 개별 지정.
\`isMarketClosed=true\`이면 호가창은 항상 empty 상태.
        `,
      },
    },
  },
  argTypes: {
    activeTab: {
      control: "radio",
      options: ["chart", "orderbook", "trade", "ai"],
    },
    chartState: {
      control: "radio",
      options: ["default", "skeleton", "error", "empty"],
      description: "차트 패널 상태",
    },
    orderbookState: {
      control: "radio",
      options: ["default", "skeleton", "error", "empty"],
      description: "호가창 패널 상태 (isMarketClosed=true이면 empty 강제)",
    },
    aiState: {
      control: "radio",
      options: ["default", "skeleton", "error", "empty"],
      description: "AI 예측 패널 상태",
    },
    viewport: {
      control: "radio",
      options: ["desktop", "tablet", "mobile"],
    },
    isMarketClosed: { control: "boolean" },
  },
};

export default meta;
type Story = StoryObj<typeof StockDetailPage>;

// ─── 데코레이터 ───────────────────────────────────────────────

const desktopDec = (Story: React.ComponentType) => (
  <div style={{ minWidth: "1440px" }}><Story /></div>
);
const tabletDec = (Story: React.ComponentType) => (
  <div style={{ width: "768px" }}><Story /></div>
);
const mobileDec = (Story: React.ComponentType) => (
  <div style={{ width: "393px" }}><Story /></div>
);

// ════════════════════════════════════════════════════════════════
// Desktop Stories
// ════════════════════════════════════════════════════════════════

export const DesktopChart: Story = {
  name: "Desktop / Chart Tab — Default",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop" },
  decorators: [desktopDec],
};

export const DesktopDownTrend: Story = {
  name: "Desktop / Down Trend",
  args: { ...COMMON_ARGS, stock: MOCK_STOCK_DOWN, activeTab: "chart", viewport: "desktop" },
  decorators: [desktopDec],
};

export const DesktopTabSwitching: Story = {
  name: "Desktop / Tab Switching Demo",
  render: () => {
    const [tab, setTab] = useState<"chart" | "orderbook" | "trade" | "ai">("chart");
    return (
      <div style={{ minWidth: "1440px" }}>
        <StockDetailPage
          {...COMMON_ARGS}
          activeTab={tab}
          onTabChange={(t) => setTab(t as any)}
          viewport="desktop"
        />
      </div>
    );
  },
};

export const DesktopMarketClosed: Story = {
  name: "Desktop / Market Closed",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop", isMarketClosed: true },
  decorators: [desktopDec],
};

// ── 패널별 상태 ───────────────────────────────────────────────

export const DesktopChartSkeleton: Story = {
  name: "Desktop / Chart Panel — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop", chartState: "skeleton" },
  decorators: [desktopDec],
};

export const DesktopChartError: Story = {
  name: "Desktop / Chart Panel — Error",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop", chartState: "error" },
  decorators: [desktopDec],
};

export const DesktopOrderbookSkeleton: Story = {
  name: "Desktop / Orderbook Panel — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop", orderbookState: "skeleton" },
  decorators: [desktopDec],
};

export const DesktopOrderbookError: Story = {
  name: "Desktop / Orderbook Panel — Error",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop", orderbookState: "error" },
  decorators: [desktopDec],
};

export const DesktopAISkeleton: Story = {
  name: "Desktop / AI Panel — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop", aiState: "skeleton" },
  decorators: [desktopDec],
};

export const DesktopAIError: Story = {
  name: "Desktop / AI Panel — Error",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop", aiState: "error" },
  decorators: [desktopDec],
};

export const DesktopAllSkeleton: Story = {
  name: "Desktop / All Panels — Skeleton (Initial Load)",
  args: {
    ...COMMON_ARGS,
    activeTab: "chart",
    viewport: "desktop",
    chartState: "skeleton",
    orderbookState: "skeleton",
    aiState: "skeleton",
  },
  decorators: [desktopDec],
};

export const DesktopAllError: Story = {
  name: "Desktop / All Panels — Error",
  args: {
    ...COMMON_ARGS,
    activeTab: "chart",
    viewport: "desktop",
    chartState: "error",
    orderbookState: "error",
    aiState: "error",
  },
  decorators: [desktopDec],
};

export const DesktopStockInfo: Story = {
  name: "Desktop / Stock Info Tab — Placeholder",
  args: { ...COMMON_ARGS, activeTab: "orderbook", viewport: "desktop" },
  decorators: [desktopDec],
};

// ════════════════════════════════════════════════════════════════
// Tablet Stories
// ════════════════════════════════════════════════════════════════

export const TabletChart: Story = {
  name: "Tablet / Chart Tab — Default",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDec],
};

export const TabletOrderbookSkeleton: Story = {
  name: "Tablet / Orderbook Panel — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "tablet", orderbookState: "skeleton" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDec],
};

export const TabletOrderbookError: Story = {
  name: "Tablet / Orderbook Panel — Error",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "tablet", orderbookState: "error" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDec],
};

export const TabletMarketClosed: Story = {
  name: "Tablet / Market Closed",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "tablet", isMarketClosed: true },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDec],
};

// ════════════════════════════════════════════════════════════════
// Mobile Stories
// ════════════════════════════════════════════════════════════════

export const MobileChart: Story = {
  name: "Mobile / Chart Tab",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const MobileOrderbookSkeleton: Story = {
  name: "Mobile / Orderbook Panel — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "mobile", orderbookState: "skeleton" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const MobileOrderbookError: Story = {
  name: "Mobile / Orderbook Panel — Error",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "mobile", orderbookState: "error" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const MobileMarketClosed: Story = {
  name: "Mobile / Market Closed",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "mobile", isMarketClosed: true },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const MobileAITab: Story = {
  name: "Mobile / AI Tab",
  args: { ...COMMON_ARGS, activeTab: "ai", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const MobileTabSwitching: Story = {
  name: "Mobile / Tab Switching Demo",
  parameters: { viewport: { defaultViewport: "mobile1" } },
  render: () => {
    const [tab, setTab] = useState<"chart" | "orderbook" | "trade" | "ai">("chart");
    return (
      <div style={{ width: "393px" }}>
        <StockDetailPage
          {...COMMON_ARGS}
          activeTab={tab}
          onTabChange={(t) => setTab(t as any)}
          viewport="mobile"
        />
      </div>
    );
  },
};

// ════════════════════════════════════════════════════════════════
// Playground
// ════════════════════════════════════════════════════════════════

export const Playground: Story = {
  name: "Playground",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop" },
  decorators: [desktopDec],
};