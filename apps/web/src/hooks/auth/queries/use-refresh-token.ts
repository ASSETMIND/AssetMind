import { useMutation } from '@tanstack/react-query';
import { refreshToken } from '../../../api/auth';

// 리프레시 토큰 훅
export function useRefreshToken() {
	return useMutation({
		mutationFn: refreshToken,
	});
}
