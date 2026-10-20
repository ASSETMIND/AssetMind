import { Routes, Route } from 'react-router-dom';
import Header from './components/layout/header';
import { useRefresh } from './hooks/auth/use-refresh';
import OauthCallback from './components/auth/oauth-callback';
import MainPage from './pages/main-page';
import StockDetailPage from './pages/stock-detail-page';
import ErrorBoundary from './components/common/error-boundary';

export default function App() {
	const { isInitialized } = useRefresh();

	if (!isInitialized) {
		return (
			<div className='flex h-screen items-center justify-center'>
				<div className='flex flex-col items-center gap-4'>
					<div className='h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-blue-500' />
					<p className='text-gray-500'>Loading...</p>
				</div>
			</div>
		);
	}

	return (
		<div className='min-h-screen w-full'>
			<Header />
			<main className='w-full'>
				<ErrorBoundary>
					<Routes>
						<Route path='/' element={
							<ErrorBoundary>
								<MainPage />
							</ErrorBoundary>
						} />
						<Route path='/stock/:id' element={
							<ErrorBoundary>
								<StockDetailPage />
							</ErrorBoundary>
						} />
						<Route
							path='/oauth/callback/google'
							element={<OauthCallback provider='google' />}
						/>
						<Route
							path='/oauth/callback/kakao'
							element={<OauthCallback provider='kakao' />}
						/>
						<Route
							path='*'
							element={<div className='p-10 text-center text-gray-500'>404 Not Found</div>}
						/>
					</Routes>
				</ErrorBoundary>
			</main>
		</div>
	);
}