// 일반 자체 로그인
export interface LoginParams {
	id: string;
	password: string; // LoginResponse는 AuthResponse를 확장
}

// 소셜로그인
export interface SocialLoginParams {
	provider: 'kakao' | 'google' | null;
	code: string; // 인가 코드
}

// 회원가입
export interface SignupParams {
	id: string;
	password: string;
}

// 아이디 찾기
export interface FindIdParams {
	name: string;
	phone: string;
}

// 비밀번호 재설정 전 사용자 확인
export interface VerifyUserParams {
	email: string;
	phone: string;
}

// 비밀번호 재설정 파라미터
export interface ResetPasswordParams {
	token: string;
	newPassword: string;
}

// 통합 인증 성공 응답 로그인, 회원가입, 소셜로그인
export interface AuthResponse {
	accessToken: string;
	user: {
		id: number;
		email: string;
		name: string;
	};
}

// LoginResponse와 RefreshTokenResponse가 AuthResponse를 확장
export interface LoginResponse extends AuthResponse {}

// 비밀번호 재설정 토큰 응답
export interface VerifyTokenResponse {
	token: string;
}

// 아이디 찾기 응답
export interface FindIdResponse {
	email: string;
}

// 토큰 갱신 응답
export interface RefreshTokenResponse extends AuthResponse {}
