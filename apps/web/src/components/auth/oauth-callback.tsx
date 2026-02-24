import { useEffect, useRef } from 'react';
import { useSocialLoginLogic } from '../../hooks/auth/use-social-login-logic';
import type { SocialProvider } from '../../hooks/auth/queries/use-social-login';

type Props = {
	provider: SocialProvider;
};

export default function OauthCallback({ provider }: Props) {
	const { actions } = useSocialLoginLogic();

	// useEffect가 두 번 실행되는 것을 방지
	const isCalled = useRef(false);

	useEffect(() => {
		if (!isCalled.current) {
			isCalled.current = true;
			actions.handleSocialCallback(provider);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [provider]);

	return (
		<div className='flex h-screen w-full flex-col items-center justify-center gap-6 bg-white'>
			{/* 로딩 스피너 UI */}
			<div className='relative flex h-16 w-16 items-center justify-center'>
				<div className='absolute h-full w-full animate-spin rounded-full border-4 border-gray-200 border-t-primary' />
			</div>

			<div className='flex flex-col items-center gap-2 text-gray-600'>
				<h2 className='text-xl font-bold text-gray-900'>
					{provider === 'google' ? 'Google' : 'Kakao'} 로그인 중
				</h2>
				<p className='text-sm'>잠시만 기다려주세요...</p>
			</div>
		</div>
	);
}
