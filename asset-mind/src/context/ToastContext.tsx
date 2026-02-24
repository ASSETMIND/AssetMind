import { createContext, useContext, useState, type ReactNode, useCallback } from "react";
import { ToastItem, type ToastVariant } from "../components/common/Toast/ToastItem";

export type ToastCaseType = 
  | 'PASSWORD_CHANGE_SUCCESS' // 비밀번호 변경 완료
  | 'VERIFICATION_FAIL'       // 인증 실패 (입력 불일치)
  | 'IDENTITY_FAIL'           // 본인인증 실패 (시스템 오류)
  | 'LOGIN_FAIL';             // 로그인 실패

const TOAST_CONTENTS: Record<ToastCaseType, { variant: ToastVariant; title: string; message: string }> = {
  PASSWORD_CHANGE_SUCCESS: {
    variant: 'success',
    title: '비밀번호가 변경되었습니다.',
    message: '서비스 이용을 위해 다시 로그인해 주세요.',
  },
  VERIFICATION_FAIL: {
    variant: 'error',
    title: '인증에 실패했습니다.',
    message: '입력하신 정보가 정확한지 확인해 주세요.',
  },
  IDENTITY_FAIL: {
    variant: 'error',
    title: '본인인증에 실패했습니다.',
    message: '잠시 후 다시 시도해주세요.',
  },
  LOGIN_FAIL: {
    variant: 'error',
    title: '로그인에 실패했습니다.',
    message: '잠시 후 다시 시도해주세요.',
  }
};

interface ToastData {
  id: string;
  variant: ToastVariant;
  title: string;
  message: string;
}

interface ToastContextType {
  showToast: (type: ToastCaseType, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback((type: ToastCaseType, duration: number = 3000) => {
    const content = TOAST_CONTENTS[type];
    const id = Math.random().toString(36).substr(2, 9);

    setToasts((prev) => [...prev, { 
      id, 
      variant: content.variant, 
      title: content.title, 
      message: content.message 
    }]);

    setTimeout(() => removeToast(id), duration);
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed top-8 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-3 items-center pointer-events-none w-full max-w-fit">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto animate-toast-in">
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