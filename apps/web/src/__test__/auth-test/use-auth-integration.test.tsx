import { renderHook, act, waitFor } from '@testing-library/react';
import { useSignupLogic } from '../../hooks/auth/use-signup-logic';
import { useLoginLogic } from '../../hooks/auth/use-login-logic';
import { useRefresh } from '../../hooks/auth/use-refresh';
import { setAccessToken } from '../../libs/axios';
import { useAuthStore } from '../../store/auth';

/*
 * 인증 관련 훅(useSignupLogic, useLoginLogic, useRefresh)들을 연동하여
 * 실제 사용자가 '회원가입 -> 로그인 -> 세션 유지(새로고침)'를 경험하는
 * 전체적인 인증 플로우(E2E 유사)를 검증하는 통합 테스트 코드
 */

// 외부 의존성 모킹 (Axios 유틸, Store)
jest.mock('../libs/axios', () => {
	const originalModule = jest.requireActual('../libs/axios');
	return {
		...originalModule,
		setAccessToken: jest.fn(),
		removeAuthTokens: jest.fn(),
	};
});

jest.mock('../store/auth', () => ({
	useAuthStore: jest.fn(),
}));

// 쿼리 훅 모킹 (MSW 대신 직접 제어)
const mockCheckEmail = jest.fn();
const mockSendEmail = jest.fn();
const mockVerifyEmail = jest.fn();
const mockSignup = jest.fn();
const mockLogin = jest.fn();
const mockRefreshToken = jest.fn();

jest.mock('../hooks/auth/queries/use-email-verification', () => ({
	useCheckEmail: () => ({ mutateAsync: mockCheckEmail, isPending: false }),
	useSendEmailCode: () => ({ mutateAsync: mockSendEmail, isPending: false }),
	useVerifyEmailCode: () => ({
		mutateAsync: mockVerifyEmail,
		isPending: false,
	}),
}));

jest.mock('../hooks/auth/queries/use-signup', () => ({
	useSignup: () => ({ mutate: mockSignup, isPending: false }),
}));

jest.mock('../hooks/auth/queries/use-login', () => ({
	useLogin: () => ({ mutate: mockLogin, isPending: false }),
}));

jest.mock('../hooks/auth/queries/use-refresh-token', () => ({
	useRefreshToken: () => ({ mutateAsync: mockRefreshToken }),
}));

