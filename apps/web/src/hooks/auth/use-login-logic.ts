import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate } from 'react-router-dom';
import { loginSchema, type LoginSchemaType } from '../../libs/schema/auth';
import { useLogin } from './use-login';
import { setAccessToken } from '../../libs/axios';
import { useAuthStore } from '../../store/auth';

type Props = {
	onClose: () => void;
};

// 전체적인 로그인 비즈니스 로직에 대한 훅
export function useLoginLogic({ onClose }: Props) {
	const navigate = useNavigate();
	const [toastMessage, setToastMessage] = useState<string | null>(null);
	const { login } = useAuthStore();

	const formMethods = useForm<LoginSchemaType>({
		resolver: zodResolver(loginSchema),
		mode: 'onSubmit',
		defaultValues: {
			id: '',
			password: '',
		},
	});

	const { handleSubmit, setError } = formMethods;
	// 리액트쿼리 뮤테이션
	const { mutate: loginMutate, isPending: isLoggingIn } = useLogin();

	// 제출 핸들러
	const onSubmit = handleSubmit((data) => {
		loginMutate(
			{ id: data.id, password: data.password },
			{
				onSuccess: (response) => {
					// response 타입은 AuthResponse (LoginResponse)
					if (response.accessToken) {
						setAccessToken(response.accessToken);
					}
					// Refresh Token은 백엔드에서 HttpOnly 쿠키로 설정하므로 클라이언트에서 처리하지 않음
					login(response.user || { id: 0, email: data.id });

					// [성공 메시지]
					setToastMessage('로그인 되었습니다.');

					onClose();
					navigate('/');
				},
				onError: (error: any) => {
					const status = error?.response?.status;

					if (status === 401 || status === 404) {
						setError('password', {
							type: 'manual',
							message: '아이디 또는 비밀번호를 확인해주세요.',
						});
					} else {
						setError('password', {
							type: 'manual',
							message: '회원이 아닙니다. 회원가입을 진행해 주세요',
						});
					}
				},
			},
		);
	});

	return {
		formMethods,
		state: {
			isLoggingIn,
			toastMessage,
		},
		actions: {
			onSubmit,
			setToastMessage,
		},
	};
}
