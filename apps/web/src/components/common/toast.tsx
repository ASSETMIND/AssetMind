/*
	토스트 컴포넌트는 추후 보수 예정
	현재 토스트를 사용하는 곳이 없어 상세 테스트 진행 안함
	시간 2.5초 유지, 닫기버튼 있음 
*/

import { useEffect, useState } from 'react';
import Portal from './portal';
import CloseIcon from '../icon/close';

type Props = {
	children: React.ReactNode;
	onClose: () => void;
	duration?: number;
};

export default function Toast({ children, onClose, duration = 2500 }: Props) {
	const [isClosing, setIsClosing] = useState(false);

	// 임시 로직임 확정로직 X
	useEffect(() => {
		const timer = setTimeout(() => {
			setIsClosing(true);
		}, duration);
		return () => clearTimeout(timer);
	}, [duration]);

	useEffect(() => {
		if (isClosing) {
			const timer = setTimeout(() => {
				onClose();
			}, 300);
			return () => clearTimeout(timer);
		}
	}, [isClosing, onClose]);

	const handleClose = () => {
		setIsClosing(true);
	};

	return (
		<Portal type='toast'>
			<div className='fixed bottom-8 left-0 right-0 z-50 flex justify-center'>
				<div
					className={`
            mx-4 max-w-sm
            flex items-center justify-between gap-4
            rounded-xl border bg-bg-modal 
            pl-6 pr-4 py-4
            transform transition-all duration-300 ease-in-out
            ${
							isClosing
								? 'translate-y-4 opacity-0'
								: 'translate-y-0 opacity-100'
						}
          `}
				>
					<p className='flex-1 text-sm font-medium'>{children}</p>
					<button
						type='button'
						onClick={handleClose}
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
