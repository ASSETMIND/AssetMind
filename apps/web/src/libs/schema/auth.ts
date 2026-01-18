import { z } from 'zod';

/*
  비밀 번호 정규식
  최소 8자 이상 대소문자,특수문자 숫자 최소 한개 포함
*/
const passwordRegex = /^(?=.*[a-zA-Z])(?=.*[0-9])(?=.*[!@#$%^&*]).{8,}$/;

// 회원가입 스키마 정의
export const signupSchema = z.object({
	// 이메일 기반 아이디 입력
	id: z
		.string()
		.min(1, '이메일을 입력해주세요.')
		.email('올바른 이메일 형식이 아닙니다.'),

	// 정규식을 준수한 비밀번호 입력
	password: z
		.string()
		.min(8, '비밀번호는 8자 이상이어야 합니다.')
		.regex(passwordRegex, '영문, 숫자, 특수문자를 모두 포함해야 합니다.'),
	passwordConfirm: z.string().min(1, '비밀번호를 입력해주세요'),
});

// zod 스키마로부터 추론된 정적 타입
export type SignupSchemaType = z.infer<typeof signupSchema>;
