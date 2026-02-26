import { http, HttpResponse, ws, type HttpResponseResolver } from 'msw';

/*
  [Resolvers]
  실제 요청을 처리하고 응답을 생성하는 로직 함수
*/

// 회원가입 Resolver
const signupResolver: HttpResponseResolver = async ({ request }) => {
	const requestBody = (await request.json()) as {
		user_name: string;
		email: string;
		password: string;
		sign_up_token: string;
	};

	const email = requestBody.email;
	console.log('MSW: 회원가입 요청 받음', requestBody);

	if (email === 'fail@test.com') {
		return HttpResponse.json(
			{ message: '이미 존재하는 계정입니다.' },
			{ status: 409 },
		);
	}

	return HttpResponse.json(
		{
			message: '회원가입이 완료되었습니다!',
			user: { email },
		},
		{ status: 201 },
	);
};

// 이메일 중복 확인 Resolver
const checkIdResolver: HttpResponseResolver = ({ request }) => {
	const url = new URL(request.url);
	const email = url.searchParams.get('email');

	console.log(`[MSW] 중복 확인 요청옴: ${email}`);

	if (email === 'fail@test.com') {
		return HttpResponse.json({
			success: true,
			message: null,
			data: true, // 중복됨
		});
	}

	return HttpResponse.json({
		success: true,
		message: null,
		data: false, // 사용 가능
	});
};

// 인증번호 전송 Resolver
const sendCodeResolver: HttpResponseResolver = async ({ request }) => {
	const body = (await request.json()) as { email: string };
	console.log(`[MSW] 인증코드 발송 요청: ${body.email}`);

	// 성공 응답 (200 OK)
	return HttpResponse.json(
		{ message: '인증번호가 발송되었습니다.' },
		{ status: 200 },
	);
};

// 인증번호 검증 Resolver
const verifyCodeResolver: HttpResponseResolver = async ({ request }) => {
	const body = (await request.json()) as { email: string; code: string };
	console.log(`[MSW] 코드 검증 요청: ${body.code} (email: ${body.email})`);

	// [테스트 시나리오] '123456' 입력 시에만 성공
	if (body.code === '123456') {
		return HttpResponse.json(
			{
				success: true,
				message: '인증되었습니다.',
				data: {
					sign_up_token: 'mock-sign-up-token-eyJhbGciOiJIUzI1NiJ9',
				},
			},
			{ status: 200 },
		);
	}

	// 그 외에는 실패 (400 Bad Request)
	return HttpResponse.json(
		{ message: '인증번호가 일치하지 않습니다.' },
		{ status: 400 },
	);
};

// 일반 로그인 Resolver
const loginResolver: HttpResponseResolver = async ({ request }) => {
	const body = (await request.json()) as { email: string; password: string };
	console.log(`[MSW] 로그인 요청: ${body.email}`);

	// [테스트 시나리오] 특정 계정으로 로그인 시 성공
	if (body.email === 'test@test.com' && body.password === 'test1234!') {
		return HttpResponse.json(
			{
				success: true,
				message: null,
				data: {
					access_token:
						'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI2YWMyNTI5ZS1kMDY3LTQ2ODQtOTZhOS0yYmYzNGM1NDBhMDYiLCJyb2xlIjoiVVNFUiIsImlhdCI6MTc2OTk1MTkxMywiZXhwIjoxNzY5OTUzNzEzfQ.WErNWe_zgQrhPXe5PKlTKZ-aeX7JDKjDev2Yu2Fmp8k',
				},
			},
			{
				status: 200,
				headers: {
					'Set-Cookie': `refresh_token=mock-refresh-token-${Date.now()}; Path=/; Max-Age=604800; HttpOnly; SameSite=Lax`,
				},
			},
		);
	}

	// 실패 시나리오 (401 Unauthorized)
	return HttpResponse.json(
		{ message: '아이디 또는 비밀번호가 일치하지 않습니다.' },
		{ status: 401 },
	);
};

