import { renderHook, act } from '@testing-library/react';
import { useSocialLoginLogic } from '../hooks/auth/use-social-login-logic';
import { useSocialLogin } from '../hooks/auth/queries/use-social-login';
import { useSearchParams } from 'react-router-dom';
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
	useSearchParams: jest.fn(),
}));

jest.mock('../hooks/auth/queries/use-social-login', () => ({
	useSocialLogin: jest.fn(),
}));

jest.mock('../libs/axios', () => ({
	setAccessToken: jest.fn(),
}));

jest.mock('../store/auth', () => ({
	useAuthStore: jest.fn(),
}));

describe('useSocialLoginLogic 유닛 테스트', () => {
	let mockOnSuccess: jest.Mock;
	let mockOnError: jest.Mock;
	let mockLoginAction: jest.Mock;
	let mockMutate: jest.Mock;

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

		mockOnSuccess = jest.fn();
		mockOnError = jest.fn();
		mockLoginAction = jest.fn();
		mockMutate = jest.fn();

		(useSearchParams as jest.Mock).mockReturnValue([new URLSearchParams()]);

		(useAuthStore as unknown as jest.Mock).mockReturnValue({
			login: mockLoginAction,
		});

		(useSocialLogin as jest.Mock).mockImplementation(() => {
			return {
				mutate: mockMutate,
				isPending: false,
			};
		});
	});

	describe('소셜 로그인 리다이렉트 (handleSocialLogin)', () => {
		test('Kakao provider 전달 시 Kakao 인증 URL로 이동하고 상태를 변경해야 한다', () => {
			// Given: 훅이 렌더링된 상태
			const { result } = renderHook(() => useSocialLoginLogic());

			// When: 'kakao' provider로 handleSocialLogin 함수를 호출
			act(() => {
				result.current.actions.handleSocialLogin('kakao');
			});

			// Then: isRedirecting 상태가 true가 되고, window.location.href가 카카오 인증 URL로 변경
			expect(result.current.state.isRedirecting).toBe(true);
			expect(window.location.href).toBe(MOCK_KAKAO_URL);
		});

		test('Google provider 전달 시 Google 인증 URL로 이동하고 상태를 변경해야 한다', () => {
			// Given: 훅이 렌더링된 상태
			const { result } = renderHook(() => useSocialLoginLogic());

			// When: 'google' provider로 handleSocialLogin 함수를 호출
			act(() => {
				result.current.actions.handleSocialLogin('google');
			});

			// Then: isRedirecting 상태가 true가 되고, window.location.href가 구글 인증 URL로 변경
			expect(result.current.state.isRedirecting).toBe(true);
			expect(window.location.href).toBe(MOCK_GOOGLE_URL);
		});
	});

	describe('소셜 로그인 콜백 처리 (handleSocialCallback)', () => {
		test('URL에 code가 없으면 경고 메시지를 설정하고 에러 콜백을 호출해야 한다', () => {
			// Given: URL 파라미터에 'code'가 없는 상태
			(useSearchParams as jest.Mock).mockReturnValue([new URLSearchParams('')]);
			const { result } = renderHook(() =>
				useSocialLoginLogic({ onSuccess: mockOnSuccess, onError: mockOnError }),
			);

			// When: handleSocialCallback 함수를 호출
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// Then: 에러 콜백이 호출되고, mutate 함수는 호출되지 않음
			expect(mockOnError).toHaveBeenCalledWith(
				'인증 정보를 받아오지 못했습니다. 다시 시도해주세요.',
			);
			expect(mockOnSuccess).not.toHaveBeenCalled();
			expect(mockMutate).not.toHaveBeenCalled();
		});

		test('URL에 error가 있으면 에러 메시지를 설정하고 에러 콜백을 호출해야 한다', () => {
			// Given: URL 파라미터에 'error'가 있는 상태
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('error=access_denied'),
			]);
			const { result } = renderHook(() =>
				useSocialLoginLogic({ onSuccess: mockOnSuccess, onError: mockOnError }),
			);

			// When: handleSocialCallback 함수를 호출
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// Then: 에러 콜백이 호출되고, mutate 함수는 호출되지 않음
			expect(mockOnError).toHaveBeenCalledWith(
				'로그인 과정에서 오류가 발생했습니다. 다시 시도해주세요.',
			);
			expect(mockOnSuccess).not.toHaveBeenCalled();
			expect(mockMutate).not.toHaveBeenCalled();
		});

		test('URL에 code가 있으면 mutation을 실행해야 한다', () => {
			// Given: URL 파라미터에 'code'가 있는 상태
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('code=test-auth-code'),
			]);
			const { result } = renderHook(() => useSocialLoginLogic());

			// When: handleSocialCallback 함수를 호출
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// Then: mutate 함수가 올바른 provider와 code로 호출됨
			expect(mockMutate).toHaveBeenCalledWith(
				{
					provider: 'kakao',
					code: 'test-auth-code',
				},
				expect.any(Object),
			);
		});
	});

	describe('로그인 API 응답 처리 (Mutation Callbacks)', () => {
		// onSuccess/onError는 이제 mutate 호출 시 전달되므로,
		// handleSocialCallback을 호출하여 mutate가 실행된 후 인자를 캡처해야 함.

		beforeEach(() => {
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('code=test-code'),
			]);
		});

		test('로그인 성공(onSuccess) 시 토큰 저장, 스토어 업데이트, 성공 콜백이 수행되어야 한다', () => {
			// Given: API 성공 응답 데이터
			const mockResponse = {
				accessToken: 'new-access-token',
				user: { id: 1, email: 'social@test.com' },
			};

			const { result } = renderHook(() =>
				useSocialLoginLogic({ onSuccess: mockOnSuccess, onError: mockOnError }),
			);

			// When: 소셜 콜백 실행 -> mutate 호출 -> onSuccess 콜백 실행
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			const mutateCall = mockMutate.mock.calls[0];
			const options = mutateCall[1]; // 두 번째 인자가 옵션 객체

			act(() => {
				options.onSuccess(mockResponse);
			});

			// Then: 토큰이 저장되고, 로그인 상태가 업데이트되며, 성공 콜백 호출
			expect(setAccessToken).toHaveBeenCalledWith('new-access-token');
			expect(mockLoginAction).toHaveBeenCalledWith(mockResponse.user);
			expect(mockOnSuccess).toHaveBeenCalled();
		});

		test('로그인 성공 시 accessToken이 응답에 없으면 토큰 저장을 건너뛰어야 한다', () => {
			// Given: accessToken이 없는 API 성공 응답 데이터
			const mockResponse = {
				user: { id: 1, email: 'social@test.com' },
			};

			const { result } = renderHook(() =>
				useSocialLoginLogic({ onSuccess: mockOnSuccess, onError: mockOnError }),
			);

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			const options = mockMutate.mock.calls[0][1];
			act(() => {
				options.onSuccess(mockResponse);
			});

			// Then: 토큰 저장은 호출되지 않고, 로그인 상태 업데이트와 성공 콜백 호출
			expect(setAccessToken).not.toHaveBeenCalled();
			expect(mockLoginAction).toHaveBeenCalledWith(mockResponse.user);
			expect(mockOnSuccess).toHaveBeenCalled();
		});

		test('로그인 실패(onError) 시 에러 로그, 에러 콜백이 수행되어야 한다', () => {
			// Given: API 실패를 나타내는 에러 객체
			const mockError = new Error('API Error');
			const { result } = renderHook(() =>
				useSocialLoginLogic({ onSuccess: mockOnSuccess, onError: mockOnError }),
			);

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			const options = mockMutate.mock.calls[0][1];
			act(() => {
				options.onError(mockError);
			});

			// Then: 에러가 콘솔에 기록되고, 에러 콜백 호출
			expect(console.error).toHaveBeenCalledWith(
				'소셜 로그인 실패:',
				mockError,
			);
			expect(mockOnError).toHaveBeenCalledWith(
				'로그인에 실패했습니다. 다시 시도해주세요.',
			);
			expect(mockOnSuccess).not.toHaveBeenCalled();
		});

		test('Props 없이 호출되어도 에러 발생 시 안전하게 처리되어야 한다', () => {
			const mockError = new Error('API Error');
			const { result } = renderHook(() => useSocialLoginLogic()); // No props

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			const options = mockMutate.mock.calls[0][1];
			act(() => {
				options.onError(mockError); // onError?.() 호출 테스트
			});

			expect(console.error).toHaveBeenCalled();
			// 크래시 없이 실행 완료됨을 검증
		});
	});

	describe('Feature: 콜백(Props) 미전달 시 분기 테스트', () => {
		test('Scenario: 콜백 없이 소셜 로그인 프로세스 진행 시 크래시가 발생하지 않아야 한다', () => {
			const { result } = renderHook(() => useSocialLoginLogic()); // No props

			// 1. Error param (onError missing)
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('error=access_denied'),
			]);
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// 2. No code/error (onError missing)
			(useSearchParams as jest.Mock).mockReturnValue([new URLSearchParams('')]);
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// 3. Code exists
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('code=123'),
			]);

			// Mutation Success (onSuccess missing)
			mockMutate.mockImplementation((_data, options) => {
				options.onSuccess({ accessToken: 'token', user: {} });
			});
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// Mutation Error (onError missing)
			mockMutate.mockImplementation((_data, options) => {
				options.onError(new Error('Fail'));
			});
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});
		});
	});
});
