// src/components/common/Modal.tsx
import type { ReactNode } from "react";
import { X } from "lucide-react";
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

      {/* 모달 컨테이너 (index.css 스타일 적용) */}
      <div className={cn("modal-container", className)}>
        {/* 닫기 버튼 (우측 상단 고정) */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-6 right-6 text-text-primary hover:opacity-70 transition-opacity outline-none"
          aria-label="Close modal"
        >
          <X className="w-6 h-6" />
        </button>

        {/* 내부 콘텐츠 */}
        {children}
      </div>
    </div>
  );
};