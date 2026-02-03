import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "../../lib/utils";

type InputState = 'default' | 'error' | 'success';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  message?: string;
  state?: InputState;
  icon?: ReactNode;
  onIconClick?: () => void;
  rightSection?: ReactNode;
  rightSectionWidth?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ 
    className, 
    label, 
    error, 
    message, 
    state = 'default',
    icon, 
    onIconClick, 
    rightSection,
    rightSectionWidth = "pr-[50px]", 
    ...props 
  }, ref) => {
    
    const finalState = error ? 'error' : state;
    const finalMessage = error || message;

    return (
      <div className="w-full flex flex-col gap-2">
        {/* Label: L2(16px) Regular */}
        {label && (
          <label className="text-l2 font-normal text-text-primary">
            {label}
          </label>
        )}

        <div className="relative">
          <input
            ref={ref}
            className={cn(
              // 1. [Layout] 높이 57px, 좌측 패딩 25px
              "w-full h-[57px] px-[25px] rounded-lg border outline-none transition-all duration-200",
              
              // 2. [Typography] B2 수정 (14px 강제 적용)
              "text-[14px] leading-[150%] font-normal",
              "text-text-primary placeholder:text-text-placeholder",
              
              // 3. [Colors] 배경색 #1C1D21
              "bg-[#1C1D21] border-border-inputNormal",
              
              // 4. [Interaction]
              "focus:border-border-inputFocus focus:bg-[#1C1D21]",
              
              // 5. [Padding] 우측 여백
              (icon || rightSection) && rightSectionWidth,
              
              // 6. [State Styles] - 텍스트 색상 관련 부분 제거
              finalState === 'error' && "border-border-inputError focus:border-border-inputError placeholder:text-text-error/50",
              finalState === 'success' && "border-border-inputSuccess focus:border-border-inputSuccess", 
              
              className
            )}
            {...props}
          />
          
          {/* 아이콘 */}
          {icon && !rightSection && (
            <button
              type="button"
              onClick={onIconClick}
              className="absolute right-[20px] top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary flex items-center justify-center"
            >
              {icon}
            </button>
          )}

          {/* 우측 버튼 슬롯 */}
          {rightSection && (
            <div className="absolute right-[10px] top-1/2 -translate-y-1/2">
              {rightSection}
            </div>
          )}
        </div>

        {/* 하단 메시지 */}
        {finalMessage && (
          <p className={cn(
            "text-l4 mt-1",
            finalState === 'error' ? "text-text-error" : 
            finalState === 'success' ? "text-text-success" : 
            "text-text-secondary"
          )}>
            {finalMessage}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";