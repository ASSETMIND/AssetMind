import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/utils";

type ButtonVariant = 'primary' | 'secondary' | 'kakao' | 'google';
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  /**
   * [접근성] 로딩 상태
   */
  isLoading?: boolean;
  loadingText?: string;
}

export const Button = ({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  fullWidth = false,
  isLoading = false,
  loadingText = "로딩 중...",
  disabled,
  className,
  'aria-label': ariaLabel,
  ...props 
}: ButtonProps) => {
  
  const baseStyles = "inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-inputFocus focus-visible:ring-offset-2 focus-visible:ring-offset-background-primary disabled:pointer-events-none disabled:opacity-50";
  
  const variants = {
    primary: "bg-button-large-primary text-button-large-label hover:bg-button-large-primaryHover",
    secondary: "bg-gray-100 text-gray-900 hover:bg-gray-200",
    kakao: "bg-social-kakao-bg hover:opacity-90",
    google: "bg-social-google-bg border border-border-inputNormal hover:bg-gray-50",
  };

  const sizes = {
    sm: "h-9 px-3 text-xs",
    md: "h-[52px] px-6 text-base",
    lg: "h-[54px] px-8 text-[16px]",
    icon: "w-12 h-12 rounded-full flex items-center justify-center p-0",
  };

  // [접근성] icon 버튼 경고
  if (process.env.NODE_ENV === 'development' && size === 'icon' && !ariaLabel) {
    console.warn('Button: icon 크기의 버튼은 aria-label이 필요합니다.');
  }

  const isDisabled = disabled || isLoading;

  return (
    <button
      className={cn(
        baseStyles,
        variants[variant],
        sizes[size],
        fullWidth ? "w-full" : "",
        className
      )}
      disabled={isDisabled}
      aria-busy={isLoading ? true : undefined}
      aria-disabled={isDisabled ? true : undefined}
      aria-label={ariaLabel}
      {...props}
    >
      {isLoading ? (
        <>
          <svg 
            className="animate-spin -ml-1 mr-2 h-4 w-4" 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle 
              className="opacity-25" 
              cx="12" 
              cy="12" 
              r="10" 
              stroke="currentColor" 
              strokeWidth="4"
            />
            <path 
              className="opacity-75" 
              fill="currentColor" 
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span>{loadingText}</span>
          <span className="sr-only">처리 중입니다.</span>
        </>
      ) : (
        children
      )}
    </button>
  );
};
