import Header from './components/layout/header';
import { useRefresh } from './hooks/auth/use-refresh';

export default function App() {
	// 앱 실행 시 딱 한 번 실행되어 토큰 복구를 시도
	const { isInitialized } = useRefresh();

	// 임시로 스켈레톤 UI 삽입 (추후 교체 예정)
	if (!isInitialized) {
		return (
			<div className='flex h-screen items-center justify-center'>
				Loading...
			</div>
		);
	}

	return (
		<>
			<Header />
		</>
	);
}
