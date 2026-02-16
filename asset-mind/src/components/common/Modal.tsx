import { type ReactNode, useEffect, useRef, useCallback } from "react";
import { CloseIcon } from "../icons/CloseIcon"; 
import { cn } from "../../lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
  title?: string;
  description?: string;
}

export const Modal = ({ 
  isOpen, 
  onClose, 
  children, 
  className,
  title,
  description
}: ModalProps) => {
  // [접근성] 모달이 열리기 전 포커스된 요소 저장
  const previousFocusRef = useRef<HTMLElement | null>(null);
  // [접근성] 모달 컨테이너 ref
  const modalRef = useRef<HTMLDivElement>(null);
  // [접근성] 닫기 버튼 ref
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // [접근성] ESC 키로 모달 닫기
  const handleEscapeKey = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      onClose();
    }
  }, [onClose]);

  // [접근성] Focus Trap 구현
  const handleTabKey = useCallback((event: KeyboardEvent) => {
    if (event.key !== 'Tab' || !modalRef.current) return;

    const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (event.shiftKey) {
      if (document.activeElement === firstElement) {
        lastElement?.focus();
        event.preventDefault();
      }
    } else {
      if (document.activeElement === lastElement) {
        firstElement?.focus();
        event.preventDefault();
      }
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      // [접근성] 모달 열릴 때
      previousFocusRef.current = document.activeElement as HTMLElement;
      document.body.style.overflow = 'hidden';
      
      setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 0);

      document.addEventListener('keydown', handleEscapeKey);
      document.addEventListener('keydown', handleTabKey);
    } else {
      // [접근성] 모달 닫힐 때
      document.body.style.overflow = '';
      
      if (previousFocusRef.current) {
        previousFocusRef.current.focus();
      }

      document.removeEventListener('keydown', handleEscapeKey);
      document.removeEventListener('keydown', handleTabKey);
    }

    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEscapeKey);
      document.removeEventListener('keydown', handleTabKey);
    };
  }, [isOpen, handleEscapeKey, handleTabKey]);

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
      <div 
        ref={modalRef}
        className={cn("modal-container", className)}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? "modal-title" : undefined}
        aria-describedby={description ? "modal-description" : undefined}
      >
        {/* 닫기 버튼 (우측 상단 고정) */}
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          className="absolute top-6 right-6 text-text-secondary hover:text-text-primary transition-colors outline-none focus-visible:ring-2 focus-visible:ring-border-inputFocus focus-visible:ring-offset-2 focus-visible:ring-offset-background-surface rounded"
          aria-label="모달 닫기"
        >
          <CloseIcon className="w-6 h-6" />
        </button>

        {title && (
          <h2 id="modal-title" className="sr-only">
            {title}
          </h2>
        )}
        {description && (
          <p id="modal-description" className="sr-only">
            {description}
          </p>
        )}

        {/* 내부 콘텐츠 */}
        {children}
      </div>
    </div>
  );
};
