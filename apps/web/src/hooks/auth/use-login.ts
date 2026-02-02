import { useMutation } from '@tanstack/react-query';
import { login } from '../../api/auth';
import type { LoginParams, LoginResponse } from '../../types/auth';

// 로그인 뮤테이션 훅
export const useLogin = () => {
	return useMutation<LoginResponse, Error, LoginParams>({
		mutationFn: login,
	});
};
