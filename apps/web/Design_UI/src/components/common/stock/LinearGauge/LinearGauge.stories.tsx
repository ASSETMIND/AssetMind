import type { Meta, StoryObj } from "@storybook/react";
import { LinearGauge } from "./LinearGauge";

const meta: Meta<typeof LinearGauge> = {
  title: "Components/Stock/LinearGauge",
  component: LinearGauge,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
  },
  argTypes: {
    buyRatio: {
      control: { type: "range", min: 0, max: 100, step: 1 },
      description: "Buy ratio (0~100). Sell ratio is calculated automatically.",
    },
  },
};

export default meta;
type Story = StoryObj<typeof LinearGauge>;

// ─── Default ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default (50:50)",
  args: { buyRatio: 50 },
  decorators: [
    (Story) => (
      <div style={{ padding: "24px", backgroundColor: "#131316" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── All States ───────────────────────────────────────────────

export const AllStates: Story = {
  name: "All States",
  render: () => {
    const cases = [
      { label: "매수 우세 (70:30)", buyRatio: 70 },
      { label: "매도 우세 (30:70)", buyRatio: 30 },
      { label: "균형 (50:50)",      buyRatio: 50 },
      { label: "극단 매수 (99:1)",  buyRatio: 99 },
      { label: "극단 매도 (1:99)",  buyRatio: 1  },
      { label: "전량 매수 (100:0)", buyRatio: 100 },
      { label: "전량 매도 (0:100)", buyRatio: 0  },
    ];
    return (
      <div style={{ padding: "24px", backgroundColor: "#131316", display: "flex", flexDirection: "column", gap: "24px" }}>
        {cases.map(({ label, buyRatio }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: "24px" }}>
            <span style={{ fontSize: "13px", color: "#9194A1", width: "160px", flexShrink: 0 }}>{label}</span>
            <LinearGauge buyRatio={buyRatio} />
          </div>
        ))}
      </div>
    );
  },
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: { buyRatio: 62 },
  decorators: [
    (Story) => (
      <div style={{ padding: "24px", backgroundColor: "#131316" }}>
        <Story />
      </div>
    ),
  ],
};