// 소셜 로그인 Resolver (Kakao, Google 공통)
const socialLoginResolver: HttpResponseResolver = async ({
	request,
	params,
}) => {
	// URL 파라미터에서 provider 추출 (예: /auth/login/kakao -> params.provider = 'kakao')
	const { provider } = params;
	const body = (await request.json()) as { code: string };

	console.log(`[MSW] 소셜 로그인 요청 (${provider}):`, body.code);

	// 성공 시나리오
	return HttpResponse.json(
		{
			accessToken: `mock-access-token-${provider}`,
			user: {
				id: provider === 'kakao' ? 200 : 300,
				email: `${provider}_user@test.com`,
				name: `${provider} 사용자`,
				loginType: provider,
			},
		},
		{
			status: 200,
			headers: {
				'Set-Cookie': `refresh_token=mock-social-refresh-token-${Date.now()}; Path=/; Max-Age=604800; HttpOnly; SameSite=Lax`,
			},
		},
	);
};

// 토큰 갱신 Resolver
const refreshTokenResolver: HttpResponseResolver = async ({ cookies }) => {
	console.log('[MSW] 토큰 갱신 요청 받음');
	console.log('[MSW] Cookies:', cookies); // 디버깅용: 실제 들어오는 쿠키 확인

	// 쿠키 확인 (RTR) - MSW에서 파싱해준 cookies 객체 사용
	const refreshToken = cookies.refresh_token;
	if (!refreshToken) {
		return HttpResponse.json(
			{ message: 'Refresh Token이 없습니다.' },
			{ status: 401 },
		);
	}

	return HttpResponse.json(
		{
			success: true,
			message: null,
			data: {
				access_token: 'mock-new-access-token-' + Date.now(),
			},
		},
		{
			status: 200,
			headers: {
				'Set-Cookie': `refresh_token=mock-new-refresh-token-${Date.now()}; Path=/; Max-Age=604800; HttpOnly; SameSite=Lax`,
			},
		},
	);
};

// 로그아웃 Resolver
const logoutResolver: HttpResponseResolver = async () => {
	console.log('[MSW] 로그아웃 요청 받음');
	// 클라이언트에서 토큰을 삭제하는 것이 주 목적이므로,
	// 서버에서는 성공 응답만 보내주면 됨
	return HttpResponse.json(
		{
			success: true,
			message: '로그아웃 성공',
			data: null,
		},
		{ status: 200 },
	);
};

// 주식 랭킹 조회 Resolver
const stockRankingResolver: HttpResponseResolver = ({ request }) => {
	const url = new URL(request.url);
	const limit = Number(url.searchParams.get('limit')) || 10;

	console.log(`[MSW] 주식 랭킹 조회 요청 (limit: ${limit})`);

	// 가짜 주식 데이터 생성
	const mockData = Array.from({ length: limit }).map((_, i) => ({
		stockCode: String(i + 1).padStart(6, '0'), // 000001, 000002...
		stockName: `테스트종목 ${i + 1}`,
		currentPrice: 10000 + i * 500 + Math.floor(Math.random() * 1000),
		changeRate: Number((Math.random() * 20 - 10).toFixed(2)), // -10.00 ~ +10.00
		cumulativeAmount: 1000000000 + i * 50000000, // 10억 + @
		cumulativeVolume: 100000 + i * 5000,
	}));

	return HttpResponse.json(mockData, {
		status: 200,
	});
};

// WebSocket 핸들러 정의
const stockSocket = ws.link('ws://localhost:8080/stocks');

