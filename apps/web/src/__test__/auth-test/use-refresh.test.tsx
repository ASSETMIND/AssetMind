import { renderHook, waitFor } from '@testing-library/react';
import { useRefresh } from '../../hooks/auth/use-refresh';
import { useRefreshToken } from '../../hooks/auth/queries/use-refresh-token';
import { useAuthStore } from '../../store/auth';
import { removeAuthTokens } from '../../libs/axios';

// 애플리케이션 초기 로드 시 사용자의 세션(액세스 토큰)을 복구하는 useRefresh 훅의 방어 로직 및 에러 처리 동작을 검증하는 유닛 테스트 코드

jest.mock('../hooks/auth/queries/use-refresh-token');
jest.mock('../store/auth');
jest.mock('../libs/axios');

describe('useRefresh Hook', () => {
	const mockRefreshMutate = jest.fn();
	const mockLogin = jest.fn();
	const mockLogout = jest.fn();

	beforeEach(() => {
		jest.clearAllMocks();
		(useRefreshToken as jest.Mock).mockReturnValue({
			mutateAsync: mockRefreshMutate,
		});
		(useAuthStore as unknown as jest.Mock).mockReturnValue({
			login: mockLogin,
			logout: mockLogout,
		});
		Object.defineProperty(window, 'localStorage', {
			value: {
				getItem: jest.fn(),
				setItem: jest.fn(),
				removeItem: jest.fn(),
			},
			writable: true,
		});
	});

	/*
	 * - 비로그인 사용자의 애플리케이션 접근 시나리오 검증
	 * - 로컬 스토리지에 인증 플래그가 없을 때 불필요한 토큰 갱신 API가 호출되지 않음을 방어 로직을 통해 확인
	 * - API 호출 없이도 훅의 초기화 상태(isInitialized)가 정상적으로 완료 처리되는지 확인
	 */
	test('인증 상태가 아닐 경우(localStorage 없음) 갱신 시도 없이 초기화된다', async () => {
		(window.localStorage.getItem as jest.Mock).mockReturnValue(null);

		const { result } = renderHook(() => useRefresh());

		await waitFor(() => expect(result.current.isInitialized).toBe(true));
		expect(mockRefreshMutate).not.toHaveBeenCalled();
	});

	/*
	 * - 리프레시 토큰 만료 또는 유효하지 않은 세션으로 인한 토큰 갱신 실패 상황 검증
	 * - 에러 발생 시 클라이언트에 남아있는 기존 인증 토큰들이 안전하게 삭제(removeAuthTokens)되는지 확인
	 * - 전역 스토어의 로그아웃(logout) 액션이 호출되어 전역 인증 상태가 완전히 초기화되는지 확인
	 */
	test('토큰 갱신 실패 시 로그아웃 처리된다', async () => {
		const consoleSpy = jest
			.spyOn(console, 'error')
			.mockImplementation(() => {});
		(window.localStorage.getItem as jest.Mock).mockReturnValue('true');
		mockRefreshMutate.mockRejectedValue(new Error('Refresh failed'));

		const { result } = renderHook(() => useRefresh());

		await waitFor(() => expect(result.current.isInitialized).toBe(true));

		expect(mockRefreshMutate).toHaveBeenCalled();
		expect(removeAuthTokens).toHaveBeenCalled();
		expect(mockLogout).toHaveBeenCalled();

		consoleSpy.mockRestore();
	});
});
