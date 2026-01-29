import { http, HttpResponse, type HttpResponseResolver } from 'msw';

/*
  [Resolvers]
  실제 요청을 처리하고 응답을 생성하는 로직 함수
*/

// 회원가입 Resolver
const signupResolver: HttpResponseResolver = async ({ request }) => {
	const requestBody = (await request.json()) as {
		id?: string;
		email?: string;
		password?: string;
	};

	const email = requestBody.email || requestBody.id;
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
		return HttpResponse.json([
			{ id: 1, email: 'fail@test.com', name: '기존유저' },
		]);
	}

	return HttpResponse.json([]);
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
		return HttpResponse.json({ message: '인증되었습니다.' }, { status: 200 });
	}

	// 그 외에는 실패 (400 Bad Request)
	return HttpResponse.json(
		{ message: '인증번호가 일치하지 않습니다.' },
		{ status: 400 },
	);
};

// 일반 로그인 Resolver
const loginResolver: HttpResponseResolver = async ({ request }) => {
	const body = (await request.json()) as { id: string; password: string };
	console.log(`[MSW] 로그인 요청: ${body.id}`);

	// [테스트 시나리오] 특정 계정으로 로그인 시 성공
	if (body.id === 'test@test.com' && body.password === 'password123!') {
		return HttpResponse.json(
			{
				accessToken: 'mock-access-token-12345', // 가짜 토큰 발급
				user: {
					id: 1,
					email: body.id,
					name: '테스트유저',
				},
			},
			{ status: 200 },
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
		{ status: 200 },
	);
};

// 토큰 갱신 Resolver
const refreshTokenResolver: HttpResponseResolver = async () => {
	console.log('[MSW] 토큰 갱신 요청 받음');
	// 실제 백엔드에서는 리프레시 토큰을 사용하여 새 액세스 토큰을 발급합니다.
	// 여기서는 간단히 새로운 가짜 액세스 토큰과 사용자 정보를 반환합니다.
	return HttpResponse.json(
		{
			accessToken: 'mock-new-access-token-' + Date.now(), // 매번 다른 토큰 반환
			user: {
				id: 1,
				email: 'refreshed@test.com',
				name: '갱신된유저',
			},
		},
		{ status: 200 },
	);
};

/*
  [Handlers]
  URL 경로와 HTTP 메서드를 Resolver 함수와 매핑
*/
export const handlers = [
	// 회원가입 (POST)
	http.post('*/auth/signup', signupResolver),

	// 이메일 중복 확인 (GET)
	http.get('*/users', checkIdResolver),

	// 인증번호 발송 (POST)
	http.post('*/api/auth/send-code', sendCodeResolver),

	// 인증번호 검증 (POST)
	http.post('*/api/auth/verify-code', verifyCodeResolver),

	// 일반 로그인 (POST)
	http.post('*/api/auth/login', loginResolver),

	// 소셜 로그인 (POST)
	http.post('*/auth/login/:provider', socialLoginResolver),

	// 토큰 갱신 (POST)
	http.post('*/auth/refresh', refreshTokenResolver),
];
