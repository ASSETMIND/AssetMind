import CloseIcon from '../icon/close';
import Portal from './portal';

// props로 클로즈 버튼과 내용을 정의
type Props = {
	children: React.ReactNode;
	onClose: () => void;
};

/*
	공통 모달 스타일 컴포넌트
	실제 컨텐츠는 children으로 주입받으며, 레이아웃과 오버레이, 블러 처리만 담당
 */

export default function Modal({ children, onClose }: Props) {
	/*
      Portal을 사용해 모달을 DOM 트리의 최상위(보통 document.body)로 이동시켜 렌더링
      부모 컴포넌트의 z-index 속성에 의해 모달이 잘리는 문제를 방지
    */
	return (
		<Portal>
			<div className='fixed inset-0 z-50 flex items-center justify-center bg-black/60 transition-opacity'>
				<div
					className='
          relative 
					min-w-md
					px-8
					py-10
          overflow-hidden 
          border
          bg-bg-modal 
          font-poppins
          mx-4
        '
				>
					<button
						onClick={onClose}
						className='absolute top-6 right-6 cursor-pointer' // 절대위치 정의로 자리고정
						aria-label='Close modal'
					>
						<CloseIcon />
					</button>

					{/* 자식 컨텐츠 영역 */}
					<div>{children}</div>
				</div>
			</div>
		</Portal>
	);
}
