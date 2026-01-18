import { useEffect, useState } from 'react';
import Portal from './portal';
import CloseIcon from '../icon/close';

type Props = {
	children: React.ReactNode;
	onClose: () => void;
	duration?: number;
};

export default function Toast({ children, onClose, duration = 2000 }: Props) {
	const [isClosing, setIsClosing] = useState(false);

	// 자동 닫힘 타이머 (기본 2초)
	useEffect(() => {
		setIsClosing(false);
		const timer = setTimeout(() => {
			setIsClosing(true);
		}, duration);
		return () => clearTimeout(timer);
	}, [duration, children]); // 의존성 배열에 children을 추가해서 강제 초기화

	return (
		<Portal type='toast'>
			<div className='fixed top-6 left-0 right-0 z-50 flex justify-center pointer-events-none'>
				<div
					onTransitionEnd={() => isClosing && onClose()}
					className={`
            pointer-events-auto
            flex items-center justify-between gap-4
            min-w-sm p-4
            bg-black border border-border-modal
            ease-in-out
            ${
							isClosing
								? 'opacity-0 -translate-y-6'
								: 'opacity-100 translate-y-0'
						}
          `}
				>
					<p className='flex-1 text-sm font-bold'>{children}</p>

					<button
						type='button'
						onClick={() => setIsClosing(true)}
						className='flex items-center justify-center'
						aria-label='닫기'
					>
						<CloseIcon />
					</button>
				</div>
			</div>
		</Portal>
	);
}
