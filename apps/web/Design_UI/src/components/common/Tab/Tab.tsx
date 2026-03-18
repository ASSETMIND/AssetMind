import { useState } from "react";
import { cn } from "../../../lib/utils";

export interface TabItem {
  label: string;
  value: string;
}

interface TabProps {
  items: TabItem[];
  defaultValue?: string;
  value?: string;
  onChange?: (value: string) => void;
  className?: string;
}

/**
 * Tab 컴포넌트
 *
 * 디자인 스펙:
 * - 컨테이너: bg #1C1D21 (background.surface), padding 4px, border-radius 8px
 * - 활성 칩: bg #383A42 (border.inputNormal), border-radius 6px, padding 좌우 14px 상하 6px
 * - 비활성 칩: 배경 없음, 동일 padding
 */
export const Tab = ({
  items,
  defaultValue,
  value: controlledValue,
  onChange,
  className,
}: TabProps) => {
  const [internalValue, setInternalValue] = useState(
    defaultValue ?? items[0]?.value
  );

  const activeValue = controlledValue ?? internalValue;

  const handleClick = (val: string) => {
    if (!controlledValue) setInternalValue(val);
    onChange?.(val);
  };

  return (
    <div
      className={cn(
        "inline-flex gap-0 bg-background-surface rounded-[8px] p-[4px]",
        className
      )}
      role="tablist"
      aria-orientation="horizontal"
    >
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
              "px-[14px] py-[6px] rounded-[6px] text-l3 transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-inputFocus",
              "cursor-pointer",
              isActive
                ? "bg-border-inputNormal text-text-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
};