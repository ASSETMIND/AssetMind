import { renderHook, act } from '@testing-library/react';
import { useSignupLogic } from '../hooks/auth/use-signup-logic';

// api 모킹
const mockCheckIDMutate = jest.fn();
const mockSendEmailMutate = jest.fn();
const mockVerifyCodeMutate = jest.fn();
const mockSignupMutate = jest.fn();

jest.mock('../hooks/auth/use-check-ID', () => ({
	useCheckID: () => ({ mutateAsync: mockCheckIDMutate, isPending: false }),
}));

jest.mock('../hooks/auth/use-email-verification', () => ({
	useSendEmailCode: () => ({
		mutateAsync: mockSendEmailMutate,
		isPending: false,
	}),
	useVerifyEmailCode: () => ({
		mutateAsync: mockVerifyCodeMutate,
		isPending: false,
	}),
}));

jest.mock('../hooks/auth/use-signup', () => ({
	useSignup: () => ({ mutate: mockSignupMutate, isPending: false }),
}));

describe('useSignupLogic 유닛 테스트', () => {
	const defaultProps = {
		onClose: jest.fn(),
		onClickLogin: jest.fn(),
	};

	beforeEach(() => {
		jest.clearAllMocks();
	});

	// 이제부터 테스트 진행
	// 아이디 관리 및 상태 초기화 테스트
	describe('1. 아이디 관리 및 상태 초기화', () => {
		test('유효하지 않은 이메일 형식이면 API를 호출하지 않아야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('id', 'invalid-email');
			});

			await act(async () => {
				await result.current.actions.handleCheckID();
			});

			expect(mockCheckIDMutate).not.toHaveBeenCalled();
		});

		//
		test('아이디 중복 확인 결과가 "중복(false)"이면 에러를 설정해야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// 유효한 이메일 입력
			await act(async () => {
				result.current.formMethods.setValue('id', 'duplicate@test.com');
			});

			// API가 false(중복)를 반환하도록 설정
			mockCheckIDMutate.mockResolvedValue(false);

			// 실행
			await act(async () => {
				await result.current.actions.handleCheckID();
			});

			// 검증: 중복 에러 메시지가 설정되어야 함
			expect(result.current.state.isIDChecked).toBe(false);
			expect(result.current.formMethods.formState.errors.id?.message).toBe(
				'이미 사용 중인 아이디입니다.',
			);
			expect(result.current.state.toastMessage).toBe(
				'이미 사용 중인 아이디입니다.',
			);
		});

		test('아이디 입력값이 변경되면 기존의 인증 상태들이 모두 초기화되어야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// 중복 에러 상태로 시작
			mockCheckIDMutate.mockResolvedValue(false);
			await act(async () => {
				result.current.formMethods.setValue('id', 'dup@email.com');
			});
			await act(async () => {
				await result.current.actions.handleCheckID();
			});

			// 에러가 있는지 확인
			expect(result.current.formMethods.formState.errors.id?.type).toBe(
				'duplicate',
			);

			// 아이디 값이 변경됨 -> handleIdChange 호출
			await act(async () => {
				result.current.actions.handleIdChange();
			});

			// 중복 에러가 사라져야 함 (초기화 확인)
			expect(result.current.formMethods.formState.errors.id).toBeUndefined();
		});
	});

	// 이메일 인증번호 전송 흐름 테스트
	describe('2. 인증번호 전송 흐름', () => {
		test('아이디 중복 확인을 하지 않고 전송을 누르면 경고 메시지가 떠야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			expect(mockSendEmailMutate).not.toHaveBeenCalled();
			expect(result.current.state.toastMessage).toBe(
				'먼저 아이디 중복 확인을 진행해주세요.',
			);
		});

		// API가 명시적 에러 메시지를 줄 때
		test('이메일 발송 API가 실패하면 서버 에러 메시지를 토스트에 띄워야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// 전제 조건: ID 확인 완료
			mockCheckIDMutate.mockResolvedValue(true);
			await act(async () => {
				result.current.formMethods.setValue('id', 'valid@email.com');
			});
			await act(async () => {
				await result.current.actions.handleCheckID();
			});

			// API 실패 Mocking (서버 메시지 있음)
			mockSendEmailMutate.mockRejectedValue({
				response: { data: { message: '서버 에러 발생' } },
			});

			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			expect(result.current.state.isEmailSent).toBe(false);
			expect(result.current.state.toastMessage).toBe('서버 에러 발생');
		});

		// API가 메시지 없이 실패할 때 (기본값 사용)
		test('이메일 발송 실패 시 서버 응답 메시지가 없으면 기본 메시지를 띄워야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			// 전제 조건 설정
			mockCheckIDMutate.mockResolvedValue(true);
			await act(async () => {
				result.current.formMethods.setValue('id', 'valid@email.com');
			});
			await act(async () => {
				await result.current.actions.handleCheckID();
			});

			// API 실패 Mocking (response 없음 -> 기본 메시지 사용)
			mockSendEmailMutate.mockRejectedValue(new Error('Network Error'));

			await act(async () => {
				await result.current.actions.handleSendEmailAuth();
			});

			// 기본 에러 메시지 확인
			expect(result.current.state.toastMessage).toBe(
				'인증번호 발송에 실패했습니다.',
			);
		});
	});

	// 인증번호 검증 흐름 테스트
	describe('3. 인증번호 검증 흐름', () => {
		test('인증번호가 6자리가 아니면 API를 호출하지 않고 경고해야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('authCode', '123'); // 3자리
			});

			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			expect(mockVerifyCodeMutate).not.toHaveBeenCalled();
			expect(result.current.state.toastMessage).toContain(
				'6자리를 입력해주세요',
			);
		});

		test('인증번호 검증에 실패하면 에러 메시지와 Form 에러를 설정해야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('id', 'test@test.com');
				result.current.formMethods.setValue('authCode', '123456');
			});

			const errorMsg = '인증번호가 틀렸습니다.';
			mockVerifyCodeMutate.mockRejectedValue({
				response: { data: { message: errorMsg } },
			});

			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			expect(result.current.state.isEmailVerified).toBe(false);
			expect(result.current.state.toastMessage).toBe(errorMsg);
			expect(
				result.current.formMethods.formState.errors.authCode?.message,
			).toBe(errorMsg);
		});

		test('인증번호 검증 성공 시 isEmailVerified가 true가 되어야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('authCode', '123456');
			});

			mockVerifyCodeMutate.mockResolvedValue(true);

			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});

			expect(result.current.state.isEmailVerified).toBe(true);
			expect(result.current.state.toastMessage).toBe(
				'이메일 인증이 완료되었습니다.',
			);
		});
	});

	// 최종 회원가입 제출(onSubmit) 테스트
	describe('4. 회원가입 제출(onSubmit)', () => {
		const setupReadyToSubmit = async (result: any) => {
			await act(async () => {
				result.current.formMethods.setValue('id', 'final@test.com');
				result.current.formMethods.setValue('password', 'password123!');
				result.current.formMethods.setValue('passwordConfirm', 'password123!');
				result.current.formMethods.setValue('authCode', '123456');
			});

			mockVerifyCodeMutate.mockResolvedValue(true);
			await act(async () => {
				await result.current.actions.handleVerifyEmailAuth();
			});
		};

		test('이메일 인증이 완료되지 않았으면 가입 요청을 보내지 않아야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));

			await act(async () => {
				result.current.formMethods.setValue('id', 'no-auth@test.com');
				result.current.formMethods.setValue('password', 'pass123!');
				result.current.formMethods.setValue('passwordConfirm', 'pass123!');
				result.current.formMethods.setValue('authCode', '000000');
			});

			await act(async () => {
				await result.current.actions.onSubmit({} as any);
			});

			expect(mockSignupMutate).not.toHaveBeenCalled();
			expect(result.current.state.toastMessage).toBe(
				'이메일 인증을 완료해주세요.',
			);
		});

		// 회원가입 실패(onError) 케이스 커버
		test('회원가입 요청이 실패하면(onError) 에러 메시지를 토스트에 띄워야 한다', async () => {
			const { result } = renderHook(() => useSignupLogic(defaultProps));
			await setupReadyToSubmit(result);

			// 실패 시뮬레이션: onError 콜백 실행
			const serverErrorMsg = '이미 가입된 회원입니다.';
			mockSignupMutate.mockImplementation((_data, options) => {
				if (options?.onError) {
					options.onError({ message: serverErrorMsg });
				}
			});

			await act(async () => {
				await result.current.actions.onSubmit({} as any);
			});

			expect(result.current.state.toastMessage).toBe(serverErrorMsg);
		});

		test('모든 조건 만족 시 가입 요청을 보내고, 성공 시 페이지 이동 콜백을 실행해야 한다', async () => {
			jest.useFakeTimers();

			const { result } = renderHook(() => useSignupLogic(defaultProps));
			await setupReadyToSubmit(result);

			// 성공 시뮬레이션: onSuccess 콜백 실행
			mockSignupMutate.mockImplementation((_data, options) => {
				options.onSuccess();
			});

			await act(async () => {
				await result.current.actions.onSubmit({} as any);
			});

			expect(mockSignupMutate).toHaveBeenCalledWith(
				expect.objectContaining({
					id: 'final@test.com',
					password: 'password123!',
				}),
				expect.any(Object),
			);

			expect(result.current.state.toastMessage).toBe(
				'회원가입 완료! 로그인해주세요.',
			);

			act(() => {
				jest.advanceTimersByTime(2000);
			});

			expect(defaultProps.onClose).toHaveBeenCalled();
			expect(defaultProps.onClickLogin).toHaveBeenCalled();

			jest.useRealTimers();
		});
	});
});
