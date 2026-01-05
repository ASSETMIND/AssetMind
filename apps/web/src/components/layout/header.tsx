import { useState } from 'react';
import Button from '../common/button';
import LogoIcon from '../icon/logo';
import LoginModal from '../auth/login-modal';
import SignupModal from '../auth/signup-modal';

type ModalType = 'login' | 'signup' | 'findIdPw' | null;

export default function Header() {
	const [modalType, setModalType] = useState<ModalType>(null);

	const closeAll = () => setModalType(null);

	return (
		<>
			<header className='flex w-full items-center justify-between px-4 py-4'>
				<LogoIcon />
				<Button
					size='sm'
					className='w-16'
					onClick={() => setModalType('login')}
				>
					로그인
				</Button>
			</header>

			{modalType === 'login' && (
				<LoginModal
					onClose={closeAll}
					onClickSignup={() => setModalType('signup')}
					onClickFindIdPw={() => setModalType('findIdPw')}
				/>
			)}

			{modalType === 'signup' && (
				<SignupModal
					onClose={closeAll}
					onClickLogin={() => setModalType('login')}
				/>
			)}
		</>
	);
}
