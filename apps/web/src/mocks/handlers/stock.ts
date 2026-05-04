import { http, HttpResponse, ws, type HttpResponseResolver } from 'msw';

const ALERT_THRESHOLD = 10.0;
const COOLDOWN_MS = 30 * 60 * 1000;
const TOTAL_STOCKS_COUNT = 80;

// ─── 랭킹 핸들러 ──────────────────────────────────────────────

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

// ─── 캔들스틱 차트 핸들러 ─────────────────────────────────────

const stockCandlesResolver: HttpResponseResolver = ({ request, params }) => {
	const url = new URL(request.url);
	const timeframe = url.searchParams.get('timeframe') ?? '1d';
	const limit = Number(url.searchParams.get('limit')) || 100;

	const isIntraday = timeframe === '1m' || timeframe === '5m';
	const intervalMs = timeframe === '1m'
		? 60_000
		: timeframe === '5m'
			? 300_000
			: timeframe === '1d'
				? 86_400_000
				: timeframe === '1w'
					? 604_800_000
					: 2_592_000_000; // 1M ≒ 30일

	const now = Date.now();
	let price = 75000;

	const data = Array.from({ length: limit }).map((_, i) => {
		const t = now - (limit - 1 - i) * intervalMs;
		const open = price;
		const change = (Math.random() - 0.48) * price * 0.02;
		const close = Math.max(1000, Math.floor(open + change));
		const high = Math.floor(Math.max(open, close) * (1 + Math.random() * 0.01));
		const low  = Math.floor(Math.min(open, close) * (1 - Math.random() * 0.01));
		price = close;

		return isIntraday
			? { time: Math.floor(t / 1000), open, high, low, close }
			: { time: new Date(t).toISOString().slice(0, 10), open, high, low, close };
	});

	return HttpResponse.json({ success: true, message: null, data }, { status: 200 });
};

// ─── 히스토리 핸들러 ──────────────────────────────────────────

const stockHistoryResolver: HttpResponseResolver = ({ request }) => {
	const url = new URL(request.url);
	const limit = Number(url.searchParams.get('limit')) || 20;

	let price = 75000;
	const now = Date.now();
	const DAY_MS = 86_400_000;

	const data = Array.from({ length: limit }).map((_, i) => {
		const t = now - (limit - 1 - i) * DAY_MS;
		const open = price;
		const change = (Math.random() - 0.48) * price * 0.02;
		const close = Math.max(1000, Math.floor(open + change));
		const high = Math.floor(Math.max(open, close) * (1 + Math.random() * 0.01));
		const low  = Math.floor(Math.min(open, close) * (1 - Math.random() * 0.01));
		price = close;

		return {
			date: new Date(t).toISOString().slice(0, 10),
			open, high, low, close,
			volume: Math.floor(Math.random() * 1000000 + 100000),
		};
	});

	return HttpResponse.json({ success: true, message: null, data }, { status: 200 });
};

// ─── SockJS + WebSocket ───────────────────────────────────────

const sockJsInfoResolver: HttpResponseResolver = () =>
	HttpResponse.json(
		{ websocket: true, origins: ['*:*'], cookie_needed: false, entropy: Math.floor(Math.random() * 9999999999) },
		{ status: 200 },
	);

const stockSocket = ws.link(new RegExp('.*/ws-stock/.*/.*/websocket$'));

