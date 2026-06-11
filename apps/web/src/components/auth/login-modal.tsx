import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../common/modal';
import Button from '../common/button';
import Input from '../common/input';
import Toast from '../common/toast';
import EyeOn from '../icon/eye-on';
import EyeOff from '../icon/eye-off';
import GoogleIcon from '../icon/google';
import KakaoIcon from '../icon/kakao';
import { useLoginLogic } from '../../hooks/auth/use-login-logic';
import { useSocialLoginLogic } from '../../hooks/auth/use-social-login-logic';

type Props = {
	onClose: () => void;
	onClickSignup: () => void;
	onClickFindIdPw: () => void;
};

export default function LoginModal({ onClose, onClickSignup, onClickFindIdPw }: Props) {
	const navigate = useNavigate();
	const [toastMessage, setToastMessage] = useState<string | null>(null);
	const [showPw, setShowPw] = useState(false);

	const { formMethods, state: loginState, actions: loginActions } = useLoginLogic({
		onSuccess: () => {
			setToastMessage('로그인 되었습니다.');
			setTimeout(() => { onClose(); navigate('/'); }, 1000);
		},
		onError: (message) => setToastMessage(message),
	});

	const { state: socialState, actions: socialActions } = useSocialLoginLogic();
	const { register, formState: { errors } } = formMethods;

	return (
		<>
			<Modal
				isOpen
				onClose={onClose}
				title='로그인'
				className='w-[calc(100vw-32px)] max-w-[480px] bg-[#1C1D21] rounded-[40px] px-[24px] py-[40px] sm:px-[40px] sm:py-[50px] max-h-[90dvh] overflow-y-auto'
			>
				{/* 헤더 */}
				<div style={{ textAlign: 'center', marginBottom: '40px' }}>
					<h2 style={{ fontSize: 'clamp(32px, 8vw, 48px)', fontWeight: 500, color: '#FFFFFF', margin: '0 0 8px', lineHeight: '120%', letterSpacing: '-0.05em' }}>LOGIN</h2>
					<p style={{ fontSize: 'clamp(14px, 4vw, 20px)', fontWeight: 400, color: '#FFFFFF', margin: 0, lineHeight: '140%' }}>AssetMind에 오신 것을 환영합니다.</p>
				</div>

				{/* 폼 */}
				<form onSubmit={loginActions.onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
					<Input
						label='아이디'
						type='email'
						placeholder='아이디를 입력해 주세요.'
						error={errors.email?.message}
						{...register('email')}
					/>
					<Input
						label='비밀번호'
						type={showPw ? 'text' : 'password'}
						placeholder='비밀번호를 입력해 주세요.'
						error={errors.password?.message}
						icon={showPw ? <EyeOn /> : <EyeOff />}
						onIconClick={() => setShowPw(!showPw)}
						{...register('password')}
					/>
					<Button size='lg' type='submit' disabled={loginState.isLoggingIn || socialState.isRedirecting} className='mt-4'>
						{loginState.isLoggingIn ? '로그인 중...' : '로그인'}
					</Button>
				</form>

				{/* 하단 링크 */}
				<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', marginTop: '16px', fontSize: '13px', color: '#9194A1' }}>
					<button onClick={onClickFindIdPw} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9194A1' }}>아이디 찾기</button>
					<div style={{ width: '1px', height: '12px', backgroundColor: '#2F3037' }} />
					<button onClick={onClickFindIdPw} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9194A1' }}>비밀번호 찾기</button>
					<div style={{ width: '1px', height: '12px', backgroundColor: '#2F3037' }} />
					<button onClick={onClickSignup} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9194A1' }}>회원가입</button>
				</div>

				{/* 구분선 */}
				<div style={{ position: 'relative', margin: '24px 0' }}>
					<div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center' }}>
						<div style={{ width: '100%', borderTop: '1px solid #2F3037' }} />
					</div>
					<div style={{ position: 'relative', display: 'flex', justifyContent: 'center', fontSize: '14px', color: '#9194A1' }}>
						<span style={{ backgroundColor: '#1C1D21', padding: '0 8px' }}>or continue with</span>
					</div>
				</div>

				{/* 소셜 로그인 */}
				<div style={{ display: 'flex', justifyContent: 'center', gap: '16px' }}>
					<button
						onClick={() => socialActions.handleSocialLogin('google')}
						style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, borderRadius: '50%', overflow: 'hidden' }}
					>
						<GoogleIcon />
					</button>
					<button
						onClick={() => socialActions.handleSocialLogin('kakao')}
						style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, borderRadius: '50%', overflow: 'hidden' }}
					>
						<KakaoIcon />
					</button>
				</div>
			</Modal>

			{toastMessage && <Toast onClose={() => setToastMessage(null)}>{toastMessage}</Toast>}
		</>
	);
}