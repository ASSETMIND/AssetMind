// 임시로 api 주소를 만들고 생성해서 각각 201요청과 200요청을 받게 만듦
// json-server로 테스트 완료
// 최상위 폴더의 db.json, routes.json 파일에 목업서버 정의 > 테스트 진행

import { axiosInstance } from '../libs/axios';
import type { SignupParams } from '../types/auth';

// 회원가입 POST /auth/signup
export async function signup(data: SignupParams): Promise<void> {
	await axiosInstance.post('api/auth/signup', data);
}

// ID 중복 확인 true면 중복아이디 없음 / false면 중복아이디 있음
export async function checkIDDuplicate(email: string): Promise<boolean> {
	const { data } = await axiosInstance.get(`api/users?email=${email}`);
	return data.length === 0; // 데이터가 없으면 빈배열 반환 -> true
}
