import type { Meta, StoryObj } from "@storybook/react";
import { useEffect, useState } from "react";
import { StockTable } from "./StockTable";
import { TickerAnimation } from "../TickerAnimation/TickerAnimation";
import type { StockRow } from "./StockTable";

const MOCK_ROWS: StockRow[] = [
  { id: "1",  rank: 1,  isFavorite: true,  name: "삼성전자",       price: 75000,  changeRate: 2.35,  tradeAmount: 980000, buyRatio: 62 },
  { id: "2",  rank: 2,  isFavorite: false, name: "SK하이닉스",     price: 182000, changeRate: -1.2,  tradeAmount: 720000, buyRatio: 38 },
  { id: "3",  rank: 3,  isFavorite: false, name: "LG에너지솔루션", price: 410000, changeRate: 0.45,  tradeAmount: 540000, buyRatio: 51 },
  { id: "4",  rank: 4,  isFavorite: false, name: "현대차",         price: 231000, changeRate: -3.1,  tradeAmount: 430000, buyRatio: 29 },
  { id: "5",  rank: 5,  isFavorite: true,  name: "NAVER",         price: 198000, changeRate: 1.08,  tradeAmount: 380000, buyRatio: 70 },
  { id: "6",  rank: 6,  isFavorite: false, name: "카카오",         price: 54000,  changeRate: 0,     tradeAmount: 310000, buyRatio: 50 },
  { id: "7",  rank: 7,  isFavorite: false, name: "포스코홀딩스",   price: 389000, changeRate: -0.55, tradeAmount: 270000, buyRatio: 44 },
  { id: "8",  rank: 8,  isFavorite: false, name: "삼성바이오로직스", price: 875000, changeRate: 4.2, tradeAmount: 250000, buyRatio: 78 },
  { id: "9",  rank: 9,  isFavorite: false, name: "셀트리온",       price: 167000, changeRate: -2.0,  tradeAmount: 210000, buyRatio: 33 },
  { id: "10", rank: 10, isFavorite: false, name: "기아",           price: 95000,  changeRate: 1.5,   tradeAmount: 190000, buyRatio: 60 },
];

const EXTREME_ROWS: StockRow[] = [
  { id: "e1", rank: 1, isFavorite: false, name: "극단 매수 (99:1)", price: 10000, changeRate: 29.9,  tradeAmount: 999999, buyRatio: 99 },
  { id: "e2", rank: 2, isFavorite: false, name: "극단 매도 (1:99)", price: 10000, changeRate: -29.9, tradeAmount: 999999, buyRatio: 1  },
  { id: "e3", rank: 3, isFavorite: false, name: "보합 (50:50)",     price: 10000, changeRate: 0,     tradeAmount: 500000, buyRatio: 50 },
];

const meta: Meta<typeof StockTable> = {
  title: "Components/Stock/StockTable",
  component: StockTable,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
    layout: "fullscreen",
    docs: {
      canvas: {
        layout: "fullscreen",
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof StockTable>;

// ─── Default ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default",
  args: { rows: MOCK_ROWS },
  decorators: [
    (Story) => (
      <div className="bg-background-primary p-4" style={{ minWidth: "1200px" }}>
        <Story />
      </div>
    ),
  ],
};

export const ExtremeRatios: Story = {
  name: "Extreme Ratios (99:1) — min-width 4px",
  args: { rows: EXTREME_ROWS },
  decorators: [
    (Story) => (
      <div className="bg-background-primary p-4" style={{ minWidth: "1200px" }}>
        <Story />
      </div>
    ),
  ],
};

export const TickerAnimationDemo: Story = {
  name: "Ticker Animation — Dynamic Price Updates",
  render: () => {
    const [rows, setRows] = useState<StockRow[]>(MOCK_ROWS);

    useEffect(() => {
      // 각 행마다 독립적인 인터벌 — 랜덤 딜레이로 자연스러운 갱신
      const timers = MOCK_ROWS.map((row) => {
        const randomInterval = 1500 + Math.random() * 3000; // 1.5~4.5초 랜덤
        return setInterval(() => {
          const delta = Math.floor((Math.random() - 0.5) * 2000);
          if (delta === 0) return;
          setRows((prev) =>
            prev.map((r) =>
              r.id === row.id
                ? { ...r, price: Math.max(1000, r.price + delta) }
                : r
            )
          );
        }, randomInterval);
      });
      return () => timers.forEach(clearInterval);
    }, []);

    return (
      <div className="bg-background-primary p-4" style={{ minWidth: "1200px" }}>
        <p className="text-text-secondary text-b2 mb-4">
          각 종목마다 독립적으로 갱신 — 상승 시 붉은색, 하락 시 파란색 배경 깜빡임
        </p>
        <div style={{ width: "1200px" }}>
          {rows.map((row) => (
            <TickerAnimation key={row.id} row={row} />
          ))}
        </div>
      </div>
    );
  },
};

export const Playground: Story = {
  name: "Playground",
  args: { rows: MOCK_ROWS.slice(0, 3) },
  decorators: [
    (Story) => (
      <div className="bg-background-primary p-4" style={{ minWidth: "1200px" }}>
        <Story />
      </div>
    ),
  ],
};