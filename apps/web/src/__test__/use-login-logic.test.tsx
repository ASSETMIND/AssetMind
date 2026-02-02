import { renderHook, act, waitFor } from '@testing-library/react';
import { useLoginLogic } from '../hooks/auth/use-login-logic';
import { useLogin } from '../hooks/auth/use-login';
import { setAccessToken } from '../libs/axios';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';

// 모듈 및 api 모킹
jest.mock('../hooks/auth/use-login', () => ({
	useLogin: jest.fn(),
}));

jest.mock('react-router-dom', () => ({
	useNavigate: jest.fn(),
}));

jest.mock('../libs/axios', () => ({
	setAccessToken: jest.fn(),
}));

jest.mock('../store/auth', () => ({
	useAuthStore: jest.fn(),
}));

// 유닛 테스트 시작
describe('useLoginLogic 유닛 테스트', () => {
	const defaultProps = {
		onClose: jest.fn(),
	};

	let mockLoginMutate: jest.Mock;
	let mockNavigate: jest.Mock;
	let mockLoginAction: jest.Mock;

	beforeEach(() => {
		jest.clearAllMocks();

		mockLoginMutate = jest.fn();
		mockNavigate = jest.fn();
		mockLoginAction = jest.fn();

		(useLogin as jest.Mock).mockReturnValue({
			mutate: mockLoginMutate,
			isPending: false,
		});

		(useNavigate as jest.Mock).mockReturnValue(mockNavigate);

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
					accessToken: 'test-access-token',
					user: { id: 1, email: 'test@test.com' },
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

		test('로그인 성공 시 토큰 저장, 스토어 업데이트, 성공 토스트 표시, 페이지 이동이 수행되어야 한다', async () => {
			const { result } = renderLoginHook();

			//[로그인 성공] 폼 입력
			await act(async () => {
				result.current.formMethods.register('id');
				result.current.formMethods.register('password');

				result.current.formMethods.setValue('id', 'test@test.com', {
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
				{ id: 'test@test.com', password: 'password123!' },
				expect.any(Object),
			);
			expect(setAccessToken).toHaveBeenCalledWith('test-access-token');
			expect(mockLoginAction).toHaveBeenCalledWith({
				id: 1,
				email: 'test@test.com',
			});

			expect(result.current.state.toastMessage).toBe('로그인 되었습니다.');
			expect(defaultProps.onClose).toHaveBeenCalled();
			expect(mockNavigate).toHaveBeenCalledWith('/');
		});

		test('로그인 실패(401 Unauthorized) 시 토스트는 없고 비밀번호 필드에 에러를 표시해야 한다', async () => {
			const { result } = renderLoginHook();

			// [로그인 실패] 폼 입력
			await act(async () => {
				result.current.formMethods.register('password');
				result.current.formMethods.setValue('id', 'test@test.com', {
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

			// 토스트 메시지 없음 확인
			expect(result.current.state.toastMessage).toBeNull();

			// 에러 메시지 확인
			await waitFor(() => {
				const { errors } = result.current.formMethods.formState;
				expect(errors.password?.message).toBe(
					'아이디 또는 비밀번호를 확인해주세요.',
				);
			});
		});

		test('로그인 실패(404 Not Found) 시에도 토스트 없이 비밀번호 필드에 에러를 표시해야 한다', async () => {
			const { result } = renderLoginHook();

			await act(async () => {
				result.current.formMethods.register('password');
				result.current.formMethods.setValue('id', 'test@test.com', {
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

			expect(result.current.state.toastMessage).toBeNull();

			await waitFor(() => {
				const { errors } = result.current.formMethods.formState;
				expect(errors.password?.message).toBe(
					'아이디 또는 비밀번호를 확인해주세요.',
				);
			});
		});

		test('기타 서버 에러(예: 500) 발생 시 토스트 없이 "회원이 아닙니다..." 에러를 표시해야 한다', async () => {
			const { result } = renderLoginHook();

			await act(async () => {
				result.current.formMethods.register('password');
				result.current.formMethods.setValue('id', 'test@test.com', {
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

			expect(result.current.state.toastMessage).toBeNull();

			await waitFor(() => {
				const { errors } = result.current.formMethods.formState;
				expect(errors.password?.message).toBe(
					'회원이 아닙니다. 회원가입을 진행해 주세요',
				);
			});
		});
	});
});
