import { useMutation } from '@tanstack/react-query';
import { login } from '../../api/auth';
import type { LoginParams, LoginResponse } from '../../types/auth';

export const useLogin = () => {
	return useMutation<LoginResponse, Error, LoginParams>({
		mutationFn: login,
	});
};
