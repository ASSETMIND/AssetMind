import type { Meta, StoryObj } from "@storybook/react";
import { StockInfoPanel } from "./StockInfoPanel";
import type { DonutSlice } from "../DonutChart/DonutChart";
import type { BusinessItem } from "./StockInfoPanel";

// ─── Mock Data ────────────────────────────────────────────────

const MOCK_COMPANY = {
  name: "삼성전자",
  market: "국내",
  ticker: "005930",
  exchange: "코스피",
  homepageUrl: "https://www.samsung.com/sec",
  source: "",
  description:
    "동사는 1969년 설립되어 수원시 영통구에 본사를 두고 있으며, 3개의 생산기지와 2개의 연구개발법인, 다수의 해외 판매법인을 운영하는 글로벌 전자 기업입니다.",
  marketCap: "400조 8000억 원",
  enterpriseValue: "380조 1000억 원",
  companyName: "Samsung Electronics Co., Ltd.",
  ceo: "한종희, 경계현",
  listingDate: "1975년 06월 11일",
  listingDateSub: "1975년 06월 11일 기준",
  shares: "5,969,782,550주",
  sharesSub: "2026년 04월 15일 기준",
};

const MOCK_DONUT_SLICES: DonutSlice[] = [
  { label: "TV, 모니터, 냉장고, 세탁기, 에어컨, 스마트폰 등", value: 45.32, color: "#4FA3B8" },
  { label: "스마트폰용 OLED패널 등",                          value: 28.17, color: "#8A6BBE" },
  { label: "범례 3",                                          value: 16.45, color: "#C9A24D" },
  { label: "범례 4",                                          value: 10.06, color: "#73B959" },
];

// CategoryModal에 전달할 공통 Mock 데이터
const MOCK_MODAL_STOCK_LIST = [
  { id: "s1", name: "종목명", chartData: [{ value: 100 }, { value: 98 }, { value: 95 }, { value: 93 }, { value: 91 }], currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "s2", name: "종목명", chartData: [{ value: 100 }, { value: 99 }, { value: 97 }, { value: 96 }, { value: 94 }], currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "s3", name: "종목명", chartData: [{ value: 100 }, { value: 102 }, { value: 104 }, { value: 103 }, { value: 105 }], currentPrice: "0,000원", changeRate: "+0.00%", isRise: true  },
  { id: "s4", name: "종목명", chartData: [{ value: 100 }, { value: 99 }, { value: 97 }, { value: 95 }, { value: 93 }], currentPrice: "0,000원", changeRate: "-0.00%", isRise: false },
];

const MOCK_MODAL_ETF_LIST = [
  { id: "e1", name: "종목명", currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "e2", name: "종목명", currentPrice: "0,000원", changeRate: "0.00%",  isRise: null  },
  { id: "e3", name: "종목명", currentPrice: "0,000원", changeRate: "+0.00%", isRise: true  },
  { id: "e4", name: "종목명", currentPrice: "0,000원", changeRate: "-0.00%", isRise: false },
];

const MOCK_RETURN_CARDS = [
  { label: "어제보다",    value: "-0.00%", isRise: false },
  { label: "1개월 전보다", value: "+0.00%", isRise: true  },
  { label: "3개월 전보다", value: "+0.00%", isRise: true  },
  { label: "1년 전보다",  value: "-0.00%", isRise: false },
];

const MOCK_MODAL_PROPS = {
  categoryName: "카테고리명",
  categorySubtitle: "0개 회사 · 0개 ETF",
  returnCards: MOCK_RETURN_CARDS,
  returnBaseLabel: "기준 : 전일 종가",
  stockList: MOCK_MODAL_STOCK_LIST,
  etfList: MOCK_MODAL_ETF_LIST,
};

const MOCK_MAIN_BUSINESSES: BusinessItem[] = [
  { id: "b1", name: "사업명 1", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 1" } },
  { id: "b2", name: "사업명 2", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 2" } },
  { id: "b3", name: "사업명 3", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 3" } },
  { id: "b4", name: "사업명 4", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 4" } },
  { id: "b5", name: "사업명 5", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 5" } },
  { id: "b6", name: "사업명 6", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 6" } },
];

const MOCK_OTHER_BUSINESSES: BusinessItem[] = [
  { id: "o1", name: "사업명 1", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 1" } },
  { id: "o2", name: "사업명 2", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 2" } },
  { id: "o3", name: "사업명 3", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 3" } },
  { id: "o4", name: "사업명 4", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 4" } },
  { id: "o5", name: "사업명 5", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 5" } },
  { id: "o6", name: "사업명 6", marketCap: "0위", modalProps: { ...MOCK_MODAL_PROPS, categoryName: "사업명 6" } },
];

const DEFAULT_ARGS = {
  company: MOCK_COMPANY,
  donutSlices: MOCK_DONUT_SLICES,
  donutBaseDate: "2025년 12월 기준",
  donutNote: "마이너스 매출비중 : 계열사간 내부거래 등에 따른 조정",
  mainBusinesses: MOCK_MAIN_BUSINESSES,
  otherBusinesses: MOCK_OTHER_BUSINESSES,
  onRetry: () => alert("Retry"),
};

// ─── Meta ─────────────────────────────────────────────────────

const meta: Meta<typeof StockInfoPanel> = {
  title: "Components/Stock/StockInfoPanel",
  component: StockInfoPanel,
  tags: ["autodocs"],
  parameters: {
    backgrounds: {
      default: "dark",
      values: [{ name: "dark", value: "#131316" }],
    },
    layout: "padded",
    docs: {
      description: {
        component:
          "종목정보 탭 패널. 좌측 탭(스크롤 책갈피)과 우측 콘텐츠(기업 기본 정보·매출산업 구성·주요 사업)로 구성됩니다. 1036×820 고정 크기, 내부 스크롤.",
      },
    },
  },
  argTypes: {
    status: {
      control: "radio",
      options: ["default", "skeleton", "error"],
      description: "default: 정상 | skeleton: 로딩 중 | error: API 실패",
    },
  },
};

export default meta;
type Story = StoryObj<typeof StockInfoPanel>;

// ─── Stories ──────────────────────────────────────────────────

export const Default: Story = {
  name: "Default",
  args: { ...DEFAULT_ARGS, status: "default" },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}>
        <Story />
      </div>
    ),
  ],
};

export const Skeleton: Story = {
  name: "Skeleton",
  args: { status: "skeleton" },
  parameters: {
    docs: {
      description: { story: "API 호출 중 Skeleton 애니메이션 표시 상태입니다." },
    },
  },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}>
        <Story />
      </div>
    ),
  ],
};

export const Error: Story = {
  name: "Error",
  args: { status: "error", onRetry: () => alert("Retry") },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}>
        <Story />
      </div>
    ),
  ],
};

export const Playground: Story = {
  name: "Playground",
  args: { ...DEFAULT_ARGS, status: "default" },
  decorators: [
    (Story) => (
      <div style={{ backgroundColor: "#131316", padding: "24px", display: "inline-block" }}>
        <Story />
      </div>
    ),
  ],
};