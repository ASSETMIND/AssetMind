import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState } from 'react';

interface Props {
	children: React.ReactNode;
}
// 리액트 쿼리를 전역에서 실행할 수 있게 만드는 프로바이더 함수
export default function QueryProvider({ children }: Props) {
	const [queryClient] = useState(
		() =>
			new QueryClient({
				// 기본 글로벌 옵션 설정
				defaultOptions: {
					queries: {
						// 창이 포커스될 때 데이터 자동 갱신 여부 (기본값: true)
						refetchOnWindowFocus: true,
						staleTime: 60 * 1000, // 1분
						retry: 2, // API 요청 실패 시 재시도 횟수
					},
				},
			})
	);

	return (
		<QueryClientProvider client={queryClient}>
			{children}
			<ReactQueryDevtools initialIsOpen={false} buttonPosition='bottom-right' />
		</QueryClientProvider>
	);
}
