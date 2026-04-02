import { http, HttpResponse, ws, type HttpResponseResolver } from 'msw';

// 쿨타임 및 임계치 설정 (백엔드 로직과 동일하게 유지)
const ALERT_THRESHOLD = 10.0;
const COOLDOWN_MS = 30 * 60 * 1000; // 30분
const TOTAL_STOCKS_COUNT = 80;

// 주식 랭킹 조회 Resolver (HTTP 초기 로드용)
const stockRankingResolver: HttpResponseResolver = ({ request }) => {
	const url = new URL(request.url);
	const limit = Number(url.searchParams.get('limit')) || 40;
	const isVolume = url.pathname.includes('volume');

	const mockData = Array.from({ length: limit }).map((_, i) => {
		const basePrice = 10000 + (limit - i) * 1000;
		const currentPrice = basePrice + Math.floor(Math.random() * 2000) - 1000;
		const priceChange = currentPrice - basePrice;
		const changeRate = Number(((priceChange / basePrice) * 100).toFixed(2));

		return {
			stockCode: String(i + 1).padStart(6, '0'),
			stockName: `테스트종목 ${i + 1}`,
			currentPrice,
			priceChange,
			changeRate,
			cumulativeAmount: 5000000000 - i * 50000000,
			cumulativeVolume: 10000000 - i * 50000,
		};
	});

	const sortedData = [...mockData].sort((a, b) =>
		isVolume
			? b.cumulativeVolume - a.cumulativeVolume
			: b.cumulativeAmount - a.cumulativeAmount,
	);

	return HttpResponse.json(
		{ success: true, message: null, data: sortedData },
		{ status: 200 },
	);
};

const sockJsInfoResolver: HttpResponseResolver = () => {
	return HttpResponse.json(
		{
			websocket: true,
			origins: ['*:*'],
			cookie_needed: false,
			entropy: Math.floor(Math.random() * 9999999999),
		},
		{ status: 200 },
	);
};

const stockSocket = ws.link(new RegExp('.*/ws-stock/.*/.*/websocket$'));