/*
  [Handlers]
  URL 경로와 HTTP 메서드를 Resolver 함수와 매핑
*/
export const handlers = [
	// 회원가입 (POST)
	http.post('*/auth/register', signupResolver),

	// 이메일 중복 확인 (GET)
	http.get('*/api/auth/check-email', checkIdResolver),

	// 인증번호 발송 (POST)
	http.post('*/api/auth/code', sendCodeResolver),

	// 인증번호 검증 (POST)
	http.post('*/api/auth/code/verify', verifyCodeResolver),

	// 일반 로그인 (POST)
	http.post('*/api/auth/login', loginResolver),

	// 소셜 로그인 (POST)
	http.post('*/auth/login/:provider', socialLoginResolver),

	// 토큰 갱신 (POST)
	http.post('*/auth/reissue', refreshTokenResolver),

	// 로그아웃 (POST)
	http.post('*/auth/logout', logoutResolver),

	// 주식 랭킹 조회 (GET)
	http.get('*/api/stocks/ranking/value', stockRankingResolver),

	// WebSocket 연결 핸들링
	stockSocket.addEventListener('connection', ({ client }) => {
		console.log('[MSW] WebSocket connected');

		let intervalId: any;
		let currentLimit = 10;

		client.addEventListener('message', (event) => {
			const data = event.data as string;

			// 1. CONNECT 프레임 처리
			if (data.startsWith('CONNECT') || data.startsWith('STOMP')) {
				client.send('CONNECTED\nversion:1.2\n\n\0');
				return;
			}

			// 2. SUBSCRIBE 프레임 처리
			if (data.startsWith('SUBSCRIBE')) {
				const destMatch = data.match(/destination:([^\n]+)/);
				const idMatch = data.match(/id:([^\n]+)/);

				if (destMatch && idMatch) {
					const destination = destMatch[1].trim();
					const id = idMatch[1].trim();

					if (
						destination === '/topic/ranking/value' ||
						destination === '/topic/ranking/volume'
					) {
						console.log(`[MSW] STOMP 구독 시작: ${destination}`);

						const sendUpdate = () => {
							let mockData = Array.from({ length: currentLimit }).map(
								(_, i) => ({
									stockCode: String(i + 1).padStart(6, '0'),
									stockName: `테스트종목 ${i + 1}`,
									currentPrice:
										10000 + i * 500 + Math.floor(Math.random() * 1000),
									changeRate: Number((Math.random() * 20 - 10).toFixed(2)),
									cumulativeAmount: 1000000000 + i * 50000000,
									cumulativeVolume: 10000000 - i * 5000,
								}),
							);

							// 거래량 순일 경우 데이터 특성 약간 변경 (테스트용)
							if (destination === '/topic/ranking/volume') {
								mockData = mockData.sort(
									(a, b) => b.cumulativeVolume - a.cumulativeVolume,
								);
							}

							const payload = JSON.stringify({
								type:
									destination === '/topic/ranking/value'
										? 'RANKING_VALUE_UPDATE'
										: 'RANKING_VOLUME_UPDATE',
								data: mockData,
							});

							// STOMP MESSAGE 프레임 구성
							const messageFrame = `MESSAGE\ndestination:${destination}\nsubscription:${id}\nmessage-id:${Date.now()}\ncontent-type:application/json\n\n${payload}\0`;

							client.send(messageFrame);
						};

						sendUpdate();
						if (intervalId) clearInterval(intervalId);
						intervalId = setInterval(sendUpdate, 1000);
					}
				}
				return;
			}

			// 3. SEND 프레임 처리 (Limit 업데이트 등)
			if (data.startsWith('SEND')) {
				const destMatch = data.match(/destination:([^\n]+)/);
				if (destMatch && destMatch[1].trim().startsWith('/app/ranking/')) {
					const bodyParts = data.split('\n\n');
					if (bodyParts.length >= 2) {
						try {
							const bodyStr = bodyParts[1].replace(/\0$/, '');
							const body = JSON.parse(bodyStr);
							if (body.limit) {
								currentLimit = body.limit;
								console.log(`[MSW] Limit 업데이트: ${currentLimit}`);
							}
						} catch (e) {
							console.error('[MSW] Body 파싱 에러', e);
						}
					}
				}
			}
		});

		client.addEventListener('close', () => {
			if (intervalId) clearInterval(intervalId);
		});
	}),
];
