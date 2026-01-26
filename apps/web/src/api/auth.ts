// 임시로 api 주소를 만들고 생성해서 각각 201요청과 200요청을 받게 만듦
// json-server로 테스트 완료
// 최상위 폴더의 db.json, routes.json 파일에 목업서버 정의 > 테스트 진행

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
