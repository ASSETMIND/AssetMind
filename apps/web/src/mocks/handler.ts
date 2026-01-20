import { http, HttpResponse, type HttpResponseResolver } from 'msw';

/*
  [Resolvers]
  실제 요청을 처리하고 응답을 생성하는 로직 함수
*/

// 회원가입 Resolver
const signupResolver: HttpResponseResolver = async ({ request }) => {
	// 요청 본문 파싱
	const requestBody = (await request.json()) as {
		id?: string;
		email?: string;
		password?: string;
	};

	// 클라이언트에서 id로 보내는지 email로 보내는지 확인하여 추출
	const email = requestBody.email || requestBody.id;

	console.log('MSW: 회원가입 요청 받음', requestBody);

	// [테스트 시나리오] 이미 가입된 이메일
	if (email === 'fail@test.com') {
		return HttpResponse.json(
			{ message: '이미 존재하는 계정입니다.' },
			{ status: 409 },
		);
	}

	// 정상 가입 처리
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

	// [테스트 시나리오] 중복된 이메일 (배열 반환)
	if (email === 'fail@test.com') {
		return HttpResponse.json([
			{ id: 1, email: 'fail@test.com', name: '기존유저' },
		]);
	}

	// [테스트 시나리오] 사용 가능 (빈 배열)
	return HttpResponse.json([]);
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
];
