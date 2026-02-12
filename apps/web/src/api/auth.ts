import { axiosInstance, removeAuthTokens } from '../libs/axios';
import type {
	LoginParams,
	LoginResponse,
	LogoutResponse,
	ReissueTokenResponse,
	SignupParams,
	VerifyEmailResponse,
} from '../types/auth';

// 회원가입 POST
export async function signup(data: SignupParams): Promise<void> {
	await axiosInstance.post('auth/register', data);
}

/**
 * 이메일 사용 가능 여부를 확인합니다. (회원가입 시 중복 체크)
 * @param email 확인할 이메일
 * @returns 사용 가능하면 true, 중복이면 false
 */
export async function checkEmailAvailability(email: string): Promise<boolean> {
	const { data } = await axiosInstance.get<{ data: boolean }>(
		'/auth/check-email',
		{
			params: { email },
		},
	);
	return !data.data; // API 응답: data:true (중복) -> false 반환 / data:false (사용가능) -> true 반환
}

// 인증번호 이메일 발송 요청
export async function sendVerificationCode(email: string): Promise<void> {
	// body에 email을 담아서 POST 요청
	await axiosInstance.post('auth/code', { email });
}

// 인증번호 검증 요청
export async function verifyEmailCode(
	email: string,
	code: string,
): Promise<string> {
	const { data } = await axiosInstance.post<VerifyEmailResponse>(
		'auth/code/verify',
		{ email, code },
	);

	const token = data?.data?.sign_up_token;
	if (!token) throw new Error(data?.message || '인증 토큰을 찾을 수 없습니다.');
	return token;
}

export async function login(data: LoginParams): Promise<LoginResponse> {
	// <LoginResponse> 제네릭을 사용하여 리턴 타입을 명시
	const { data: response } = await axiosInstance.post<LoginResponse>(
		'auth/login',
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
export const refreshToken = async (): Promise<ReissueTokenResponse> => {
	const { data } =
		await axiosInstance.post<ReissueTokenResponse>('/auth/reissue'); // Refresh Token은 인터셉터에서 처리
	return data;
};

// 로그아웃 API 함수 (서버에 Refresh Token 무효화 요청)
export const logout = async (): Promise<void> => {
	await axiosInstance.post<LogoutResponse>('/auth/logout');
	removeAuthTokens();
};