export const stockHandlers = [
	http.get('*/api/stocks/ranking/:type', stockRankingResolver),
	http.get('*/ws-stock/info', sockJsInfoResolver),
	http.post('*/ws-stock/**/xhr', () => HttpResponse.text('o\n')),
	http.post('*/ws-stock/**/xhr_streaming', () => HttpResponse.text('o\n')),
	http.post('*/ws-stock/**/xhr_send', () =>
		HttpResponse.text('', { status: 204 }),
	),

	stockSocket.addEventListener('connection', ({ client }) => {
		console.log('[MSW] WebSocket connected (SockJS Mocking)');
		client.send('o');

		const sendStomp = (frame: string) => {
			client.send('a' + JSON.stringify([frame]));
		};

		const sockJsHeartbeatId = setInterval(() => {
			client.send('h');
		}, 20000);

		// 다중 구독 관리
		const subscriptionIntervals = new Map<string, any>();
		const lastAlertSentMap = new Map<string, number>();

		let currentLimit = 40;
		// 80개의 전체 종목 데이터 풀 생성
		let fullStockData = Array.from({ length: TOTAL_STOCKS_COUNT }).map(
			(_, i) => {
				const basePrice = 50000 + Math.floor(Math.random() * 50000);
				return {
					stockCode: String(i + 1).padStart(6, '0'),
					stockName: `시뮬레이션 종목 ${i + 1}`,
					basePrice,
					currentPrice: basePrice,
					priceChange: 0,
					changeRate: 0,
					cumulativeAmount: 5000000000 - i * 50000000,
					cumulativeVolume: 10000000 - i * 50000,
				};
			},
		);

		client.addEventListener('message', (event) => {
			let data = event.data as string;
			if (data.startsWith('["')) {
				try {
					data = JSON.parse(data)[0];
				} catch (e) {}
			}

			if (data.startsWith('CONNECT') || data.startsWith('STOMP')) {
				sendStomp('CONNECTED\nversion:1.2\nheart-beat:0,0\n\n\0');
				return;
			}

			if (data.startsWith('SUBSCRIBE')) {
				const destMatch = data.match(/destination:([^\n]+)/);
				const idMatch = data.match(/id:([^\n]+)/);

				if (destMatch && idMatch) {
					const destination = destMatch[1].trim();
					const subId = idMatch[1].trim();

					// 통합 모니터링 및 업데이트 루프
					const interval = setInterval(() => {
						const now = Date.now();

						// 모든 종목 가격 변동 계산
						fullStockData = fullStockData.map((stock) => {
							// 알림 테스트를 위해 변동폭을 현실보다 조금 크게 설정 (+- 10% 도달 가능하도록)
							const volatility = stock.basePrice * 0.02; // 기준가의 2% 내외 변동
							const change = Math.random() * volatility * 2 - volatility;
							const nextPrice = Math.max(
								1000,
								Math.floor(stock.currentPrice + change),
							);
							const priceChange = nextPrice - stock.basePrice;
							const changeRate = Number(
								((priceChange / stock.basePrice) * 100).toFixed(2),
							);

							// 백엔드 로직: 급등락 감시 및 쿨타임 체크 (알림 채널 전용)
							if (destination === '/topic/surge-alerts') {
								const isThresholdMet = Math.abs(changeRate) >= ALERT_THRESHOLD;
								const lastSentTime = lastAlertSentMap.get(stock.stockCode) || 0;
								const isOffCooldown = now - lastSentTime > COOLDOWN_MS;

								if (isThresholdMet && isOffCooldown) {
									lastAlertSentMap.set(stock.stockCode, now);
									const payload = JSON.stringify({
										stockCode: stock.stockCode,
										stockName: stock.stockName,
										rate: changeRate >= 0 ? 'UP' : 'DOWN',
										currentPrice: String(nextPrice),
										changeRate: (changeRate >= 0 ? '+' : '') + changeRate + '%',
										alertTime: new Date().toLocaleTimeString('ko-KR', {
											hour12: false,
										}),
									});
									sendStomp(
										`MESSAGE\ndestination:${destination}\nsubscription:${subId}\nmessage-id:${now}\ncontent-type:application/json\n\n${payload}\0`,
									);
								}
							}

							return {
								...stock,
								currentPrice: nextPrice,
								priceChange,
								changeRate,
							};
						});

						// 랭킹 데이터 전송 (랭킹 채널인 경우)
						if (destination.includes('/topic/ranking/')) {
							const isVolumeTopic = destination.includes('volume');
							const sortedData = [...fullStockData]
								.sort((a, b) =>
									isVolumeTopic
										? b.cumulativeVolume - a.cumulativeVolume
										: b.cumulativeAmount - a.cumulativeAmount,
								)
								.slice(0, currentLimit);

							const payload = JSON.stringify({
								type: isVolumeTopic
									? 'RANKING_VOLUME_UPDATE'
									: 'RANKING_VALUE_UPDATE',
								data: sortedData,
							});
							sendStomp(
								`MESSAGE\ndestination:${destination}\nsubscription:${subId}\nmessage-id:${now}\ncontent-type:application/json\n\n${payload}\0`,
							);
						}
					}, 1000);

					subscriptionIntervals.set(subId, interval);
				}
			}

			if (data.startsWith('UNSUBSCRIBE')) {
				const idMatch = data.match(/id:([^\n]+)/);
				if (idMatch) {
					const subId = idMatch[1].trim();
					if (subscriptionIntervals.has(subId)) {
						clearInterval(subscriptionIntervals.get(subId));
						subscriptionIntervals.delete(subId);
					}
				}
			}
		});

		client.addEventListener('close', () => {
			subscriptionIntervals.forEach((interval) => clearInterval(interval));
			subscriptionIntervals.clear();
			clearInterval(sockJsHeartbeatId);
		});
	}),
];
