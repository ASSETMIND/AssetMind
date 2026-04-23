import React from "react";

// ─── Types ────────────────────────────────────────────────────

export interface DonutSlice {
  label: string;
  value: number; // 비율 0~100
  color: string;
}

export interface DonutChartProps {
  slices: DonutSlice[];
  size?: number; // 기본 152
}

// ─── DonutChart ───────────────────────────────────────────────

export const DonutChart: React.FC<DonutChartProps> = ({
  slices,
  size = 152,
}) => {
  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - 4;
  const innerR = outerR * 0.58; // 도넛 두께

  // 총합 기준 정규화
  const total = slices.reduce((s, d) => s + d.value, 0) || 1;

  // 각 슬라이스의 path 계산
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const polarToXY = (angle: number, r: number) => ({
    x: cx + r * Math.cos(toRad(angle - 90)),
    y: cy + r * Math.sin(toRad(angle - 90)),
  });

  const paths: { d: string; color: string }[] = [];
  let startAngle = 0;

  slices.forEach((slice) => {
    const angle = (slice.value / total) * 360;
    const endAngle = startAngle + angle;
    const largeArc = angle > 180 ? 1 : 0;

    const o1 = polarToXY(startAngle, outerR);
    const o2 = polarToXY(endAngle, outerR);
    const i1 = polarToXY(endAngle, innerR);
    const i2 = polarToXY(startAngle, innerR);

    const d = [
      `M ${o1.x.toFixed(3)} ${o1.y.toFixed(3)}`,
      `A ${outerR} ${outerR} 0 ${largeArc} 1 ${o2.x.toFixed(3)} ${o2.y.toFixed(3)}`,
      `L ${i1.x.toFixed(3)} ${i1.y.toFixed(3)}`,
      `A ${innerR} ${innerR} 0 ${largeArc} 0 ${i2.x.toFixed(3)} ${i2.y.toFixed(3)}`,
      "Z",
    ].join(" ");

    paths.push({ d, color: slice.color });
    startAngle = endAngle;
  });

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ flexShrink: 0 }}
    >

      {paths.map((p, i) => (
        <path key={i} d={p.d} fill={p.color} />
      ))}
      {/* 중앙 원 */}
      <circle cx={cx} cy={cy} r={innerR} fill="#21242C" />
    </svg>
  );
};

export default DonutChart;