import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { signupSchema, type SignupSchemaType } from '../../libs/schema/auth';
import { useSignup } from './use-signup';
import {
	useSendEmailCode,
	useVerifyEmailCode,
	useCheckEmail,
} from './use-email-verification';

type Props = {
	onClose: () => void;
	onClickLogin: () => void;
};

export function useSignupLogic({ onClose, onClickLogin }: Props) {
	const [toastMessage, setToastMessage] = useState<string | null>(null);
	const [isIDChecked, setIsIDChecked] = useState(false);
	const [isEmailSent, setIsEmailSent] = useState(false);
	const [isEmailVerified, setIsEmailVerified] = useState(false);
	const [successMessage, setSuccessMessage] = useState<string | null>(null);

	const formMethods = useForm<SignupSchemaType>({
		resolver: zodResolver(signupSchema),
		mode: 'onChange',
		defaultValues: {
			id: '',
			authCode: '',
			password: '',
			passwordConfirm: '',
		},
	});

	const {
		getValues,
		setError,
		clearErrors,
		trigger,
		watch,
		handleSubmit,
		formState: { errors },
	} = formMethods;

	const { mutate: signupMutate, isPending: isSignupPending } = useSignup();
	const { mutateAsync: checkEmailMutate, isPending: isCheckingEmail } =
		useCheckEmail();

	// 이메일 발송 및 검증 Mutation
	const { mutateAsync: sendEmailMutate, isPending: isSendingEmail } =
		useSendEmailCode();
	const { mutateAsync: verifyCodeMutate, isPending: isVerifyingCode } =
		useVerifyEmailCode();

	// 입력값이 바뀌면 모든 인증 단계 초기화 (처음부터 다시)
	const handleIdChange = () => {
		if (isIDChecked) setIsIDChecked(false);
		if (isEmailSent) setIsEmailSent(false);
		if (isEmailVerified) setIsEmailVerified(false);
		if (successMessage) setSuccessMessage(null);
		if (errors.id?.type === 'duplicate') clearErrors('id');
	};

	// 1단계: 아이디 중복 확인 로직
	const handleCheckID = async () => {
		const email = getValues('id');
		const isValidFormat = await trigger('id');
		if (!isValidFormat) return;

		// 중복 확인 요청
		const isAvailable = await checkEmailMutate(email);

		if (isAvailable) {
			setToastMessage('사용 가능한 아이디입니다. 인증번호를 전송해주세요.');
			setSuccessMessage('사용 가능한 아이디입니다.');
			setIsIDChecked(true); // 중복확인 통과
			clearErrors('id');
		} else {
			const msg = '이미 사용 중인 아이디입니다.';
			setError('id', { type: 'duplicate', message: msg });
			setToastMessage(msg);
			setSuccessMessage(null);
			setIsIDChecked(false);
		}
	};

	// 2단계: 인증번호 전송 로직
	const handleSendEmailAuth = async () => {
		if (!isIDChecked) {
			setToastMessage('먼저 아이디 중복 확인을 진행해주세요.');
			return;
		}

		const email = getValues('id');

		try {
			// 실제 이메일 발송 API 호출
			await sendEmailMutate(email);

			setToastMessage('인증번호가 발송되었습니다. 이메일을 확인해주세요.');
			setIsEmailSent(true); // 입력창 활성화
			setIsEmailVerified(false); // 재전송 시 인증 상태 초기화
		} catch (error: any) {
			// 에러 처리
			const msg =
				error?.response?.data?.message || '인증번호 발송에 실패했습니다.';
			setToastMessage(msg);
			setIsEmailSent(false);
		}
	};

	// 3단계: 인증번호 확인 로직
	const handleVerifyEmailAuth = async () => {
		const email = getValues('id');
		const code = getValues('authCode');

		if (code.length !== 6) {
			setToastMessage('인증번호 6자리를 입력해주세요.');
			return;
		}

		try {
			// 실제 인증번호 검증 API 호출
			await verifyCodeMutate({ email, code });

			// 성공 시 (에러가 발생하지 않으면 성공으로 간주)
			setIsEmailVerified(true);
			setToastMessage('이메일 인증이 완료되었습니다.');
			clearErrors('authCode'); // 기존 에러 제거
		} catch (error: any) {
			// 실패 시 (400 Bad Request 등)
			setIsEmailVerified(false);
			const errorMsg =
				error?.response?.data?.message || '인증번호가 일치하지 않습니다.';

			// 폼 에러 설정 (빨간 테두리 및 메시지 표시용)
			setError('authCode', { message: errorMsg });
			setToastMessage(errorMsg);
		}
	};

	const onSubmit = handleSubmit((data) => {
		if (isSignupPending) return;
		if (!isEmailVerified) {
			setToastMessage('이메일 인증을 완료해주세요.');
			return;
		}

		signupMutate(
			{
				email: data.id,
				password: data.password,
			},
			{
				onSuccess: () => {
					setToastMessage('회원가입 완료! 로그인해주세요.');
					setTimeout(() => {
						onClose();
						onClickLogin();
					}, 2000);
				},
				onError: (e: any) => setToastMessage(e?.message || '가입 실패'),
			},
		);
	});

	// 비밀 번호 일치여부 확인
	const password = watch('password');
	const passwordConfirm = watch('passwordConfirm');

	const isPasswordMatch =
		!!password &&
		!!passwordConfirm &&
		password === passwordConfirm &&
		!errors.passwordConfirm;

	return {
		formMethods,
		state: {
			isIDChecked, // 중복 확인 상태
			isEmailSent, // 전송 상태
			isEmailVerified, // 인증 완료 상태
			successMessage,
			toastMessage,
			isSignupPending,
			isPasswordMatch,
			isCheckingID: isCheckingEmail || isSendingEmail || isVerifyingCode,
		},
		actions: {
			setToastMessage,
			handleIdChange,
			handleCheckID, // 중복 확인 함수
			handleSendEmailAuth, // 전송 함수
			handleVerifyEmailAuth, // 검증 함수
			// [삭제됨] handleVerifySuccess, handleVerifyError 제거
			onSubmit,
		},
	};
}
