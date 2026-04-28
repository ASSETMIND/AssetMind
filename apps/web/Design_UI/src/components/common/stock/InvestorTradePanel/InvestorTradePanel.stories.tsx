import type { Meta, StoryObj } from "@storybook/react";
import { InvestorTradePanel } from "./InvestorTradePanel";
import type {
  TrendDataPoint, TrendTableRow,
  ProgramTradeRow, CreditTradeRow, LendingTradeRow,
  ShortTradeRow, CfdTradeRow,
} from "./InvestorTradePanel";

// ─── Mock Data ────────────────────────────────────────────────

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
  { time: "2026-04-02", individual: -2400000,  foreign:  4700000,  institution: -1500000 },
  { time: "2026-04-03", individual:  6800000,  foreign: -8200000,  institution:  3800000 },
  { time: "2026-04-06", individual: -7100000,  foreign: 10500000,  institution: -5200000 },
  { time: "2026-04-07", individual:  4300000,  foreign: -7400000,  institution:  2900000 },
  { time: "2026-04-08", individual: -1900000,  foreign:  3600000,  institution: -1200000 },
  { time: "2026-04-09", individual:  9100000,  foreign: -13000000, institution:  6700000 },
  { time: "2026-04-10", individual: -5600000,  foreign:  8900000,  institution: -3900000 },
  { time: "2026-04-13", individual:  3800000,  foreign: -5100000,  institution:  2400000 },
  { time: "2026-04-14", individual: -2100000,  foreign:  4400000,  institution: -1800000 },
  { time: "2026-04-15", individual:  7500000,  foreign: -10200000, institution:  5100000 },
];

const MOCK_TABLE_DATA: TrendTableRow[] = Array.from({ length: 10 }, (_, i) => ({
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

const ALL_ARGS = {
  buyList: MOCK_BUY_LIST,
  sellList: MOCK_SELL_LIST,
  rankBaseDateTime: "2026.04.19 15:30",
  trendData: MOCK_TREND_DATA,
  trendBaseDateTime: "2026.04.19 15:30",
  tableData: MOCK_TABLE_DATA,
  programData: MOCK_PROGRAM_DATA,
  creditData: MOCK_CREDIT_DATA,
  lendingData: MOCK_LENDING_DATA,
  shortData: MOCK_SHORT_DATA,
  cfdData: MOCK_CFD_DATA,
  onViewNetBuy: () => alert("투자자별 순매수 보기"),
  onRetry: () => alert("Retry"),
};

// ─── Meta ─────────────────────────────────────────────────────

const meta: Meta<typeof InvestorTradePanel> = {
  title: "Components/Stock/InvestorTradePanel",
  component: InvestorTradePanel,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "거래현황 탭 통합 패널. 거래원 매매 상위(매수/매도 상위 5) + 투자자별 매매 동향(라인 차트 + 데이터 테이블 + 투자 유형별 현황)으로 구성됩니다. `status` prop으로 default·skeleton·error 상태 전환 가능.",
      },
    },
  },
  argTypes: {
    status: {
      control: "radio",
      options: ["default", "skeleton", "error"],
      description: "default: 정상 | skeleton: 로딩 중 | error: API 실패",
    },
  },
};

export default meta;
type Story = StoryObj<typeof InvestorTradePanel>;

// ─── Stories ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default",
  args: { ...ALL_ARGS, status: "default", panelWidth: 1036, panelHeight: 820 },
  decorators: [(Story) => <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}><Story /></div>],
};

export const Skeleton: Story = {
  name: "Skeleton",
  args: { status: "skeleton", panelWidth: 1036, panelHeight: 820 },
  parameters: {
    docs: { description: { story: "API 호출 중 Skeleton 애니메이션 표시 상태입니다." } },
  },
  decorators: [(Story) => <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}><Story /></div>],
};

export const Error: Story = {
  name: "Error",
  args: { status: "error", onRetry: () => alert("Retry"), panelWidth: 1036, panelHeight: 820 },
  decorators: [(Story) => <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}><Story /></div>],
};

export const Tablet: Story = {
  name: "Tablet — Default",
  args: { ...ALL_ARGS, status: "default", panelWidth: 710, panelHeight: 820 },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [(Story) => <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}><Story /></div>],
};

export const Mobile: Story = {
  name: "Mobile — Default",
  args: { ...ALL_ARGS, status: "default", panelWidth: 345, panelHeight: 657 },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [(Story) => <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}><Story /></div>],
};

export const Playground: Story = {
  name: "Playground",
  args: { ...ALL_ARGS, status: "default", panelWidth: 1036, panelHeight: 820 },
  decorators: [(Story) => <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}><Story /></div>],
};