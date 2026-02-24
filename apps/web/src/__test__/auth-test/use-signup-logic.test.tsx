import { renderHook, act } from '@testing-library/react';
import { useSignupLogic } from '../../hooks/auth/use-signup-logic';
import { useSignup } from '../../hooks/auth/queries/use-signup';

/*
 * 회원가입 비즈니스 로직(useSignupLogic) 커스텀 훅의 이메일 중복 확인, 인증번호 발송 및 검증,
 * 최종 폼 제출 과정의 상태 변화와 예외 처리를 통합적으로 검증하는 유닛 테스트 코드
 */

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
	useSignup: jest.fn(),
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
		(useSignup as jest.Mock).mockReturnValue({
			mutate: mockSignupMutate,
			isPending: false,
		});
	});

	describe('아이디(이메일) 중복 확인', () => {
		/*
		 * - 이메일 유효성 검사 실패 시나리오 검증
		 * - 형식에 맞지 않는 이메일 입력 후 중복 확인 요청 시 API가 호출되지 않음을 방어 로직을 통해 확인
		 */
		test('유효하지 않은 이메일 형식 입력 시 API를 호출하지 않는다', async () => {
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

		/*
		 * - 이메일 중복 확인 실패 시나리오 검증
		 * - API 응답이 중복(false)일 때 훅의 내부 상태가 실패로 변경되는지 확인
		 * - 폼 에러 상태 및 외부 주입된 에러 콜백이 정상적으로 호출되는지 확인
		 */
		test('이미 사용 중인 이메일일 경우 에러 메시지를 표시한다', async () => {
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

		/*
		 * - 사용자 입력 변경에 따른 에러 상태 초기화 검증
		 * - 중복 에러가 발생한 상태에서 이메일 값을 다시 수정했을 때 기존 에러가 초기화되는지 확인
		 */
		test('이메일 입력값이 변경되면 기존 인증 상태가 초기화된다', async () => {
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

		/*
		 * - 인증 완료 후 데이터 무결성 검증
		 * - 중복 확인이 성공한 상태에서 사용자가 이메일을 다시 수정할 경우 기존 성공 상태가 초기화되는지 확인
		 */
		test('이메일 중복 확인 성공 후 이메일을 변경하면 인증 상태가 초기화된다', async () => {
			// Given: 중복 확인 성공 상태
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('email', 'valid@test.com', {
					shouldValidate: false,
				});
			});
			mockCheckEmailMutate.mockResolvedValue(true);
			await act(async () => {
				await result.current.actions.handleCheckEmail();
			});
			expect(result.current.state.isEmailChecked).toBe(true);

			// When: 이메일 변경
			await act(async () => {
				result.current.actions.handleEmailChange();
			});

			// Then: 상태 초기화
			expect(result.current.state.isEmailChecked).toBe(false);
		});

		/*
		 * - 이메일 중복 확인 성공 시나리오 검증
		 * - API 응답이 사용 가능(true)일 때 상태가 성공으로 변경되고 성공 메시지가 설정되는지 확인
		 * - 다음 단계를 안내하는 토스트 메시지가 호출되는지 확인
		 */
		test('사용 가능한 이메일일 경우 성공 메시지를 표시한다', async () => {
			// Given
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('email', 'valid@test.com', {
					shouldValidate: false,
				});
			});

			mockCheckEmailMutate.mockResolvedValue(true); // Available

			// When
			await act(async () => {
				await result.current.actions.handleCheckEmail();
			});

			// Then
			expect(result.current.state.isEmailChecked).toBe(true);
			expect(result.current.state.successMessage).toBe(
				'사용 가능한 아이디입니다.',
			);
			expect(mockOnToast).toHaveBeenCalledWith(
				'사용 가능한 아이디입니다. 인증번호를 전송해주세요.',
			);
		});
	});

	describe('인증번호 전송', () => {
		/*
		 * - 인증 단계 순서 강제 로직 검증
		 * - 이메일 중복 확인이 완료되지 않은 상태에서 인증번호 발송 시도 시 API 호출을 막고 경고를 표시하는지 확인
		 */
		test('중복 확인을 하지 않고 전송 시도 시 경고 메시지를 표시한다', async () => {
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

		/*
		 * - 인증번호 발송 API 에러 핸들링 검증
		 * - 서버에서 에러 응답 반환 시 상태가 실패로 유지되고 전달된 에러 메시지가 정상 표시되는지 확인
		 */
		test('이메일 발송 실패 시 서버 에러 메시지를 표시한다', async () => {
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

	describe('인증번호 검증', () => {
		/*
		 * - 인증번호 길이 유효성 검사 로직 검증
		 * - 6자리가 아닌 인증번호 입력 후 검증 시도 시 API 요청을 사전에 차단하고 에러 콜백을 호출하는지 확인
		 */
		test('인증번호가 6자리가 아니면 API를 호출하지 않는다', async () => {
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

		/*
		 * - 인증번호 검증 API 실패 핸들링 검증
		 * - 잘못된 인증번호로 인해 서버 에러 발생 시 상태가 실패로 유지되고 폼 에러가 설정되는지 확인
		 */
		test('인증번호 검증 실패 시 에러 메시지를 표시한다', async () => {
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

		/*
		 * - 인증번호 검증 성공 시나리오 검증
		 * - API 성공 응답 수신 시 인증 완료 상태로 변경되고 성공 안내 토스트 메시지가 호출되는지 확인
		 */
		test('인증번호 검증 성공 시 토큰을 저장하고 인증 완료 상태가 된다', async () => {
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

	describe('회원가입 제출', () => {
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

		/*
		 * - 최종 제출 전 필수 인증 단계 완료 여부 검증
		 * - 이메일 인증이 완료되지 않은 상태에서 폼 제출 시도 시 API 호출을 차단하고 에러를 표시하는지 확인
		 */
		test('이메일 인증 미완료 시 가입 요청을 보내지 않는다', async () => {
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

		/*
		 * - 최종 회원가입 API 실패 핸들링 검증
		 * - 제출 과정에서 서버 에러 발생 시 주입된 에러 콜백을 통해 메시지가 정상 출력되는지 확인
		 */
		test('회원가입 요청 실패 시 에러 메시지를 표시한다', async () => {
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

		/*
		 * - 정상적인 회원가입 폼 제출 시나리오 검증
		 * - 입력한 정보와 발급받은 가입 토큰이 API 요청 페이로드에 정확히 포함되는지 확인
		 * - 외부 주입된 성공 콜백 함수가 정상적으로 호출되는지 확인
		 */
		test('모든 조건 만족 시 가입 요청을 보내고 성공 처리한다', async () => {
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

		/*
		 * - 외부 주입 콜백 Props 미설정 시의 훅 안정성 검증
		 * - 성공 콜백이 없는 상태에서 회원가입 성공 로직이 실행되어도 런타임 에러 없이 동작하는지 확인
		 */
		test('Props 없이 호출되어도 에러 없이 동작해야 한다', async () => {
			// Given: 콜백 없이 훅 초기화
			const { result } = renderHook(() => useSignupLogic());

			await act(async () => {
				result.current.formMethods.reset({
					name: '테스트유저',
					email: 'final@test.com',
					password: 'password123!',
					passwordConfirm: 'password123!',
					authCode: '123456',
				});
			});

			mockVerifyCodeMutate.mockResolvedValue('mock-sign-up-token');
			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			mockSignupMutate.mockImplementation((_data, options) => {
				options.onSuccess(); // onSuccess?.() 호출 테스트
			});

			await act(async () => {
				await result.current.actions.onSubmit();
			});
			// 크래시 없이 실행 완료됨을 검증
		});

		/*
		 * - 전체 인증 상태 초기화 로직 검증
		 * - 이메일, 인증번호 발송, 검증이 모두 성공적으로 완료된 상태에서 이메일 값이 변경될 경우 모든 단계의 인증 상태가 초기화되는지 확인
		 */
		test('handleEmailChange는 모든 인증 상태를 초기화해야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// 1. Check Email Success
			mockCheckEmailMutate.mockResolvedValue(true);
			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com', {
					shouldValidate: false,
				});
				await result.current.actions.handleCheckEmail();
			});

			// 2. Send Email Success
			mockSendEmailMutate.mockResolvedValue(undefined);
			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			// 3. Verify Code Success
			mockVerifyCodeMutate.mockResolvedValue('token');
			await act(async () => {
				result.current.formMethods.setValue('authCode', '123456', {
					shouldValidate: false,
				});
				await result.current.actions.handleVerifyEmailAuth();
			});

			// Verify setup
			expect(result.current.state.isEmailChecked).toBe(true);
			expect(result.current.state.isEmailSent).toBe(true);
			expect(result.current.state.isEmailVerified).toBe(true);

			// Action
			await act(async () => {
				result.current.actions.handleEmailChange();
			});

			// Assert
			expect(result.current.state.isEmailChecked).toBe(false);
			expect(result.current.state.isEmailSent).toBe(false);
			expect(result.current.state.isEmailVerified).toBe(false);
			expect(result.current.state.successMessage).toBeNull();
		});

		/*
		 * - 응답 객체에 명시적인 에러 메시지가 없을 때의 방어 로직 검증
		 * - 네트워크 에러 등으로 서버 메시지를 읽을 수 없을 때 사전에 정의된 기본 에러 문구를 출력하는지 확인
		 */
		test('인증번호 발송 실패 시 기본 에러 메시지를 사용한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// Setup: Email checked
			mockCheckEmailMutate.mockResolvedValue(true);
			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com', {
					shouldValidate: false,
				});
				await result.current.actions.handleCheckEmail();
			});

			// Mock Error without response.data.message
			mockSendEmailMutate.mockRejectedValue(new Error('Network Error'));

			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			expect(mockOnError).toHaveBeenCalledWith('인증번호 발송에 실패했습니다.');
		});

		/*
		 * - 에러 메시지 추출 우선순위 로직 검증 1
		 * - 서버 통신 에러 객체의 구조가 다를 때 최상단 message 프로퍼티를 정상적으로 추출하여 표출하는지 확인
		 */
		test('인증번호 검증 실패 시 에러 메시지 우선순위를 확인한다 (message prop)', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('authCode', '123456', {
					shouldValidate: false,
				});
			});

			// Mock Error with message property only
			mockVerifyCodeMutate.mockRejectedValue(new Error('Simple Error'));

			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			expect(mockOnError).toHaveBeenCalledWith('Simple Error');
		});

		/*
		 * - 에러 메시지 추출 우선순위 로직 검증 2
		 * - 에러 객체가 완전히 비어있을 경우 사전에 정의된 기본 에러 문구를 출력하여 앱 크래시를 방지하는지 확인
		 */
		test('인증번호 검증 실패 시 에러 메시지 우선순위를 확인한다 (fallback)', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('authCode', '123456', {
					shouldValidate: false,
				});
			});

			// Mock Error with nothing
			mockVerifyCodeMutate.mockRejectedValue({});

			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			expect(mockOnError).toHaveBeenCalledWith('인증번호가 일치하지 않습니다.');
		});

		/*
		 * - API 요청 진행 중 중복 실행 방지 로직 검증
		 * - 폼 제출 로직이 처리 중일 때 사용자의 추가적인 제출 시도가 발생해도 API가 중복으로 호출되지 않음을 확인
		 */
		test('회원가입 요청 중(isSignupPending)에는 중복 제출을 방지한다', async () => {
			(useSignup as jest.Mock).mockReturnValue({
				mutate: mockSignupMutate,
				isPending: true,
			});

			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				await result.current.actions.onSubmit();
			});

			expect(mockSignupMutate).not.toHaveBeenCalled();
		});

		/*
		 * - 회원가입 API 실패 시 응답 에러 객체가 비어있을 때의 예외 처리 검증
		 * - 명시적인 에러 메시지가 파싱되지 않을 경우 훅 내부의 기본 실패 문구를 출력하는지 확인
		 */
		test('회원가입 실패 시 기본 에러 메시지를 사용한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// Setup ready to submit
			await act(async () => {
				result.current.formMethods.reset({
					name: 'User',
					email: 'test@test.com',
					password: 'password123!',
					passwordConfirm: 'password123!',
					authCode: '123456',
				});
			});
			mockVerifyCodeMutate.mockResolvedValue('token');
			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			// Mock onError with empty object
			mockSignupMutate.mockImplementation((_data, options) => {
				options.onError({});
			});

			await act(async () => {
				await result.current.actions.onSubmit();
			});

			expect(mockOnError).toHaveBeenCalledWith('가입 실패');
		});
	});

	describe('콜백(Props) 미전달 시 분기 테스트', () => {
		/*
		 * - 훅 내부 로직 전체의 안정성 및 방어 로직 검증
		 * - 외부 주입 Props(콜백 함수들)가 전혀 없는 상태에서 폼의 각 단계별(중복확인, 발송, 검증, 제출) 성공 및 에러 발생 시 프로그램이 강제 종료되지 않는지 확인
		 */
		test('콜백 없이 각 단계별 성공/실패 시 크래시가 발생하지 않아야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic()); // No props

			// 1. 이메일 확인
			// Success (onToast missing)
			mockCheckEmailMutate.mockResolvedValue(true);
			await act(async () => {
				result.current.formMethods.setValue('email', 'valid@test.com', {
					shouldValidate: false,
				});
				await result.current.actions.handleCheckEmail();
			});
			// Fail (onError missing)
			mockCheckEmailMutate.mockResolvedValue(false);
			await act(async () => {
				await result.current.actions.handleCheckEmail();
			});

			// 2. 이메일 송신
			// Fail (onError missing) - Precondition: isEmailChecked=false
			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			// Reset state for success path
			mockCheckEmailMutate.mockResolvedValue(true);
			await act(async () => {
				await result.current.actions.handleCheckEmail();
			});

			// Success (onToast missing)
			mockSendEmailMutate.mockResolvedValue(undefined);
			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});
			// Fail API (onError missing)
			mockSendEmailMutate.mockRejectedValue(new Error('Fail'));
			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			// 3. 코드 검증
			// Fail length (onError missing)
			await act(async () => {
				result.current.formMethods.setValue('authCode', '123', {
					shouldValidate: false,
				});
				await result.current.actions.handleVerifyEmailAuth();
			});

			// 4. 제출
			// Submit API Fail (onError missing) & e?.message branch (null error)
			mockSignupMutate.mockImplementation((_data, options) => {
				options.onError(null);
			});
			await act(async () => {
				await result.current.actions.onSubmit();
			});
		});
	});
});
