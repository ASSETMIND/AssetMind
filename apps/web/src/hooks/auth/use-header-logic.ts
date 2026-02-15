import { useState } from 'react';
import { useAuthStore } from '../../store/auth';
import { removeAuthTokens } from '../../libs/axios';
import { logout as apiLogout } from '../../api/auth';

export type ModalType = 'login' | 'signup' | 'findIdPw' | 'logout' | null;

export function useHeaderLogic() {
	const [modalType, setModalType] = useState<ModalType>(null);
	const { isLoggedIn, logout } = useAuthStore();

	const openModal = (type: ModalType) => setModalType(type);
	const closeAll = () => setModalType(null);

	const handleLogoutConfirm = async () => {
		try {
			// 서버에 로그아웃 요청 (리프레시 토큰 무효화)
			await apiLogout();
		} catch (error) {
			console.error('Server logout failed:', error);
			// 서버 로그아웃 실패해도 클라이언트 측 로그아웃은 진행
		} finally {
			removeAuthTokens(); // 클라이언트 측 토큰 삭제
			logout(); // Zustand 상태 업데이트
			closeAll(); // 모달 닫기
		}
	};

	return {
		state: {
			modalType,
			isLoggedIn,
		},
		actions: {
			openModal,
			closeAll,
			handleLogoutConfirm,
		},
	};
}
