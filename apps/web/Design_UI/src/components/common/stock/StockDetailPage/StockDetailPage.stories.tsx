import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { StockDetailPage } from "./StockDetailPage";
import type { CandlestickData } from "../TradingViewWrapper/TradingViewWrapper";
import type { OrderbookRow, MarketInfo } from "../OrderbookTable/OrderbookTable";
import type { TradeTickRow } from "../TradeTickerList/TradeTickerList";
import type { SparklineDataPoint } from "../AIPredictionPanel/SparklineChart";
import type { AnalysisData } from "../AIPredictionPanel/PredictionAnalysisWidget";
import type {
  TrendDataPoint, TrendTableRow,
  ProgramTradeRow, CreditTradeRow, LendingTradeRow,
  ShortTradeRow, CfdTradeRow,
} from "../InvestorTradePanel/InvestorTradePanel";
import type { CompanyInfo, BusinessItem } from "../StockInfoPanel/StockInfoPanel";
import type { DonutSlice } from "../DonutChart/DonutChart";

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

const MOCK_BUY_LIST = [
  { rank: 1, name: "미래에셋증권", quantity: 1240000 },
  { rank: 2, name: "키움증권",     quantity: 980000  },
  { rank: 3, name: "삼성증권",     quantity: 750000  },
  { rank: 4, name: "NH투자증권",   quantity: 620000  },
  { rank: 5, name: "한국투자증권", quantity: 430000  },
];

const MOCK_SELL_LIST = [
  { rank: 1, name: "외국계A",      quantity: 1100000 },
  { rank: 2, name: "외국계B",      quantity: 870000  },
  { rank: 3, name: "KB증권",       quantity: 650000  },
  { rank: 4, name: "신한투자증권", quantity: 490000  },
  { rank: 5, name: "메리츠증권",   quantity: 310000  },
];

const MOCK_TREND_DATA: TrendDataPoint[] = [
  { time: "2026-03-19", individual: -5200000,  foreign:  8100000,  institution:  2300000 },
  { time: "2026-03-20", individual:  3100000,  foreign: -4200000,  institution:  1800000 },
  { time: "2026-03-23", individual: -1800000,  foreign:  6500000,  institution: -3200000 },
  { time: "2026-03-24", individual:  7400000,  foreign: -9800000,  institution:  4100000 },
  { time: "2026-03-25", individual: -6300000,  foreign: 12000000,  institution: -2700000 },
  { time: "2026-03-26", individual:  2900000,  foreign: -5600000,  institution:  3500000 },
  { time: "2026-03-27", individual: -4100000,  foreign:  7300000,  institution: -1900000 },
  { time: "2026-03-30", individual:  8200000,  foreign: -11000000, institution:  5600000 },
  { time: "2026-03-31", individual: -3700000,  foreign:  9400000,  institution: -4300000 },
  { time: "2026-04-01", individual:  5100000,  foreign: -6800000,  institution:  2100000 },
];

const MOCK_TRADE_TABLE: TrendTableRow[] = Array.from({ length: 10 }, (_, i) => ({
  date: `2026-04-${String(15 - i).padStart(2, "0")}`,
  closePrice: 75000 + Math.floor((Math.random() - 0.5) * 3000),
  changeRate: parseFloat(((Math.random() - 0.5) * 4).toFixed(2)),
  changeAmount: Math.floor((Math.random() - 0.5) * 2000),
  individualNet: Math.floor((Math.random() - 0.5) * 10000000),
  foreignNet: Math.floor((Math.random() - 0.5) * 15000000),
  foreignRatio: parseFloat((52 + (Math.random() - 0.5) * 2).toFixed(2)),
  institutionNet: Math.floor((Math.random() - 0.5) * 8000000),
}));

