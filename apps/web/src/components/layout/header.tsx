import { useState } from 'react';
import Button from '../common/button';
import LogoIcon from '../icon/logo';
import LoginModal from '../auth/login-modal';
import SignupModal from '../auth/signup-modal';
import { useAuthStore } from '../../store/auth';
import { removeAuthTokens } from '../../libs/axios';
import { logout as apiLogout } from '../../api/auth';

// 모달 타입정의 어떤 모달을 띄울지 선택함
type ModalType = 'login' | 'signup' | 'findIdPw' | null;

export default function Header() {
	const [modalType, setModalType] = useState<ModalType>(null);

	// Zustand에서 로그인 상태와 로그아웃 액션만 가져옴
	const { isLoggedIn, logout } = useAuthStore();

	// 모달 on, off
	const closeAll = () => setModalType(null);

	// 로그아웃 핸들러
	const handleLogout = async () => {
		try {
			// 서버에 로그아웃 요청 (리프레시 토큰 무효화)
			await apiLogout();
		} catch (error) {
			console.error('Server logout failed:', error);
			// 서버 로그아웃 실패해도 클라이언트 측 로그아웃은 진행
		} finally {
			removeAuthTokens(); // 클라이언트 측 토큰 삭제 (액세스, 리프레시 모두)
			logout(); // Zustand 상태 업데이트
		}
	};

	return (
		<>
			<header className='flex w-full items-center justify-between px-4 py-4'>
				<LogoIcon />

				{/* 로그인 상태(isLoggedIn)에 따라 버튼 분기 렌더링 */}
				{isLoggedIn ? (
					<Button
						size='sm'
						className='w-auto px-3' // 로그아웃 텍스트 길이에 맞춰 너비 조정
						onClick={handleLogout}
					>
						로그아웃
					</Button>
				) : (
					<Button
						size='sm'
						className='w-16'
						onClick={() => setModalType('login')}
					>
						로그인
					</Button>
				)}
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
