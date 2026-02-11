import { renderHook, act } from '@testing-library/react';
import { useSignupLogic } from '../hooks/auth/use-signup-logic';

// api 모킹
const mockCheckEmailMutate = jest.fn();
const mockSendEmailMutate = jest.fn();
const mockVerifyCodeMutate = jest.fn();
const mockSignupMutate = jest.fn();

jest.mock('../hooks/auth/queries/use-email-verification', () => ({
	useSendEmailCode: () => ({
		mutateAsync: mockSendEmailMutate,
		isPending: false,
	}),
	useVerifyEmailCode: () => ({
		mutateAsync: mockVerifyCodeMutate,
		isPending: false,
	}),
	useCheckEmail: () => ({
		mutateAsync: mockCheckEmailMutate,
		isPending: false,
	}),
}));

jest.mock('../hooks/auth/queries/use-signup', () => ({
	useSignup: () => ({ mutate: mockSignupMutate, isPending: false }),
}));

describe('useSignupLogic 유닛 테스트', () => {
	const mockOnSuccess = jest.fn();
	const mockOnError = jest.fn();
	const mockOnToast = jest.fn();

	const defaultProps = {
		onSuccess: mockOnSuccess,
		onError: mockOnError,
		onToast: mockOnToast,
	};

	beforeEach(() => {
		jest.clearAllMocks();
	});

	describe('Feature: 아이디(이메일) 중복 확인', () => {
		test('Scenario: 유효하지 않은 이메일 형식 입력 시 API를 호출하지 않는다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('email', 'invalid-email', {
					shouldValidate: false,
				});
			});

			// When
			await act(async () => {
				await result.current.actions.handleCheckEmail();
			});

			// Then
			expect(mockCheckEmailMutate).not.toHaveBeenCalled();
		});

		test('Scenario: 이미 사용 중인 이메일일 경우 에러 메시지를 표시한다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// 유효한 이메일 입력
			await act(async () => {
				result.current.formMethods.setValue('email', 'duplicate@test.com', {
					shouldValidate: false,
				});
			});

			// API가 false(중복)를 반환하도록 설정
			mockCheckEmailMutate.mockResolvedValue(false);

			// When
			await act(async () => {
				await result.current.actions.handleCheckEmail();
			});

			// Then
			expect(result.current.state.isEmailChecked).toBe(false);
			expect(result.current.formMethods.formState.errors.email?.message).toBe(
				'이미 사용 중인 아이디입니다.',
			);
			expect(mockOnError).toHaveBeenCalledWith('이미 사용 중인 아이디입니다.');
		});

		test('Scenario: 이메일 입력값이 변경되면 기존 인증 상태가 초기화된다', async () => {
			// Given: 중복 에러가 발생한 상태
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// 중복 에러 상태로 시작
			mockCheckEmailMutate.mockResolvedValue(false);
			await act(async () => {
				result.current.formMethods.setValue('email', 'dup@email.com', {
					shouldValidate: false,
				});
			});
			await act(async () => {
				await result.current.actions.handleCheckEmail();
			});

			expect(result.current.formMethods.formState.errors.email?.type).toBe(
				'duplicate',
			);

			// When: 사용자가 이메일을 수정함
			await act(async () => {
				result.current.actions.handleEmailChange();
			});

			// Then: 에러가 사라지고 초기화되어야 함
			expect(result.current.formMethods.formState.errors.email).toBeUndefined();
		});
	});

	describe('Feature: 인증번호 전송', () => {
		test('Scenario: 중복 확인을 하지 않고 전송 시도 시 경고 메시지를 표시한다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// When
			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			expect(mockSendEmailMutate).not.toHaveBeenCalled();
			expect(mockOnError).toHaveBeenCalledWith(
				'먼저 아이디 중복 확인을 진행해주세요.',
			);
		});

		test('Scenario: 이메일 발송 실패 시 서버 에러 메시지를 표시한다', async () => {
			// Given: 중복 확인 완료 상태
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			mockCheckEmailMutate.mockResolvedValue(true);
			await act(async () => {
				result.current.formMethods.setValue('email', 'valid@email.com', {
					shouldValidate: false,
				});
			});
			await act(async () => {
				await result.current.actions.handleCheckEmail();
			});

			// API 실패 Mocking (서버 메시지 있음)
			mockSendEmailMutate.mockRejectedValue({
				response: { data: { message: '서버 에러 발생' } },
			});

			// When
			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			// Then
			expect(result.current.state.isEmailSent).toBe(false);
			expect(mockOnError).toHaveBeenCalledWith('서버 에러 발생');
		});
	});

	describe('Feature: 인증번호 검증', () => {
		test('Scenario: 인증번호가 6자리가 아니면 API를 호출하지 않는다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('authCode', '123', {
					shouldValidate: false,
				}); // 3자리
			});

			// When
			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			// Then
			expect(mockVerifyCodeMutate).not.toHaveBeenCalled();
			expect(mockOnError).toHaveBeenCalledWith(
				'인증번호 6자리를 입력해주세요.',
			);
		});

		test('Scenario: 인증번호 검증 실패 시 에러 메시지를 표시한다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com', {
					shouldValidate: false,
				});
				result.current.formMethods.setValue('authCode', '123456', {
					shouldValidate: false,
				});
			});

			const errorMsg = '인증번호가 틀렸습니다.';
			mockVerifyCodeMutate.mockRejectedValue({
				response: { data: { message: errorMsg } },
			});

			// When
			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			// Then
			expect(result.current.state.isEmailVerified).toBe(false);
			expect(mockOnError).toHaveBeenCalledWith(errorMsg);
			expect(
				result.current.formMethods.formState.errors.authCode?.message,
			).toBe(errorMsg);
		});

		test('Scenario: 인증번호 검증 성공 시 토큰을 저장하고 인증 완료 상태가 된다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('authCode', '123456', {
					shouldValidate: false,
				});
			});

			// API가 토큰 문자열을 반환한다고 가정
			mockVerifyCodeMutate.mockResolvedValue('mock-sign-up-token');

			// When
			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			// Then
			expect(result.current.state.isEmailVerified).toBe(true);
			expect(mockOnToast).toHaveBeenCalledWith('이메일 인증이 완료되었습니다.');
		});
	});

	describe('Feature: 회원가입 제출', () => {
		// 공통 Setup 함수
		const setupReadyToSubmit = async (result: any) => {
			await act(async () => {
				result.current.formMethods.reset({
					name: '테스트유저',
					email: 'final@test.com',
					password: 'password123!',
					passwordConfirm: 'password123!',
					authCode: '123456',
				});
			});

			// 인증 성공 시 토큰 반환
			mockVerifyCodeMutate.mockResolvedValue('mock-sign-up-token');
			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});
		};

		test('Scenario: 이메일 인증 미완료 시 가입 요청을 보내지 않는다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.reset({
					name: '테스트유저',
					email: 'no-auth@test.com',
					password: 'pass123!',
					passwordConfirm: 'pass123!',
					authCode: '000000',
				});
			});

			// When
			await act(async () => {
				await result.current.actions.onSubmit();
			});

			// Then
			expect(mockSignupMutate).not.toHaveBeenCalled();
			expect(mockOnError).toHaveBeenCalledWith('이메일 인증을 완료해주세요.');
		});

		test('Scenario: 회원가입 요청 실패 시 에러 메시지를 표시한다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));
			await setupReadyToSubmit(result);

			// 실패 시뮬레이션: onError 콜백 실행
			const serverErrorMsg = '이미 가입된 회원입니다.';
			mockSignupMutate.mockImplementation((_data, options) => {
				if (options?.onError) {
					options.onError({ message: serverErrorMsg });
				}
			});

			// When
			await act(async () => {
				await result.current.actions.onSubmit();
			});

			// Then
			expect(mockOnError).toHaveBeenCalledWith(serverErrorMsg);
		});

		test('Scenario: 모든 조건 만족 시 가입 요청을 보내고 성공 처리한다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));
			await setupReadyToSubmit(result);

			// 성공 시뮬레이션: onSuccess 콜백 실행
			mockSignupMutate.mockImplementation((_data, options) => {
				options.onSuccess();
			});

			// When
			await act(async () => {
				await result.current.actions.onSubmit();
			});

			// Then
			expect(mockSignupMutate).toHaveBeenCalledWith(
				expect.objectContaining({
					user_name: '테스트유저',
					email: 'final@test.com',
					password: 'password123!',
					sign_up_token: 'mock-sign-up-token',
				}),
				expect.any(Object),
			);

			expect(mockOnSuccess).toHaveBeenCalled();
		});
	});
});
