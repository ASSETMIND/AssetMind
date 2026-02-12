import { useMutation } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { signup } from '../../../api/auth';
import type { SignupParams } from '../../../types/auth';

// 최종 회원가입 훅
export function useSignup() {
	return useMutation({
		mutationFn: (data: SignupParams) => signup(data),

		// 성공 시 실행될 로직
		onSuccess: () => {
			console.log('회원가입 성공!');
		},

		// 에러일 때 로직
		onError: (error: AxiosError) => {
			console.error('회원가입 실패:', error);
		},
	});
}
