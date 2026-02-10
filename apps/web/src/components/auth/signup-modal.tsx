import Modal from '../common/modal';
import Button from '../common/button';
import AuthInput from '../auth/auth-input';
import Input from '../common/input';
import Toast from '../common/toast';
import { useSignupLogic } from '../../hooks/auth/use-signup-logic';

/*
  회원가입 화면 UI
  
  UI 렌더링 및 사용자 인터랙션 연결
  비즈니스 로직은 'useSignupLogic' 훅으로 위임하여 관심사 분리(SoC) 실현
  React Hook Form + Zod를 통해 유효성 검사 및 에러 상태 구독
*/

type Props = {
	onClose: () => void;
	onClickLogin: () => void;
};

export default function SignupModal({ onClose, onClickLogin }: Props) {
	// 비즈니스 로직과 상태 관리를 커스텀 훅에서 불러옴
	// state: UI 렌더링에 필요한 상태 (loading, verified, message 등)
	const { formMethods, state, actions } = useSignupLogic({
		onClose,
		onClickLogin,
	});

	const {
		register,
		formState: { errors },
	} = formMethods;

	const getEmailButtonConfig = () => {
		// 1. 중복 확인 전 -> "중복 확인"
		if (!state.isEmailChecked) {
			return {
				text: state.isCheckingEmail ? '확인 중' : '중복 확인',
				onClick: actions.handleCheckEmail,
				disabled: state.isCheckingEmail,
			};
		}
		// 2. 중복 확인 완료 & 전송 전 -> "인증번호 전송"
		if (!state.isEmailSent) {
			return {
				text: '인증번호 전송',
				onClick: actions.handleSendEmailAuth,
				disabled: false,
			};
		}
		// 3. 전송 완료 -> "재전송"
		return {
			text: '재전송',
			onClick: actions.handleSendEmailAuth,
			disabled: state.isEmailVerified, // 인증 완료되면 재전송 불가
		};
	};

	const emailBtnConfig = getEmailButtonConfig();

	return (
		<Modal onClose={onClose}>
			<div className='flex flex-col w-full px-2'>
				<h2 className='mb-4 text-center text-4xl font-bold'>SIGN UP</h2>

				<form onSubmit={actions.onSubmit} className='flex flex-col gap-6'>
					{/* 1. 이름 입력 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>이름</label>
						<AuthInput
							type='text'
							placeholder='이름을 입력해 주세요'
							errorMessage={errors.name?.message}
							{...register('name')}
						/>
					</div>

					{/* 2. 아이디 입력 (중복 확인 -> 인증번호 전송) */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>아이디</label>
						<div className='relative'>
							<Input
								type='text'
								placeholder='이메일 형식 입력'
								readOnly={state.isEmailVerified}
								className={`pr-24 ${
									errors.email
										? 'border-red-500'
										: state.isEmailChecked // 중복 확인만 통과해도 파란색 표시
											? 'border-blue-500'
											: ''
								}`}
								{...register('email', {
									// 입력값 변경 시 상태 초기화 위임
									onChange: actions.handleEmailChange,
								})}
							/>

							{/* 상태에 따라 변하는 버튼 (중복확인 -> 인증번호 전송 -> 재전송) */}
							<Button
								type='button'
								size='sm'
								className='absolute right-2 top-1/2 h-8 w-24 -translate-y-1/2 text-xs'
								onClick={emailBtnConfig.onClick}
								disabled={emailBtnConfig.disabled}
							>
								{emailBtnConfig.text}
							</Button>

							{/* 에러 및 성공 메시지 출력 */}
							{errors.email && errors.email.type !== 'duplicate' && (
								<p className='absolute -bottom-5 left-1 text-xs text-red-500'>
									{errors.email.message}
								</p>
							)}
							{state.successMessage && !errors.email && (
								<p className='absolute -bottom-5 left-1 text-xs text-blue-500'>
									{state.successMessage}
								</p>
							)}
						</div>
					</div>

					{/* 2. 인증번호 입력 
              - 조건부 렌더링 제거: 항상 화면에 보임
              - UX 개선: 전송 전(!isEmailSent)에는 입력을 비활성화(disabled)
          */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>인증번호</label>
						<div className='relative'>
							<Input
								type='text'
								placeholder='인증번호 6자리'
								maxLength={6}
								disabled={!state.isEmailSent || state.isEmailVerified}
								className={`pr-20 ${
									errors.authCode
										? 'border-red-500'
										: state.isEmailVerified
											? 'border-blue-500'
											: ''
								}`}
								{...register('authCode')}
							/>

							<Button
								type='button'
								size='sm'
								className='absolute right-2 top-1/2 h-8 w-24 -translate-y-1/2 text-xs'
								onClick={actions.handleVerifyEmailAuth}
								disabled={!state.isEmailSent || state.isEmailVerified}
							>
								{state.isEmailVerified ? '인증완료' : '인증확인'}
							</Button>

							{errors.authCode && (
								<p className='absolute -bottom-5 left-1 text-xs text-red-500'>
									{errors.authCode.message}
								</p>
							)}
							{state.isEmailVerified && (
								<p className='absolute -bottom-5 left-1 text-xs text-blue-500'>
									이메일 인증이 완료되었습니다.
								</p>
							)}
						</div>
					</div>

					{/* 3. 비밀번호 입력 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>비밀번호</label>
						<AuthInput
							type='password'
							placeholder='영문, 숫자, 특수문자 포함 8자 이상'
							errorMessage={errors.password?.message}
							{...register('password')}
						/>
					</div>

					{/* 4. 비밀번호 확인 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>비밀번호 확인</label>
						<div className='relative'>
							<AuthInput
								type='password'
								placeholder='비밀번호를 한 번 더 입력해 주세요.'
								errorMessage={errors.passwordConfirm?.message}
								{...register('passwordConfirm')}
								className={
									errors.passwordConfirm
										? 'border-red-500'
										: state.isPasswordMatch
											? 'border-blue-500'
											: ''
								}
							/>
							{state.isPasswordMatch && (
								<p className='absolute -bottom-5 left-1 text-xs text-blue-500'>
									비밀번호가 일치합니다.
								</p>
							)}
						</div>
					</div>

					<Button type='submit' size='md' disabled={state.isSignupPending}>
						{state.isSignupPending ? '가입 처리 중...' : '가입하기'}
					</Button>
				</form>

				<div className='mt-4 flex gap-4 items-center justify-center'>
					<p>이미 계정이 있으신가요?</p>
					<button
						className='cursor-pointer font-semibold'
						onClick={onClickLogin}
						type='button'
					>
						로그인
					</button>
				</div>
			</div>

			{state.toastMessage && (
				<Toast onClose={() => actions.setToastMessage(null)}>
					{state.toastMessage}
				</Toast>
			)}
		</Modal>
	);
}
