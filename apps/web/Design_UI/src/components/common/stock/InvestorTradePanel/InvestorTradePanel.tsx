import React, { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  LineSeries,
  type IChartApi,
  type LineData,
} from "lightweight-charts";

// ─── Types ────────────────────────────────────────────────────

export type TradePanelStatus = "default" | "skeleton" | "error";
export type TrendPeriod = "daily" | "weekly";
export type InvestorType = "program" | "credit" | "lending" | "short" | "cfd";

export interface TraderRankItem {
  rank: number;
  name: string;
  quantity: number;
}

export interface TrendDataPoint {
  time: string;
  individual: number;
  foreign: number;
  institution: number;
}

export interface TrendTableRow {
  date: string;
  closePrice: number;
  changeRate: number;
  changeAmount: number;
  individualNet: number;
  foreignNet: number;
  foreignRatio: number;
  institutionNet: number;
}

export interface ProgramTradeRow {
  date: string;
  netBuyChange: number;
  netBuy: number;
  buy: number;
  sell: number;
  nonArbitrageNet: number;
}

export interface CreditTradeRow {
  date: string;
  type: "융자" | "대주";
  changeQty: number;
  newQty: number;
  repayQty: number;
  balanceQty: number;
  balanceRate: number;
}

export interface LendingTradeRow {
  date: string;
  changeQty: number;
  newQty: number;
  repayQty: number;
  balanceQty: number;
}

export interface ShortTradeRow {
  date: string;
  tradeAmountRatio: number;
  shortQty: number;
  shortAmount: number;
  shortAvgPrice: number;
  tradeAmount: number;
}

export interface CfdTradeRow {
  date: string;
  newBuyQty: number;
  repayBuyQty: number;
  balanceBuyQty: number;
  buyBalanceRate: number;
  newSellQty: number;
  repaySellQty: number;
  balanceSellQty: number;
  sellBalanceRate: number;
}

export interface InvestorTradePanelProps {
  status?: TradePanelStatus;
  // 거래원 매매 상위
  buyList?: TraderRankItem[];
  sellList?: TraderRankItem[];
  rankBaseDateTime?: string;
  // 투자자별 매매 동향
  trendData?: TrendDataPoint[];
  trendBaseDateTime?: string;
  tableData?: TrendTableRow[];
  programData?: ProgramTradeRow[];
  creditData?: CreditTradeRow[];
  lendingData?: LendingTradeRow[];
  shortData?: ShortTradeRow[];
  cfdData?: CfdTradeRow[];
  onRetry?: () => void;
  onViewNetBuy?: () => void;
  // 패널 크기 (뷰포트별 override)
  panelWidth?: number;
  panelHeight?: number;
}

// ─── 색상 ─────────────────────────────────────────────────────

const RISE = "#EA580C";
const FALL = "#256AF4";
const IND_COLOR = "#C9A24D";
const FOR_COLOR = "#4FA3B8";
const INST_COLOR = "#8A6BBE";
const TABLE_BG1 = "#21242C";
const TABLE_BG2 = "transparent";

// ─── Helpers ──────────────────────────────────────────────────

const fmt = (v: number) => v.toLocaleString("ko-KR");
const fmtRate = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const fmtSigned = (v: number) => `${v >= 0 ? "+" : ""}${fmt(v)}`;
const signColor = (v: number) => v > 0 ? RISE : v < 0 ? FALL : "#9194A1";

// ─── Skeleton ─────────────────────────────────────────────────

const SkeletonBox = ({ w, h = 14 }: { w: number | string; h?: number }) => (
  <div
    className="animate-[skeleton-pulse_700ms_ease-out_400ms_infinite]"
    style={{ width: w, height: `${h}px`, borderRadius: "4px", backgroundColor: "#21242C", flexShrink: 0 }}
  />
);

const PanelSkeleton = () => (
  <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
    {Array.from({ length: 5 }).map((_, i) => (
      <div key={i} style={{ display: "flex", gap: "12px", alignItems: "center" }}>
        <SkeletonBox w={12} />
        <SkeletonBox w={80} />
        <SkeletonBox w="100%" h={22} />
      </div>
    ))}
  </div>
);

