import { useMutation } from '@tanstack/react-query';
import {
	sendVerificationCode,
	verifyEmailCode,
	checkEmailAvailability,
} from '../../api/auth';

// 이메일 중복 확인 (사용 가능 여부) 훅
export function useCheckEmail() {
	return useMutation({
		mutationFn: (email: string) => checkEmailAvailability(email),
	});
}

// 인증번호 발송 훅
export function useSendEmailCode() {
	return useMutation({
		mutationFn: (email: string) => sendVerificationCode(email),
	});
}

// 인증번호 검증 훅
export function useVerifyEmailCode() {
	return useMutation({
		mutationFn: ({ email, code }: { email: string; code: string }) =>
			verifyEmailCode(email, code),
	});
}
