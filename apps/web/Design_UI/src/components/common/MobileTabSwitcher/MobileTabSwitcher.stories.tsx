import type { Meta, StoryObj } from "@storybook/react";
import { MobileTabSwitcher } from "./MobileTabSwitcher";
import { ChartIcon } from "../../icons/ChartIcon";
import { StockInfoIcon } from "../../icons/StockInfoIcon";
import { TradeStatusIcon } from "../../icons/TradeStatusIcon";
import { AIPredictionIcon } from "../../icons/AIPredictionIcon";

const MOCK_ITEMS = [
  { label: "차트", value: "chart", icon: <ChartIcon /> },
  { label: "종목 정보", value: "info", icon: <StockInfoIcon /> },
  { label: "거래 현황", value: "trade", icon: <TradeStatusIcon /> },
  { label: "AI 예측", value: "ai", icon: <AIPredictionIcon /> },
];

const meta: Meta<typeof MobileTabSwitcher> = {
  title: "Components/Common/MobileTabSwitcher",
  component: MobileTabSwitcher,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
    viewport: {
      defaultViewport: "mobile1",
    },
  },
  argTypes: {
    items: {
      description: "Array of tab items ({ label, value, icon })",
    },
    defaultValue: {
      description: "Default selected value (uncontrolled)",
    },
    value: {
      description: "Controlled selected value",
    },
    onChange: {
      description: "Callback fired when the selected tab changes",
    },
  },
};

export default meta;
type Story = StoryObj<typeof MobileTabSwitcher>;

// ─── Default ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default",
  args: {
    items: MOCK_ITEMS,
    defaultValue: "chart",
  },
};

// ─── Sticky 인터랙션 데모 ──────────────────────────────────────

export const StickyInteraction: Story = {
  name: "Sticky Interaction (Scroll Demo)",
  render: () => (
    <div className="relative h-[600px] overflow-y-auto bg-background-primary flex flex-col">
      {/* 스크롤 유도용 콘텐츠 */}
      <div className="flex-1 p-4 flex flex-col gap-3">
        <p className="text-text-secondary text-b2 mb-2">
          ↓ 아래로 스크롤하면 탭이 하단에 고정됩니다
        </p>
        {Array.from({ length: 20 }).map((_, i) => (
          <div key={i} className="h-12 bg-background-surface rounded-[8px]" />
        ))}
      </div>

      {/* 탭은 flex 컨테이너 맨 아래 — sticky bottom-0 동작 */}
      <MobileTabSwitcher items={MOCK_ITEMS} defaultValue="chart" />
    </div>
  ),
};

// ─── Active states ────────────────────────────────────────────

export const ActiveStates: Story = {
  name: "Active States",
  render: () => (
    <div className="flex flex-col gap-6 bg-background-primary p-4">
      {MOCK_ITEMS.map((item) => (
        <div key={item.value}>
          <p className="text-text-secondary text-b2 mb-2">Active: {item.label}</p>
          <MobileTabSwitcher items={MOCK_ITEMS} defaultValue={item.value} />
        </div>
      ))}
    </div>
  ),
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: {
    items: MOCK_ITEMS,
    defaultValue: "chart",
  },
};