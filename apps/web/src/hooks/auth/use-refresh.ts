import { useState, useEffect } from 'react';
import { setAccessToken, removeAuthTokens } from '../../libs/axios';
import { refreshToken as apiRefreshToken } from '../../api/auth';
import { useAuthStore } from '../../store/auth';

// 로그인 리프레시 토큰에 대한 훅
export function useRefresh() {
	const [isInitialized, setIsInitialized] = useState(false);
	const { login, logout: storeLogout } = useAuthStore();

	useEffect(() => {
		const trySilentRefresh = async () => {
			// 로그인 상태 플래그가 없으면 갱신 시도하지 않음 (로그아웃 상태로 간주)
			const isAuthenticated = localStorage.getItem('isAuthenticated');
			if (!isAuthenticated) {
				setIsInitialized(true);
				return;
			}

			try {
				// HttpOnly 쿠키에 저장된 Refresh Token이 있다면 브라우저가 자동으로 요청에 포함
				// 클라이언트에서는 토큰 존재 여부를 알 수 없으므로, 일단 갱신을 시도하고 실패 시 로그아웃 처리
				const response = await apiRefreshToken(); // API refresh 함수 호출

				// 성공 시 새 토큰 저장 및 로그인 상태 복구
				const newAccessToken = response.data.access_token;
				setAccessToken(newAccessToken);

				// 백엔드 명세상 유저 정보가 없으므로 기본값으로 로그인 처리
				login({
					id: 0,
					email: '',
					name: '사용자',
				});
			} catch (error) {
				console.error('Silent refresh 실패:', error);
				// 갱신 실패는 유효한 리프레시 토큰이 없다는 의미이므로, 모든 로컬 인증 정보를 제거
				removeAuthTokens(); // 리프레시 실패 시 모든 토큰 삭제
				storeLogout(); // 로그인 상태 초기화
			} finally {
				setIsInitialized(true);
			}
		};

		trySilentRefresh();
	}, [login, storeLogout]); // login, storeLogout을 의존성 배열에 추가

	return { isInitialized };
}
