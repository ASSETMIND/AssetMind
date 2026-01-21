import { useState } from 'react';
import Button from '../common/button';
import LogoIcon from '../icon/logo';
import LoginModal from '../auth/login-modal';
import SignupModal from '../auth/signup-modal';

// 모달 타입정의 어떤 모달을 띄울지 선택함
type ModalType = 'login' | 'signup' | 'findIdPw' | null;

/*
 	모달 상태 타입 정의
 	유니언 타입을 사용하여 동시에 오직 하나의 모달만 활성화되도록 강제함
	여러 개의 boolean state(isOpenLogin, isOpenSignup 등)를 사용할 때 발생할 수 있는 에러 방지
 */

export default function Header() {
	const [modalType, setModalType] = useState<ModalType>(null);

	// 모달 on, off
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

			{/* 조건부 렌더링으로 각 조건에 맞는 모달만 띄움 */}
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
