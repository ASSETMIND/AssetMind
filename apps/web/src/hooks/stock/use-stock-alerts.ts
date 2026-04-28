import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useWebSocket } from '../web-socket/use-web-socket';
import { STOCK_WS_URL, SURGE_ALERTS_TOPIC } from '../../api/stock';
import type { SurgeAlertPayload } from '../../types/stock';

export const SURGE_ALERTS_QUERY_KEY = ['stock', 'surgeAlerts'];

export function useSurgeAlerts() {
	const queryClient = useQueryClient();
	const { isConnected, subscribe } = useWebSocket(STOCK_WS_URL, {
		autoDisconnectInBackground: true,
	});

	const { data: alerts = [] } = useQuery<SurgeAlertPayload[]>({
		queryKey: SURGE_ALERTS_QUERY_KEY,
		queryFn: () => [],
		staleTime: Infinity,
		gcTime: Infinity,
	});

	useEffect(() => {
		if (!isConnected) return;

		const subscription = subscribe(SURGE_ALERTS_TOPIC, (data: any) => {
			if (data) {
				try {
					const newAlert: SurgeAlertPayload = data;

					queryClient.setQueryData<SurgeAlertPayload[]>(
						SURGE_ALERTS_QUERY_KEY,
						(oldAlerts = []) => {
							return [newAlert, ...oldAlerts].slice(0, 10);
						},
					);
				} catch (error) {
					console.error('Failed to parse stock alert message:', error);
				}
			}
		});

		return () => {
			subscription?.unsubscribe();
		};
	}, [isConnected, subscribe, queryClient]);

	return { alerts };
}

// 가장 최근에 수신된 급등락 알림 하나만 관리하는 커스텀 훅
export function useLatestSurgeAlert() {
	const { alerts } = useSurgeAlerts();
	const [latestAlert, setLatestAlert] = useState<SurgeAlertPayload | null>(
		null,
	);

	useEffect(() => {
		if (alerts && alerts.length > 0) {
			setLatestAlert(alerts[0]);
		}
	}, [alerts]);

	const clearAlert = () => setLatestAlert(null);

	return { latestAlert, clearAlert };
}
