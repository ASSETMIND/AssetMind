import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/index.css';
import App from './App.tsx';
import QueryProvider from './providers/query-providers.tsx';
import { BrowserRouter } from 'react-router-dom';

async function enableMocking() {
	// 개발 환경이 아니면 모킹을 활성화하지 않음
	if (!import.meta.env.DEV) {
		return;
	}

	const { worker } = await import('./mocks/browser');

	// Service Worker 시작
	return worker.start();
}

enableMocking().then(() => {
	createRoot(document.getElementById('root')!).render(
		<StrictMode>
			<BrowserRouter>
				<QueryProvider>
					<App />
				</QueryProvider>
			</BrowserRouter>
		</StrictMode>,
	);
});
