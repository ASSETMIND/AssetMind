import { http, HttpResponse, ws, type HttpResponseResolver } from 'msw';

// 주식 랭킹 조회 Resolver (HTTP 초기 로드용)
const stockRankingResolver: HttpResponseResolver = ({ request }) => {
	const url = new URL(request.url);
	const limit = Number(url.searchParams.get('limit')) || 10;
	const isVolume = url.pathname.includes('volume');

	const mockData = Array.from({ length: limit }).map((_, i) => {
		const basePrice = 10000 + (limit - i) * 1000; // 기준가
		const currentPrice = basePrice + Math.floor(Math.random() * 2000) - 1000; // 기준가 근처에서 시작
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
		isVolume ? b.cumulativeVolume - a.cumulativeVolume : b.cumulativeAmount - a.cumulativeAmount
	);

	return HttpResponse.json({ success: true, message: null, data: sortedData }, { status: 200 });
};

const sockJsInfoResolver: HttpResponseResolver = () => {
	return HttpResponse.json({ websocket: true, origins: ['*:*'], cookie_needed: false, entropy: Math.floor(Math.random() * 9999999999) }, { status: 200 });
};

// WebSocket 핸들러 정의 (SockJS의 모든 세션 경로를 가로채기 위해 더 넓은 범위의 정규표현식 사용)
const stockSocket = ws.link(new RegExp('.*/ws-stock/.*/.*/websocket$'));

export const stockHandlers = [
	http.get('*/api/stocks/ranking/:type', stockRankingResolver),
	http.get('*/ws-stock/info', sockJsInfoResolver),
	http.post('*/ws-stock/**/xhr', () => HttpResponse.text('o\n')),
	http.post('*/ws-stock/**/xhr_streaming', () => HttpResponse.text('o\n')),
	http.post('*/ws-stock/**/xhr_send', () => HttpResponse.text('', { status: 204 })),

	stockSocket.addEventListener('connection', ({ client }) => {
		console.log('[MSW] WebSocket connected (SockJS Mocking)');
		client.send('o');

		const sendStomp = (frame: string) => {
			client.send('a' + JSON.stringify([frame]));
		};

		const sockJsHeartbeatId = setInterval(() => {
			client.send('h');
		}, 20000);

		const subscriptionIntervals = new Map<string, any>();
		let currentLimit = 10;
		// basePrice(기준가)를 포함하여 데이터를 관리합니다.
		let cachedData: any[] = [];

		client.addEventListener('message', (event) => {
			let data = event.data as string;
			if (data.startsWith('["')) {
				try { data = JSON.parse(data)[0]; } catch (e) {}
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

					if (destination.includes('/topic/ranking/')) {
						const isVolumeTopic = destination.includes('volume');
						const interval = setInterval(() => {
							// 1. 데이터 초기화 (기준가 설정)
							if (cachedData.length !== currentLimit) {
								cachedData = Array.from({ length: currentLimit }).map((_, i) => {
									const basePrice = 10000 + (currentLimit - i) * 1000;
									return {
										stockCode: String(i + 1).padStart(6, '0'),
										stockName: `테스트종목 ${i + 1}`,
										basePrice, // 기준가 저장 (변하지 않음)
										currentPrice: basePrice,
										priceChange: 0,
										changeRate: 0,
										cumulativeAmount: 5000000000 - i * 50000000,
										cumulativeVolume: 10000000 - i * 50000,
									};
								});
							} else {
								// 2. 데이터 실시간 업데이트 (기준가 대비 변동 계산)
								cachedData = cachedData.map(item => {
									if (Math.random() > 0.6) { // 40% 확률로 가격 변동
										// 현재가를 -500 ~ +500원 사이로 랜덤하게 변경
										const nextPrice = Math.max(1000, item.currentPrice + (Math.floor(Math.random() * 11) - 5) * 100);
										const priceChange = nextPrice - item.basePrice;
										const changeRate = Number(((priceChange / item.basePrice) * 100).toFixed(2));
										
										return {
											...item,
											currentPrice: nextPrice,
											priceChange,
											changeRate,
											cumulativeAmount: item.cumulativeAmount + Math.floor(Math.random() * 5000000),
											cumulativeVolume: item.cumulativeVolume + Math.floor(Math.random() * 500),
										};
									}
									return item;
								});
							}

							const sortedData = [...cachedData].sort((a, b) => 
								isVolumeTopic ? b.cumulativeVolume - a.cumulativeVolume : b.cumulativeAmount - a.cumulativeAmount
							);

							const payload = JSON.stringify({
								type: isVolumeTopic ? 'RANKING_VOLUME_UPDATE' : 'RANKING_VALUE_UPDATE',
								data: sortedData,
							});
							sendStomp(`MESSAGE\ndestination:${destination}\nsubscription:${subId}\nmessage-id:${Date.now()}\ncontent-type:application/json\n\n${payload}\0`);
						}, 1000);
						subscriptionIntervals.set(subId, interval);
					}

					// 알림 구독 로직 (여기도 기준가 대비 변동 반영)
					if (destination === '/topic/surge-alerts') {
						const mockStocks = [
							{ stockCode: '005930', stockName: '삼성전자', basePrice: 75000 },
							{ stockCode: '000660', stockName: 'SK하이닉스', basePrice: 130000 },
							{ stockCode: '035420', stockName: 'NAVER', basePrice: 190000 },
							{ stockCode: '035720', stockName: '카카오', basePrice: 53000 },
						];

						const interval = setInterval(() => {
							const stock = mockStocks[Math.floor(Math.random() * mockStocks.length)];
							// -3% ~ +3% 사이의 변동을 시뮬레이션하여 알림 생성
							const drift = (Math.random() * 6 - 3).toFixed(2);
							const currentPrice = Math.floor(stock.basePrice * (1 + Number(drift) / 100));

							const payload = JSON.stringify({
								stockCode: stock.stockCode,
								stockName: stock.stockName,
								rate: Number(drift) >= 0 ? 'UP' : 'DOWN',
								currentPrice: String(currentPrice),
								changeRate: (Number(drift) >= 0 ? '+' : '') + drift + '%',
								alertTime: new Date().toLocaleTimeString('ko-KR', { hour12: false }),
							});
							sendStomp(`MESSAGE\ndestination:${destination}\nsubscription:${subId}\nmessage-id:${Date.now()}\ncontent-type:application/json\n\n${payload}\0`);
						}, 7000);
						subscriptionIntervals.set(subId, interval);
					}
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
			subscriptionIntervals.forEach(interval => clearInterval(interval));
			subscriptionIntervals.clear();
			clearInterval(sockJsHeartbeatId);
		});
	}),
];
