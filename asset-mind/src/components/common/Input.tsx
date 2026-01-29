import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "../../lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: ReactNode;
  onIconClick?: () => void;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, icon, onIconClick, ...props }, ref) => {
    return (
      <div className="w-full flex flex-col gap-2">
        {/* Label: L2(16px), White(#FFFFFF) */}
        {label && (
          <label className="text-l2 font-normal text-text-primary">
            {label}
          </label>
        )}

        <div className="relative">
          <input
            ref={ref}
            className={cn(
              // 1. [Layout] 피그마 수치 반영: 높이 57px, 좌우 패딩 25px
              // h-[57px]: 피그마 인스펙터 높이
              // px-[25px]: 피그마 인스펙터 좌측 여백
              "w-full h-[57px] px-[25px] rounded-lg border outline-none transition-all duration-200",
              
              // 2. [Typography] 텍스트 b2(14px), placeholder 색상
              // flex와 items-center를 사용할 수 없는 input 태그 특성상, 
              // h-[57px]와 leading-normal로 수직 중앙 정렬을 유도합니다.
              "text-b2 text-text-primary placeholder:text-text-placeholder font-normal leading-normal",
              
              // 3. [Colors] 배경 Primary(#131316), 테두리 Normal
              "bg-background-primary border-border-inputNormal",
              
              // 4. [Interaction]
              "focus:border-border-inputFocus focus:bg-background-primary",
              
              // 5. [Icon Padding] 아이콘이 있을 경우 우측 패딩을 넉넉히 줌 (50px)
              icon && "pr-[50px]",
              
              // 6. [Error State]
              error && "border-border-inputError focus:border-border-inputError text-text-error placeholder:text-text-error/50",
              
              className
            )}
            {...props}
          />
          
          {/* 아이콘: 수직 중앙 정렬 (top-1/2 -translate-y-1/2) */}
          {icon && (
            <button
              type="button"
              onClick={onIconClick}
              // 우측 여백도 피그마 대칭성을 고려하여 right-[25px] 근처로 배치
              className="absolute right-[20px] top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary flex items-center justify-center"
            >
              {icon}
            </button>
          )}
        </div>

        {/* 에러 메시지 */}
        {error && (
          <p className="text-l4 text-text-error mt-1">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";