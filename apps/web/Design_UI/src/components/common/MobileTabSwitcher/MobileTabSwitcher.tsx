import { useEffect, useRef, useState } from "react";
import { cn } from "../../../lib/utils";

export interface MobileTabItem {
  label: string;
  value: string;
  icon: React.ReactNode;
}

interface MobileTabSwitcherProps {
  items: MobileTabItem[];
  defaultValue?: string;
  value?: string;
  onChange?: (value: string) => void;
  className?: string;
}

/**
 * MobileTabSwitcher 컴포넌트
 *
 * 디자인 스펙:
 * - 상단 좌우 border-radius: 20px (rounded-tl-[20px] rounded-tr-[20px])
 * - 외곽선: #252525 굵기 1px
 * - 활성 탭: #FFFFFF
 * - 비활성 탭: #9F9F9F 불투명도 70%
 * - 스크롤 시 화면 하단에 Sticky 고정
 */
export const MobileTabSwitcher = ({
  items,
  defaultValue,
  value: controlledValue,
  onChange,
  className,
}: MobileTabSwitcherProps) => {
  const [internalValue, setInternalValue] = useState(
    defaultValue ?? items[0]?.value
  );
  const [isSticky, setIsSticky] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const activeValue = controlledValue ?? internalValue;

  const handleClick = (val: string) => {
    if (!controlledValue) setInternalValue(val);
    onChange?.(val);
  };

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => setIsSticky(!entry.isIntersecting),
      { threshold: 0, rootMargin: "0px" }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <div
        className={cn(
          "sticky bottom-0 z-50 w-full",
          "bg-background-primary",
          "rounded-tl-[20px] rounded-tr-[20px]",
          "border border-[#252525]",
          "transition-shadow duration-200",
          isSticky && "shadow-[0_-2px_12px_rgba(0,0,0,0.4)]",
          className
        )}
        role="tablist"
        aria-orientation="horizontal"
      >
        {/* w-[393px] h-[64px], 좌우 패딩 40px, 상하 패딩 10px, 탭 간격 자동(justify-between) */}
        <div className="w-full h-[64px] flex items-center justify-between px-[40px] py-[10px]">
          {items.map((item) => {
            const isActive = activeValue === item.value;
            return (
              <button
                key={item.value}
                role="tab"
                aria-selected={isActive}
                tabIndex={isActive ? 0 : -1}
                onClick={() => handleClick(item.value)}
                className={cn(
                  "flex flex-col items-center gap-1.5",
                  "transition-colors duration-150",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-inputFocus rounded-lg",
                  "cursor-pointer",
                  isActive
                    ? "text-[#FFFFFF]"
                    : "text-[#9F9F9F] opacity-70"
                )}
              >
                <span className="w-6 h-6 flex items-center justify-center" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="text-[12px] font-bold leading-none">{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Sticky 감지용 sentinel — 탭 아래에 위치 */}
      <div ref={sentinelRef} className="h-0" aria-hidden="true" />
    </>
  );
};