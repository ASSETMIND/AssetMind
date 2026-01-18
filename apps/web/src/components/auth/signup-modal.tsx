import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { signupSchema, type SignupSchemaType } from '../../libs/schema/auth';

import Modal from '../common/modal';
import Button from '../common/button';
import AuthInput from '../auth/auth-input';
import Input from '../common/input';
import IdentityVerifyButton from './identity-verify-button';
import Toast from '../common/toast';
import { useSignup } from '../../hooks/auth/use-signup';
import { useCheckID } from '../../hooks/auth/use-check-ID';
import type { IdentityVerificationResponse } from '../../types/portone';

/*
	회원가입 화면 UI 구성을 담당하는 view 역할의 컴포넌트

	실제 로직이나 라우팅은 props로 주입받은 함수에 위임
	이 컴포넌트는 UI 렌더링에만 집중하도록 설계
 */

type Props = {
	onClose: () => void;
	onClickLogin: () => void;
};

/*
  회원가입 모달 컴포넌트 (포트원 V2 적용)
  1. 중복 확인 성공 시: 파란색 테두리 + 파란색 텍스트 메시지
  2. 중복 확인 실패 시: 빨간색 테두리 + 빨간색 에러 메시지 없음(숨김) + 토스트 메시지 출력
  3. 일반 유효성 검사 실패 시: 빨간색 테두리 + 빨간색 에러 메시지 출력
  4. 입력값 변경 시: 인증 상태 초기화
  5. 본인인증 로직: 성공/실패 시 상태 및 토스트 처리
 */
