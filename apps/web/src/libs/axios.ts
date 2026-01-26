import axios, {
	AxiosError,
	type AxiosResponse,
	type InternalAxiosRequestConfig,
} from 'axios';

/*
  [토큰 관리 전략]
  Access Token 이 파일 내부 변수(accessToken)에 저장 (메모리)
  Refresh Token 브라우저 쿠키(httpOnly)에 저장 (자동 전송됨)
*/

const BASE_URL = 'http://localhost:4000';

//  Axios 인스턴스 생성
export const axiosInstance = axios.create({
	baseURL: BASE_URL,
	headers: { 'Content-Type': 'application/json' },
	withCredentials: true, // 쿠키 자동 전송 설정
});

// Access Token을 저장할 변수 (메모리)
let accessToken: string | null = null;

// 외부(로그인 로직 등)에서 토큰을 설정하는 함수
export const setAccessToken = (token: string | null) => {
	accessToken = token;
};

// 로그아웃 함수
export const removeAccessToken = () => {
	accessToken = null;
};

// [요청 인터셉터] 모든 요청 헤더에 Access Token 주입
axiosInstance.interceptors.request.use(
	(config: InternalAxiosRequestConfig) => {
		if (accessToken && config.headers) {
			config.headers.Authorization = `Bearer ${accessToken}`;
		}
		return config;
	},
	(error) => Promise.reject(error),
);

// [응답 인터셉터] 401 에러(토큰 만료) 처리
axiosInstance.interceptors.response.use(
	(response: AxiosResponse) => response,
	async (error: AxiosError) => {
		const originalRequest = error.config as InternalAxiosRequestConfig & {
			_retry?: boolean;
		};

		// 401 에러이고, 아직 재시도를 안 했다면
		if (error.response?.status === 401 && !originalRequest._retry) {
			originalRequest._retry = true; // 재시도 플래그 설정 (무한 루프 방지)

			try {
				// 토큰 재발급 요청 (Refresh Token은 쿠키에 있어서 자동 전송됨)
				const { data } = await axiosInstance.post<{ accessToken: string }>(
					'/api/auth/refresh',
				);

				//  새 토큰 저장
				setAccessToken(data.accessToken);

				//  실패했던 원래 요청의 헤더 업데이트 후 재요청
				if (originalRequest.headers) {
					originalRequest.headers.Authorization = `Bearer ${data.accessToken}`;
				}
				return axiosInstance(originalRequest);
			} catch (refreshError) {
				console.error('Refresh token expired');
				setAccessToken(null);

				return Promise.reject(refreshError);
			}
		}

		return Promise.reject(error);
	},
);
