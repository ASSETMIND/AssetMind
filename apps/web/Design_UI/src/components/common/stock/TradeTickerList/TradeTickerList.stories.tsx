import type { Meta, StoryObj } from "@storybook/react";
import { useEffect, useRef, useState } from "react";
import { TradeTickerList } from "./TradeTickerList";
import type { TradeTickRow } from "./TradeTickerList";

// ─── Mock 데이터 ──────────────────────────────────────────────────────────────

const BASE_PRICE = 100_000;

function makeTrades(count: number): TradeTickRow[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `trade-init-${i}`,
    price: BASE_PRICE + Math.floor((Math.random() - 0.5) * 2000),
    quantity: Math.floor(Math.random() * 50) + 1,
    isBuy: Math.random() > 0.5,
  }));
}

// ─── Meta ─────────────────────────────────────────────────────────────────────

const meta: Meta<typeof TradeTickerList> = {
  title: "Components/Stock/TradeTickerList",
  component: TradeTickerList,
  parameters: {
    layout: "centered",
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#1C1D21" }],
    },
  },
  tags: ["autodocs"],
};

export default meta;
type Story = StoryObj<typeof TradeTickerList>;

// ─── Static (정적 목 데이터) ──────────────────────────────────────────────────

export const Static: Story = {
  args: {
    trades: makeTrades(20),
    tradeStrength: 87,
    height: 320,
  },
};

// ─── RealTime (신규 체결 진입 애니메이션 확인용) ──────────────────────────────

let idCounter = 100;

const RealTimeDemo = () => {
  const [trades, setTrades] = useState<TradeTickRow[]>(() => makeTrades(15));
  const [strength, setStrength] = useState(87);
  const [running, setRunning] = useState(true);
  const runningRef = useRef(running);
  runningRef.current = running;

  useEffect(() => {
    const interval = setInterval(() => {
      if (!runningRef.current) return;
      const newTrade: TradeTickRow = {
        id: `trade-rt-${idCounter++}`,
        price: BASE_PRICE + Math.floor((Math.random() - 0.5) * 2000),
        quantity: Math.floor(Math.random() * 50) + 1,
        isBuy: Math.random() > 0.5,
      };
      setTrades((prev) => [newTrade, ...prev].slice(0, 30));
      setStrength((prev) => Math.min(200, Math.max(0, prev + Math.floor((Math.random() - 0.5) * 10))));
    }, 800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px", alignItems: "flex-start" }}>
      <button
        onClick={() => setRunning((v) => !v)}
        style={{
          padding: "6px 16px",
          borderRadius: "8px",
          border: "1px solid rgba(255,255,255,0.2)",
          background: "transparent",
          color: "#fff",
          cursor: "pointer",
          fontSize: "13px",
        }}
      >
        {running ? "⏸ 일시정지" : "▶ 재개"}
      </button>
      <div style={{ width: "200px", background: "#1C1D21", borderRadius: "8px", padding: "8px" }}>
        <TradeTickerList trades={trades} tradeStrength={strength} height={320} />
      </div>
    </div>
  );
};

export const RealTime: Story = {
  render: () => <RealTimeDemo />,
  parameters: {
    docs: {
      description: {
        story: "800ms 간격으로 신규 체결이 상단에 추가됩니다. 슬라이드인 + flash 애니메이션을 확인하세요.",
      },
    },
  },
};

// ─── Empty (체결 없음) ────────────────────────────────────────────────────────

export const Empty: Story = {
  args: {
    trades: [],
    tradeStrength: 0,
    height: 200,
  },
};

// ─── WithinOrderbook (OrderbookTable 내 사용 맥락 시뮬레이션) ────────────────

export const NarrowContainer: Story = {
  args: {
    trades: makeTrades(20),
    tradeStrength: 112,
    height: 400,
  },
  decorators: [
    (Story) => (
      <div style={{ width: "120px", background: "#1C1D21", borderRadius: "8px", padding: "8px" }}>
        <Story />
      </div>
    ),
  ],
  parameters: {
    docs: {
      description: {
        story: "OrderbookTable 왼쪽 컬럼처럼 좁은 컨테이너(120px) 내 사용 예시.",
      },
    },
  },
};