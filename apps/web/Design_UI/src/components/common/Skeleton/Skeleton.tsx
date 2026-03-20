import { cn } from "../../../lib/utils";

type SkeletonVariant =
  | "chart"       // 차트 영역 — 상단 와이드 블록
  | "table-row"   // 테이블 행 — 원형 아바타 + 직사각형 블록들
  | "card"        // 카드형 — AI 패널, 종목 정보 등
  | "orderbook"   // 호가창 — 좌우 컬럼 직사각형 블록
  | "spinner";    // 전체 화면 스피너 — 탭 전환 시

interface SkeletonProps {
  variant?: SkeletonVariant;
  rows?: number;      // table-row, orderbook variant에서 반복 행 수
  className?: string;
}

/**
 * Skeleton 컴포넌트
 *
 * 디자인 스펙:
 * - 색상: #21242C (background.elevated) ↔ #2C2C30 (background.hover) 번갈아 깜빡
 * - 딜레이: 400ms 후 시작, 300ms ease-out으로 전환
 * - variant: chart / table-row / card / orderbook / spinner
 */

// shimmer 대신 두 색상 펄스 애니메이션 — tailwind.config에 keyframes 추가 필요
// keyframes: { 'skeleton-pulse': { '0%, 100%': { backgroundColor: '#21242C' }, '50%': { backgroundColor: '#2C2C30' } } }
// animation: { 'skeleton-pulse': 'skeleton-pulse 700ms ease-out 400ms infinite' }
const pulseClass = "animate-skeleton-pulse rounded-[4px]";

const Block = ({ className }: { className?: string }) => (
  <div className={cn(pulseClass, className)} />
);

// ─── Chart variant ────────────────────────────────────────────
const ChartSkeleton = ({ className }: { className?: string }) => (
  <div className={cn("w-full flex flex-col gap-3", className)}>
    {/* 차트 메인 영역 */}
    <Block className="w-full h-[200px] rounded-[8px]" />
  </div>
);

// ─── Table Row variant ────────────────────────────────────────
const TableRowSkeleton = ({ rows = 10, className }: { rows?: number; className?: string }) => (
  <div className={cn("w-full flex flex-col", className)}>
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="flex items-center gap-3 px-4 py-[18px] border-b border-border-divider">
        {/* 즐겨찾기 아이콘 자리 */}
        <Block className="w-4 h-4 rounded-full shrink-0" />
        {/* 순위 */}
        <Block className="w-3 h-3 shrink-0" />
        {/* 종목 아바타 */}
        <Block className="w-9 h-9 rounded-full shrink-0" />
        {/* 종목명 */}
        <Block className="w-[120px] h-3.5" />
        {/* 우측 데이터 블록들 */}
        <div className="ml-auto flex items-center gap-6">
          <Block className="w-[80px] h-3.5" />
          <Block className="w-[60px] h-3.5" />
          <Block className="w-[80px] h-3.5" />
          <Block className="w-[120px] h-2.5 rounded-full" />
        </div>
      </div>
    ))}
  </div>
);

// ─── Card variant ─────────────────────────────────────────────
const CardSkeleton = ({ rows = 5, className }: { rows?: number; className?: string }) => (
  <div className={cn("w-full flex flex-col gap-2 p-4", className)}>
    {Array.from({ length: rows }).map((_, i) => (
      <Block
        key={i}
        className={cn("h-[52px] w-full rounded-[8px]", i % 2 === 0 ? "opacity-100" : "opacity-70")}
      />
    ))}
  </div>
);

// ─── Orderbook variant ────────────────────────────────────────
const OrderbookSkeleton = ({ rows = 8, className }: { rows?: number; className?: string }) => (
  <div className={cn("w-full flex gap-2", className)}>
    {/* 매도 호가 */}
    <div className="flex-1 flex flex-col gap-1.5">
      {Array.from({ length: rows }).map((_, i) => (
        <Block key={i} className="h-[30px] w-full rounded-[4px]" />
      ))}
    </div>
    {/* 매수 호가 */}
    <div className="flex-1 flex flex-col gap-1.5">
      {Array.from({ length: rows }).map((_, i) => (
        <Block key={i} className="h-[30px] w-full rounded-[4px]" />
      ))}
    </div>
  </div>
);

// ─── Spinner variant ──────────────────────────────────────────
const SpinnerSkeleton = ({ className }: { className?: string }) => (
  <div className={cn("w-full h-full min-h-[400px] flex items-center justify-center", className)}>
    <svg
      className="animate-spin w-5 h-5 text-text-secondary"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-label="Loading"
    >
      <circle
        className="opacity-25"
        cx="12" cy="12" r="10"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  </div>
);

// ─── Main export ──────────────────────────────────────────────
export const Skeleton = ({ variant = "table-row", rows, className }: SkeletonProps) => {
  switch (variant) {
    case "chart":     return <ChartSkeleton className={className} />;
    case "table-row": return <TableRowSkeleton rows={rows} className={className} />;
    case "card":      return <CardSkeleton rows={rows} className={className} />;
    case "orderbook": return <OrderbookSkeleton rows={rows} className={className} />;
    case "spinner":   return <SpinnerSkeleton className={className} />;
  }
};