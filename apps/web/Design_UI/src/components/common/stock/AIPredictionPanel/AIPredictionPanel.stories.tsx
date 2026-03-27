import type { Meta, StoryObj } from "@storybook/react";
import { AIPredictionPanel } from "./AIPredictionPanel";

const mockHistorical = [
  { time: "2025-03-17", value: 68000 },
  { time: "2025-03-18", value: 71000 },
  { time: "2025-03-19", value: 75000 },
  { time: "2025-03-20", value: 69000 },
  { time: "2025-03-21", value: 72000 },
  { time: "2025-03-22", value: 70000 },
  { time: "2025-03-23", value: 67000 },
  { time: "2025-03-24", value: 65000 },
  { time: "2025-03-25", value: 63000 },
];

const mockForecast = [
  { time: "2025-03-25", value: 63000 },
  { time: "2025-03-26", value: 66000 },
  { time: "2025-03-27", value: 70000 },
  { time: "2025-03-28", value: 75000 },
  { time: "2025-03-29", value: 80000 },
];

const mockForecastDown = [
  { time: "2025-03-25", value: 63000 },
  { time: "2025-03-26", value: 60000 },
  { time: "2025-03-27", value: 57000 },
  { time: "2025-03-28", value: 54000 },
  { time: "2025-03-29", value: 51000 },
];

/* ── Meta ── */
const meta: Meta<typeof AIPredictionPanel> = {
  title: "Components/Stock/AIPredictionPanel",
  component: AIPredictionPanel,
  tags: ["autodocs"],
  parameters: {
    layout: "centered",
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#111113" }],
    },
    docs: {
      description: {
        component:
          "AI 가격 예측 패널 컴포넌트. 기간 탭(1주·1개월·3개월) 전환, SVG 기반 스파크라인 차트, AI 예측가 및 방향성 확률 바를 포함한 통합 패널. 매수하기 버튼으로 외부 주문 액션 연결 가능.",
      },
    },
  },
  argTypes: {
    period: {
      control: "radio",
      options: ["1주", "1개월", "3개월"],
    },
    upProbability: { control: { type: "range", min: 0, max: 100, step: 1 } },
    downProbability: { control: { type: "range", min: 0, max: 100, step: 1 } },
    predictedPrice: { control: { type: "number" } },
    priceDiff: { control: { type: "number" } },
    changeRate: { control: { type: "number" } },
  },
};

export default meta;
type Story = StoryObj<typeof AIPredictionPanel>;

/* ── Stories ── */
export const UpTrend: Story = {
  name: "Rising Predictions",
  args: {
    historicalData: mockHistorical,
    forecastData: mockForecast,
    predictedPrice: 80000,
    priceDiff: 17000,
    changeRate: 26.98,
    baseDate: "2025년 03월 26일",
    upProbability: 72,
    downProbability: 28,
  },
};

export const DownTrend: Story = {
  name: "Falling Predictions",
  args: {
    historicalData: mockHistorical,
    forecastData: mockForecastDown,
    predictedPrice: 51000,
    priceDiff: -12000,
    changeRate: -19.05,
    baseDate: "2025년 03월 26일",
    upProbability: 25,
    downProbability: 75,
  },
};

export const EvenProbability: Story = {
  name: "Even Predictions",
  args: {
    historicalData: mockHistorical,
    forecastData: mockForecast,
    predictedPrice: 65000,
    priceDiff: 2000,
    changeRate: 3.17,
    baseDate: "2025년 03월 26일",
    upProbability: 50,
    downProbability: 50,
  },
};

export const ExtremeProbability: Story = {
  name: "Extreme Predictions",
  args: {
    historicalData: mockHistorical,
    forecastData: mockForecast,
    predictedPrice: 100000,
    priceDiff: 37000,
    changeRate: 58.73,
    baseDate: "2025년 03월 26일",
    upProbability: 99,
    downProbability: 1,
  },
};

export const Playground: Story = {
  name: "Playground",
  args: {
    historicalData: mockHistorical,
    forecastData: mockForecast,
    predictedPrice: 100000,
    priceDiff: 0,
    changeRate: 0.0,
    baseDate: "0000년 00월 00일",
    upProbability: 60,
    downProbability: 40,
  },
};