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
    primary: "bg-button-large-primary text-button-large-label hover:bg-button-large-primaryHover",
    secondary: "bg-gray-100 text-gray-900 hover:bg-gray-200",
    kakao: "bg-social-kakao-bg hover:opacity-90",
    google: "bg-social-google-bg border border-border-inputNormal hover:bg-gray-50",
  };

  const sizes = {
    sm: "h-9 px-3 text-xs",
    md: "h-[52px] px-6 text-base",
    // [수정] h-14(56px) -> h-[54px] (사용자 명세 반영)
    lg: "h-[54px] px-8 text-[16px]", // 폰트 크기도 text-lg 대신 b1(16px) 등 명세에 맞게 조정 필요시 수정
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