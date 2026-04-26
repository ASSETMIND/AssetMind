import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { CategoryModal } from "./CategoryModal";

// ─── Mock Data ────────────────────────────────────────────────

const MOCK_STOCK_LIST = [
  { id: "s1", name: "종목명", chartData: [{ value: 100 }, { value: 98 }, { value: 95 }, { value: 93 }, { value: 91 }], currentPrice: "0,000원", changeRate: "0.00%", isRise: null },
  { id: "s2", name: "종목명", chartData: [{ value: 100 }, { value: 99 }, { value: 97 }, { value: 96 }, { value: 94 }], currentPrice: "0,000원", changeRate: "0.00%", isRise: null },
  { id: "s3", name: "종목명", chartData: [{ value: 100 }, { value: 102 }, { value: 104 }, { value: 103 }, { value: 105 }], currentPrice: "0,000원", changeRate: "+0.00%", isRise: true },
  { id: "s4", name: "종목명", chartData: [{ value: 100 }, { value: 99 }, { value: 97 }, { value: 95 }, { value: 93 }], currentPrice: "0,000원", changeRate: "-0.00%", isRise: false },
];

const MOCK_ETF_LIST = [
  { id: "e1", name: "종목명", currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "e2", name: "종목명", currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "e3", name: "종목명", currentPrice: "0,000원", changeRate: "+0.00%", isRise: true  },
  { id: "e4", name: "종목명", currentPrice: "0,000원", changeRate: "-0.00%", isRise: false },
  { id: "e5", name: "종목명", currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "e6", name: "종목명", currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "e7", name: "종목명", currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "e8", name: "종목명", currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
];

const MOCK_RETURN_CARDS = [
  { label: "어제보다",    value: "-0.00%", isRise: false },
  { label: "1개월 전보다", value: "+0.00%", isRise: true  },
  { label: "3개월 전보다", value: "+0.00%", isRise: true  },
  { label: "1년 전보다",  value: "-0.00%", isRise: false },
];

const DEFAULT_ARGS = {
  categoryName: "카테고리명",
  categorySubtitle: "0개 회사 · 0개 ETF",
  returnCards: MOCK_RETURN_CARDS,
  returnBaseLabel: "기준 : 전일 종가",
  stockList: MOCK_STOCK_LIST,
  etfList: MOCK_ETF_LIST,
};

// ─── Meta ─────────────────────────────────────────────────────

const meta: Meta<typeof CategoryModal> = {
  title: "Components/Stock/CategoryModal",
  component: CategoryModal,
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
          "종목정보 탭 주요 사업 클릭 시 표시되는 카테고리 모달. 600×766 크기, 수익률 4종 카드 + 종목 리스트(미니 차트) + 그 외 회사 태그 + ETF 리스트로 구성됩니다.",
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof CategoryModal>;

// ─── 인터랙티브 데모 래퍼 ─────────────────────────────────────

const ModalDemo = (args: typeof DEFAULT_ARGS) => {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ backgroundColor: "#131316", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <button
        onClick={() => setOpen(true)}
        style={{ padding: "10px 24px", backgroundColor: "#6D4AE6", border: "none", borderRadius: "8px", color: "#FFFFFF", fontSize: "14px", cursor: "pointer" }}
      >
        모달 열기
      </button>
      <CategoryModal {...args} isOpen={open} onClose={() => setOpen(false)} />
    </div>
  );
};

// ─── Stories ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default",
  render: () => <ModalDemo {...DEFAULT_ARGS} />,
};

export const Open: Story = {
  name: "Open — Always Visible",
  render: () => (
    <div style={{ backgroundColor: "#131316", minHeight: "100vh", position: "relative" }}>
      <CategoryModal
        {...DEFAULT_ARGS}
        isOpen={true}
        onClose={() => {}}
      />
    </div>
  ),
  parameters: {
    docs: {
      description: { story: "Storybook에서 모달 UI를 항상 열린 상태로 확인할 때 사용합니다." },
    },
  },
};

export const Playground: Story = {
  name: "Playground",
  render: () => <ModalDemo {...DEFAULT_ARGS} />,
};