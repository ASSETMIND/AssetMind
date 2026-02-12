import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { loginSchema, type LoginSchemaType } from '../../libs/schema/auth';
import { useLogin } from './queries/use-login';
import { setAccessToken } from '../../libs/axios';
import { useAuthStore } from '../../store/auth';

interface Props {
	onSuccess?: () => void;
	onError?: (message: string) => void;
}

// 전체적인 로그인 비즈니스 로직에 대한 훅
export function useLoginLogic({ onSuccess, onError }: Props = {}) {
	const { login } = useAuthStore();

	const formMethods = useForm<LoginSchemaType>({
		resolver: zodResolver(loginSchema),
		mode: 'onSubmit',
		defaultValues: {
			email: '',
			password: '',
		},
	});

	const { handleSubmit, setError } = formMethods;
	// 리액트쿼리 뮤테이션
	const { mutate: loginMutate, isPending: isLoggingIn } = useLogin();

	// 제출 핸들러
	const onSubmit = handleSubmit(
		(data) => {
			if (isLoggingIn) return;
			loginMutate(
				{ email: data.email, password: data.password },
				{
					onSuccess: (response) => {
						// response 타입은 LoginResponse (success, message, data)
						const accessToken = response.data?.access_token;
						if (accessToken) {
							setAccessToken(accessToken);

							login({
								id: 0,
								email: data.email,
								name: '사용자',
							});
						}

						onSuccess?.();
					},
					onError: (error: any) => {
						const status = error?.response?.status;
						let errorMessage: string;

						if (status === 401 || status === 404) {
							errorMessage = '아이디 또는 비밀번호를 확인해주세요.';
						} else {
							errorMessage = '회원이 아닙니다. 회원가입을 진행해 주세요';
						}

						setError('password', {
							type: 'manual',
							message: errorMessage,
						});

						onError?.(errorMessage);
					},
				},
			);
		},
		(errors) => {
			console.error('로그인 유효성 검사 실패:', errors);
		},
	);

	return {
		formMethods,
		state: {
			isLoggingIn,
		},
		actions: {
			onSubmit,
		},
	};
}
