import type { Meta, StoryObj } from "@storybook/react";
import { Skeleton } from "./Skeleton";

const meta: Meta<typeof Skeleton> = {
  title: "Components/Common/Skeleton",
  component: Skeleton,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["chart", "table-row", "card", "orderbook", "spinner"],
      description:
        "chart: wide block / table-row: avatar + blocks / card: AI panel / orderbook: bid-ask columns / spinner: full-screen loader",
    },
    rows: {
      control: { type: "number", min: 1, max: 20 },
      description: "Number of repeated rows (table-row, card, orderbook variants)",
    },
  },
};

export default meta;
type Story = StoryObj<typeof Skeleton>;

// ─── Chart ────────────────────────────────────────────────────

export const Chart: Story = {
  name: "Chart Area",
  args: { variant: "chart" },
  decorators: [
    (Story) => (
      <div className="w-full bg-background-primary p-4">
        <Story />
      </div>
    ),
  ],
};

// ─── Table Row ────────────────────────────────────────────────

export const TableRow: Story = {
  name: "Table Row (Stock List)",
  args: { variant: "table-row", rows: 10 },
  decorators: [
    (Story) => (
      <div className="w-full bg-background-primary">
        <Story />
      </div>
    ),
  ],
};

// ─── Card ─────────────────────────────────────────────────────

export const Card: Story = {
  name: "Card (AI Panel / Stock Info)",
  args: { variant: "card", rows: 5 },
  decorators: [
    (Story) => (
      <div className="w-[320px] bg-background-primary">
        <Story />
      </div>
    ),
  ],
};

// ─── Orderbook ────────────────────────────────────────────────

export const Orderbook: Story = {
  name: "Orderbook (Bid-Ask Table)",
  args: { variant: "orderbook", rows: 8 },
  decorators: [
    (Story) => (
      <div className="w-[320px] bg-background-primary p-4">
        <Story />
      </div>
    ),
  ],
};

// ─── Spinner ──────────────────────────────────────────────────

export const Spinner: Story = {
  name: "Spinner (Tab Transition)",
  args: { variant: "spinner" },
  decorators: [
    (Story) => (
      <div className="w-full bg-background-primary">
        <Story />
      </div>
    ),
  ],
};

// ─── Stock List Page 전체 조합 ────────────────────────────────

export const StockListPageFull: Story = {
  name: "Stock List Page — Full Loading State",
  render: () => (
    <div className="w-full bg-background-primary flex flex-col gap-0">
      <Skeleton variant="chart" className="p-4" />
      <Skeleton variant="table-row" rows={10} />
    </div>
  ),
};

// ─── Stock Detail Page 전체 조합 ──────────────────────────────

export const StockDetailPageFull: Story = {
  name: "Stock Detail Page — Full Loading State",
  render: () => (
    <div className="w-full bg-background-primary flex gap-0">
      <div className="flex-1">
        <Skeleton variant="orderbook" rows={8} className="p-4" />
      </div>
      <div className="w-[320px] border-l border-border-divider">
        <Skeleton variant="card" rows={5} />
      </div>
    </div>
  ),
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: {
    variant: "table-row",
    rows: 5,
  },
};