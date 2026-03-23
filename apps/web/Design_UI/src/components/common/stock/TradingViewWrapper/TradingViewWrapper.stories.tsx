import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { TradingViewWrapper } from "./TradingViewWrapper";
import type { ChartPeriod, CandlestickData } from "./TradingViewWrapper";

// ─── Mock Data ────────────────────────────────────────────────

const generateMockData = (days: number): CandlestickData[] => {
  const data: CandlestickData[] = [];
  let price = 200000;
  const startDate = new Date("2025-10-01");

  for (let i = 0; i < days; i++) {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + i);
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const open = price;
    const change = (Math.random() - 0.48) * 10000;
    const close = Math.max(50000, open + change);
    const high = Math.max(open, close) + Math.random() * 5000;
    const low = Math.min(open, close) - Math.random() * 5000;
    const volume = Math.floor(Math.random() * 200000000 + 100000000);

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

const MOCK_DATA = generateMockData(180);

const meta: Meta<typeof TradingViewWrapper> = {
  title: "Components/Stock/TradingViewWrapper",
  component: TradingViewWrapper,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
    layout: "fullscreen",
    docs: {
      description: {
        component: "Lightweight Charts 기반 캔들스틱 차트 래퍼. 기간 선택 Tab 연동, 거래량 히스토그램, 시장 휴장 뱃지 포함.",
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof TradingViewWrapper>;

// ─── Default ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default",
  args: {
    data: MOCK_DATA,
    period: "1d",
    isMarketClosed: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: "640px", height: "500px", backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── Market Closed ────────────────────────────────────────────

export const MarketClosed: Story = {
  name: "Market Closed — Badge",
  args: {
    data: MOCK_DATA,
    period: "1d",
    isMarketClosed: true,
  },
  decorators: [
    (Story) => (
      <div style={{ width: "640px", height: "500px", backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── Period Control ───────────────────────────────────────────

export const PeriodControl: Story = {
  name: "Period Tab Control",
  render: () => {
    const [period, setPeriod] = useState<ChartPeriod>("1d");
    return (
      <div style={{ width: "640px", height: "500px", backgroundColor: "#131316", padding: "16px" }}>
        <TradingViewWrapper
          data={MOCK_DATA}
          period={period}
          onPeriodChange={setPeriod}
        />
        <p style={{ color: "#9194A1", fontSize: "14px", marginTop: "8px" }}>
          Selected period: {period}
        </p>
      </div>
    );
  },
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: {
    data: MOCK_DATA,
    period: "1d",
    isMarketClosed: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: "640px", height: "500px", backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};