import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { Tab } from "./Tab";

const meta: Meta<typeof Tab> = {
  title: "Components/Common/Tab",
  component: Tab,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
  },
  argTypes: {
    items: {
      description: "Array of tab items ({ label: string, value: string })",
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
type Story = StoryObj<typeof Tab>;

// ─── Stock list page — market filter ─────────────────────────

export const MarketFilter: Story = {
  name: "Market Filter (Stock List Page)",
  args: {
    items: [
      { label: "전체", value: "all" },
      { label: "국내", value: "domestic" },
      { label: "해외", value: "overseas" },
    ],
    defaultValue: "all",
  },
};

// ─── Stock detail page — chart period filter ──────────────────

export const ChartPeriodFilter: Story = {
  name: "Chart Period Filter (Stock Detail Page)",
  args: {
    items: [
      { label: "1분", value: "1m" },
      { label: "일", value: "1d" },
      { label: "주", value: "1w" },
      { label: "월", value: "1mo" },
      { label: "년", value: "1y" },
    ],
    defaultValue: "1d",
  },
};

// ─── Controlled ───────────────────────────────────────────────

export const Controlled: Story = {
  name: "Controlled",
  render: () => {
    const [active, setActive] = useState("domestic");
    return (
      <div className="flex flex-col gap-4">
        <Tab
          items={[
            { label: "전체", value: "all" },
            { label: "국내", value: "domestic" },
            { label: "해외", value: "overseas" },
          ]}
          value={active}
          onChange={setActive}
        />
        <p className="text-text-secondary text-b2">Selected: {active}</p>
      </div>
    );
  },
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: {
    items: [
      { label: "전체", value: "all" },
      { label: "국내", value: "domestic" },
      { label: "해외", value: "overseas" },
    ],
    defaultValue: "all",
  },
};