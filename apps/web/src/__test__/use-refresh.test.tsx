import { renderHook, waitFor } from '@testing-library/react';
import { useRefresh } from '../hooks/auth/use-refresh';
import { useRefreshToken } from '../hooks/auth/queries/use-refresh-token';
import { useAuthStore } from '../store/auth';
import { removeAuthTokens } from '../libs/axios';

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

	test('인증 상태가 아닐 경우(localStorage 없음) 갱신 시도 없이 초기화된다', async () => {
		(window.localStorage.getItem as jest.Mock).mockReturnValue(null);

		const { result } = renderHook(() => useRefresh());

		await waitFor(() => expect(result.current.isInitialized).toBe(true));
		expect(mockRefreshMutate).not.toHaveBeenCalled();
	});

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
