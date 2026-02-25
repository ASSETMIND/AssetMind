// 환경 변수에서 웹소켓 URL 로드 (없을 경우 기본값 처리)
export const STOCK_WS_URL = import.meta.env.VITE_WS_URL
	? `${import.meta.env.VITE_WS_URL}/stocks`
	: 'ws://localhost:8080/stocks';
