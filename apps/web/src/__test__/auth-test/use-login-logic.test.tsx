import { renderHook, act, waitFor } from '@testing-library/react';
import { useLoginLogic } from '../../hooks/auth/use-login-logic';
import { useLogin } from '../../hooks/auth/queries/use-login';
import { setAccessToken } from '../../libs/axios';
import { useAuthStore } from '../../store/auth';

// 로그인 비즈니스 로직(useLoginLogic) 커스텀 훅의 폼 제어, API 호출, 전역 상태 업데이트 및 다양한 응답(성공/실패)에 따른 에러 처리 등을 검증하는 유닛 테스트 코드

// 외부 모듈 및 API 훅 모킹
jest.mock('../hooks/auth/queries/use-login', () => ({
	useLogin: jest.fn(),
}));

jest.mock('../libs/axios', () => ({
	setAccessToken: jest.fn(),
}));

jest.mock('../store/auth', () => ({
	useAuthStore: jest.fn(),
}));

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

	// 폼 상태 에러(errors) 구독을 활성화하기 위한 헬퍼 함수
	const renderLoginHook = () => {
		return renderHook(() => {
			const logic = useLoginLogic(defaultProps);
			// eslint-disable-next-line @typescript-eslint/no-unused-vars
			const _ = logic.formMethods.formState.errors;
			return logic;
		});
	};

	describe('로그인 제출(onSubmit) 프로세스', () => {
		// API 호출 성공 모킹 헬퍼
		const setupLoginSuccess = () => {
			mockLoginMutate.mockImplementation((_data, options) => {
				options.onSuccess({
					data: {
						access_token: 'test-access-token',
					},
				});
			});
		};

		// API 호출 에러 모킹 헬퍼
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

		/*
		 * - 정상적인 로그인 정보 입력 및 폼 제출 로직 검증
		 * - API 성공 응답 수신 시 액세스 토큰이 저장되는지 확인
		 * - 전역 상태 스토어에 사용자 정보가 업데이트되는지 확인
		 * - 외부 주입된 onSuccess 콜백 함수가 실행되는지 확인
		 */
		test('로그인 성공 시 토큰 저장, 스토어 업데이트, 성공 콜백이 호출되어야 한다', async () => {
			const { result } = renderLoginHook();

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

		/*
		 * - 인증 실패(비밀번호 불일치 등) 상황의 401 에러 핸들링 검증
		 * - 주입된 onError 콜백이 올바른 안내 문구와 함께 실행되는지 확인
		 * - 폼 상태(비밀번호 필드)에 에러 메시지가 정상적으로 바인딩되는지 확인
		 */
		test('로그인 실패(401 Unauthorized) 시 에러 콜백 호출 및 비밀번호 필드에 에러를 표시해야 한다', async () => {
			const { result } = renderLoginHook();

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

		/*
		 * - 존재하지 않는 계정으로 접근 시 발생하는 404 에러 핸들링 검증
		 * - 401 에러와 동일하게 사용자의 정보 보호를 위해 모호한 안내 문구가 표시되는지 확인
		 */
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

		/*
		 * - 서버 장애나 미가입자 접근 등 기타(500 등) 에러 코드 발생 시 핸들링 검증
		 * - 회원가입을 유도하는 지정된 에러 안내 문구가 표시되는지 확인
		 */
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

		/*
		 * - 필수 입력값이 누락되거나 유효성 검사를 통과하지 못한 폼 제출 처리 검증
		 * - 콘솔에 에러를 출력하고 API 호출 등의 후속 로직이 진행되지 않음을 확인
		 */
		test('유효하지 않은 데이터로 제출 시 onInvalid 콜백이 실행되어야 한다', async () => {
			const { result } = renderLoginHook();
			const consoleSpy = jest
				.spyOn(console, 'error')
				.mockImplementation(() => {});

			await act(async () => {
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});

			expect(consoleSpy).toHaveBeenCalledWith(
				'로그인 유효성 검사 실패:',
				expect.any(Object),
			);
			consoleSpy.mockRestore();
		});

		/*
		 * - 외부 콜백 Props 없이 단독으로 훅이 사용되었을 때의 안정성 검증
		 * - 응답 페이로드에 토큰이 누락되었을 때 불필요한 저장을 건너뛰는지 방어 로직 확인
		 */
		test('Props 없이 호출해도 에러 없이 동작하며, accessToken이 없으면 저장을 건너뛴다', async () => {
			const { result } = renderHook(() => useLoginLogic());

			mockLoginMutate.mockImplementation((_data, options) => {
				options.onSuccess({
					data: { access_token: undefined },
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

		/*
		 * - 에러 발생 시 외부 주입된 콜백 Props가 없어도 훅 내부 로직이 중단되지 않는지 안정성 검증
		 */
		test('Props 없이 호출 시 에러가 발생해도 안전하게 처리되어야 한다', async () => {
			const { result } = renderHook(() => useLoginLogic());

			setupLoginError(400, 'Bad Request');

			await act(async () => {
				result.current.formMethods.setValue('email', 'test@test.com');
				result.current.formMethods.setValue('password', 'password123!');
				await result.current.actions.onSubmit({
					preventDefault: () => {},
				} as any);
			});
		});

		/*
		 * - API 요청이 이미 진행 중인 상태에서의 중복 호출 방지 로직 검증
		 * - isPending 상태일 때 onSubmit 함수가 실행되어도 mutate가 호출되지 않음을 확인
		 */
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

		/*
		 * - 백엔드 API 성공 응답 포맷이 비정상적(data 필드가 null)일 때의 예외 처리 검증
		 * - 런타임 에러 발생 없이 안전하게 로직이 마무리되는지 확인
		 */
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

		/*
		 * - 백엔드 API 실패 응답 객체가 비어있을 경우의 방어 로직 검증
		 * - 예상치 못한 에러 구조 반환 시에도 프로그램이 크래시되지 않는지 확인
		 */
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
