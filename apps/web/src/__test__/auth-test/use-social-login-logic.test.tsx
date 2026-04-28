import { renderHook, act } from '@testing-library/react';
import { useSocialLoginLogic } from '../../hooks/auth/use-social-login-logic';
import { useSocialLogin } from '../../hooks/auth/queries/use-social-login';
import { useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../../store/auth';
import { setAccessToken } from '../../libs/axios';

/*
 * 소셜 로그인(Kakao, Google)의 리다이렉션 흐름, 인가 코드(Auth Code) 추출 및 API 통신 후
 * 전역 인증 상태를 업데이트하는 useSocialLoginLogic 커스텀 훅을 검증하는 유닛 테스트 코드
 */

// 환경 변수 에러 방지를 위한 소셜 로그인 URL 상수 모킹
const MOCK_KAKAO_URL = 'http://mock-kakao.com/auth';
const MOCK_GOOGLE_URL = 'http://mock-google.com/auth';

jest.mock('../libs/constants/auth', () => ({
	KAKAO_AUTH_URL: 'http://mock-kakao.com/auth',
	GOOGLE_AUTH_URL: 'http://mock-google.com/auth',
}));

// 외부 라이브러리 및 훅 모킹
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

	// window.location 수정을 위한 원본 객체 백업
	const originalLocation = window.location;

	beforeAll(() => {
		// window.location을 수정 가능(writable)하도록 재정의하여 리다이렉트 동작 테스트 허용
		delete (window as any).location;
		Object.defineProperty(window, 'location', {
			writable: true,
			value: { href: '' },
		});

		jest.spyOn(console, 'error').mockImplementation(() => {});
	});

	afterAll(() => {
		// 테스트 종료 후 원본 객체로 복구 및 모킹 초기화
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

	describe('소셜 로그인 리다이렉트 로직', () => {
		/*
		 * - 카카오 제공자 선택 시 인증 화면으로의 전환 동작 검증
		 * - 리다이렉트 플래그가 true로 변경되고 브라우저 URL이 지정된 KAKAO_AUTH_URL로 업데이트되는지 확인
		 */
		test('Kakao provider 전달 시 Kakao 인증 URL로 이동하고 상태를 변경해야 한다', () => {
			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialLogin('kakao');
			});

			expect(result.current.state.isRedirecting).toBe(true);
			expect(window.location.href).toBe(MOCK_KAKAO_URL);
		});

		/*
		 * - 구글 제공자 선택 시 인증 화면으로의 전환 동작 검증
		 * - 리다이렉트 플래그가 true로 변경되고 브라우저 URL이 지정된 GOOGLE_AUTH_URL로 업데이트되는지 확인
		 */
		test('Google provider 전달 시 Google 인증 URL로 이동하고 상태를 변경해야 한다', () => {
			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialLogin('google');
			});

			expect(result.current.state.isRedirecting).toBe(true);
			expect(window.location.href).toBe(MOCK_GOOGLE_URL);
		});
	});

	describe('소셜 인증 콜백(리다이렉트 후) 처리 로직', () => {
		/*
		 * - 인가 코드(Auth Code) 누락 예외 처리 검증
		 * - 사용자가 인증을 완료하지 못해 쿼리 파라미터에 'code'가 없을 경우 API를 호출하지 않고 에러 콜백을 실행하는지 확인
		 */
		test('URL에 code가 없으면 경고 메시지를 설정하고 에러 콜백을 호출해야 한다', () => {
			(useSearchParams as jest.Mock).mockReturnValue([new URLSearchParams('')]);
			const { result } = renderHook(() =>
				useSocialLoginLogic({ onSuccess: mockOnSuccess, onError: mockOnError }),
			);

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			expect(mockOnError).toHaveBeenCalledWith(
				'인증 정보를 받아오지 못했습니다. 다시 시도해주세요.',
			);
			expect(mockOnSuccess).not.toHaveBeenCalled();
			expect(mockMutate).not.toHaveBeenCalled();
		});

		/*
		 * - 소셜 제공자 측 거부/오류 예외 처리 검증
		 * - 사용자가 동의를 취소하거나 제공자 오류로 인해 'error' 쿼리 파라미터가 수신될 경우 API를 호출하지 않고 에러 콜백을 실행하는지 확인
		 */
		test('URL에 error가 있으면 에러 메시지를 설정하고 에러 콜백을 호출해야 한다', () => {
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('error=access_denied'),
			]);
			const { result } = renderHook(() =>
				useSocialLoginLogic({ onSuccess: mockOnSuccess, onError: mockOnError }),
			);

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			expect(mockOnError).toHaveBeenCalledWith(
				'로그인 과정에서 오류가 발생했습니다. 다시 시도해주세요.',
			);
			expect(mockOnSuccess).not.toHaveBeenCalled();
			expect(mockMutate).not.toHaveBeenCalled();
		});

		/*
		 * - 정상적인 인가 코드 수신에 따른 API 호출 검증
		 * - URL 파라미터에 'code'가 존재할 때, 제공자 이름(provider)과 해당 코드를 페이로드로 담아 로그인 API(mutate)를 정상적으로 요청하는지 확인
		 */
		test('URL에 code가 있으면 mutation을 실행해야 한다', () => {
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('code=test-auth-code'),
			]);
			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			expect(mockMutate).toHaveBeenCalledWith(
				{
					provider: 'kakao',
					code: 'test-auth-code',
				},
				expect.any(Object),
			);
		});
	});

	describe('백엔드 소셜 로그인 API 응답 처리 로직', () => {
		beforeEach(() => {
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('code=test-code'),
			]);
		});

		/*
		 * - 소셜 로그인 API 성공 시나리오(신규 가입 또는 기존 회원 로그인 완료) 검증
		 * - 응답으로 받은 액세스 토큰을 로컬에 저장하고, 사용자 정보로 전역 스토어 상태를 업데이트한 뒤 성공 콜백을 실행하는지 확인
		 */
		test('로그인 성공(onSuccess) 시 토큰 저장, 스토어 업데이트, 성공 콜백이 수행되어야 한다', () => {
			const mockResponse = {
				accessToken: 'new-access-token',
				user: { id: 1, email: 'social@test.com' },
			};

			const { result } = renderHook(() =>
				useSocialLoginLogic({ onSuccess: mockOnSuccess, onError: mockOnError }),
			);

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			const mutateCall = mockMutate.mock.calls[0];
			const options = mutateCall[1];

			act(() => {
				options.onSuccess(mockResponse);
			});

			expect(setAccessToken).toHaveBeenCalledWith('new-access-token');
			expect(mockLoginAction).toHaveBeenCalledWith(mockResponse.user);
			expect(mockOnSuccess).toHaveBeenCalled();
		});

		/*
		 * - 응답 페이로드 누락 방어 로직 검증
		 * - 백엔드에서 인증 토큰(accessToken)을 반환하지 않았을 경우 불필요한 저장을 건너뛰고 스토어 업데이트만 정상 처리하는지 확인
		 */
		test('로그인 성공 시 accessToken이 응답에 없으면 토큰 저장을 건너뛰어야 한다', () => {
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

			expect(setAccessToken).not.toHaveBeenCalled();
			expect(mockLoginAction).toHaveBeenCalledWith(mockResponse.user);
			expect(mockOnSuccess).toHaveBeenCalled();
		});

		/*
		 * - 백엔드 소셜 로그인 API 실패 응답 처리 검증
		 * - 통신 오류 또는 서버 내부 에러 발생 시 개발자 콘솔에 로그를 남기고, 사용자에게는 기본 에러 안내 문구를 콜백으로 전달하는지 확인
		 */
		test('로그인 실패(onError) 시 에러 로그, 에러 콜백이 수행되어야 한다', () => {
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

			expect(console.error).toHaveBeenCalledWith(
				'소셜 로그인 실패:',
				mockError,
			);
			expect(mockOnError).toHaveBeenCalledWith(
				'로그인에 실패했습니다. 다시 시도해주세요.',
			);
			expect(mockOnSuccess).not.toHaveBeenCalled();
		});

		/*
		 * - 외부 주입 Props 미설정 시의 훅 안정성 검증
		 * - 사용하는 컴포넌트에서 에러 콜백을 넘겨주지 않았을 때 API 에러가 발생하더라도 앱이 크래시되지 않고 로그만 남기고 종료되는지 확인
		 */
		test('Props 없이 호출되어도 에러 발생 시 안전하게 처리되어야 한다', () => {
			const mockError = new Error('API Error');
			const { result } = renderHook(() => useSocialLoginLogic());

			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			const options = mockMutate.mock.calls[0][1];
			act(() => {
				options.onError(mockError);
			});

			expect(console.error).toHaveBeenCalled();
		});
	});

	describe('콜백(Props) 미전달 시 분기 테스트', () => {
		/*
		 * - 훅 내부 로직 전체의 방어 로직 검증
		 * - 성공/에러 콜백이 전혀 주입되지 않은 상태에서 인가 코드 수신, 에러 발생, API 성공/실패 등 모든 라이프사이클을 통과해도 에러 없이 실행이 보장되는지 확인
		 */
		test('콜백 없이 소셜 로그인 프로세스 진행 시 크래시가 발생하지 않아야 한다', () => {
			const { result } = renderHook(() => useSocialLoginLogic());

			// URL에 에러가 포함된 경우
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('error=access_denied'),
			]);
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// URL 파라미터가 완전히 비어있는 경우
			(useSearchParams as jest.Mock).mockReturnValue([new URLSearchParams('')]);
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// 정상 코드를 받아 API를 호출하는 경우
			(useSearchParams as jest.Mock).mockReturnValue([
				new URLSearchParams('code=123'),
			]);

			// API 통신 성공 시나리오
			mockMutate.mockImplementation((_data, options) => {
				options.onSuccess({ accessToken: 'token', user: {} });
			});
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});

			// API 통신 실패 시나리오
			mockMutate.mockImplementation((_data, options) => {
				options.onError(new Error('Fail'));
			});
			act(() => {
				result.current.actions.handleSocialCallback('kakao');
			});
		});
	});
});
