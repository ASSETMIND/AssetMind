import axios, { type AxiosInstance } from 'axios';

/*
	axios 인스턴스를 불러오는 함수로 /api 폴더에서 사용 -> 다른 설정이 필요없게 만듦
*/

// 환경변수에서 API 주소를 가져오거나 기본값 사용
const BASE_URL = 'http://localhost:4000';

export const axiosInstance: AxiosInstance = axios.create({
	baseURL: BASE_URL,
	headers: {
		'Content-Type': 'application/json',
	},
	// 토큰을 주고받으려면 true로 설정해 모두 허용
	withCredentials: true,
});
