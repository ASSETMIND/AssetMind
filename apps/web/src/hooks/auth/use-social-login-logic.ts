import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { KAKAO_AUTH_URL, GOOGLE_AUTH_URL } from '../../libs/constants/auth';
import { useAuthStore } from '../../store/auth';
import { setAccessToken } from '../../libs/axios';
import {
	useSocialLogin,
	type SocialProvider,
} from './queries/use-social-login';

// 제공자별 URL을 맵으로 관리
const SOCIAL_AUTH_URLS: Record<SocialProvider, string> = {
	kakao: KAKAO_AUTH_URL,
	google: GOOGLE_AUTH_URL,
};

export function useSocialLoginLogic() {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();
	const { login } = useAuthStore();

	// 상태 정의
	const [isRedirecting, setIsRedirecting] = useState(false);
	const [toastMessage, setToastMessage] = useState<string | null>(null);

	// 로그인 페이지 -> 소셜 리다이렉트
	const handleSocialLogin = (provider: SocialProvider) => {
		setIsRedirecting(true);
		window.location.href = SOCIAL_AUTH_URLS[provider];
	};

	const { mutate: processLogin, isPending: isProcessing } = useSocialLogin();

	// 콜백 페이지에서 실행할 함수
	const handleSocialCallback = (provider: SocialProvider) => {
		const code = searchParams.get('code');
		const error = searchParams.get('error');

		if (error) {
			console.error(`소셜 로그인 에러: ${error}`);
			setToastMessage(
				'로그인 과정에서 오류가 발생했습니다. 다시 시도해주세요.',
			);
			navigate('/', { replace: true });
			return;
		}

		if (code) {
			processLogin(
				{ provider, code },
				{
					onSuccess: (response) => {
						// 토큰 저장 및 로그인 처리
						if (response.accessToken) {
							setAccessToken(response.accessToken);
						}
						login(response.user);
						// 메인 페이지로 이동
						navigate('/', { replace: true });
					},
					onError: (error) => {
						console.error('소셜 로그인 실패:', error);
						setToastMessage('로그인에 실패했습니다. 다시 시도해주세요.');
						navigate('/', { replace: true }); // 실패 시 메인페이지로 이동
					},
				},
			);
		} else {
			setToastMessage('인증 정보를 받아오지 못했습니다. 다시 시도해주세요.');
			navigate('/', { replace: true });
		}
	};

	return {
		state: {
			isRedirecting, // 리다이렉트 중
			isProcessing, // API 통신 용
			toastMessage,
		},
		actions: {
			handleSocialLogin,
			handleSocialCallback,
			setToastMessage,
		},
	};
}
