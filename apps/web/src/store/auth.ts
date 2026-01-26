import { create } from 'zustand';

interface User {
	id: number;
	email: string;
	name?: string;
}

interface AuthState {
	isLoggedIn: boolean;
	user: User | null;

	// 액션함수들
	login: (user: User) => void;
	logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
	isLoggedIn: false,
	user: null,

	login: (user) => set({ isLoggedIn: true, user }),
	logout: () => set({ isLoggedIn: false, user: null }),
}));
