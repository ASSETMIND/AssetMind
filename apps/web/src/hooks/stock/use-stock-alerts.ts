import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Client } from '@stomp/stompjs';
import SockJS from 'sockjs-client';
import { STOCK_WS_URL, SURGE_ALERTS_TOPIC } from '../../api/stock';
import type { SurgeAlertPayload } from '../../types/stock';

export const SURGE_ALERTS_QUERY_KEY = ['stock', 'surgeAlerts'];

export function useSurgeAlerts() {
	const queryClient = useQueryClient();

	const { data: alerts = [] } = useQuery<SurgeAlertPayload[]>({
		queryKey: SURGE_ALERTS_QUERY_KEY,
		queryFn: () => [],
		staleTime: Infinity,
		gcTime: Infinity,
	});

	useEffect(() => {
		// STOMP 클라이언트 인스턴스 생성
		const client = new Client({
			webSocketFactory: () => new SockJS(STOCK_WS_URL),
			reconnectDelay: 5000, // 연결 끊김 시 5초 후 재연결 시도
			onConnect: () => {
				// 연결 성공 시 급등락 알림 토픽 구독
				client.subscribe(SURGE_ALERTS_TOPIC, (message) => {
					if (message.body) {
						const newAlert: SurgeAlertPayload = JSON.parse(message.body);

						// React Query 캐시 업데이트: 기존 목록 맨 앞에 새 알림 추가 (최근 10개만 유지)
						queryClient.setQueryData<SurgeAlertPayload[]>(
							SURGE_ALERTS_QUERY_KEY,
							(oldAlerts = []) => {
								return [newAlert, ...oldAlerts].slice(0, 10);
							},
						);
					}
				});
			},
		});

		client.activate(); // 웹소켓 연결 시작

		// 컴포넌트 언마운트 시 연결 해제
		return () => {
			client.deactivate();
		};
	}, [queryClient]);

	return { alerts };
}
