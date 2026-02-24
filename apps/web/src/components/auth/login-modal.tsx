import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../common/modal';
import Button from '../common/button';
import AuthInput from '../auth/auth-input';
import GoogleIcon from '../icon/google';
import KakaoIcon from '../icon/kakao';
import Toast from '../common/toast';
import { useLoginLogic } from '../../hooks/auth/use-login-logic';
import { useSocialLoginLogic } from '../../hooks/auth/use-social-login-logic';

/*
  로그인 화면 UI 구성을 담당하는 view 역할의 컴포넌트
  실제 로직이나 라우팅은 props로 주입받은 함수에 위임
 */

type Props = {
	onClose: () => void;
	onClickSignup: () => void;
	onClickFindIdPw: () => void;
};

export default function LoginModal({
	onClose,
	onClickSignup,
	onClickFindIdPw,
}: Props) {
	const navigate = useNavigate();
	const [toastMessage, setToastMessage] = useState<string | null>(null);

	// 자체적인 일반로그인
	const {
		formMethods,
		state: loginState,
		actions: loginActions,
	} = useLoginLogic({
		onSuccess: () => {
			setToastMessage('로그인 되었습니다.');
			setTimeout(() => {
				onClose();
				navigate('/');
			}, 1000);
		},
		onError: (message) => {
			setToastMessage(message);
		},
	});

	// 소셜 로그인
	const { state: socialState, actions: socialActions } = useSocialLoginLogic();

	const {
		register,
		formState: { errors },
	} = formMethods;

	return (
		<Modal onClose={onClose}>
			<div className='flex flex-col items-center w-full px-2'>
				<h2 className='text-4xl font-bold mb-4'>LOGIN</h2>
				<p className='mb-6'>AssetMind에 오신 것을 환영합니다.</p>
				<form
					onSubmit={loginActions.onSubmit}
					className='w-full flex flex-col gap-6'
				>
					{/* 1. 아이디 입력 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>아이디</label>
						<AuthInput
							type='email'
							placeholder='아이디를 입력해 주세요.'
							// 에러 메시지 전달
							errorMessage={errors.email?.message}
							className={errors.email ? 'border-red-500' : ''}
							{...register('email')}
						/>
					</div>

					{/* 2. 비밀번호 입력 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>비밀번호</label>
						<AuthInput
							type='password'
							placeholder='비밀번호를 입력해 주세요.'
							errorMessage={errors.password?.message}
							className={errors.password ? 'border-red-500' : ''}
							{...register('password')}
						/>
					</div>

					{/* Submit 버튼 */}
					<Button
						className='mt-2'
						size='lg'
						type='submit'
						disabled={loginState.isLoggingIn || socialState.isRedirecting}
					>
						{loginState.isLoggingIn ? '로그인 중...' : '로그인'}
					</Button>
				</form>

				{/* 하단 바로가기 버튼들 */}
				<div className='mt-4 flex gap-4'>
					<button className='cursor-pointer' onClick={onClickFindIdPw}>
						아이디/비밀번호 찾기
					</button>
					<p>|</p>
					<button className='cursor-pointer' onClick={onClickSignup}>
						회원가입
					</button>
				</div>

				<div className='mt-4 w-full'>
					<div className='relative flex w-full items-center justify-center'>
						<div className='absolute w-full border-t' />
						<span className='relative bg-bg-modal px-3 font-bold'>
							or continue with
						</span>
					</div>

					{/* 소셜 아이콘 버튼들 */}
					<div className='mt-4 flex justify-center gap-8'>
						<button
							onClick={() => socialActions.handleSocialLogin('google')}
							className='disabled:opacity-50 transition-transform active:scale-95'
						>
							<GoogleIcon />
						</button>

						<button
							onClick={() => socialActions.handleSocialLogin('kakao')}
							className='disabled:opacity-50 transition-transform active:scale-95'
						>
							<KakaoIcon />
						</button>
					</div>
				</div>
			</div>

			{toastMessage && (
				<Toast onClose={() => setToastMessage(null)}>{toastMessage}</Toast>
			)}
		</Modal>
	);
}
