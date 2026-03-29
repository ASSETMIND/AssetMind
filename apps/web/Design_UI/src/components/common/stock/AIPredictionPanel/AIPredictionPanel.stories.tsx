import type { Meta, StoryObj } from "@storybook/react";
import { AIPredictionPanel } from "./AIPredictionPanel";
import type { AnalysisData } from "./PredictionAnalysisWidget";

// ─── Mock Data ────────────────────────────────────────────────

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

const mockForecastUp = [
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

const mockAnalysis: AnalysisData = {
  "기술적 지표": [
    { type: "warning",  text: "경고 또는 위험 신호가 있는 내용" },
    { type: "neutral",  text: "중립적이거나 추가 확인이 필요한 내용" },
    { type: "positive", text: "긍정적 신호가 있는 내용" },
    { type: "neutral",  text: "중립적이거나 추가 확인이 필요한 내용" },
    { type: "neutral",  text: "중립적이거나 추가 확인이 필요한 내용" },
  ],
  "시장 심리": [
    { type: "positive", text: "투자자 심리 지수 낙관 구간 진입" },
    { type: "neutral",  text: "외국인 순매수 흐름 지속 중" },
    { type: "warning",  text: "공매도 비율 단기 급등 감지" },
  ],
  "수급 동향": [
    { type: "neutral",  text: "기관 순매수 전환 신호 감지" },
    { type: "positive", text: "외국인 대규모 매수 유입" },
    { type: "warning",  text: "개인 투자자 과매도 구간 진입" },
    { type: "neutral",  text: "프로그램 매매 비중 중립" },
  ],
};

const defaultArgs = {
  historicalData: mockHistorical,
  forecastData: mockForecastUp,
  predictedPrice: 80000,
  priceDiff: 17000,
  changeRate: 26.98,
  baseDate: "2025년 03월 26일",
  upProbability: 72,
  downProbability: 28,
  analysisData: mockAnalysis,
};

// ─── Meta ─────────────────────────────────────────────────────

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
          "AI 가격 예측 패널 컴포넌트. 기간 탭(1주·1개월·3개월) 전환, SVG 기반 스파크라인 차트(과거 파란 실선 + 예측 초록 점선 + 그라데이션), AI 예측가, 방향성 확률 바, 분석 근거 탭 위젯을 포함한 통합 패널. `status` prop으로 skeleton·error·empty(휴장) variant, `viewport` prop으로 desktop·tablet(340px 고정) · mobile(345×657, 하단 MobileTabSwitcher 포함) 전환 가능.",
      },
    },
  },
  argTypes: {
    status: {
      control: "radio",
      options: ["default", "skeleton", "error", "empty"],
      description: "Panel display status",
    },
    viewport: {
      control: "radio",
      options: ["desktop", "tablet", "mobile"],
      description: "Layout viewport",
    },
    period: { control: "radio", options: ["1주", "1개월", "3개월"] },
    upProbability:   { control: { type: "range", min: 0, max: 100, step: 1 } },
    downProbability: { control: { type: "range", min: 0, max: 100, step: 1 } },
    predictedPrice:  { control: { type: "number" } },
    priceDiff:       { control: { type: "number" } },
    changeRate:      { control: { type: "number" } },
  },
};

export default meta;
type Story = StoryObj<typeof AIPredictionPanel>;

// ─── Stories ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default / Up Trend",
  args: { ...defaultArgs, status: "default", viewport: "desktop" },
};

export const Tablet: Story = {
  name: "Tablet",
  args: { ...defaultArgs, status: "default", viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#111113", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};

export const Mobile: Story = {
  name: "Mobile",
  args: { ...defaultArgs, status: "default", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#111113", padding: "0" }}>
        <Story />
      </div>
    ),
  ],
};

export const DownTrend: Story = {
  name: "Down Trend",
  args: { ...defaultArgs, status: "default", viewport: "desktop", forecastData: mockForecastDown, predictedPrice: 51000, priceDiff: -12000, changeRate: -19.05, upProbability: 25, downProbability: 75 },
};

export const EvenProbability: Story = {
  name: "Even Probability (50:50)",
  args: { ...defaultArgs, status: "default", viewport: "desktop", predictedPrice: 65000, priceDiff: 2000, changeRate: 3.17, upProbability: 50, downProbability: 50 },
};

export const ExtremeProbability: Story = {
  name: "Extreme Probability (99:1)",
  args: { ...defaultArgs, status: "default", viewport: "desktop", predictedPrice: 100000, priceDiff: 37000, changeRate: 58.73, upProbability: 99, downProbability: 1 },
};

export const Skeleton: Story = {
  name: "Skeleton",
  args: { ...defaultArgs, status: "skeleton", viewport: "desktop" },
};

export const ErrorState: Story = {
  name: "Error",
  args: { status: "error", viewport: "desktop", onRetry: () => alert("Retry") },
};

export const Empty: Story = {
  name: "Empty (Market Closed)",
  args: { ...defaultArgs, status: "empty", viewport: "desktop" },
};

export const Playground: Story = {
  name: "Playground",
  args: { ...defaultArgs, status: "default", viewport: "desktop" },
};