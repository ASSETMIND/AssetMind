import { type ReactNode, useEffect, useRef, useCallback } from 'react';
import Portal from './portal';

interface ModalProps {
	isOpen: boolean;
	onClose: () => void;
	children: ReactNode;
	className?: string;
	title?: string;
	description?: string;
}

export default function Modal({
	isOpen,
	onClose,
	children,
	className,
	title,
	description,
}: ModalProps) {
	const previousFocusRef = useRef<HTMLElement | null>(null);
	const modalRef = useRef<HTMLDivElement>(null);
	const closeButtonRef = useRef<HTMLButtonElement>(null);

	const handleEscapeKey = useCallback((event: KeyboardEvent) => {
		if (event.key === 'Escape') onClose();
	}, [onClose]);

	const handleTabKey = useCallback((event: KeyboardEvent) => {
		if (event.key !== 'Tab' || !modalRef.current) return;

		const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
			'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
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
			previousFocusRef.current = document.activeElement as HTMLElement;
			document.body.style.overflow = 'hidden';
			setTimeout(() => { closeButtonRef.current?.focus(); }, 0);
			document.addEventListener('keydown', handleEscapeKey);
			document.addEventListener('keydown', handleTabKey);
		} else {
			document.body.style.overflow = '';
			previousFocusRef.current?.focus();
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
		<Portal>
			{/* 오버레이 */}
			<div
				style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(2px)' }}
			>
				{/* 백드롭 클릭 닫기 */}
				<div style={{ position: 'absolute', inset: 0 }} onClick={onClose} aria-hidden='true' />

				{/* 모달 컨테이너 */}
				<div
					ref={modalRef}
					className={className}
					role='dialog'
					aria-modal='true'
					aria-labelledby={title ? 'modal-title' : undefined}
					aria-describedby={description ? 'modal-description' : undefined}
					style={{ position: 'relative', zIndex: 1 }}
				>
					{/* 닫기 버튼 */}
					<button
						ref={closeButtonRef}
						type='button'
						onClick={onClose}
						aria-label='모달 닫기'
						style={{ position: 'absolute', top: '24px', right: '24px', background: 'none', border: 'none', cursor: 'pointer', color: '#9194A1', display: 'flex', alignItems: 'center' }}
					>
						<svg width='24' height='24' viewBox='0 0 24 24' fill='none'>
							<path d='M18 6L6 18M6 6l12 12' stroke='currentColor' strokeWidth='2' strokeLinecap='round' />
						</svg>
					</button>

					{title && <h2 id='modal-title' className='sr-only'>{title}</h2>}
					{description && <p id='modal-description' className='sr-only'>{description}</p>}

					{children}
				</div>
			</div>
		</Portal>
	);
}