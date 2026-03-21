import type { Meta, StoryObj } from "@storybook/react";
import { LocalError } from "./LocalError";

const meta: Meta<typeof LocalError> = {
  title: "Components/Common/LocalError",
  component: LocalError,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
  },
  argTypes: {
    message: {
      control: "text",
      description: "Error message to display",
    },
    onRetry: {
      description: "Callback fired when retry button is clicked",
    },
  },
};

export default meta;
type Story = StoryObj<typeof LocalError>;

// ─── Default ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default",
  args: {
    message: "데이터를 불러오는 데 실패했습니다.",
    onRetry: () => alert("다시 시도"),
  },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", width: "100%", minHeight: "400px", display: "flex", alignItems: "center" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── Custom Message ───────────────────────────────────────────

export const CustomMessage: Story = {
  name: "Custom Message",
  args: {
    message: "네트워크 연결을 확인하고 다시 시도해 주세요.",
    onRetry: () => alert("다시 시도"),
  },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", width: "100%", minHeight: "400px", display: "flex", alignItems: "center" }}>
        <Story />
      </div>
    ),
  ],
};

// ─── In Table Context ─────────────────────────────────────────

export const InTableContext: Story = {
  name: "In Table Context (Stock List)",
  render: () => (
    <div style={{ backgroundColor: "#131316", width: "1200px" }}>
      {/* 헤더 영역 시뮬레이션 */}
      <div style={{ padding: "16px", borderBottom: "1px solid #2F3037" }}>
        <span style={{ fontSize: "14px", color: "#9194A1" }}>순위 · 오늘 00:00 기준</span>
      </div>
      {/* LocalError */}
      <LocalError
        message="데이터를 불러오는 데 실패했습니다."
        onRetry={() => alert("다시 시도")}
      />
    </div>
  ),
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: {
    message: "데이터를 불러오는 데 실패했습니다.",
  },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", width: "100%", minHeight: "400px", display: "flex", alignItems: "center" }}>
        <Story />
      </div>
    ),
  ],
};