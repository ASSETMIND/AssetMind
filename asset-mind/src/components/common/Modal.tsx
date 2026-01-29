import type { ReactNode } from "react";
// [수정] 외부 라이브러리(lucide-react) 대신 우리가 만든 아이콘 사용
import { CloseIcon } from "../icons/CloseIcon"; 
import { cn } from "../../lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}

export const Modal = ({ 
  isOpen, 
  onClose, 
  children, 
  className 
}: ModalProps) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      {/* 백드롭 클릭 시 닫기 */}
      <div 
        className="absolute inset-0 bg-transparent" 
        onClick={onClose} 
        aria-hidden="true" 
      />

      {/* 모달 컨테이너 */}
      <div className={cn("modal-container", className)}>
        {/* 닫기 버튼 (우측 상단 고정) */}
        <button
          type="button"
          onClick={onClose}
          // [수정] hover 시 색상 변경 등 인터랙션 보강
          className="absolute top-6 right-6 text-text-secondary hover:text-text-primary transition-colors outline-none"
          aria-label="Close modal"
        >
          {/* [수정] CloseIcon 컴포넌트 사용 */}
          <CloseIcon className="w-6 h-6" />
        </button>

        {/* 내부 콘텐츠 */}
        {children}
      </div>
    </div>
  );
};