const MOCK_PROGRAM_DATA: ProgramTradeRow[] = Array.from({ length: 10 }, (_, i) => ({
  date: `2026-04-${String(15 - i).padStart(2, "0")}`,
  netBuyChange: Math.floor((Math.random() - 0.5) * 5000000),
  netBuy: Math.floor((Math.random() - 0.5) * 20000000),
  buy: Math.floor(Math.random() * 50000000 + 10000000),
  sell: Math.floor(Math.random() * 50000000 + 10000000),
  nonArbitrageNet: Math.floor((Math.random() - 0.5) * 15000000),
}));

const MOCK_CREDIT_DATA: CreditTradeRow[] = Array.from({ length: 10 }, (_, i) => ({
  date: `2026-04-${String(15 - i).padStart(2, "0")}`,
  type: i % 2 === 0 ? "융자" : "대주",
  changeQty: Math.floor((Math.random() - 0.5) * 100000),
  newQty: Math.floor(Math.random() * 200000 + 50000),
  repayQty: Math.floor(Math.random() * 150000 + 30000),
  balanceQty: Math.floor(Math.random() * 5000000 + 1000000),
  balanceRate: parseFloat((Math.random() * 5).toFixed(2)),
}));

const MOCK_LENDING_DATA: LendingTradeRow[] = Array.from({ length: 10 }, (_, i) => ({
  date: `2026-04-${String(15 - i).padStart(2, "0")}`,
  changeQty: Math.floor((Math.random() - 0.5) * 50000),
  newQty: Math.floor(Math.random() * 100000 + 20000),
  repayQty: Math.floor(Math.random() * 80000 + 15000),
  balanceQty: Math.floor(Math.random() * 2000000 + 500000),
}));

const MOCK_SHORT_DATA: ShortTradeRow[] = Array.from({ length: 10 }, (_, i) => ({
  date: `2026-04-${String(15 - i).padStart(2, "0")}`,
  tradeAmountRatio: parseFloat((Math.random() * 8 + 1).toFixed(2)),
  shortQty: Math.floor(Math.random() * 500000 + 100000),
  shortAmount: Math.floor(Math.random() * 30000000000 + 5000000000),
  shortAvgPrice: Math.floor(74000 + (Math.random() - 0.5) * 2000),
  tradeAmount: Math.floor(Math.random() * 400000000000 + 50000000000),
}));

const MOCK_CFD_DATA: CfdTradeRow[] = Array.from({ length: 10 }, (_, i) => ({
  date: `2026-04-${String(15 - i).padStart(2, "0")}`,
  newBuyQty: Math.floor(Math.random() * 50000),
  repayBuyQty: Math.floor(Math.random() * 40000),
  balanceBuyQty: Math.floor(Math.random() * 200000 + 50000),
  buyBalanceRate: parseFloat((Math.random() * 3).toFixed(2)),
  newSellQty: Math.floor(Math.random() * 45000),
  repaySellQty: Math.floor(Math.random() * 35000),
  balanceSellQty: Math.floor(Math.random() * 180000 + 40000),
  sellBalanceRate: parseFloat((Math.random() * 3).toFixed(2)),
}));

