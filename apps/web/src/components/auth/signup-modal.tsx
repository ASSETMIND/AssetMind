import { useState } from 'react';
import Modal from '../common/modal';
import Button from '../common/button';
import Input from '../common/input';
import Toast from '../common/toast';
import EyeOn from '../icon/eye-on';
import EyeOff from '../icon/eye-off';
import { useSignupLogic } from '../../hooks/auth/use-signup-logic';

type Props = {
	onClose: () => void;
	onClickLogin: () => void;
};

export default function SignupModal({ onClose, onClickLogin }: Props) {
	const [toastMessage, setToastMessage] = useState<string | null>(null);
	const [showPw, setShowPw] = useState(false);
	const [showPwCheck, setShowPwCheck] = useState(false);

	const { formMethods, state, actions } = useSignupLogic({
		onSuccess: () => {
			setToastMessage('회원가입 완료! 로그인해주세요.');
			setTimeout(() => { onClose(); onClickLogin(); }, 2000);
		},
		onError: (message) => setToastMessage(message),
		onToast: (message) => setToastMessage(message),
	});

	const { register, formState: { errors } } = formMethods;

	const getEmailButtonConfig = () => {
		if (!state.isEmailChecked) return { text: state.isCheckingEmail ? '확인 중' : '중복 확인', onClick: actions.handleCheckEmail, disabled: state.isCheckingEmail };
		if (!state.isEmailSent) return { text: '인증번호 전송', onClick: actions.handleSendEmailAuth, disabled: false };
		return { text: '재전송', onClick: actions.handleSendEmailAuth, disabled: state.isEmailVerified };
	};

	const emailBtnConfig = getEmailButtonConfig();

	const InnerButton = ({ text, onClick, disabled }: { text: string; onClick: () => void; disabled?: boolean }) => (
		<button
			type='button'
			onClick={onClick}
			disabled={disabled}
			style={{
				backgroundColor: '#6D4AE6',
				color: '#FFFFFF',
				fontSize: '13px',
				fontWeight: 500,
				borderRadius: '9px',
				border: 'none',
				cursor: disabled ? 'not-allowed' : 'pointer',
				height: '38px',
				padding: '0 16px',
				whiteSpace: 'nowrap',
				opacity: disabled ? 0.5 : 1,
				minWidth: '90px',
			}}
		>
			{text}
		</button>
	);

	return (
		<>
			<Modal
				isOpen
				onClose={onClose}
				title='회원가입'
				className='w-[calc(100vw-32px)] max-w-[480px] bg-[#1C1D21] rounded-[40px] px-[24px] py-[40px] sm:px-[40px] sm:py-[50px] max-h-[90dvh] overflow-y-auto'
			>
				{/* 헤더 */}
				<h2 style={{ fontSize: 'clamp(32px, 8vw, 48px)', fontWeight: 500, color: '#FFFFFF', textAlign: 'center', margin: '0 0 40px', lineHeight: '120%', letterSpacing: '-0.05em' }}>
					SIGN UP
				</h2>

				<form onSubmit={actions.onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
					<Input
						label='이름'
						type='text'
						placeholder='이름을 입력해 주세요'
						error={errors.name?.message}
						{...register('name')}
					/>

					<Input
						label='아이디'
						type='text'
						placeholder='이메일 형식 입력'
						readOnly={state.isEmailVerified}
						state={errors.email ? 'error' : state.isEmailChecked ? 'success' : 'default'}
						error={errors.email && errors.email.type !== 'duplicate' ? errors.email.message : undefined}
						message={state.successMessage && !errors.email ? state.successMessage : undefined}
						rightSection={
							<InnerButton
								text={emailBtnConfig.text}
								onClick={emailBtnConfig.onClick}
								disabled={emailBtnConfig.disabled}
							/>
						}
						rightSectionWidth='pr-[120px]'
						{...register('email', { onChange: actions.handleEmailChange })}
					/>

					<Input
						label='인증번호'
						type='text'
						placeholder='인증번호 6자리'
						maxLength={6}
						disabled={!state.isEmailSent || state.isEmailVerified}
						state={errors.authCode ? 'error' : state.isEmailVerified ? 'success' : 'default'}
						error={errors.authCode?.message}
						message={state.isEmailVerified ? '이메일 인증이 완료되었습니다.' : undefined}
						rightSection={
							<InnerButton
								text={state.isEmailVerified ? '인증 완료' : '인증 확인'}
								onClick={actions.handleVerifyEmailAuth}
								disabled={!state.isEmailSent || state.isEmailVerified}
							/>
						}
						rightSectionWidth='pr-[120px]'
						{...register('authCode')}
					/>

					<Input
						label='비밀번호'
						type={showPw ? 'text' : 'password'}
						placeholder='영문, 숫자, 특수문자 포함 8자 이상'
						error={errors.password?.message}
						icon={showPw ? <EyeOn /> : <EyeOff />}
						onIconClick={() => setShowPw(!showPw)}
						{...register('password')}
					/>

					<Input
						label='비밀번호 확인'
						type={showPwCheck ? 'text' : 'password'}
						placeholder='비밀번호를 한 번 더 입력해 주세요.'
						error={errors.passwordConfirm?.message}
						state={state.isPasswordMatch ? 'success' : 'default'}
						message={state.isPasswordMatch ? '비밀번호가 일치합니다.' : undefined}
						icon={showPwCheck ? <EyeOn /> : <EyeOff />}
						onIconClick={() => setShowPwCheck(!showPwCheck)}
						{...register('passwordConfirm')}
					/>

					{/* 가입하기 버튼 — 키보드 가림 방지용 여백 */}
					<div style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}>
						<Button type='submit' size='lg' disabled={state.isSignupPending} className='mt-4'>
							{state.isSignupPending ? '가입 처리 중...' : '가입하기'}
						</Button>
					</div>
				</form>

				{/* 로그인 전환 */}
				<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginTop: '16px', paddingBottom: 'env(safe-area-inset-bottom, 16px)' }}>
					<span style={{ fontSize: '14px', color: '#9194A1' }}>이미 계정이 있으신가요?</span>
					<button onClick={onClickLogin} type='button' style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '14px', fontWeight: 500, color: '#FFFFFF' }}>
						로그인
					</button>
				</div>
			</Modal>

			{toastMessage && <Toast onClose={() => setToastMessage(null)}>{toastMessage}</Toast>}
		</>
	);
}