const ChartSkeleton = () => (
  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
    <SkeletonBox w="100%" h={243} />
    {Array.from({ length: 5 }).map((_, i) => <SkeletonBox key={i} w="100%" h={28} />)}
  </div>
);

// ─── Error ────────────────────────────────────────────────────

const ErrorBlock = ({ onRetry }: { onRetry?: () => void }) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "200px", gap: "16px" }}>
    <svg width="30" height="28" viewBox="0 0 30 28" fill="none">
      <path d="M16.3261 0.724424C15.8071 -0.241475 14.1932 -0.241475 13.6742 0.724424L0.174404 25.8319C0.0533393 26.057 -0.0065451 26.3091 0.00056714 26.5637C0.00767938 26.8183 0.0815466 27.0668 0.214994 27.285C0.348442 27.5032 0.536934 27.6837 0.762161 27.809C0.987389 27.9343 1.2417 28.0001 1.50038 28H28.4999C28.7586 28.0005 29.013 27.935 29.2383 27.8099C29.4636 27.6848 29.6522 27.5044 29.7856 27.2862C29.919 27.0679 29.9927 26.8194 29.9995 26.5648C30.0063 26.3102 29.946 26.0582 29.8244 25.8334L16.3261 0.724424ZM16.5001 23.5693H13.5002V20.6154H16.5001V23.5693ZM13.5002 17.6616V10.2771H16.5001L16.5016 17.6616H13.5002Z" fill="#6B7280" />
    </svg>
    <p style={{ fontSize: "14px", color: "#9F9F9F", textAlign: "center", margin: 0 }}>
      데이터를 불러오지 못했습니다.<br />잠시 후 다시 시도해 주세요.
    </p>
    <button
      onClick={onRetry}
      style={{ width: "100px", height: "38px", backgroundColor: "#6D4AE6", border: "none", borderRadius: "8px", cursor: "pointer", fontSize: "14px", fontWeight: 500, color: "#FFFFFF" }}
    >
      다시 시도
    </button>
  </div>
);

// ─── 드롭다운 ─────────────────────────────────────────────────

const Dropdown = ({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { label: string; value: string }[];
  onChange: (v: string) => void;
}) => {
  const [open, setOpen] = useState(false);
  const label = options.find((o) => o.value === value)?.label ?? value;
  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "inline-flex", alignItems: "center", gap: "4px",
          padding: "4px 10px", backgroundColor: "#2C2C30",
          border: "none", borderRadius: "6px", cursor: "pointer",
          fontSize: "12px", fontWeight: 400, color: "#FFFFFF",
        }}
      >
        {label}
        <span style={{ fontSize: "10px", color: "#9194A1" }}>▾</span>
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, zIndex: 10,
          backgroundColor: "#21242C", border: "1px solid #2F3037",
          borderRadius: "8px", overflow: "hidden", minWidth: "130px",
        }}>
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false); }}
              style={{
                display: "block", width: "100%", padding: "8px 14px",
                backgroundColor: opt.value === value ? "#2C2C30" : "transparent",
                border: "none", cursor: "pointer",
                fontSize: "12px", fontWeight: 400, color: "#FFFFFF", textAlign: "left",
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── 거래원 매매 상위 ─────────────────────────────────────────
// 매수: 왼쪽 정렬 (순위 | 이름 | 바+수량)
// 매도: 오른쪽 정렬 (바+수량 | 이름 | 순위) — 시안 기준

const RankRow = ({
  item,
  maxQty,
  side,
}: {
  item: TraderRankItem;
  maxQty: number;
  side: "buy" | "sell";
}) => {
  const barPct = maxQty > 0 ? Math.round((item.quantity / maxQty) * 100) : 0;
  const color = side === "buy" ? RISE : FALL;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
      }}
    >
      {/* 순위 */}
      <span style={{
        fontSize: "14px", fontWeight: 400, color: "#9194A1",
        width: "16px", flexShrink: 0, textAlign: "center",
      }}>
        {item.rank}
      </span>

      {/* 거래원명 */}
      <span style={{
        fontSize: "14px", fontWeight: 400, color: "#FFFFFF",
        width: "68px", flexShrink: 0, whiteSpace: "nowrap",
        overflow: "hidden", textOverflow: "ellipsis",
        textAlign: "left",
      }}>
        {item.name}
      </span>

      {/* 바 + 수량 */}
      <div style={{
        flex: 1, position: "relative", height: "20px",
        display: "flex", alignItems: "center",
        borderRadius: "3px", overflow: "hidden",
      }}>
        {/* 바 채움 — 불투명도 20% */}
        <div style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: `${barPct}%`,
          height: "100%",
          backgroundColor: color,
          opacity: 0.2,
          borderRadius: "3px",
          transition: "width 0.3s ease",
        }} />
        {/* 수량 텍스트 — 색상 100% */}
        <span style={{
          position: "relative", zIndex: 1,
          width: "100%",
          fontSize: "12px", fontWeight: 400, color: color,
          textAlign: "left",
          paddingLeft: "8px",
          fontVariantNumeric: "tabular-nums",
          whiteSpace: "nowrap",
          boxSizing: "border-box",
        }}>
          {fmt(item.quantity)} 주
        </span>
      </div>
    </div>
  );
};

