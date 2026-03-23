import type { Meta, StoryObj } from "@storybook/react";
import { OrderbookTable } from "./OrderbookTable";
import type { OrderbookRow, TradeTickRow, MarketInfo } from "./OrderbookTable";

// ─── Mock Data ────────────────────────────────────────────────

const MOCK_ASKS: OrderbookRow[] = [
  { price: 100000, changeRate: -10.00, quantity: 1200 },
  { price: 99500,  changeRate: -10.45, quantity: 800  },
  { price: 99000,  changeRate: -10.90, quantity: 2100 },
  { price: 98500,  changeRate: -11.35, quantity: 500  },
  { price: 98000,  changeRate: -11.80, quantity: 1800 },
  { price: 97500,  changeRate: -12.25, quantity: 900  },
  { price: 97000,  changeRate: -12.70, quantity: 3200 },
  { price: 96500,  changeRate: -13.15, quantity: 700  },
  { price: 96000,  changeRate: -13.60, quantity: 1500 },
  { price: 95500,  changeRate: -14.05, quantity: 600  },
  { price: 95000,  changeRate: -14.50, quantity: 1100 },
];

const MOCK_BIDS: OrderbookRow[] = [
  { price: 94500,  changeRate: -14.95, quantity: 2500 },
  { price: 94000,  changeRate: -15.40, quantity: 1300 },
  { price: 93500,  changeRate: -15.85, quantity: 800  },
  { price: 93000,  changeRate: -16.30, quantity: 3500 },
  { price: 92500,  changeRate: -16.75, quantity: 600  },
  { price: 92000,  changeRate: -17.20, quantity: 1900 },
  { price: 91500,  changeRate: -17.65, quantity: 700  },
  { price: 91000,  changeRate: -18.10, quantity: 2200 },
  { price: 90500,  changeRate: -18.55, quantity: 400  },
  { price: 90000,  changeRate: -19.00, quantity: 1600 },
  { price: 89500,  changeRate: -19.45, quantity: 900  },
  { price: 89000,  changeRate: -19.90, quantity: 1100 },
];

const MOCK_TRADES: TradeTickRow[] = [
  { price: 94800, quantity: 1, isBuy: true  },
  { price: 94750, quantity: 1, isBuy: false },
  { price: 94800, quantity: 1, isBuy: true  },
  { price: 94700, quantity: 1, isBuy: false },
  { price: 94750, quantity: 1, isBuy: true  },
  { price: 94800, quantity: 1, isBuy: false },
  { price: 94750, quantity: 1, isBuy: true  },
  { price: 94700, quantity: 1, isBuy: false },
  { price: 94800, quantity: 1, isBuy: true  },
  { price: 94750, quantity: 1, isBuy: false },
  { price: 94700, quantity: 1, isBuy: true  },
  { price: 94750, quantity: 1, isBuy: false },
  { price: 94800, quantity: 1, isBuy: true  },
  { price: 94700, quantity: 1, isBuy: false },
];

const MOCK_MARKET_INFO: MarketInfo = {
  weekHigh: 135000,
  weekLow: 82000,
  upperLimit: 130000,
  lowerLimit: 70000,
  riseVI: undefined,
  fallVI: undefined,
  open: 98000,
  high: 102000,
  low: 93000,
  volume: 12345678,
  volumeUnit: "1,234만 5,678",
  changeFromYesterday: -5,
  midPrice: 96750,
};

const meta: Meta<typeof OrderbookTable> = {
  title: "Components/Stock/OrderbookTable",
  component: OrderbookTable,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
    layout: "fullscreen",
    docs: {
      description: {
        component: "매도/매수 호가, 시세 정보 패널, 체결 내역을 포함한 호가창 컴포넌트. 잔량 바는 상대적 비율로 렌더링되며 방사형 그라데이션 배경 적용.",
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof OrderbookTable>;

// ─── Default ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default",
  args: {
    currentPrice: 100000,
    currentChangeRate: 10.00,
    asks: MOCK_ASKS,
    bids: MOCK_BIDS,
    trades: MOCK_TRADES,
    tradeStrength: 85,
    marketInfo: MOCK_MARKET_INFO,
    onQuickOrder: () => alert("빠른 주문"),
  },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── Market Closed ────────────────────────────────────────────

export const MarketClosed: Story = {
  name: "Market Closed — Badge",
  args: {
    currentPrice: 100000,
    currentChangeRate: 10.00,
    asks: MOCK_ASKS,
    bids: MOCK_BIDS,
    trades: MOCK_TRADES,
    tradeStrength: 85,
    marketInfo: MOCK_MARKET_INFO,
    isMarketClosed: true,
    onQuickOrder: () => alert("빠른 주문"),
  },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: {
    currentPrice: 100000,
    currentChangeRate: 10.00,
    asks: MOCK_ASKS,
    bids: MOCK_BIDS,
    trades: MOCK_TRADES,
    tradeStrength: 85,
    marketInfo: MOCK_MARKET_INFO,
  },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};