describe('Auth 통합 테스트 (회원가입 -> 로그인 -> 토큰 갱신)', () => {
	const mockLoginAction = jest.fn();
	const mockLogoutAction = jest.fn();

	beforeEach(() => {
		jest.clearAllMocks();
		(useAuthStore as unknown as jest.Mock).mockReturnValue({
			login: mockLoginAction,
			logout: mockLogoutAction,
		});
	});

	/*
	 * - 사용자 시나리오 전체 흐름(회원가입 -> 로그인 -> 토큰 갱신) 검증
	 * - 각 단계의 상태 변화 및 API 모킹 호출이 순차적으로 올바르게 이루어지는지 확인
	 */
	test('사용자는 회원가입 절차를 완료한 후 로그인을 수행하고, 세션을 유지할 수 있다', async () => {
		// 테스트 시나리오를 위한 가상 사용자 데이터 및 인메모리 DB 설정
		const testUser = {
			email: 'flow-test@example.com',
			password: 'FlowPassword123!',
			name: '플로우유저',
		};
		const registeredDb = new Set<string>();

		// API 모킹 구현부
		// - 이메일 중복 확인: DB에 없으면 사용 가능 처리
		mockCheckEmail.mockImplementation(async (email) => {
			return !registeredDb.has(email);
		});

		// - 인증번호 전송: 무조건 성공 처리
		mockSendEmail.mockResolvedValue(undefined);

		// - 인증번호 검증: 특정 번호('123456') 입력 시 성공 토큰 반환
		mockVerifyEmail.mockImplementation(async ({ code }) => {
			if (code === '123456') return 'mock-signup-token';
			throw new Error('Invalid code');
		});

		// - 회원가입: 성공 시 인메모리 DB에 이메일 저장 후 onSuccess 콜백 실행
		mockSignup.mockImplementation((data, options) => {
			registeredDb.add(data.email);
			options.onSuccess();
		});

		// - 로그인: DB에 이메일이 존재하고 비밀번호가 일치하면 액세스 토큰 반환
		mockLogin.mockImplementation((data, options) => {
			if (registeredDb.has(data.email) && data.password === testUser.password) {
				options.onSuccess({ data: { access_token: 'flow-access-token' } });
			} else {
				options.onError({ response: { status: 401 } });
			}
		});

		// - 토큰 갱신(Refresh): 성공 시 새로운 액세스 토큰 반환
		mockRefreshToken.mockResolvedValue({
			data: { access_token: 'new-refreshed-token' },
		});

		// Phase 1: 회원가입 (Signup) 흐름 검증
		const onSignupSuccess = jest.fn();
		const onSignupError = jest.fn();
		const onToast = jest.fn();

		const { result: signupResult } = renderHook(() =>
			useSignupLogic({
				onSuccess: onSignupSuccess,
				onError: onSignupError,
				onToast,
			}),
		);

		// 이메일 입력 및 중복 확인 검증
		await act(async () => {
			signupResult.current.formMethods.setValue('email', testUser.email);
		});
		await act(async () => {
			await signupResult.current.actions.handleCheckEmail();
		});
		expect(signupResult.current.state.isEmailChecked).toBe(true);
		expect(onToast).toHaveBeenCalledWith(
			'사용 가능한 아이디입니다. 인증번호를 전송해주세요.',
		);

		// 인증번호 전송 로직 검증
		await act(async () => {
			await signupResult.current.actions.handleSendEmailAuth();
		});
		expect(signupResult.current.state.isEmailSent).toBe(true);

		// 인증번호 입력 및 검증 성공 로직 검증
		await act(async () => {
			signupResult.current.formMethods.setValue('authCode', '123456');
		});
		await act(async () => {
			await signupResult.current.actions.handleVerifyEmailAuth();
		});
		expect(signupResult.current.state.isEmailVerified).toBe(true);

		// 필수 정보 입력 및 폼 제출(회원가입) 로직 검증
		await act(async () => {
			signupResult.current.formMethods.setValue('name', testUser.name);
			signupResult.current.formMethods.setValue('password', testUser.password);
			signupResult.current.formMethods.setValue(
				'passwordConfirm',
				testUser.password,
			);
		});
		await act(async () => {
			await signupResult.current.actions.onSubmit();
		});

		// 회원가입 성공 콜백 정상 호출 확인
		await waitFor(() => {
			expect(onSignupSuccess).toHaveBeenCalled();
		});
		expect(onSignupError).not.toHaveBeenCalled();

		// Phase 2: 로그인 (Login) 흐름 검증
		const onLoginSuccess = jest.fn();
		const onLoginError = jest.fn();

		const { result: loginResult } = renderHook(() =>
			useLoginLogic({
				onSuccess: onLoginSuccess,
				onError: onLoginError,
			}),
		);

		// 가입한 계정 정보 입력 및 로그인 폼 제출 검증
		await act(async () => {
			loginResult.current.formMethods.setValue('email', testUser.email);
			loginResult.current.formMethods.setValue('password', testUser.password);
		});
		await act(async () => {
			await loginResult.current.actions.onSubmit({
				preventDefault: () => {},
			} as any);
		});

		// 로그인 성공 콜백 정상 호출 확인
		await waitFor(() => {
			expect(onLoginSuccess).toHaveBeenCalled();
		});
		expect(onLoginError).not.toHaveBeenCalled();

		// Axios 유틸 함수 호출 및 토큰 저장 확인
		expect(setAccessToken).toHaveBeenCalledWith('flow-access-token');

		// Zustand 스토어의 login 액션 호출 여부 및 파라미터 확인
		expect(mockLoginAction).toHaveBeenCalledWith(
			expect.objectContaining({
				email: testUser.email,
				name: '사용자', // useLoginLogic에서 하드코딩된 값 확인
			}),
		);

		// Phase 3: 세션 유지 (RTR - 리프레시 토큰) 흐름 검증
		// 페이지 새로고침(또는 재접속) 상황을 시뮬레이션하기 위해 localStorage 설정
		localStorage.setItem('isAuthenticated', 'true');

		const { result: refreshResult } = renderHook(() => useRefresh());

		// 토큰 갱신 초기화 완료 대기 검증
		await waitFor(() => {
			expect(refreshResult.current.isInitialized).toBe(true);
		});

		// 리프레시 토큰 API 정상 호출 확인
		expect(mockRefreshToken).toHaveBeenCalled();

		// 새로 발급된 액세스 토큰으로 Axios 유틸 함수 호출 확인
		expect(setAccessToken).toHaveBeenCalledWith('new-refreshed-token');

		// 스토어의 login 액션이 호출되어 인증 상태가 복구되는지 확인
		expect(mockLoginAction).toHaveBeenCalledWith(
			expect.objectContaining({ email: '', name: '사용자' }),
		);
	});
});