// ─── 라인 차트 ────────────────────────────────────────────────

const TrendLineChart: React.FC<{ data: TrendDataPoint[] }> = ({ data }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "#1C1D21" }, textColor: "#9194A1" },
      grid: { vertLines: { color: "#2F3037" }, horzLines: { color: "#2F3037" } },
      rightPriceScale: { borderColor: "#2F3037" },
      timeScale: { borderColor: "#2F3037", timeVisible: true },
      crosshair: { vertLine: { color: "#9194A1", width: 1, style: 3 }, horzLine: { color: "#9194A1", width: 1, style: 3 } },
      width: containerRef.current.clientWidth,
      height: 243,
    });

    const toLineData = (key: keyof Omit<TrendDataPoint, "time">): LineData[] =>
      data.map((d) => ({ time: d.time as any, value: d[key] }));

    chart.addSeries(LineSeries, { color: IND_COLOR, lineWidth: 2 }).setData(toLineData("individual"));
    chart.addSeries(LineSeries, { color: FOR_COLOR, lineWidth: 2 }).setData(toLineData("foreign"));
    chart.addSeries(LineSeries, { color: INST_COLOR, lineWidth: 2 }).setData(toLineData("institution"));
    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, [data]);

  return <div ref={containerRef} style={{ width: "100%", height: "243px" }} />;
};

// ─── 데이터 테이블 공통 ───────────────────────────────────────

const MoreButton = ({ expanded, onToggle }: { expanded: boolean; onToggle: () => void }) => (
  <div style={{ display: "flex", justifyContent: "center", padding: "10px 0" }}>
    <button
      onClick={onToggle}
      style={{ backgroundColor: "transparent", border: "none", cursor: "pointer", fontSize: "12px", color: "#9194A1" }}
    >
      {expanded ? "접기 ▴" : "더 보기 ▾"}
    </button>
  </div>
);

const thStyle: React.CSSProperties = {
  padding: "8px 12px", textAlign: "right", color: "#9194A1",
  fontWeight: 400, fontSize: "12px",
  borderBottom: "1px solid #2F3037", whiteSpace: "nowrap",
};
const tdBase: React.CSSProperties = { padding: "8px 12px", textAlign: "right", fontSize: "12px", fontWeight: 400 };

// 추세 데이터 테이블
const TrendDataTable: React.FC<{ rows: TrendTableRow[] }> = ({ rows }) => {
  const [expanded, setExpanded] = useState(false);
  const displayed = expanded ? rows : rows.slice(0, 8);
  const HEADERS = ["일자", "종가", "등락률", "등락금액", "개인 순매수", "외국인 순매수", "외국인 지분율", "기관 순매수"];
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>
          {displayed.map((row, i) => (
            <tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : TABLE_BG2 }}>
              <td style={{ ...tdBase, color: "#9194A1" }}>{row.date}</td>
              <td style={{ ...tdBase, color: "#FFFFFF", fontVariantNumeric: "tabular-nums" }}>{fmt(row.closePrice)}원</td>
              <td style={{ ...tdBase, color: signColor(row.changeRate) }}>{fmtRate(row.changeRate)}</td>
              <td style={{ ...tdBase, color: signColor(row.changeAmount) }}>{fmtSigned(row.changeAmount)}원</td>
              <td style={{ ...tdBase, color: signColor(row.individualNet) }}>{fmtSigned(row.individualNet)}주</td>
              <td style={{ ...tdBase, color: signColor(row.foreignNet) }}>{fmtSigned(row.foreignNet)}주</td>
              <td style={{ ...tdBase, color: "#9194A1" }}>{row.foreignRatio.toFixed(2)}%</td>
              <td style={{ ...tdBase, color: signColor(row.institutionNet) }}>{fmtSigned(row.institutionNet)}주</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
    </div>
  );
};

