import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/index.css';
import App from './App.tsx';
import QueryProvider from './providers/query-providers.tsx';

// MSW 모킹 활성화 함수
async function enableMocking() {
	// 개발 환경(development)이 아니라면 아무것도 하지 않고 종료
	if (import.meta.env.MODE !== 'development') {
		return;
	}
	const { worker } = await import('./mocks/browser');

	// Service Worker 시작
	return worker.start({
		onUnhandledRequest: 'bypass',
	});
}

// MSW 실행이 완료된 후, React 앱 렌더링
enableMocking().then(() => {
	createRoot(document.getElementById('root')!).render(
		<StrictMode>
			<QueryProvider>
				<App />
			</QueryProvider>
		</StrictMode>
	);
});
