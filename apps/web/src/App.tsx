import { Routes, Route } from 'react-router-dom';
import Header from './components/layout/header';
import { useRefresh } from './hooks/auth/use-refresh';
import OauthCallback from './components/auth/oauth-callback';
import MainPage from './pages/main-page';

export default function App() {
	// 앱 초기화 (토큰 리프레시 시도)
	const { isInitialized } = useRefresh();

	// 초기화 전 로딩 화면 (전역 로딩)
	if (!isInitialized) {
		return (
			<div className='flex h-screen items-center justify-center'>
				<div className='flex flex-col items-center gap-4'>
					{/* 간단한 로딩 스피너 */}
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
				<Routes>
					<Route path='/' element={<MainPage />} />

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
						element={<div className='p-10 text-center'>404 Not Found</div>}
					/>
				</Routes>
			</main>
		</div>
	);
}