// 프로그램 매매 테이블
const ProgramTable: React.FC<{ rows: ProgramTradeRow[] }> = ({ rows }) => {
  const [expanded, setExpanded] = useState(false);
  const [subFilter, setSubFilter] = useState("all");
  const displayed = expanded ? rows : rows.slice(0, 8);
  const HEADERS = ["일자", "순매수 증감", "순매수", "매수", "매도", "비차익 순매수"];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <Dropdown value={subFilter} options={[{ label: "전체", value: "all" }, { label: "비차익·차익 거래", value: "nonarbitrage" }]} onChange={setSubFilter} />
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
          <tbody>
            {displayed.map((row, i) => (
              <tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : TABLE_BG2 }}>
                <td style={{ ...tdBase, color: "#9194A1" }}>{row.date}</td>
                <td style={{ ...tdBase, color: signColor(row.netBuyChange) }}>{fmtSigned(row.netBuyChange)}</td>
                <td style={{ ...tdBase, color: signColor(row.netBuy) }}>{fmtSigned(row.netBuy)}</td>
                <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.buy)}</td>
                <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.sell)}</td>
                <td style={{ ...tdBase, color: signColor(row.nonArbitrageNet) }}>{fmtSigned(row.nonArbitrageNet)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
    </div>
  );
};

// 신용거래 테이블
const CreditTable: React.FC<{ rows: CreditTradeRow[] }> = ({ rows }) => {
  const [expanded, setExpanded] = useState(false);
  const [creditFilter, setCreditFilter] = useState("융자");
  const filtered = rows.filter((r) => r.type === creditFilter);
  const displayed = expanded ? filtered : filtered.slice(0, 8);
  const HEADERS = ["일자", "증감수량", "신규수량", "상환수량", "잔고수량", "잔고율"];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <Dropdown value={creditFilter} options={[{ label: "신용융자", value: "융자" }, { label: "신용대주", value: "대주" }]} onChange={setCreditFilter} />
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
          <tbody>
            {displayed.map((row, i) => (
              <tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : TABLE_BG2 }}>
                <td style={{ ...tdBase, color: "#9194A1" }}>{row.date}</td>
                <td style={{ ...tdBase, color: signColor(row.changeQty) }}>{fmtSigned(row.changeQty)}</td>
                <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.newQty)}</td>
                <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.repayQty)}</td>
                <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.balanceQty)}</td>
                <td style={{ ...tdBase, color: "#9194A1" }}>{row.balanceRate.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
    </div>
  );
};

// 대차거래 테이블
const LendingTable: React.FC<{ rows: LendingTradeRow[] }> = ({ rows }) => {
  const [expanded, setExpanded] = useState(false);
  const displayed = expanded ? rows : rows.slice(0, 8);
  const HEADERS = ["일자", "증감수량", "신규수량", "상환수량", "잔고수량"];
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>
          {displayed.map((row, i) => (
            <tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : TABLE_BG2 }}>
              <td style={{ ...tdBase, color: "#9194A1" }}>{row.date}</td>
              <td style={{ ...tdBase, color: signColor(row.changeQty) }}>{fmtSigned(row.changeQty)}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.newQty)}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.repayQty)}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.balanceQty)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
    </div>
  );
};

// 공매도 테이블
const ShortTable: React.FC<{ rows: ShortTradeRow[] }> = ({ rows }) => {
  const [expanded, setExpanded] = useState(false);
  const displayed = expanded ? rows : rows.slice(0, 8);
  const HEADERS = ["일자", "거래대금대비 비율", "공매도 수량", "공매도 금액", "공매도 평균가", "거래대금"];
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>
          {displayed.map((row, i) => (
            <tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : TABLE_BG2 }}>
              <td style={{ ...tdBase, color: "#9194A1" }}>{row.date}</td>
              <td style={{ ...tdBase, color: "#9194A1" }}>{row.tradeAmountRatio.toFixed(2)}%</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.shortQty)}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.shortAmount)}원</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.shortAvgPrice)}원</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.tradeAmount)}원</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
    </div>
  );
};

