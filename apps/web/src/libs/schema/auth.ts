import { z } from 'zod';

/*
	비밀 번호 정규식
	최소 8자 이상 대소문자,특수문자 숫자 최소 한개 포함
*/
const passwordRegex = /^(?=.*[a-zA-Z])(?=.*[0-9])(?=.*[^a-zA-Z0-9]).{8,}$/;

// 회원가입 스키마 정의
export const signupSchema = z
	.object({
		// 이름 입력
		name: z.string().min(1, '이름을 입력해주세요.'),

		// 이메일 기반 아이디 입력
		email: z
			.string()
			.min(1, '이메일을 입력해주세요.')
			.email('올바른 이메일 형식이 아닙니다.'),

		// 인증번호 6자리 유효성 검사
		authCode: z.string().length(6, '인증번호 6자리를 입력해주세요.'),

		// 정규식을 준수한 비밀번호 입력
		password: z
			.string()
			.min(8, '비밀번호는 8자 이상이어야 합니다.')
			.regex(passwordRegex, '영문, 숫자, 특수문자를 모두 포함해야 합니다.'),

		passwordConfirm: z.string().min(1, '비밀번호를 입력해주세요'),
	})
	// 비밀번호 일치 로직
	.refine((data) => data.password === data.passwordConfirm, {
		path: ['passwordConfirm'], // 에러가 발생할 필드
		message: '비밀번호가 일치하지 않습니다.',
	});

// zod 스키마로부터 추론된 정적 타입
export type SignupSchemaType = z.infer<typeof signupSchema>;

// 로그인 스키마 정의
// 아이디는 이메일 형식인 것만 체크
// 비밀번호: 입력 여부만 체크
export const loginSchema = z.object({
	id: z
		.string()
		.min(1, '아이디를 입력해주세요.')
		.email('올바른 이메일 형식이 아닙니다.'),
	password: z.string().min(1, '비밀번호를 입력해주세요.'),
});

// 로그인 타입 추론
export type LoginSchemaType = z.infer<typeof loginSchema>;
