import { useMutation } from '@tanstack/react-query';
import { checkIDDuplicate } from '../../api/auth';

// 아이디 중복확인 훅
export function useCheckID() {
	return useMutation({
		mutationFn: (email: string) => checkIDDuplicate(email),
	});
}
