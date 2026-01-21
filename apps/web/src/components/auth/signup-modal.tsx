import Modal from '../common/modal';
import Button from '../common/button';
import AuthInput from '../auth/auth-input';
import Input from '../common/input';
import IdentityVerifyButton from './identity-verify-button';
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

	return (
		<Modal onClose={onClose}>
			<div className='flex flex-col w-full px-2'>
				<h2 className='mb-4 text-center text-4xl font-bold'>SIGN UP</h2>

				<form onSubmit={actions.onSubmit} className='flex flex-col gap-6'>
					{/* 아이디(이메일) 입력 필드 
            	중복 확인 및 유효성 검사 로직이 포함됨
          */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>아이디</label>
						<div className='relative'>
							<Input
								type='text'
								placeholder='영문 소문자, 숫자 포함 4~20자'
								// [UI 적용] 상태에 따른 테두리 색상 변경 (에러: 빨강, 성공: 파랑)
								className={`pr-24 ${
									errors.id
										? 'border-red-500'
										: state.successMessage
											? 'border-blue-500'
											: ''
								}`}
								{...register('id', {
									// 입력값 변경 시 '중복 확인 완료' 상태 초기화 등을 훅 내부 로직으로 위임
									onChange: actions.handleIdChange,
								})}
							/>

							<Button
								type='button'
								size='sm'
								className='absolute right-2 top-1/2 h-8 w-20 -translate-y-1/2 text-xs'
								onClick={actions.handleCheckID}
								disabled={state.isCheckingID}
							>
								{state.isCheckingID ? '확인 중' : '중복 확인'}
							</Button>

							{/* [UI 로직] 하단 메시지 렌더링 조건
                 1. 에러가 'duplicate'(중복) 타입일 경우: 텍스트는 숨기고 토스트만 띄움 (요구사항)
                 2. 일반 에러(형식 미달 등)일 경우: 빨간색 에러 메시지 표시
                 3. 성공 메시지가 있을 경우: 파란색 성공 메시지 표시
              */}
							{errors.id && errors.id.type !== 'duplicate' ? (
								<p className='absolute -bottom-5 left-1 text-xs text-red-500'>
									{errors.id.message}
								</p>
							) : state.successMessage ? (
								<p className='absolute -bottom-5 left-1 text-xs text-blue-500'>
									{state.successMessage}
								</p>
							) : null}
						</div>
					</div>

					{/* 비밀번호 입력 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>비밀번호</label>
						<AuthInput
							type='password'
							placeholder='영문, 숫자, 특수문자 포함 8자 이상'
							errorMessage={errors.password?.message}
							{...register('password')}
						/>
					</div>

					{/* 비밀번호 확인
            	Zod Schema의 .refine()을 통해 일치 여부가 검증
              불일치 시 errors.passwordConfirm에 자동으로 에러가 담김
          */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>비밀번호 확인</label>
						<div className='relative'>
							<AuthInput
								type='password'
								placeholder='비밀번호를 한 번 더 입력해 주세요.'
								errorMessage={errors.passwordConfirm?.message}
								{...register('passwordConfirm')}
								// 에러 발생 시 빨간 테두리 적용
								className={errors.passwordConfirm ? 'border-red-500' : ''}
							/>
						</div>
					</div>

					{/* 본인인증 버튼 
            	인증 성공/실패 핸들러를 Props로 전달
          */}
					<IdentityVerifyButton
						onSuccess={actions.handleVerifySuccess}
						onError={actions.handleVerifyError}
						isVerified={state.isVerified}
					/>

					{/* 가입하기 버튼 (API 요청 중일 때 비활성화) */}
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

			{/* 전역 피드백용 토스트 메시지 */}
			{state.toastMessage && (
				<Toast onClose={() => actions.setToastMessage(null)}>
					{state.toastMessage}
				</Toast>
			)}
		</Modal>
	);
}