// CFD 테이블
const CfdTable: React.FC<{ rows: CfdTradeRow[] }> = ({ rows }) => {
  const [expanded, setExpanded] = useState(false);
  const displayed = expanded ? rows : rows.slice(0, 8);
  const HEADERS = ["일자", "신규 매수 수량", "상환 매수 수량", "잔고 매수 수량", "매수 잔고율", "신규 매도 수량", "상환 매도 수량", "잔고 매도 수량", "매도 잔고율"];
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr>{HEADERS.map((h) => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
        <tbody>
          {displayed.map((row, i) => (
            <tr key={i} style={{ backgroundColor: i % 2 === 0 ? TABLE_BG1 : TABLE_BG2 }}>
              <td style={{ ...tdBase, color: "#9194A1" }}>{row.date}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.newBuyQty)}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.repayBuyQty)}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.balanceBuyQty)}</td>
              <td style={{ ...tdBase, color: "#9194A1" }}>{row.buyBalanceRate.toFixed(2)}%</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.newSellQty)}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.repaySellQty)}</td>
              <td style={{ ...tdBase, color: "#FFFFFF" }}>{fmt(row.balanceSellQty)}</td>
              <td style={{ ...tdBase, color: "#9194A1" }}>{row.sellBalanceRate.toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 8 && <MoreButton expanded={expanded} onToggle={() => setExpanded((v) => !v)} />}
    </div>
  );
};

// ─── InvestorTradePanel (통합 패널) ───────────────────────────

