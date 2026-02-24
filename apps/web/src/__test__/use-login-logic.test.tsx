import { renderHook, act, waitFor } from '@testing-library/react';
import { useLoginLogic } from '../hooks/auth/use-login-logic';
import { useLogin } from '../hooks/auth/queries/use-login';
import { setAccessToken } from '../libs/axios';
import { useAuthStore } from '../store/auth';

// 모듈 및 api 모킹
jest.mock('../hooks/auth/queries/use-login', () => ({
	useLogin: jest.fn(),
}));

jest.mock('../libs/axios', () => ({
	setAccessToken: jest.fn(),
}));

jest.mock('../store/auth', () => ({
	useAuthStore: jest.fn(),
}));

// 유닛 테스트 시작
describe('useLoginLogic 유닛 테스트', () => {
	const mockOnSuccess = jest.fn();
	const mockOnError = jest.fn();

	const defaultProps = {
		onSuccess: mockOnSuccess,
		onError: mockOnError,
	};

	let mockLoginMutate: jest.Mock;
	let mockLoginAction: jest.Mock;

	beforeEach(() => {
		jest.clearAllMocks();

		mockLoginMutate = jest.fn();
		mockLoginAction = jest.fn();

		(useLogin as jest.Mock).mockReturnValue({
			mutate: mockLoginMutate,
			isPending: false,
		});

		(useAuthStore as unknown as jest.Mock).mockReturnValue({
			login: mockLoginAction,
		});
	});

	// Hook 렌더링 시 errors 구독을 강제
	const renderLoginHook = () => {
		return renderHook(() => {
			const logic = useLoginLogic(defaultProps);
			// eslint-disable-next-line @typescript-eslint/no-unused-vars
			const _ = logic.formMethods.formState.errors;
			return logic;
		});
	};

	describe('로그인 제출(onSubmit) 프로세스', () => {
		// 로그인 성공
		const setupLoginSuccess = () => {
			mockLoginMutate.mockImplementation((_data, options) => {
				options.onSuccess({
					data: {
						access_token: 'test-access-token',
					},
				});
			});
		};

		// 로그인 에러
		const setupLoginError = (status: number, message?: string) => {
			mockLoginMutate.mockImplementation((_data, options) => {
				options.onError({
					response: {
						status,
						data: { message },
					},
				});
			});
		};

		test('로그인 성공 시 토큰 저장, 스토어 업데이트, 성공 콜백이 호출되어야 한다', async () => {
			const { result } = renderLoginHook();

			//[로그인 성공] 폼 입력
			await act(async () => {
				result.current.formMethods.register('email');
				result.current.formMethods.register('password');

				result.current.formMethods.setValue('email', 'test@test.com', {
					shouldValidate: true,
				});
				result.current.formMethods.setValue('password', 'password123!', {
					shouldValidate: true,
				});
			});

			setupLoginSuccess();

			// 폼 제출
			await act(async () => {
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			expect(mockLoginMutate).toHaveBeenCalledWith(
				{ email: 'test@test.com', password: 'password123!' },
				expect.any(Object),
			);
			expect(setAccessToken).toHaveBeenCalledWith('test-access-token');
			expect(mockLoginAction).toHaveBeenCalledWith({
				id: 0,
				email: 'test@test.com',
				name: '사용자',
			});

			expect(mockOnSuccess).toHaveBeenCalled();
		});

		test('로그인 실패(401 Unauthorized) 시 에러 콜백 호출 및 비밀번호 필드에 에러를 표시해야 한다', async () => {
			const { result } = renderLoginHook();

			// [로그인 실패] 폼 입력
			await act(async () => {
				result.current.formMethods.register('password');
				result.current.formMethods.setValue('email', 'test@test.com', {
					shouldValidate: true,
				});
				result.current.formMethods.setValue('password', 'wrong-password', {
					shouldValidate: true,
				});
			});

			setupLoginError(401, 'Unauthorized');

			await act(async () => {
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			// 에러 콜백 확인
			expect(mockOnError).toHaveBeenCalledWith(
				'아이디 또는 비밀번호를 확인해주세요.',
			);

			// 에러 메시지 확인
			await waitFor(() => {
				const { errors } = result.current.formMethods.formState;
				expect(errors.password?.message).toBe(
					'아이디 또는 비밀번호를 확인해주세요.',
				);
			});
		});

		test('로그인 실패(404 Not Found) 시에도 에러 콜백 호출 및 비밀번호 필드에 에러를 표시해야 한다', async () => {
			const { result } = renderLoginHook();

			await act(async () => {
				result.current.formMethods.register('password');
				result.current.formMethods.setValue('email', 'test@test.com', {
					shouldValidate: true,
				});
				result.current.formMethods.setValue('password', 'unknown', {
					shouldValidate: true,
				});
			});

			setupLoginError(404, 'User Not Found');

			await act(async () => {
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			expect(mockOnError).toHaveBeenCalledWith(
				'아이디 또는 비밀번호를 확인해주세요.',
			);

			await waitFor(() => {
				const { errors } = result.current.formMethods.formState;
				expect(errors.password?.message).toBe(
					'아이디 또는 비밀번호를 확인해주세요.',
				);
			});
		});

		test('기타 서버 에러(예: 500) 발생 시 "회원이 아닙니다..." 에러를 표시해야 한다', async () => {
			const { result } = renderLoginHook();

			await act(async () => {
				result.current.formMethods.register('password');
				result.current.formMethods.setValue('email', 'test@test.com', {
					shouldValidate: true,
				});
				result.current.formMethods.setValue('password', 'valid', {
					shouldValidate: true,
				});
			});

			const serverMsg = '서버 내부 오류가 발생했습니다.';
			setupLoginError(500, serverMsg);

			await act(async () => {
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			expect(mockOnError).toHaveBeenCalledWith(
				'회원이 아닙니다. 회원가입을 진행해 주세요',
			);

			await waitFor(() => {
				const { errors } = result.current.formMethods.formState;
				expect(errors.password?.message).toBe(
					'회원이 아닙니다. 회원가입을 진행해 주세요',
				);
			});
		});

		test('유효하지 않은 데이터로 제출 시 onInvalid 콜백이 실행되어야 한다', async () => {
			const { result } = renderLoginHook();
			const consoleSpy = jest
				.spyOn(console, 'error')
				.mockImplementation(() => {});

			// 필수값 미입력 상태에서 제출 (email, password 공란)
			await act(async () => {
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			// console.error 호출 확인
			expect(consoleSpy).toHaveBeenCalledWith(
				'로그인 유효성 검사 실패:',
				expect.any(Object),
			);
			consoleSpy.mockRestore();
		});

		test('Props 없이 호출해도 에러 없이 동작하며, accessToken이 없으면 저장을 건너뛴다', async () => {
			const { result } = renderHook(() => useLoginLogic()); // Default Props 테스트

			// Mock success but no token
			mockLoginMutate.mockImplementation((_data, options) => {
				options.onSuccess({
					data: { access_token: undefined }, // No token
				});
			});

			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com');
				result.current.formMethods.setValue('password', 'password123!');
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			expect(setAccessToken).not.toHaveBeenCalled();
		});

		test('Props 없이 호출 시 에러가 발생해도 안전하게 처리되어야 한다', async () => {
			const { result } = renderHook(() => useLoginLogic()); // Default Props 테스트

			setupLoginError(400, 'Bad Request');

			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com');
				result.current.formMethods.setValue('password', 'password123!');
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});
			// 에러 없이 종료됨을 확인 (onError?.() 호출 시 크래시 안남)
		});

		test('로그인 진행 중(isLoggingIn: true)일 때는 제출이 막혀야 한다', async () => {
			(useLogin as jest.Mock).mockReturnValue({
				mutate: mockLoginMutate,
				isPending: true,
			});

			const { result } = renderLoginHook();

			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com');
				result.current.formMethods.setValue('password', 'password123!');
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			expect(mockLoginMutate).not.toHaveBeenCalled();
		});

		test('onSuccess 호출 시 response.data가 null이어도 안전하게 처리된다', async () => {
			const { result } = renderHook(() => useLoginLogic());

			mockLoginMutate.mockImplementation((_data, options) => {
				options.onSuccess({ data: null } as any);
			});

			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com');
				result.current.formMethods.setValue('password', 'password123!');
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			expect(setAccessToken).not.toHaveBeenCalled();
		});

		test('onError 호출 시 error 객체가 비어있어도 안전하게 처리된다', async () => {
			const { result } = renderHook(() => useLoginLogic());

			mockLoginMutate.mockImplementation((_data, options) => {
				options.onError(null);
			});

			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com');
				result.current.formMethods.setValue('password', 'password123!');
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});
		});
	});
});