export const stockHandlers = [
	http.get('*/api/stocks/ranking/:type', stockRankingResolver),
	http.get('*/api/stocks/:stockCode/charts/candles', stockCandlesResolver),
	http.get('*/api/stocks/:stockCode/history', stockHistoryResolver),
	http.get('*/ws-stock/info', sockJsInfoResolver),
	http.post('*/ws-stock/**/xhr', () => HttpResponse.text('o\n')),
	http.post('*/ws-stock/**/xhr_streaming', () => HttpResponse.text('o\n')),
	http.post('*/ws-stock/**/xhr_send', () => HttpResponse.text('', { status: 204 })),

	stockSocket.addEventListener('connection', ({ client }) => {
		console.log('[MSW] WebSocket connected (SockJS Mocking)');
		client.send('o');

		const sendStomp = (frame: string) => client.send('a' + JSON.stringify([frame]));
		const sockJsHeartbeatId = setInterval(() => client.send('h'), 20000);
		const subscriptionIntervals = new Map<string, any>();
		const lastAlertSentMap = new Map<string, number>();
		let currentLimit = 40;

		let fullStockData = Array.from({ length: TOTAL_STOCKS_COUNT }).map((_, i) => {
			const basePrice = 50000 + Math.floor(Math.random() * 50000);
			return {
				stockCode: String(i + 1).padStart(6, '0'),
				stockName: `테스트종목 ${i + 1}`,
				basePrice,
				currentPrice: basePrice,
				priceChange: 0,
				changeRate: 0,
				cumulativeAmount: 5000000000 - i * 50000000,
				cumulativeVolume: 10000000 - i * 50000,
			};
		});

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
				const idMatch   = data.match(/id:([^\n]+)/);
				if (destMatch && idMatch) {
					const destination = destMatch[1].trim();
					const subId       = idMatch[1].trim();

					const interval = setInterval(() => {
						const now = Date.now();
						fullStockData = fullStockData.map((stock) => {
							const volatility = stock.basePrice * 0.02;
							const change = Math.random() * volatility * 2 - volatility;
							const nextPrice  = Math.max(1000, Math.floor(stock.currentPrice + change));
							const priceChange = nextPrice - stock.basePrice;
							const changeRate  = Number(((priceChange / stock.basePrice) * 100).toFixed(2));

							if (destination === '/topic/surge-alerts') {
								const isThresholdMet = Math.abs(changeRate) >= ALERT_THRESHOLD;
								const lastSentTime   = lastAlertSentMap.get(stock.stockCode) || 0;
								const isOffCooldown  = now - lastSentTime > COOLDOWN_MS;
								if (isThresholdMet && isOffCooldown) {
									lastAlertSentMap.set(stock.stockCode, now);
									const payload = JSON.stringify({
										stockCode:   stock.stockCode,
										stockName:   stock.stockName,
										rate:        changeRate >= 0 ? 'UP' : 'DOWN',
										currentPrice: String(nextPrice),
										changeRate:  (changeRate >= 0 ? '+' : '') + changeRate + '%',
										alertTime:   new Date().toLocaleTimeString('ko-KR', { hour12: false }),
									});
									sendStomp(`MESSAGE\ndestination:${destination}\nsubscription:${subId}\nmessage-id:${now}\ncontent-type:application/json\n\n${payload}\0`);
								}
							}
							return { ...stock, currentPrice: nextPrice, priceChange, changeRate };
						});

						if (destination.includes('/topic/ranking/')) {
							const isVolumeTopic = destination.includes('volume');
							const sortedData = [...fullStockData]
								.sort((a, b) => isVolumeTopic ? b.cumulativeVolume - a.cumulativeVolume : b.cumulativeAmount - a.cumulativeAmount)
								.slice(0, currentLimit);
							const payload = JSON.stringify({
								type: isVolumeTopic ? 'RANKING_VOLUME_UPDATE' : 'RANKING_VALUE_UPDATE',
								data: sortedData,
							});
							sendStomp(`MESSAGE\ndestination:${destination}\nsubscription:${subId}\nmessage-id:${now}\ncontent-type:application/json\n\n${payload}\0`);
						}

						// 개별 종목 실시간 데이터 (/topic/stocks/{stockCode})
						if (destination.startsWith('/topic/stocks/')) {
							const code = destination.split('/').pop() ?? '';
							const stock = fullStockData.find((s) => s.stockCode === code);
							if (stock) {
								const payload = JSON.stringify({
									stockCode:        stock.stockCode,
									currentPrice:     String(stock.currentPrice),
									priceChange:      String(stock.priceChange),
									changeRate:       String(stock.changeRate),
									openPrice:        String(stock.basePrice),
									highPrice:        String(Math.floor(stock.currentPrice * 1.02)),
									lowPrice:         String(Math.floor(stock.currentPrice * 0.98)),
									executionVolume:  String(Math.floor(Math.random() * 10000)),
									cumulativeAmount: String(stock.cumulativeAmount),
									cumulativeVolume: String(stock.cumulativeVolume),
									time:             new Date().toTimeString().slice(0, 8).replace(/:/g, ''),
								});
								sendStomp(`MESSAGE\ndestination:${destination}\nsubscription:${subId}\nmessage-id:${now}\ncontent-type:application/json\n\n${payload}\0`);
							}
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