import CloseIcon from '../icon/close';
import Portal from './portal';

type Props = {
	children: React.ReactNode;
	onClose: () => void;
};

export default function Modal({ children, onClose }: Props) {
	const handleBgClick = (e: React.MouseEvent) => {
		if (e.target === e.currentTarget) {
			onClose();
		}
	};

	return (
		<Portal>
			<div
				onClick={handleBgClick}
				className='fixed inset-0 z-50 flex items-center justify-center bg-black/60 transition-opacity'
			>
				<div
					className='
          relative 
					min-w-md
					px-8
					py-10
          overflow-hidden 
          rounded-2xl 
          border border-border-modal 
          bg-bg-modal 
          font-poppins
          mx-4
        '
				>
					<button
						onClick={onClose}
						className='absolute top-6 right-6 text-text-sub hover:text-white transition-colors cursor-pointer'
						aria-label='Close modal'
					>
						<CloseIcon />
					</button>

					<div className='text-white'>{children}</div>
				</div>
			</div>
		</Portal>
	);
}
