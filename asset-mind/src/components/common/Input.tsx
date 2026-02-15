import { forwardRef, type InputHTMLAttributes, type ReactNode, useId } from "react";
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
    id: providedId,
    ...props 
  }, ref) => {
    
    const generatedId = useId();
    const inputId = providedId || generatedId;
    const messageId = `${inputId}-message`;
    
    const finalState = error ? 'error' : state;
    const finalMessage = error || message;

    return (
      <div className="w-full flex flex-col gap-2">
        {/* Label: L2(16px) Regular */}
        {label && (
          <label 
            htmlFor={inputId}
            className="text-l2 font-normal text-text-primary"
          >
            {label}
          </label>
        )}

        <div className="relative">
          <input
            ref={ref}
            id={inputId}
            aria-describedby={finalMessage ? messageId : undefined}
            aria-invalid={finalState === 'error' ? true : undefined}
            className={cn(
              // 1. [Layout] 기본 스타일
              "w-full h-[57px] px-[25px] rounded-lg border outline-none transition-all duration-200",
              
              // 2. [Typography] 텍스트 스타일
              "text-[14px] leading-[150%] font-normal",
              "text-text-primary placeholder:text-text-placeholder",
              
              // 3. [Colors] 기본 배경
              "bg-[#1C1D21] border-border-inputNormal",
              
              // 4. [Interaction]
              "focus:border-border-inputFocus focus:bg-[#1C1D21]",
              
              // 5. [Padding] 아이콘 또는 우측 섹션이 있을 때 패딩 조정
              (icon || rightSection) && rightSectionWidth,
              
              // 6. [State Styles] 오류 및 성공 상태 스타일
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
              aria-label={props['aria-label'] || "Toggle visibility"}
              className="absolute right-[20px] top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary focus:text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-border-inputFocus focus-visible:ring-offset-2 focus-visible:ring-offset-background-primary rounded transition-colors flex items-center justify-center"
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
          <p 
            id={messageId}
            aria-live={finalState === 'error' ? 'assertive' : 'polite'}
            role={finalState === 'error' ? 'alert' : undefined}
            className={cn(
              "text-l4 mt-1",
              finalState === 'error' ? "text-text-error" : 
              finalState === 'success' ? "text-text-success" : 
              "text-text-secondary"
            )}
          >
            {finalMessage}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
