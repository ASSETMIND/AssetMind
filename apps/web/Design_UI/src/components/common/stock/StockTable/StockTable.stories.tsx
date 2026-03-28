import type { Meta, StoryObj } from "@storybook/react";
import { StockTable } from "./StockTable";
import type { StockRow } from "./StockTable";

const MOCK_ROWS: StockRow[] = [
  { id: "1",  rank: 1,  isFavorite: true,  name: "삼성전자",         price: 75000,  changeRate: 2.35,  tradeAmount: 980000, buyRatio: 62 },
  { id: "2",  rank: 2,  isFavorite: false, name: "SK하이닉스",       price: 182000, changeRate: -1.2,  tradeAmount: 720000, buyRatio: 38 },
  { id: "3",  rank: 3,  isFavorite: false, name: "LG에너지솔루션",   price: 410000, changeRate: 0.45,  tradeAmount: 540000, buyRatio: 51 },
  { id: "4",  rank: 4,  isFavorite: false, name: "현대차",           price: 231000, changeRate: -3.1,  tradeAmount: 430000, buyRatio: 29 },
  { id: "5",  rank: 5,  isFavorite: true,  name: "NAVER",           price: 198000, changeRate: 1.08,  tradeAmount: 380000, buyRatio: 70 },
  { id: "6",  rank: 6,  isFavorite: false, name: "카카오",           price: 54000,  changeRate: 0,     tradeAmount: 310000, buyRatio: 50 },
  { id: "7",  rank: 7,  isFavorite: false, name: "포스코홀딩스",     price: 389000, changeRate: -0.55, tradeAmount: 270000, buyRatio: 44 },
  { id: "8",  rank: 8,  isFavorite: false, name: "삼성바이오로직스", price: 875000, changeRate: 4.2,   tradeAmount: 250000, buyRatio: 78 },
  { id: "9",  rank: 9,  isFavorite: false, name: "셀트리온",         price: 167000, changeRate: -2.0,  tradeAmount: 210000, buyRatio: 33 },
  { id: "10", rank: 10, isFavorite: false, name: "기아",             price: 95000,  changeRate: 1.5,   tradeAmount: 190000, buyRatio: 60 },
];

const meta: Meta<typeof StockTable> = {
  title: "Components/Stock/StockTable",
  component: StockTable,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "주가 데이터 테이블. `viewport` prop으로 desktop(1200px) · tablet(768px) · mobile(393px) 레이아웃 전환. 모든 뷰포트에서 폰트는 15px medium으로 통일. 모바일에서는 거래대금·거래비율 컬럼 생략, 태블릿에서는 거래비율 컬럼 생략.",
      },
    },
  },
  argTypes: {
    viewport: {
      control: "radio",
      options: ["desktop", "tablet", "mobile"],
      description: "Layout viewport",
    },
  },
};

export default meta;
type Story = StoryObj<typeof StockTable>;

export const Desktop: Story = {
  name: "Desktop",
  args: { rows: MOCK_ROWS, viewport: "desktop" },
  parameters: { viewport: { defaultViewport: "desktop" } },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "16px", minWidth: "1200px" }}>
        <Story />
      </div>
    ),
  ],
};

export const Tablet: Story = {
  name: "Tablet",
  args: { rows: MOCK_ROWS, viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};

export const Mobile: Story = {
  name: "Mobile",
  args: { rows: MOCK_ROWS, viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};

export const Playground: Story = {
  name: "Playground",
  args: { rows: MOCK_ROWS, viewport: "desktop" },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "16px" }}>
        <Story />
      </div>
    ),
  ],
};