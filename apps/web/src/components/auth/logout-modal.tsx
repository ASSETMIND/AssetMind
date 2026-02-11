import Modal from '../common/modal';
import Button from '../common/button';

// UX 경험을 위해 넣은 로그아웃 확인 모달
type Props = {
	onClose: () => void;
	onConfirm: () => void;
};

export default function LogoutModal({ onClose, onConfirm }: Props) {
	return (
		<Modal onClose={onClose}>
			<div className='flex flex-col w-full px-2 gap-6'>
				<p>정말 로그아웃 하시겠습니까?</p>
				<div className='flex gap-4 w-full justify-center'>
					<Button size='sm' onClick={onClose}>
						취소
					</Button>
					<Button size='sm' onClick={onConfirm}>
						확인
					</Button>
				</div>
			</div>
		</Modal>
	);
}
