import { useMutation } from '@tanstack/react-query';
import { socialLogin } from '../../../api/auth';
import type { AuthResponse } from '../../../types/auth';

export type SocialProvider = 'kakao' | 'google';

// 소셜 로그인 훅
export function useSocialLogin() {
	return useMutation({
		mutationFn: ({
			provider,
			code,
		}: {
			provider: SocialProvider;
			code: string;
		}) => socialLogin(provider, code) as Promise<AuthResponse>,
	});
}
