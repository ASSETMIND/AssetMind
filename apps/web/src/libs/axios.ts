import axios from 'axios';

const ACCESS_TOKEN_KEY = 'accessToken';

export const getAccessToken = (): string | null => {
	return localStorage.getItem(ACCESS_TOKEN_KEY);
};

export const setAccessToken = (token: string | null) => {
	// Access Token은 Authorization 헤더에 항상 포함
	if (token) {
		localStorage.setItem(ACCESS_TOKEN_KEY, token);
		axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
	} else {
		localStorage.removeItem(ACCESS_TOKEN_KEY);
		delete axiosInstance.defaults.headers.common['Authorization'];
	}
};

// Access Token과 Refresh Token 모두 제거하는 함수
export const removeAuthTokens = () => {
	localStorage.removeItem(ACCESS_TOKEN_KEY);
	delete axiosInstance.defaults.headers.common['Authorization'];
	// HttpOnly 쿠키로 관리되는 Refresh Token은 서버 측 로그아웃 엔드포인트 호출을 통해 제거
};

export const axiosInstance = axios.create({
	baseURL: '/api', // 모든 요청이 /api로 시작하도록 설정 (Vite Proxy 트리거)
	headers: {
		'Content-Type': 'application/json',
	},
	withCredentials: true, // CORS 요청 시 쿠키를 주고받기 위해 필요 (HttpOnly Cookie 사용 시)
});

// 요청 인터셉터: Access Token을 Authorization 헤더에 추가
axiosInstance.interceptors.request.use((config) => {
	const token = getAccessToken();
	if (token) {
		config.headers.Authorization = `Bearer ${token}`;
	}
	return config;
});

// 응답 인터셉터: 401 에러 발생 시 토큰 갱신 시도
axiosInstance.interceptors.response.use(
	(response) => response,
	async (error) => {
		const originalRequest = error.config;
		// 401 에러이고, 이전에 재시도하지 않은 요청인 경우
		if (error.response?.status === 401 && !originalRequest._retry) {
			originalRequest._retry = true; // 재시도 플래그 설정

			try {
				// 토큰 갱신 API 호출 (Refresh Token은 서버에서 HttpOnly Cookie 등으로 관리,
				// 필요시 요청 바디/헤더에 명시적으로 포함하여 전송)
				const { data } = await axiosInstance.post('/auth/refresh'); // api/auth.ts의 refreshToken 함수 호출
				setAccessToken(data.accessToken);
				originalRequest.headers.Authorization = `Bearer ${data.accessToken}`; // 원래 요청 헤더 업데이트
				return axiosInstance(originalRequest); // 원래 요청 재시도
			} catch (refreshError) {
				console.error('Token refresh failed:', refreshError);
				removeAuthTokens(); // 갱신 실패 시 모든 토큰 삭제
				// useAuthStore().logout()은 React 컴포넌트/훅 외부에서 직접 호출하기 어려움
				// useRefresh 훅에서 이 상태를 감지하고 처리하도록 설계
				return Promise.reject(refreshError);
			}
		}
		return Promise.reject(error);
	},
);
