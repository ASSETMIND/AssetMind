import { axiosInstance } from '../libs/axios';

const baseUrl = import.meta.env.VITE_WS_URL || '';

// SockJS는 http 핸드셰이크를 사용하므로 ws://를 http://로 변환하고, 중복 경로 방지를 위해 /ws-stock만 붙임
export const STOCK_WS_URL = `${baseUrl.replace(/^ws/, 'http')}/ws-stock`;

export async function getStockRanking(
	type: 'VALUE' | 'VOLUME' = 'VALUE',
	limit = 40,
) {
	const endpoint =
		type === 'VALUE' ? '/stocks/ranking/value' : '/stocks/ranking/volume';

	// 백엔드 ApiResponse { data: [...] } 구조에 맞춰 언래핑
	const { data } = await axiosInstance.get<{ data: any[] }>(endpoint, {
		params: { limit },
	});
	return data.data;
}
