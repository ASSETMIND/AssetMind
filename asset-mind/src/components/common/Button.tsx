import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/utils";

type ButtonVariant = 'primary' | 'secondary' | 'kakao' | 'google';
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
}

export const Button = ({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  fullWidth = false, 
  className, 
  ...props 
}: ButtonProps) => {
  
  const baseStyles = "inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50";
  
  const variants = {
    // [복구] 사용자님 기존 커스텀 클래스 적용
    primary: "bg-button-large-primary text-button-large-label hover:bg-button-large-primaryHover",
    secondary: "bg-gray-100 text-gray-900 hover:bg-gray-200",
    
    // 소셜 버튼 배경색
    kakao: "bg-social-kakao-bg hover:opacity-90",
    google: "bg-social-google-bg border border-border-inputNormal hover:bg-gray-50",
  };

  const sizes = {
    sm: "h-9 px-3 text-xs",
    md: "h-[52px] px-6 text-base",
    lg: "h-14 px-8 text-lg",
    // [복구] 아이콘이 w-10까지 커질 수 있도록 패딩 제거 및 flex 정렬만 유지
    icon: "w-12 h-12 rounded-full flex items-center justify-center p-0",
  };

  return (
    <button
      className={cn(
        baseStyles,
        variants[variant],
        sizes[size],
        fullWidth ? "w-full" : "",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
};