export const InvestorTradePanel: React.FC<InvestorTradePanelProps> = ({
  status = "default",
  buyList = [],
  sellList = [],
  rankBaseDateTime = "",
  trendData = [],
  trendBaseDateTime = "",
  tableData = [],
  programData = [],
  creditData = [],
  lendingData = [],
  shortData = [],
  cfdData = [],
  onRetry,
  onViewNetBuy,
  panelWidth = 1036,
  panelHeight = 820,
}) => {
  const [period, setPeriod] = useState<TrendPeriod>("daily");
  const [activeTab, setActiveTab] = useState<InvestorType>("program");

  const maxBuyQty = Math.max(...buyList.map((i) => i.quantity), 1);
  const maxSellQty = Math.max(...sellList.map((i) => i.quantity), 1);

  const INVESTOR_TABS: { label: string; value: InvestorType }[] = [
    { label: "프로그램 매매", value: "program" },
    { label: "신용거래",     value: "credit"  },
    { label: "대차거래",     value: "lending" },
    { label: "공매도",       value: "short"   },
    { label: "CFD",          value: "cfd"     },
  ];

  return (
    // 외부 프레임: 뷰포트별 크기, 좌우 패딩 30px, 내부 스크롤
    <div
      style={{
        width: `${panelWidth}px`,
        height: `${panelHeight}px`,
        backgroundColor: "#1C1D21",
        borderRadius: "12px",
        padding: "24px 16px",
        boxSizing: "border-box",
        overflowY: "auto",
        overflowX: panelWidth <= 345 ? "auto" : "hidden",
        scrollbarWidth: "none",
        display: "flex",
        flexDirection: "column",
        gap: "32px",
      }}
    >
      {/* ── 거래원 매매 상위 ── */}
      <div>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "16px" }}>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>거래원 매매 상위</span>
          <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1" }}>
            거래소에서 제공하는 주요 거래원의 실시간 데이터입니다.
          </span>
        </div>

        {rankBaseDateTime && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "12px" }}>
            <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1" }}>
              기준 : {rankBaseDateTime}
            </span>
          </div>
        )}

        {status === "skeleton" && (
          <div style={{ display: "flex", gap: "40px" }}>
            <div style={{ flex: 1 }}><PanelSkeleton /></div>
            <div style={{ flex: 1 }}><PanelSkeleton /></div>
          </div>
        )}
        {status === "error" && <ErrorBlock onRetry={onRetry} />}
        {status === "default" && (
          /* 모바일(345px): 매수/매도 상하 배치 / 그 외: 좌우 배치 */
          <div style={{
            display: "flex",
            flexDirection: panelWidth <= 345 ? "column" : "row",
            gap: panelWidth <= 345 ? "24px" : "40px",
          }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "10px" }}>
              <span style={{ fontSize: "14px", fontWeight: 700, color: "#FFFFFF" }}>매수 상위 5</span>
              {buyList.map((item) => (
                <RankRow key={item.rank} item={item} maxQty={maxBuyQty} side="buy" />
              ))}
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "10px" }}>
              <span style={{ fontSize: "14px", fontWeight: 700, color: "#FFFFFF" }}>매도 상위 5</span>
              {sellList.map((item) => (
                <RankRow key={item.rank} item={item} maxQty={maxSellQty} side="sell" />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── 구분선 ── */}
      <div style={{ height: "1px", backgroundColor: "#2F3037", flexShrink: 0 }} />

      {/* ── 투자자별 매매 동향 ── */}
      <div>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "16px" }}>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>투자자별 매매 동향</span>
          <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1" }}>
            외국인 순매수량은 장외거래를 포함한 매매수량입니다.
          </span>
        </div>

        {status === "skeleton" && <ChartSkeleton />}
        {status === "error" && <ErrorBlock onRetry={onRetry} />}
        {status === "default" && (
          <>
            {trendBaseDateTime && (
              <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "12px" }}>
                <span style={{ fontSize: "14px", fontWeight: 400, color: "#9194A1" }}>
                  기준 : {trendBaseDateTime}
                </span>
              </div>
            )}

            {/* 기간 드롭다운 + 순매수 보기 버튼 */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
              <Dropdown
                value={period}
                options={[{ label: "일별", value: "daily" }, { label: "1주일", value: "weekly" }]}
                onChange={(v) => setPeriod(v as TrendPeriod)}
              />
              <div style={{ flex: 1 }} />
              <button
                onClick={onViewNetBuy}
                style={{
                  width: "152px", height: "32px",
                  backgroundColor: "#2C2C30", border: "none", borderRadius: "5px",
                  cursor: "pointer", fontSize: "12px", fontWeight: 400, color: "#FFFFFF",
                }}
              >
                투자자별 순매수 보기
              </button>
            </div>

            {/* 범례 */}
            <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "12px" }}>
              {[
                { color: IND_COLOR, label: "개인" },
                { color: FOR_COLOR, label: "외국인" },
                { color: INST_COLOR, label: "기관" },
              ].map((item) => (
                <div key={item.label} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <div style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: item.color, flexShrink: 0 }} />
                  <span style={{ fontSize: "12px", fontWeight: 700, color: "#FFFFFF" }}>{item.label}</span>
                </div>
              ))}
            </div>

            {/* 라인 차트 */}
            <TrendLineChart data={trendData} />

            {/* 데이터 테이블 */}
            <div style={{ marginTop: "16px" }}>
              <TrendDataTable rows={tableData} />
            </div>

            {/* 투자 유형별 현황 */}
            <div style={{ marginTop: "24px", display: "flex", flexDirection: "column", gap: "16px" }}>
              <span style={{ fontSize: "18px", fontWeight: 700, color: "#FFFFFF" }}>투자 유형별 현황</span>
              <div style={{ display: "flex", borderBottom: "1px solid #2F3037" }}>
                {INVESTOR_TABS.map((tab) => (
                  <button
                    key={tab.value}
                    onClick={() => setActiveTab(tab.value)}
                    style={{
                      padding: "8px 16px",
                      backgroundColor: "transparent", border: "none",
                      borderBottom: activeTab === tab.value ? "2px solid #FFFFFF" : "2px solid transparent",
                      cursor: "pointer", fontSize: "14px",
                      fontWeight: activeTab === tab.value ? 700 : 400,
                      color: activeTab === tab.value ? "#FFFFFF" : "#9194A1",
                      marginBottom: "-1px", whiteSpace: "nowrap",
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              {activeTab === "program" && <ProgramTable rows={programData} />}
              {activeTab === "credit"  && <CreditTable rows={creditData} />}
              {activeTab === "lending" && <LendingTable rows={lendingData} />}
              {activeTab === "short"   && <ShortTable rows={shortData} />}
              {activeTab === "cfd"     && <CfdTable rows={cfdData} />}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default InvestorTradePanel;