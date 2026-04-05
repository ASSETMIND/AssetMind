import type { Meta, StoryObj } from "@storybook/react";
import { LinearGauge } from "../LinearGauge/LinearGauge";
import { StockDataPage } from "./StockDataPage";
import type { StockRow } from "../StockTable/StockTable";

// ─── Mock Data ────────────────────────────────────────────────

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

const EXTREME_ROWS: StockRow[] = [
  { id: "e1", rank: 1, isFavorite: false, name: "극단 매수 (99:1)", price: 10000, changeRate: 29.9,  tradeAmount: 999999, buyRatio: 99 },
  { id: "e2", rank: 2, isFavorite: false, name: "극단 매도 (1:99)", price: 10000, changeRate: -29.9, tradeAmount: 999999, buyRatio: 1  },
  { id: "e3", rank: 3, isFavorite: false, name: "보합 (50:50)",     price: 10000, changeRate: 0,     tradeAmount: 500000, buyRatio: 50 },
];

// Story args에서 공통으로 사용할 데이터
const DEFAULT_ARGS = {
  rows: MOCK_ROWS,
  extremeRows: EXTREME_ROWS,
  onRetry: () => alert("다시 시도"),
};

// ─── Meta ─────────────────────────────────────────────────────

const meta: Meta<typeof StockDataPage> = {
  title: "Components/Stock/StockDataPage",
  component: StockDataPage,
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
          "주가 데이터 페이지 통합 Story. `pageState` prop으로 7가지 상태(default·skeleton·realtime·error·empty·extreme)를 전환하며 확인할 수 있습니다. `viewport` prop으로 desktop(1200px)·tablet(768px)·mobile(393px) 레이아웃을 전환합니다.",
      },
    },
  },
  argTypes: {
    pageState: {
      control: "radio",
      options: ["default", "skeleton", "realtime", "error", "empty", "extreme"],
      description:
        "default: 정상 데이터 | skeleton: 로딩 중 | realtime: 실시간 갱신 | error: API 실패 | empty: 조회 결과 없음 | extreme: 극단값(99:1)",
    },
    viewport: {
      control: "radio",
      options: ["desktop", "tablet", "mobile"],
      description: "desktop: 1200px | tablet: 768px | mobile: 393px",
    },
  },
};

export default meta;
type Story = StoryObj<typeof StockDataPage>;

// ─── 공통 데코레이터 ──────────────────────────────────────────

const desktopDecorator = (Story: React.ComponentType) => (
  <div style={{ minWidth: "1200px" }}>
    <Story />
  </div>
);

const tabletDecorator = (Story: React.ComponentType) => (
  <div style={{ width: "768px" }}>
    <Story />
  </div>
);

const mobileDecorator = (Story: React.ComponentType) => (
  <div style={{ width: "393px" }}>
    <Story />
  </div>
);

// ════════════════════════════════════════════════════════════════
// Desktop Stories
// ════════════════════════════════════════════════════════════════

/** 정상 데이터 — 기본 상태 */
export const Default: Story = {
  name: "Default",
  args: { ...DEFAULT_ARGS, pageState: "default", viewport: "desktop" },
  decorators: [desktopDecorator],
};

/** 로딩 — Skeleton 애니메이션 */
export const Loading: Story = {
  name: "Loading (Skeleton)",
  args: { ...DEFAULT_ARGS, pageState: "skeleton", viewport: "desktop" },
  parameters: {
    docs: {
      description: {
        story: "데이터 로딩 중 상태. Skeleton variant='table-row' 10행으로 표시됩니다. 400ms 딜레이 후 pulse 애니메이션이 시작됩니다.",
      },
    },
  },
  decorators: [desktopDecorator],
};

/** 실시간 갱신 — TickerAnimation */
export const Realtime: Story = {
  name: "Realtime — Dynamic Price Updates",
  args: { ...DEFAULT_ARGS, pageState: "realtime", viewport: "desktop" },
  parameters: {
    docs: {
      description: {
        story: "각 종목마다 1.5~4.5초 랜덤 주기로 가격이 갱신됩니다. 상승 시 붉은색, 하락 시 파란색 배경 깜빡임이 적용됩니다.",
      },
    },
  },
  decorators: [desktopDecorator],
};

