import { renderHook, act } from '@testing-library/react';
import { useSocialLoginLogic } from '../hooks/auth/use-social-login-logic';
import { useMutation } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { setAccessToken } from '../libs/axios';

//'import.meta.env' 에러 해결을 위한 상수 모듈 Mocking
const MOCK_KAKAO_URL = 'http://mock-kakao.com/auth';
const MOCK_GOOGLE_URL = 'http://mock-google.com/auth';

jest.mock('../libs/constants/auth', () => ({
	KAKAO_AUTH_URL: 'http://mock-kakao.com/auth',
	GOOGLE_AUTH_URL: 'http://mock-google.com/auth',
}));

// 2. 나머지 외부 의존성 모듈 모킹
jest.mock('react-router-dom', () => ({
	useNavigate: jest.fn(),
	useSearchParams: jest.fn(),
}));

jest.mock('@tanstack/react-query', () => ({
	useMutation: jest.fn(),
}));

jest.mock('../libs/axios', () => ({
	setAccessToken: jest.fn(),
}));

jest.mock('../store/auth', () => ({
	useAuthStore: jest.fn(),
}));

jest.mock('../api/auth', () => ({
	socialLogin: jest.fn(),
}));

describe('useSocialLoginLogic 유닛 테스트', () => {
	let mockNavigate: jest.Mock;
	let mockLoginAction: jest.Mock;
	let mockMutate: jest.Mock;
	let mutationOptions: any;

	// window.location 저장을 위한 변수
	const originalLocation = window.location;

	beforeAll(() => {
		// window.location 모킹 (Read-only 에러 방지)
		delete (window as any).location;
		Object.defineProperty(window, 'location', {
			writable: true,
			value: { href: '' },
		});

		jest.spyOn(console, 'error').mockImplementation(() => {});
	});

	afterAll(() => {
		// 테스트 종료 후 원상복구
		Object.defineProperty(window, 'location', {
			writable: true,
			value: originalLocation,
		});
		jest.restoreAllMocks();
	});

	beforeEach(() => {
		jest.clearAllMocks();
		window.location.href = '';

		mockNavigate = jest.fn();
		mockLoginAction = jest.fn();
		mockMutate = jest.fn();

		(useNavigate as jest.Mock).mockReturnValue(mockNavigate);
		(useSearchParams as jest.Mock).mockReturnValue([new URLSearchParams()]);

		(useAuthStore as unknown as jest.Mock).mockReturnValue({
			login: mockLoginAction,
		});

		(useMutation as jest.Mock).mockImplementation((options) => {
			mutationOptions = options;
			return {
				mutate: mockMutate,
				isPending: false,
			};
		});
	});

	describe('소셜 로그인 리다이렉트 (handleSocialLogin)', () => {
		test('Kakao provider 전달 시 Kakao 인증 URL로 이동하고 상태를 변경해야 한다', () => {
			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialLogin('kakao');
			});

			expect(result.current.state.isRedirecting).toBe(true);
			// 실제 import 대신 Mocking된 URL과 비교
			expect(window.location.href).toBe(MOCK_KAKAO_URL);
		});

		test('Google provider 전달 시 Google 인증 URL로 이동하고 상태를 변경해야 한다', () => {
			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialLogin('google');
			});

			expect(result.current.state.isRedirecting).toBe(true);
			expect(window.location.href).toBe(MOCK_GOOGLE_URL);
		});
	});

	describe('소셜 로그인 콜백 처리 (handleSocialCallback)', () => {
		test('URL에 code가 없으면 경고창을 띄우고 메인으로 이동해야 한다', () => {
			(useSearchParams as jest.Mock).mockReturnValue([new URLSearchParams('')]);

			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			expect(result.current.state.toastMessage).toBe(
				'인증 정보를 받아오지 못했습니다. 다시 시도해주세요.',
			);
			expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
			expect(mockMutate).not.toHaveBeenCalled();
		});

		test('URL에 error가 있으면 토스트 메시지를 표시하고 로그인 페이지로 이동해야 한다', () => {
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('error=access_denied'),
			]);
			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			expect(result.current.state.toastMessage).toBe(
				'로그인 과정에서 오류가 발생했습니다. 다시 시도해주세요.',
			);
			expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
			expect(mockMutate).not.toHaveBeenCalled();
		});

		test('URL에 code가 있으면 mutation을 실행해야 한다', () => {
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('code=test-auth-code'),
			]);

			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			expect(mockMutate).toHaveBeenCalledWith({
				provider: 'kakao',
				code: 'test-auth-code',
			});
		});
	});

	describe('로그인 API 응답 처리 (Mutation Callbacks)', () => {
		beforeEach(() => {
			renderHook(() => useSocialLoginLogic());
		});

		test('로그인 성공(onSuccess) 시 토큰 저장, 스토어 업데이트, 페이지 이동이 수행되어야 한다', () => {
			const mockResponse = {
				accessToken: 'new-access-token',
				user: { id: 1, email: 'social@test.com' },
			};

			act(() => {
				mutationOptions.onSuccess(mockResponse);
			});

			expect(setAccessToken).toHaveBeenCalledWith('new-access-token');
			expect(mockLoginAction).toHaveBeenCalledWith(mockResponse.user);
			expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
		});

		test('로그인 성공 시 accessToken이 응답에 없으면 토큰 저장을 건너뛰어야 한다', () => {
			const mockResponse = { user: { id: 1, email: 'social@test.com' } };

			act(() => {
				mutationOptions.onSuccess(mockResponse);
			});

			expect(setAccessToken).not.toHaveBeenCalled();
			expect(mockLoginAction).toHaveBeenCalledWith(mockResponse.user);
			expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
		});

		test('로그인 실패(onError) 시 에러 로그, 토스트 메시지, 페이지 이동이 수행되어야 한다', () => {
			const mockError = new Error('API Error');
			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				mutationOptions.onError(mockError);
			});

			expect(console.error).toHaveBeenCalledWith(
				'소셜 로그인 실패:',
				mockError,
			);
			expect(result.current.state.toastMessage).toBe(
				'로그인에 실패했습니다. 다시 시도해주세요.',
			);
			expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
		});
	});
});
