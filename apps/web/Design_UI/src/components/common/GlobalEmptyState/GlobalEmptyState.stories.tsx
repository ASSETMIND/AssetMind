import type { Meta, StoryObj } from "@storybook/react";
import { GlobalEmptyState } from "./GlobalEmptyState";

const meta: Meta<typeof GlobalEmptyState> = {
  title: "Components/Common/GlobalEmptyState",
  component: GlobalEmptyState,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
  },
  argTypes: {
    variant: {
      control: "radio",
      options: ["no-data", "market-closed"],
      description: "no-data: 조회 결과 없음 / market-closed: 시장 휴장",
    },
    display: {
      control: "radio",
      options: ["inline", "badge"],
      description: "inline: 영역 중앙 표시 / badge: 우측 상단 소형 뱃지",
    },
    message: {
      control: "text",
      description: "Custom main message (optional)",
    },
    subMessage: {
      control: "text",
      description: "Custom sub message (optional)",
    },
  },
};

export default meta;
type Story = StoryObj<typeof GlobalEmptyState>;

// ─── Stock Chart Empty (no-data, inline) ──────────────────────

export const StockChartEmpty: Story = {
  name: "Stock Chart — No Data",
  args: { variant: "no-data", display: "inline" },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", width: "1200px", minHeight: "400px", display: "flex", alignItems: "center" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── 호가창 Empty (market-closed, inline) ─────────────────────

export const OrderbookEmpty: Story = {
  name: "Orderbook — Market Closed",
  args: { variant: "market-closed", display: "inline" },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", width: "320px", minHeight: "600px", display: "flex", alignItems: "center" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── Badge variant ────────────────────────────────────────────

export const BadgeVariant: Story = {
  name: "Badge — Market Closed (차트·AI 패널 우측 상단)",
  args: { variant: "market-closed", display: "badge" },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "24px" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── Badge in context ─────────────────────────────────────────

export const BadgeInContext: Story = {
  name: "Badge — In Chart Context",
  render: () => (
    <div style={{ backgroundColor: "#131316", padding: "16px", position: "relative", width: "600px" }}>
      {/* 차트 필터 탭 + 뱃지 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          {["1분", "일", "주", "월", "년"].map((label) => (
            <span key={label} style={{ fontSize: "14px", color: "#9194A1", cursor: "pointer" }}>{label}</span>
          ))}
        </div>
        <GlobalEmptyState variant="market-closed" display="badge" />
      </div>
      {/* 차트 영역 placeholder */}
      <div style={{ width: "100%", height: "300px", backgroundColor: "#1C1D21", borderRadius: "8px" }} />
    </div>
  ),
};

// ─── All States ───────────────────────────────────────────────

export const AllStates: Story = {
  name: "All States",
  render: () => (
    <div style={{ backgroundColor: "#131316", display: "flex", flexDirection: "column", gap: "32px", padding: "24px" }}>
      <div>
        <p style={{ fontSize: "12px", color: "#9194A1", marginBottom: "8px" }}>no-data / inline</p>
        <div style={{ border: "1px solid #2F3037", borderRadius: "8px" }}>
          <GlobalEmptyState variant="no-data" display="inline" />
        </div>
      </div>
      <div>
        <p style={{ fontSize: "12px", color: "#9194A1", marginBottom: "8px" }}>market-closed / inline</p>
        <div style={{ border: "1px solid #2F3037", borderRadius: "8px" }}>
          <GlobalEmptyState variant="market-closed" display="inline" />
        </div>
      </div>
      <div>
        <p style={{ fontSize: "12px", color: "#9194A1", marginBottom: "8px" }}>market-closed / badge</p>
        <GlobalEmptyState variant="market-closed" display="badge" />
      </div>
    </div>
  ),
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: {
    variant: "market-closed",
    display: "inline",
  },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", width: "100%", minHeight: "300px", display: "flex", alignItems: "center" }}>
        <Story />
      </div>
    ),
  ],
};