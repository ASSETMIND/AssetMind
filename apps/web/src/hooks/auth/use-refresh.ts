import { useState, useEffect } from 'react';
import { setAccessToken, getAccessToken } from '../../libs/axios';
import { refreshToken } from '../../api/auth';
import { useAuthStore } from '../../store/auth';

// 로그인 리프레시 토큰에 대한 훅
export function useRefresh() {
	const [isInitialized, setIsInitialized] = useState(false);
	const { login, logout } = useAuthStore();

	useEffect(() => {
		const trySilentRefresh = async () => {
			try {
				const storedAccessToken = getAccessToken();
				if (storedAccessToken) {
					// 기존 액세스 토큰이 있다면, 이를 사용하여 갱신 시도
					// refreshToken 함수는 내부적으로 axiosInstance를 사용하여 /auth/refresh 엔드포인트를 호출
					const data = await refreshToken();

					// 성공 시 새 토큰 저장 및 로그인 상태 복구
					setAccessToken(data.accessToken);
					login(data.user);
				} else {
					// 저장된 토큰이 없으면, 로그인 상태가 아님을 명확히 함
					logout();
				}
			} catch (error) {
				setAccessToken(null); // 실패시 로그인 X
				logout();
			} finally {
				setIsInitialized(true);
			}
		};

		trySilentRefresh();
	}, []);

	return { isInitialized };
}
