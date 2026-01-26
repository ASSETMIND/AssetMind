import { useState, useEffect } from 'react';
import { axiosInstance, setAccessToken } from '../../libs/axios';
import { useAuthStore } from '../../store/auth';

export function useRefresh() {
	const [isInitialized, setIsInitialized] = useState(false);
	const { login, logout } = useAuthStore();

	useEffect(() => {
		const trySilentRefresh = async () => {
			try {
				// 새로고침 시 토큰 재발급 시도
				const { data } = await axiosInstance.post('/api/auth/refresh');

				// 성공 시 메모리에 토큰 설정
				setAccessToken(data.accessToken);

				// 로그인 상태 복구
				login(data.user);
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
