import { useEffect, useRef, useState } from "react";
import { cn } from "../../../lib/utils";

type PriceChangeVariant = "rise" | "fall" | "flat";

interface PriceChangeTokenProps {
  value: number;       // 등락률 수치 (예: 2.35, -1.20, 0)
  showSign?: boolean;  // 부호(+/-) 표시 여부, 기본 true
  animated?: boolean;  // 슬롯머신 애니메이션 여부, 기본 false
  className?: string;
}

function getVariant(value: number): PriceChangeVariant {
  if (value > 0) return "rise";
  if (value < 0) return "fall";
  return "flat";
}

const textColorMap: Record<PriceChangeVariant, string> = {
  rise: "text-status-rise",
  fall: "text-status-fall",
  flat: "text-text-secondary",
};

const signMap: Record<PriceChangeVariant, string> = {
  rise: "+",
  fall: "", 
  flat: "",
};

/**
 * PriceChangeToken 컴포넌트
 *
 * 등락률 수치를 상승(rise) / 하락(fall) / 보합(flat) 상태에 따라
 * 색상 토큰(status.rise, status.fall)을 적용해 텍스트로 표시합니다.
 *
 * @animated true 시 값 변경 시 슬롯머신 스타일 세로 스크롤 애니메이션 재생
 */
export const PriceChangeToken = ({
  value,
  showSign = true,
  animated = false,
  className,
}: PriceChangeTokenProps) => {
  const variant = getVariant(value);
  const sign = showSign ? signMap[variant] : "";
  const formatted = `${sign}${value.toFixed(2)}%`;

  const [displayValue, setDisplayValue] = useState(formatted);
  const [isAnimating, setIsAnimating] = useState(false);
  const prevValueRef = useRef(value);

  useEffect(() => {
    if (!animated) {
      setDisplayValue(formatted);
      return;
    }
    if (prevValueRef.current !== value) {
      setIsAnimating(true);
      const timer = setTimeout(() => {
        setDisplayValue(formatted);
        setIsAnimating(false);
      }, 150);
      prevValueRef.current = value;
      return () => clearTimeout(timer);
    }
  }, [value, formatted, animated]);

  return (
    <span
      className={cn(
        "inline-block overflow-hidden text-b2 font-medium tabular-nums",
        textColorMap[variant],
        className
      )}
      aria-label={`등락률 ${formatted}`}
      aria-live="polite"
    >
      <span
        className={cn(
          "inline-block transition-transform duration-150",
          isAnimating ? "-translate-y-full opacity-0" : "translate-y-0 opacity-100"
        )}
      >
        {displayValue}
      </span>
    </span>
  );
};