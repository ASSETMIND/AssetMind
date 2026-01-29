import { createContext, useContext, useState, type ReactNode, useCallback } from "react";
import { ToastItem, type ToastVariant } from "../components/common/Toast/ToastItem";

// 1. [정의] 사용 가능한 토스트 타입은 딱 4가지만 존재
export type ToastCaseType = 
  | 'PASSWORD_CHANGE_SUCCESS' // 비밀번호 변경 완료
  | 'VERIFICATION_FAIL'       // 인증 실패 (입력 불일치)
  | 'IDENTITY_FAIL'           // 본인인증 실패 (시스템 오류)
  | 'LOGIN_FAIL';             // 로그인 실패

// 2. [데이터] 각 타입별 고정 문구 및 디자인 정의
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
  // 함수 인자를 'type' 하나로 제한하여 다른 문구 입력 불가능하게 함
  showToast: (type: ToastCaseType) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  // [수정] type만 받아서 미리 정의된 문구를 뿌려주는 방식으로 변경
  const showToast = useCallback((type: ToastCaseType) => {
    const content = TOAST_CONTENTS[type]; // 해당 타입의 문구 가져오기
    const id = Math.random().toString(36).substr(2, 9);

    setToasts((prev) => [...prev, { 
      id, 
      variant: content.variant, 
      title: content.title, 
      message: content.message 
    }]);

    // 3초 뒤 자동 삭제
    setTimeout(() => removeToast(id), 3000);
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