export default function SignupModal({ onClose, onClickLogin }: Props) {
	const [isVerified, setIsVerified] = useState(false);

	// 인증 완료 후 받은 identityVerificationId 저장 (백엔드 전송용 임시)
	const [verificationId, setVerificationID] = useState<string | null>(null);

	// 사용자 피드백용 토스트 메시지
	const [toastMessage, setToastMessage] = useState<string | null>(null);

	// 아이디 중복 확인 완료 여부
	const [isIDChecked, setIsIDChecked] = useState(false);

	// 중복 확인 성공 메시지
	const [successMessage, setSuccessMessage] = useState<string | null>(null);

	// 회원가입 요청 뮤테이션
	const { mutate, isPending } = useSignup();

	// 아이디 중복 확인 뮤테이션
	const { mutateAsync: checkID, isPending: isCheckingID } = useCheckID();

	const {
		register,
		handleSubmit,
		trigger,
		getValues,
		setError,
		clearErrors,
		watch, // 실시간 비밀번호 감지
		reset, // 폼 초기화
		formState: { errors },
	} = useForm<SignupSchemaType>({
		resolver: zodResolver(signupSchema),
		mode: 'onChange',
		defaultValues: {
			id: '',
			password: '',
			passwordConfirm: '',
		},
	});

	// 비밀번호 실시간 비교 로직
	const password = watch('password');
	const passwordConfirm = watch('passwordConfirm');
	const isPasswordMismatch =
		password && passwordConfirm && password !== passwordConfirm;

	// 컴포넌트 언마운트 시 상태 초기화
	useEffect(() => {
		return () => {
			// 모달이 닫힐 때 폼 데이터 및 로컬 상태 초기화
			reset();
			setToastMessage(null);
			setIsVerified(false);
			setVerificationID(null); // ID 초기화
			setIsIDChecked(false);
			setSuccessMessage(null);
		};
	}, [reset]);

	// 이메일 중복 확인 로직
	const handleCheckID = async () => {
		const email = getValues('id');
		const isValidFormat = await trigger('id');

		// 유효성 검사 실패 시 함수 종료 (이때는 zod 에러이므로 아래 텍스트가 나옴)
		if (!isValidFormat) return;

		const isAvailable = await checkID(email);

		if (isAvailable) {
			// [성공 로직]
			const msg = '사용 가능한 아이디입니다.';
			setToastMessage(msg); // 토스트 출력
			setSuccessMessage(msg); // 성공 메시지 설정 (파란색)
			setIsIDChecked(true);
			clearErrors('id'); // 기존 에러 제거
		} else {
			// [실패 로직]
			const msg = '이미 사용 중인 아이디입니다.';

			// type을 'duplicate'로 지정하여 렌더링 시 구분
			setError('id', {
				type: 'duplicate',
				message: msg,
			});

			setToastMessage(msg); // 토스트 출력
			setSuccessMessage(null); // 성공 메시지 제거
			setIsIDChecked(false);
		}
	};

	/* [요구사항: Verification/Success]
    인증 성공 시 호출: 상태를 true로 변경하여 버튼 UI를 인증 완료(Disabled)로 전환
    identityVerificationId를 확인하고 저장함
  */
	const handleVerifySuccess = (response: IdentityVerificationResponse) => {
		console.log('본인인증 V2 성공:', response);

		// V2에서는 identityVerificationId가 존재해야 성공
		if (response.identityVerificationId) {
			setIsVerified(true);
			setVerificationID(response.identityVerificationId);
			setToastMessage('본인인증이 완료되었습니다.');
		}
	};

	/* [요구사항: Verification/Fail]
    인증 실패 또는 취소 시 호출: 에러 메시지를 토스트로 출력
  */
	const handleVerifyError = (msg: string) => {
		setToastMessage(msg || '본인인증에 실패했습니다.');
		setIsVerified(false);
		setVerificationID(null); // 실패 시 ID 초기화
	};

	/* 회원가입 제출 로직 */
	const onSubmit = (data: SignupSchemaType) => {
		// 중복 요청 방지: 이미 처리 중이라면 함수 종료
		if (isPending) return;

		if (!isIDChecked) {
			setToastMessage('아이디 중복 확인을 해주세요.');
			return;
		}

		// ID값도 함께 체크
		if (!isVerified || !verificationId) {
			setToastMessage('본인인증을 진행해주세요.');
			return;
		}

		// 제출 전 비밀번호 최종 확인 (실시간 피드백 외 안전장치)
		if (data.password !== data.passwordConfirm) {
			setToastMessage('비밀번호가 일치하지 않습니다.');
			return;
		}

		mutate(
			{
				id: data.id,
				password: data.password,
				identityVerificationId: verificationId,
			},
			{
				onSuccess: () => {
					setToastMessage('회원가입이 완료되었습니다! 로그인해주세요.');
					setTimeout(() => {
						onClose();
						onClickLogin();
					}, 2000);
				},
				// 에러 처리 구체화: 서버 메시지가 있으면 우선 출력
				onError: (error: any) => {
					const errorMsg =
						error?.response?.data?.message ||
						error?.message ||
						'가입에 실패했습니다. 다시 시도해주세요.';
					setToastMessage(errorMsg);
				},
			},
		);
	};

	return (
		<Modal onClose={onClose}>
			<div className='flex flex-col w-full px-2'>
				<h2 className='mb-4 text-center text-4xl font-bold'>SIGN UP</h2>

				<form onSubmit={handleSubmit(onSubmit)} className='flex flex-col gap-6'>
					{/* 아이디 입력 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>아이디</label>
						<div className='relative'>
							<Input
								type='text'
								placeholder='영문 소문자, 숫자 포함 4~20자'
								className={`pr-24 ${
									errors.id
										? 'border-red-500'
										: successMessage
											? 'border-blue-500'
											: ''
								}`}
								{...register('id', {
									onChange: () => {
										// [상태 초기화] 사용자가 다시 입력하면 인증/성공 상태 해제 및 에러 즉시 제거
										setIsIDChecked(false);
										setSuccessMessage(null);
										clearErrors('id');
									},
								})}
							/>

							<Button
								type='button'
								size='sm'
								className='absolute right-2 top-1/2 h-8 w-20 -translate-y-1/2 text-xs'
								onClick={handleCheckID}
								disabled={isCheckingID}
							>
								{isCheckingID ? '확인 중' : '중복 확인'}
							</Button>

							{/* [UI 로직] 
                  에러 타입이 'duplicate'(중복 확인 실패)가 아닐 때만 하단 텍스트 출력 (즉, Zod 유효성 검사 실패 등은 표시됨)
                  성공 메시지가 있으면 파란색 텍스트 출력
              */}
							{errors.id && errors.id.type !== 'duplicate' ? (
								<p className='absolute -bottom-5 left-1 text-xs text-red-500'>
									{errors.id.message}
								</p>
							) : successMessage ? (
								<p className='absolute -bottom-5 left-1 text-xs text-blue-500'>
									{successMessage}
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

					{/* 비밀번호 확인 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>비밀번호 확인</label>
						<AuthInput
							type='password'
							placeholder='비밀번호를 한 번 더 입력해 주세요.'
						/>
					</div>

					{/* 본인인증 섹션 */}
					<div className='flex flex-col gap-2'>
						<label className='font-medium'>휴대폰 번호</label>

						<div className='relative'>
							<Input type='tel' placeholder='010-0000-0000' className='pr-28' />
							<Button
								type='button'
								size='sm'
								className='absolute right-2 top-1/2 h-8 w-24 -translate-y-1/2 text-xs'
							>
								인증번호 전송
							</Button>
						</div>

						<div className='relative'>
							<AuthInput
								type='password'
								placeholder='비밀번호를 한 번 더 입력해 주세요.'
								errorMessage={
									errors.passwordConfirm?.message ||
									(isPasswordMismatch
										? '비밀번호가 일치하지 않습니다.'
										: undefined)
								}
								{...register('passwordConfirm')}
								className={isPasswordMismatch ? 'border-red-500' : ''}
							/>
						</div>
					</div>

					{/* 본인인증 버튼 */}
					<IdentityVerifyButton
						onSuccess={handleVerifySuccess}
						onError={handleVerifyError}
						isVerified={isVerified}
					/>

					{/* isPending 상태를 통한 중복 클릭 방지 */}
					<Button type='submit' size='md' disabled={isPending}>
						{isPending ? '가입 처리 중...' : '가입하기'}
					</Button>
				</form>

				{/* 하단 바로가기 버튼들 */}
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

			{toastMessage && (
				<Toast onClose={() => setToastMessage(null)}>{toastMessage}</Toast>
			)}
		</Modal>
	);
}
