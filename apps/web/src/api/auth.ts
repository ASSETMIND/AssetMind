import { axiosInstance } from '../libs/axios';
import type { LoginParams, LoginResponse, SignupParams } from '../types/auth';

// 회원가입 POST /auth/signup
export async function signup(data: SignupParams): Promise<void> {
	await axiosInstance.post('api/auth/signup', data);
}

// ID 중복 확인 true면 중복아이디 없음 / false면 중복아이디 있음
export async function checkIDDuplicate(email: string): Promise<boolean> {
	const { data } = await axiosInstance.get(`api/users?email=${email}`);
	return data.length === 0; // 데이터가 없으면 빈배열 반환 -> true
}

// 인증번호 이메일 발송 요청
export async function sendVerificationCode(email: string): Promise<void> {
	// body에 email을 담아서 POST 요청
	await axiosInstance.post('api/auth/send-code', { email });
}

// 인증번호 검증 요청
export async function verifyEmailCode(
	email: string,
	code: string,
): Promise<void> {
	await axiosInstance.post('api/auth/verify-code', { email, code });
}

export async function login(data: LoginParams): Promise<LoginResponse> {
	// <LoginResponse> 제네릭을 사용하여 리턴 타입을 명시
	const { data: response } = await axiosInstance.post<LoginResponse>(
		'api/auth/login',
		data,
	);
	return response;
}

// 소셜 로그인 api 함수
//  google | kakako
export const socialLogin = async (provider: string, code: string) => {
	// 백엔드 API 명세에 따라 url과 body는 달라질 수 있음
	const { data } = await axiosInstance.post(`/auth/login/${provider}`, {
		code,
	});
	return data;
};

// 토큰 갱신 API 함수 (AuthResponse 반환)
export const refreshToken = async (): Promise<LoginResponse> => {
	// LoginResponse가 AuthResponse를 확장하도록 변경됨
	const { data } = await axiosInstance.post<LoginResponse>('/auth/refresh'); // Refresh Token은 인터셉터에서 처리
	return data;
};

// 로그아웃 API 함수 (서버에 Refresh Token 무효화 요청)
export const logout = async (): Promise<void> => {
	// 클라이언트가 가지고 있는 리프레시 토큰을 서버에 보내 무효화하도록 요청합니다.
	// 리프레시 토큰은 HttpOnly Cookie로 관리되는 경우 서버가 자동으로 파싱합니다.
	// 그렇지 않은 경우, 요청 바디나 헤더에 명시적으로 포함해야 합니다.
	await axiosInstance.post('/auth/logout');
};
