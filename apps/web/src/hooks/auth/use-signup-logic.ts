import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { signupSchema, type SignupSchemaType } from '../../libs/schema/auth';
import { useSignup } from './use-signup';
import { useCheckID } from './use-check-ID';
import type { IdentityVerificationResponse } from '../../types/portone';

type Props = {
	onClose: () => void;
	onClickLogin: () => void;
};

/*
  회원가입 모달의 비즈니스 로직과 상태 관리를 담당하는 커스텀 훅
  폼 유효성 검사, 아이디 중복 확인, 본인인증 처리 및 최종 회원가입 요청을 수행
 */

export function useSignupLogic({ onClose, onClickLogin }: Props) {
	const [isVerified, setIsVerified] = useState(false);
	const [verificationId, setVerificationID] = useState<string | null>(null);
	const [toastMessage, setToastMessage] = useState<string | null>(null);
	const [isIDChecked, setIsIDChecked] = useState(false);
	const [successMessage, setSuccessMessage] = useState<string | null>(null);

	const formMethods = useForm<SignupSchemaType>({
		resolver: zodResolver(signupSchema),
		mode: 'onChange',
		defaultValues: {
			id: '',
			password: '',
			passwordConfirm: '',
		},
	});

	const {
		getValues,
		setError,
		clearErrors,
		trigger,
		handleSubmit,
		formState: { errors },
	} = formMethods;

	const { mutate: signupMutate, isPending: isSignupPending } = useSignup();
	const { mutateAsync: checkIDMutate, isPending: isCheckingID } = useCheckID();

	// 사용자가 아이디 입력을 변경하면 기존 중복 확인 상태 및 성공 메시지를 초기화
	const handleIdChange = () => {
		if (isIDChecked) setIsIDChecked(false);
		if (successMessage) setSuccessMessage(null);
		if (errors.id?.type === 'duplicate') clearErrors('id');
	};

	// 아이디 유효성 검사(형식) 후 서버에 중복 여부 확인
	const handleCheckID = async () => {
		const email = getValues('id');

		// Zod 스키마 검증 먼저 수행 (형식이 올바르지 않으면 API 요청 차단)
		const isValidFormat = await trigger('id');
		if (!isValidFormat) return;

		const isAvailable = await checkIDMutate(email);

		if (isAvailable) {
			const msg = '사용 가능한 아이디입니다.';
			setToastMessage(msg);
			setSuccessMessage(msg);
			setIsIDChecked(true);
			clearErrors('id');
		} else {
			const msg = '이미 사용 중인 아이디입니다.';
			// 중복 에러는 'duplicate' 타입으로 설정하여 UI에서 텍스트를 숨기고 토스트로 처리
			setError('id', { type: 'duplicate', message: msg });
			setToastMessage(msg);
			setSuccessMessage(null);
			setIsIDChecked(false);
		}
	};

	// 본인인증 성공 시 인증 ID 저장 및 상태 업데이트
	const handleVerifySuccess = (response: IdentityVerificationResponse) => {
		console.log('본인인증 V2 성공:', response);
		if (response.identityVerificationId) {
			setIsVerified(true);
			setVerificationID(response.identityVerificationId);
			setToastMessage('본인인증이 완료되었습니다.');
		}
	};

	// 본인인증 실패 또는 취소 시 에러 메시지 처리
	const handleVerifyError = (msg: string) => {
		setToastMessage(msg || '본인인증에 실패했습니다.');
		setIsVerified(false);
		setVerificationID(null);
	};

	// 모든 필수 조건(중복 확인, 본인인증) 확인 후 회원가입 요청 전송
	const onSubmit = handleSubmit((data) => {
		if (isSignupPending) return;

		if (!isIDChecked) {
			setToastMessage('아이디 중복 확인을 해주세요.');
			return;
		}
		if (!isVerified || !verificationId) {
			setToastMessage('본인인증을 진행해주세요.');
			return;
		}

		signupMutate(
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
				onError: (error: any) => {
					const errorMsg =
						error?.response?.data?.message ||
						error?.message ||
						'가입에 실패했습니다. 다시 시도해주세요.';
					setToastMessage(errorMsg);
				},
			},
		);
	});

	return {
		formMethods,
		state: {
			isVerified,
			isIDChecked,
			successMessage,
			toastMessage,
			isSignupPending,
			isCheckingID,
		},
		actions: {
			setToastMessage,
			handleIdChange,
			handleCheckID,
			handleVerifySuccess,
			handleVerifyError,
			onSubmit,
		},
	};
}