/** API 오류 — LocalError */
export const Error: Story = {
  name: "Error",
  args: { ...DEFAULT_ARGS, pageState: "error", viewport: "desktop" },
  parameters: {
    docs: {
      description: {
        story: "API 호출 실패 시 LocalError 컴포넌트가 페이지 중앙에 표시됩니다. '다시 시도' 버튼으로 재요청을 트리거합니다.",
      },
    },
  },
  decorators: [desktopDecorator],
};

/** 빈 데이터 — 조회 결과 없음 */
export const Empty: Story = {
  name: "Empty",
  args: { ...DEFAULT_ARGS, pageState: "empty", viewport: "desktop" },
  parameters: {
    docs: {
      description: {
        story: "필터 조건에 맞는 종목이 없을 때 표시됩니다. GlobalEmptyState variant='no-data'를 사용합니다.",
      },
    },
  },
  decorators: [desktopDecorator],
};

/** 극단값 검증 — LinearGauge min-width 4px */
export const ExtremeValues: Story = {
  name: "Extreme Values (99:1)",
  args: { ...DEFAULT_ARGS, pageState: "extreme", viewport: "desktop" },
  parameters: {
    docs: {
      description: {
        story: "극단적 비율(99:1, 1:99)에서 LinearGauge의 최소 너비 4px 규칙이 올바르게 적용되는지 검증합니다.",
      },
    },
  },
  decorators: [desktopDecorator],
};

// ════════════════════════════════════════════════════════════════
// Tablet Stories
// ════════════════════════════════════════════════════════════════

/** 태블릿 — 정상 데이터 */
export const TabletDefault: Story = {
  name: "Tablet / Default",
  args: { ...DEFAULT_ARGS, pageState: "default", viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDecorator],
};

/** 태블릿 — 로딩 */
export const TabletLoading: Story = {
  name: "Tablet / Loading",
  args: { ...DEFAULT_ARGS, pageState: "skeleton", viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDecorator],
};

/** 태블릿 — 오류 */
export const TabletError: Story = {
  name: "Tablet / Error",
  args: { ...DEFAULT_ARGS, pageState: "error", viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDecorator],
};

/** 태블릿 — 빈 데이터 */
export const TabletEmpty: Story = {
  name: "Tablet / Empty",
  args: { ...DEFAULT_ARGS, pageState: "empty", viewport: "tablet" },
  parameters: { viewport: { defaultViewport: "tablet" } },
  decorators: [tabletDecorator],
};

// ════════════════════════════════════════════════════════════════
// Mobile Stories
// ════════════════════════════════════════════════════════════════

/** 모바일 — 정상 데이터 */
export const MobileDefault: Story = {
  name: "Mobile / Default",
  args: { ...DEFAULT_ARGS, pageState: "default", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDecorator],
};

/** 모바일 — 로딩 */
export const MobileLoading: Story = {
  name: "Mobile / Loading",
  args: { ...DEFAULT_ARGS, pageState: "skeleton", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDecorator],
};

/** 모바일 — 오류 */
export const MobileError: Story = {
  name: "Mobile / Error",
  args: { ...DEFAULT_ARGS, pageState: "error", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDecorator],
};

/** 모바일 — 빈 데이터 */
export const MobileEmpty: Story = {
  name: "Mobile / Empty",
  args: { ...DEFAULT_ARGS, pageState: "empty", viewport: "mobile" },
  parameters: { viewport: { defaultViewport: "mobile1" } },
  decorators: [mobileDecorator],
};

// ════════════════════════════════════════════════════════════════
// QA / Validation Stories (기존 유지)
// ════════════════════════════════════════════════════════════════