// 거래현황 공통 args
const TRADE_ARGS = {
  tradeState: "default" as const,
  buyList: MOCK_BUY_LIST,
  sellList: MOCK_SELL_LIST,
  rankBaseDateTime: "2026.04.20 15:30",
  trendData: MOCK_TREND_DATA,
  trendBaseDateTime: "2026.04.20 15:30",
  tradeTableData: MOCK_TRADE_TABLE,
  programData: MOCK_PROGRAM_DATA,
  creditData: MOCK_CREDIT_DATA,
  lendingData: MOCK_LENDING_DATA,
  shortData: MOCK_SHORT_DATA,
  cfdData: MOCK_CFD_DATA,
  onViewNetBuy: () => alert("투자자별 순매수 보기"),
};

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

  // 거래현황 데이터
  ...TRADE_ARGS,

  // 종목정보 데이터
  stockInfoState: "default" as const,
  company: {
    name: "삼성전자",
    market: "국내",
    ticker: "005930",
    exchange: "코스피",
    homepageUrl: "https://www.samsung.com/sec",
    source: "",
    description: "동사는 1969년 설립되어 수원시 영통구에 본사를 두고 있으며, 3개의 생산기지와 2개의 연구개발법인, 다수의 해외 판매법인을 운영하는 글로벌 전자 기업입니다.",
    marketCap: "400조 8000억 원",
    enterpriseValue: "380조 1000억 원",
    companyName: "Samsung Electronics Co., Ltd.",
    ceo: "한종희, 경계현",
    listingDate: "1975년 06월 11일",
    listingDateSub: "1975년 06월 11일 기준",
    shares: "5,969,782,550주",
    sharesSub: "2026년 04월 15일 기준",
  } as CompanyInfo,
  donutSlices: [
    { label: "TV, 모니터, 냉장고, 세탁기, 에어컨, 스마트폰 등", value: 45.32, color: "#4FA3B8" },
    { label: "스마트폰용 OLED패널 등",                          value: 28.17, color: "#8A6BBE" },
    { label: "범례 3",                                          value: 16.45, color: "#C9A24D" },
    { label: "범례 4",                                          value: 10.06, color: "#73B959" },
  ] as DonutSlice[],
  donutBaseDate: "2025년 12월 기준",
  donutNote: "마이너스 매출비중 : 계열사간 내부거래 등에 따른 조정",
  mainBusinesses: [
    { id: "b1", name: "사업명 1", marketCap: "0위", modalProps: { categoryName: "사업명 1", categorySubtitle: "0개 회사 · 0개 ETF", returnCards: [{ label: "어제보다", value: "-0.00%", isRise: false }, { label: "1개월 전보다", value: "+0.00%", isRise: true }, { label: "3개월 전보다", value: "+0.00%", isRise: true }, { label: "1년 전보다", value: "-0.00%", isRise: false }], stockList: [], etfList: [] } },
    { id: "b2", name: "사업명 2", marketCap: "0위", modalProps: { categoryName: "사업명 2", categorySubtitle: "0개 회사 · 0개 ETF", returnCards: [], stockList: [], etfList: [] } },
    { id: "b3", name: "사업명 3", marketCap: "0위", modalProps: { categoryName: "사업명 3", categorySubtitle: "0개 회사 · 0개 ETF", returnCards: [], stockList: [], etfList: [] } },
    { id: "b4", name: "사업명 4", marketCap: "0위", modalProps: { categoryName: "사업명 4", categorySubtitle: "0개 회사 · 0개 ETF", returnCards: [], stockList: [], etfList: [] } },
    { id: "b5", name: "사업명 5", marketCap: "0위", modalProps: { categoryName: "사업명 5", categorySubtitle: "0개 회사 · 0개 ETF", returnCards: [], stockList: [], etfList: [] } },
    { id: "b6", name: "사업명 6", marketCap: "0위", modalProps: { categoryName: "사업명 6", categorySubtitle: "0개 회사 · 0개 ETF", returnCards: [], stockList: [], etfList: [] } },
  ] as BusinessItem[],
  otherBusinesses: [
    { id: "o1", name: "사업명 1", marketCap: "0위" },
    { id: "o2", name: "사업명 2", marketCap: "0위" },
    { id: "o3", name: "사업명 3", marketCap: "0위" },
    { id: "o4", name: "사업명 4", marketCap: "0위" },
    { id: "o5", name: "사업명 5", marketCap: "0위" },
    { id: "o6", name: "사업명 6", marketCap: "0위" },
  ] as BusinessItem[],
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
    tradeState: {
      control: "radio",
      options: ["default", "skeleton", "error"],
      description: "거래현황 패널 상태",
    },
    stockInfoState: {
      control: "radio",
      options: ["default", "skeleton", "error"],
      description: "종목정보 패널 상태",
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
  <div style={{ width: "393px", height: "852px", overflow: "hidden" }}><Story /></div>
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
// 거래현황 탭 Stories
// ════════════════════════════════════════════════════════════════

export const DesktopTrade: Story = {
  name: "Desktop / Trade Tab — Default",
  args: { ...COMMON_ARGS, activeTab: "trade", viewport: "desktop" },
  decorators: [desktopDec],
};

export const DesktopTradeSkeleton: Story = {
  name: "Desktop / Trade Tab — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "trade", viewport: "desktop", tradeState: "skeleton" },
  decorators: [desktopDec],
};

export const DesktopTradeError: Story = {
  name: "Desktop / Trade Tab — Error",
  args: { ...COMMON_ARGS, activeTab: "trade", viewport: "desktop", tradeState: "error" },
  decorators: [desktopDec],
};

export const TabletTrade: Story = {
  name: "Tablet / Trade Tab — Default",
  args: { ...COMMON_ARGS, activeTab: "trade", viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDec],
};

export const TabletTradeSkeleton: Story = {
  name: "Tablet / Trade Tab — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "trade", viewport: "tablet", tradeState: "skeleton" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDec],
};

export const MobileTrade: Story = {
  name: "Mobile / Trade Tab — Default",
  args: { ...COMMON_ARGS, activeTab: "trade", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const MobileTradeSkeleton: Story = {
  name: "Mobile / Trade Tab — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "trade", viewport: "mobile", tradeState: "skeleton" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const DesktopTradeTabSwitching: Story = {
  name: "Desktop / Trade Tab Switching Demo",
  parameters: {
    docs: {
      description: {
        story: "거래현황 탭 전환 인터랙션 데모. 탭 클릭으로 차트·거래현황 간 전환을 확인합니다.",
      },
    },
  },
  render: () => {
    const [tab, setTab] = useState<"chart" | "orderbook" | "trade" | "ai">("trade");
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

// ════════════════════════════════════════════════════════════════
// 종목정보 탭 Stories
// ════════════════════════════════════════════════════════════════

export const DesktopStockInfo: Story = {
  name: "Desktop / Stock Info Tab — Default",
  args: { ...COMMON_ARGS, activeTab: "orderbook", viewport: "desktop" },
  decorators: [desktopDec],
};

export const DesktopStockInfoSkeleton: Story = {
  name: "Desktop / Stock Info Tab — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "orderbook", viewport: "desktop", stockInfoState: "skeleton" },
  decorators: [desktopDec],
};

export const DesktopStockInfoError: Story = {
  name: "Desktop / Stock Info Tab — Error",
  args: { ...COMMON_ARGS, activeTab: "orderbook", viewport: "desktop", stockInfoState: "error" },
  decorators: [desktopDec],
};

export const TabletStockInfo: Story = {
  name: "Tablet / Stock Info Tab — Default",
  args: { ...COMMON_ARGS, activeTab: "orderbook", viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDec],
};

export const TabletStockInfoSkeleton: Story = {
  name: "Tablet / Stock Info Tab — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "orderbook", viewport: "tablet", stockInfoState: "skeleton" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDec],
};

export const MobileStockInfo: Story = {
  name: "Mobile / Stock Info Tab — Default",
  args: { ...COMMON_ARGS, activeTab: "orderbook", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const MobileStockInfoSkeleton: Story = {
  name: "Mobile / Stock Info Tab — Skeleton",
  args: { ...COMMON_ARGS, activeTab: "orderbook", viewport: "mobile", stockInfoState: "skeleton" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDec],
};

export const DesktopStockInfoTabSwitching: Story = {
  name: "Desktop / Stock Info Tab Switching Demo",
  parameters: {
    docs: {
      description: {
        story: "종목정보 탭 전환 인터랙션 데모. 주요 사업 클릭 시 CategoryModal이 열립니다.",
      },
    },
  },
  render: () => {
    const [tab, setTab] = useState<"chart" | "orderbook" | "trade" | "ai">("orderbook");
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

// ════════════════════════════════════════════════════════════════
// Playground
// ════════════════════════════════════════════════════════════════

export const Playground: Story = {
  name: "Playground",
  args: { ...COMMON_ARGS, activeTab: "chart", viewport: "desktop" },
  decorators: [desktopDec],
};