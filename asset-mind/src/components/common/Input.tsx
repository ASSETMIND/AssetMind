import  { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";
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
        {label && (
          <label className="text-l2 text-text-secondary">
            {label}
          </label>
        )}

        <div className="relative">
          <input
            ref={ref}
            className={cn(
              "input-base", 
              // [수정] 커서는 무조건 흰색, 입력 중 배경색 변경 방지
              "caret-white focus:bg-transparent",
              icon && "pr-10",
              // 에러 시 테두리는 빨갛게(input-error), 하지만 입력 글자는 흰색 유지(text-white)
              error && "input-error text-white",
              className
            )}
            {...props}
          />
          
          {icon && (
            <button
              type="button"
              onClick={onIconClick}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
            >
              {icon}
            </button>
          )}
        </div>

        {/* 에러 메시지는 빨간색 유지 */}
        {error && (
          <p className="text-l4 text-text-error">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";