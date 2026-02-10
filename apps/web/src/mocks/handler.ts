import { http, HttpResponse, type HttpResponseResolver } from 'msw';

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
	// 실제 백엔드에서는 리프레시 토큰을 사용하여 새 액세스 토큰을 발급
	// 여기서는 간단히 새로운 가짜 액세스 토큰과 사용자 정보를 반환
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

// 로그아웃 Resolver
const logoutResolver: HttpResponseResolver = async () => {
	console.log('[MSW] 로그아웃 요청 받음');
	// 클라이언트에서 토큰을 삭제하는 것이 주 목적이므로,
	// 서버에서는 성공 응답만 보내주면 됨
	return HttpResponse.json({ message: '로그아웃 성공' }, { status: 200 });
};

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
	http.post('*/auth/refresh', refreshTokenResolver),

	// 로그아웃 (POST)
	http.post('*/auth/logout', logoutResolver),
];