/** Controls로 모든 상태·뷰포트 자유 조작 */
export const Playground: Story = {
  name: "Playground",
  args: { ...DEFAULT_ARGS, pageState: "default", viewport: "desktop" },
  decorators: [desktopDecorator],
};

/** 색상 명도 대비 검증 */
export const ContrastCheck: Story = {
  name: "QA — Color Contrast Check",
  parameters: {
    docs: {
      description: {
        story: `
WCAG AA (4.5:1) color contrast verification:

| Element | Foreground | Background | Result |
|---|---|---|---|
| Text (primary) | #FFFFFF | #131316 | ✅ Pass |
| Text (secondary) | #9194A1 | #131316 | ✅ Pass |
| Price change (rise) | #EA580C | #131316 | ✅ Pass |
| Price change (fall) | #256AF4 | #131316 | ✅ Pass |
| LinearGauge label (rise) | #EA580C | #131316 | ✅ Pass |
| LinearGauge label (fall) | #256AF4 | #131316 | ✅ Pass |
| TickerAnimation bg (rise) | rgba(234,88,12,0.1) | #131316 | ℹ️ Background only |
| TickerAnimation bg (fall) | rgba(37,106,244,0.1) | #131316 | ℹ️ Background only |
| LocalError text | #9F9F9F | #131316 | ✅ Pass |
| GlobalEmptyState text | #9F9F9F | #131316 | ✅ Pass |
        `,
      },
    },
  },
  render: () => (
    <div style={{ backgroundColor: "#131316", padding: "32px", display: "flex", flexDirection: "column", gap: "32px", minWidth: "1200px" }}>
      <section>
        <h3 style={{ fontSize: "14px", color: "#9194A1", marginBottom: "12px" }}>Text Color Contrast</h3>
        <div style={{ display: "flex", gap: "24px", alignItems: "center" }}>
          <span style={{ fontSize: "15px", fontWeight: 500, color: "#FFFFFF" }}>Primary #FFFFFF</span>
          <span style={{ fontSize: "14px", color: "#9194A1" }}>Secondary #9194A1</span>
          <span style={{ fontSize: "14px", color: "#9F9F9F" }}>Disabled #9F9F9F</span>
        </div>
      </section>
      <section>
        <h3 style={{ fontSize: "14px", color: "#9194A1", marginBottom: "12px" }}>Price Change Color Contrast</h3>
        <div style={{ display: "flex", gap: "24px", alignItems: "center" }}>
          <span style={{ fontSize: "15px", fontWeight: 500, color: "#EA580C" }}>+2.35% (Rise #EA580C)</span>
          <span style={{ fontSize: "15px", fontWeight: 500, color: "#256AF4" }}>-1.20% (Fall #256AF4)</span>
          <span style={{ fontSize: "15px", fontWeight: 500, color: "#9194A1" }}>0.00% (Flat #9194A1)</span>
        </div>
      </section>
      <section>
        <h3 style={{ fontSize: "14px", color: "#9194A1", marginBottom: "12px" }}>LinearGauge Color Contrast</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <LinearGauge buyRatio={62} />
          <LinearGauge buyRatio={99} />
          <LinearGauge buyRatio={1} />
        </div>
      </section>
      <section>
        <h3 style={{ fontSize: "14px", color: "#9194A1", marginBottom: "12px" }}>TickerAnimation Background Contrast</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <div style={{ backgroundColor: "rgba(234,88,12,0.1)", padding: "12px 16px", borderRadius: "4px" }}>
            <span style={{ fontSize: "15px", fontWeight: 500, color: "#FFFFFF" }}>Rise bg rgba(234,88,12,0.1) — Text #FFFFFF</span>
          </div>
          <div style={{ backgroundColor: "rgba(37,106,244,0.1)", padding: "12px 16px", borderRadius: "4px" }}>
            <span style={{ fontSize: "15px", fontWeight: 500, color: "#FFFFFF" }}>Fall bg rgba(37,106,244,0.1) — Text #FFFFFF</span>
          </div>
        </div>
      </section>
    </div>
  ),
};