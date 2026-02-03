// src/context/ToastContext.tsx
import { createContext, useContext, useState, type ReactNode, useCallback } from "react";
import { ToastItem, type ToastVariant } from "../components/common/Toast/ToastItem";

interface ToastData {
  id: string;
  variant: ToastVariant;
  title: string;
  message: string;
}

interface ToastContextType {
  showToast: (variant: ToastVariant, title: string, message: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback((variant: ToastVariant, title: string, message: string) => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, variant, title, message }]);

    // 3초 뒤 자동 삭제
    setTimeout(() => removeToast(id), 3000);
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      
      {/* [수정된 레이아웃] 
        1. fixed top-8: 화면 위에서 조금 떨어진 위치
        2. left-1/2 -translate-x-1/2: 정확히 가로 중앙 정렬
        3. z-[9999]: 모달보다 위에 뜨도록 최상위 설정
      */}
      <div className="fixed top-8 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-3 items-center pointer-events-none w-full max-w-fit">
        {toasts.map((toast) => (
          <div 
            key={toast.id} 
            // [애니메이션 적용] tailwind.config.js에 추가한 'animate-toast-in' 사용
            className="pointer-events-auto animate-toast-in"
          >
            <ToastItem
              variant={toast.variant}
              title={toast.title}
              message={toast.message}
              onClose={() => removeToast(toast.id)}
            />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within a ToastProvider");
  return context;
};