import Button from '../common/button';
import LogoIcon from '../icon/logo';
import LoginModal from '../auth/login-modal';
import SignupModal from '../auth/signup-modal';
import LogoutModal from '../auth/logout-modal';
import { useHeaderLogic } from '../../hooks/auth/use-header-logic';

export default function Header() {
	const { state, actions } = useHeaderLogic();
	const { modalType, isLoggedIn } = state;
	const { openModal, closeAll, handleLogoutConfirm } = actions;

	return (
		<>
			<header className='flex w-full items-center justify-between px-4 py-4'>
				<LogoIcon />

				{/* 로그인 상태(isLoggedIn)에 따라 버튼 분기 렌더링 */}
				{isLoggedIn ? (
					<Button
						size='sm'
						className='w-auto px-3' // 로그아웃 텍스트 길이에 맞춰 너비 조정
						onClick={() => openModal('logout')}
					>
						로그아웃
					</Button>
				) : (
					<Button size='sm' className='w-16' onClick={() => openModal('login')}>
						로그인
					</Button>
				)}
			</header>

			{/* 조건부 렌더링으로 각 조건에 맞는 모달만 띄움 */}
			{modalType === 'login' && (
				<LoginModal
					onClose={closeAll}
					onClickSignup={() => openModal('signup')}
					onClickFindIdPw={() => openModal('findIdPw')}
				/>
			)}

			{modalType === 'signup' && (
				<SignupModal
					onClose={closeAll}
					onClickLogin={() => openModal('login')}
				/>
			)}

			{modalType === 'logout' && (
				<LogoutModal onClose={closeAll} onConfirm={handleLogoutConfirm} />
			)}
		</>
	);
}
