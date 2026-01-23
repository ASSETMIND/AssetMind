import { useMutation } from '@tanstack/react-query';
import { sendVerificationCode, verifyEmailCode } from '../../api/auth';

// 인증번호 발송 훅
export const useSendEmailCode = () => {
	return useMutation({
		mutationFn: (email: string) => sendVerificationCode(email),
	});
};

// 인증번호 검증 훅
export const useVerifyEmailCode = () => {
	return useMutation({
		mutationFn: ({ email, code }: { email: string; code: string }) =>
			verifyEmailCode(email, code),
	});
};
