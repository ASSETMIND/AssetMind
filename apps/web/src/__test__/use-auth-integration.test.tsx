import { renderHook, act, waitFor } from '@testing-library/react';
import { useSignupLogic } from '../hooks/auth/use-signup-logic';
import { useLoginLogic } from '../hooks/auth/use-login-logic';
import { useRefresh } from '../hooks/auth/use-refresh';
import { setAccessToken } from '../libs/axios';
import { useAuthStore } from '../store/auth';

// 1. 외부 의존성 모킹 (Axios 유틸, Store)
// 실제 API 호출은 MSW가 처리하므로 쿼리 훅(useLogin, useSignup 등)은 모킹하지 않고 실제 코드를 사용합니다.
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

// 2. 쿼리 훅 모킹 (MSW 대신 직접 제어)
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

describe('Auth 통합 테스트 (회원가입 -> 로그인)', () => {
	const mockLoginAction = jest.fn();
	const mockLogoutAction = jest.fn();

	beforeEach(() => {
		jest.clearAllMocks();
	});

	beforeEach(() => {
		(useAuthStore as unknown as jest.Mock).mockReturnValue({
			login: mockLoginAction,
			logout: mockLogoutAction,
		});
	});

	test('사용자는 회원가입 절차를 완료한 후 로그인을 수행할 수 있다', async () => {
		// 0. 테스트 시나리오를 위한 가짜 백엔드 로직 구현
		const testUser = {
			email: 'flow-test@example.com',
			password: 'FlowPassword123!',
			name: '플로우유저',
		};
		const registeredDb = new Set<string>(); // 인메모리 DB

		// [Mock 구현] 이메일 중복 확인: DB에 없으면 사용 가능
		mockCheckEmail.mockImplementation(async (email) => {
			return !registeredDb.has(email);
		});

		// [Mock 구현] 인증번호 전송: 항상 성공
		mockSendEmail.mockResolvedValue(undefined);

		// [Mock 구현] 인증번호 검증: '123456'일 때만 토큰 반환
		mockVerifyEmail.mockImplementation(async ({ code }) => {
			if (code === '123456') return 'mock-signup-token';
			throw new Error('Invalid code');
		});

		// [Mock 구현] 회원가입: DB에 이메일 저장
		mockSignup.mockImplementation((data, options) => {
			registeredDb.add(data.email);
			options.onSuccess();
		});

		// [Mock 구현] 로그인: DB에 있고 비밀번호 일치 시 성공
		mockLogin.mockImplementation((data, options) => {
			if (registeredDb.has(data.email) && data.password === testUser.password) {
				options.onSuccess({ data: { access_token: 'flow-access-token' } });
			} else {
				options.onError({ response: { status: 401 } });
			}
		});

		// [Mock 구현] 토큰 갱신: 성공 시 새 토큰 반환
		mockRefreshToken.mockResolvedValue({
			data: { access_token: 'new-refreshed-token' },
		});

		// =======================================================
		// Phase 1: 회원가입 (Signup)
		// =======================================================
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

		// 1-1. 이메일 입력 및 중복 확인
		await act(async () => {
			signupResult.current.formMethods.setValue('email', testUser.email);
		});

		await act(async () => {
			await signupResult.current.actions.handleCheckEmail();
		});

		// 중복 확인 성공 검증
		expect(signupResult.current.state.isEmailChecked).toBe(true);
		expect(onToast).toHaveBeenCalledWith(
			'사용 가능한 아이디입니다. 인증번호를 전송해주세요.',
		);

		// 1-2. 인증번호 전송
		await act(async () => {
			await signupResult.current.actions.handleSendEmailAuth();
		});
		expect(signupResult.current.state.isEmailSent).toBe(true);

		// 1-3. 인증번호 검증
		await act(async () => {
			signupResult.current.formMethods.setValue('authCode', '123456');
		});

		await act(async () => {
			await signupResult.current.actions.handleVerifyEmailAuth();
		});
		expect(signupResult.current.state.isEmailVerified).toBe(true);

		// 1-4. 나머지 정보 입력 및 회원가입 제출
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

		// 회원가입 성공 콜백 호출 확인
		await waitFor(() => {
			expect(onSignupSuccess).toHaveBeenCalled();
		});
		expect(onSignupError).not.toHaveBeenCalled();

		// =======================================================
		// Phase 2: 로그인 (Login)
		// =======================================================
		const onLoginSuccess = jest.fn();
		const onLoginError = jest.fn();

		const { result: loginResult } = renderHook(() =>
			useLoginLogic({
				onSuccess: onLoginSuccess,
				onError: onLoginError,
			}),
		);

		// 2-1. 가입한 정보로 로그인 시도
		await act(async () => {
			loginResult.current.formMethods.setValue('email', testUser.email);
			loginResult.current.formMethods.setValue('password', testUser.password);
		});

		await act(async () => {
			await loginResult.current.actions.onSubmit({
				preventDefault: () => {},
			} as any);
		});

		// 2-2. 로그인 성공 검증
		await waitFor(() => {
			expect(onLoginSuccess).toHaveBeenCalled();
		});
		expect(onLoginError).not.toHaveBeenCalled();

		// 토큰 저장 확인
		expect(setAccessToken).toHaveBeenCalledWith('flow-access-token');

		// 스토어 로그인 액션 호출 확인
		expect(mockLoginAction).toHaveBeenCalledWith(
			expect.objectContaining({
				email: testUser.email,
				name: '사용자', // useLoginLogic에서 하드코딩된 값
			}),
		);

		// =======================================================
		// Phase 3: 세션 유지 (RTR) - 페이지 새로고침 시뮬레이션
		// =======================================================
		// 로그인 성공 상태 가정 (localStorage 설정)
		localStorage.setItem('isAuthenticated', 'true');

		const { result: refreshResult } = renderHook(() => useRefresh());

		// 훅 내부의 useEffect가 실행되고 초기화될 때까지 대기
		await waitFor(() => {
			expect(refreshResult.current.isInitialized).toBe(true);
		});

		// 리프레시 토큰 API 호출 확인
		expect(mockRefreshToken).toHaveBeenCalled();

		// 갱신된 액세스 토큰 저장 확인
		expect(setAccessToken).toHaveBeenCalledWith('new-refreshed-token');

		// 로그인 상태 복구 확인 (useRefresh 로직상 email은 빈 문자열)
		expect(mockLoginAction).toHaveBeenCalledWith(
			expect.objectContaining({ email: '', name: '사용자' }),
		);
	});
});
