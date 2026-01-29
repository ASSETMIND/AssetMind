import axios from 'axios';

const ACCESS_TOKEN_KEY = 'accessToken';

export const getAccessToken = (): string | null => {
	return localStorage.getItem(ACCESS_TOKEN_KEY);
};

export const setAccessToken = (token: string | null) => {
	if (token) {
		localStorage.setItem(ACCESS_TOKEN_KEY, token);
	} else {
		localStorage.removeItem(ACCESS_TOKEN_KEY);
	}
};

export const removeAccessToken = () => {
	localStorage.removeItem(ACCESS_TOKEN_KEY);
};

export const axiosInstance = axios.create({
	baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
	headers: {
		'Content-Type': 'application/json',
	},
});

axiosInstance.interceptors.request.use((config) => {
	const token = getAccessToken();
	if (token) {
		config.headers.Authorization = `Bearer ${token}`;
	}
	return config;
});
