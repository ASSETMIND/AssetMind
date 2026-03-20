import type { Meta, StoryObj } from "@storybook/react";
import { useEffect, useState } from "react";
import { PriceChangeToken } from "./PriceChangeToken";

const meta: Meta<typeof PriceChangeToken> = {
  title: "Components/Common/PriceChangeToken",
  component: PriceChangeToken,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
  },
  argTypes: {
    value: {
      control: { type: "number", step: 0.01 },
      description: "Price change rate (positive: rise, negative: fall, 0: flat)",
    },
    showSign: {
      control: "boolean",
      description: "Whether to show +/- sign prefix",
    },
    animated: {
      control: "boolean",
      description: "Enable slot-machine animation on value change",
    },
  },
};

export default meta;
type Story = StoryObj<typeof PriceChangeToken>;

// ─── Individual states ────────────────────────────────────────

export const Rise: Story = {
  name: "Rise",
  args: { value: 2.35 },
};

export const Fall: Story = {
  name: "Fall",
  args: { value: -1.2 },
};

export const Flat: Story = {
  name: "Flat",
  args: { value: 0 },
};

// ─── All states ───────────────────────────────────────────────

export const AllStates: Story = {
  name: "All States",
  render: () => (
    <div className="flex flex-col gap-4 p-4 bg-background-primary">
      <div className="flex gap-6 items-center">
        <PriceChangeToken value={2.35} />
        <PriceChangeToken value={-1.2} />
        <PriceChangeToken value={0} />
      </div>
      <div className="flex gap-6 items-center">
        <PriceChangeToken value={2.35} showSign={false} />
        <PriceChangeToken value={-1.2} showSign={false} />
      </div>
    </div>
  ),
};

// ─── Slot machine animation ───────────────────────────────────

export const SlotMachineAnimation: Story = {
  name: "Slot Machine Animation",
  render: () => {
    const mockValues = [2.35, -1.2, 0.45, -3.1, 1.08, 0, -0.55, 4.2];
    const [index, setIndex] = useState(0);

    useEffect(() => {
      const interval = setInterval(() => {
        setIndex((prev) => (prev + 1) % mockValues.length);
      }, 1200);
      return () => clearInterval(interval);
    }, []);

    return (
      <div className="flex flex-col gap-3 p-4 bg-background-primary">
        <p className="text-text-secondary text-b2">Updates every 1.2s</p>
        <PriceChangeToken value={mockValues[index]} animated />
      </div>
    );
  },
};

// ─── Contrast check ───────────────────────────────────────────

export const ContrastCheck: Story = {
  name: "Contrast Check",
  render: () => (
    <div className="flex gap-6 p-6 bg-background-primary rounded-lg">
      <PriceChangeToken value={2.35} />
      <PriceChangeToken value={-1.2} />
      <PriceChangeToken value={0} />
    </div>
  ),
};

// ─── Playground ───────────────────────────────────────────────

export const Playground: Story = {
  name: "Playground",
  args: {
    value: 2.35,
    showSign: true,
    animated: false,
  },
};