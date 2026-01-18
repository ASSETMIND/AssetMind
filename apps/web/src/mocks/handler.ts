import { http, HttpResponse } from 'msw';

/*
  MSW 핸들러 정의 목록
  회원가입(POST) 및 이메일 중복 확인(GET) API 모킹
  'fail@test.com' 입력 시 실패/중복 시나리오가 동작하도록 설정
 */
export const handlers = [
	/*
    회원가입 요청 (POST /auth/signup)
    요청 본문 파싱 및 데이터 추출
    특정 이메일 입력 시 409 Conflict 에러 반환 (가입 실패 테스트용)
    그 외 경우 201 Created 성공 응답 반환
   */
	http.post('*/auth/signup', async ({ request }) => {
		// 타입 단언을 통해 request body의 구조 명시 (id -> email로 수정)
		const requestBody = (await request.json()) as { email: string };

		console.log('MSW: 회원가입 요청 받음', requestBody);

		// [테스트 시나리오] 이미 가입된 이메일로 가정
		if (requestBody.email === 'fail@test.com') {
			return HttpResponse.json(
				{ message: '이미 존재하는 계정입니다.' },
				{ status: 409 },
			);
		}

		// 정상 가입 처리
		return HttpResponse.json(
			{
				message: '회원가입이 완료되었습니다!',
				user: { email: requestBody.email },
			},
			{ status: 201 },
		);
	}),

	/*
    이메일 중복 확인 (GET /users)
    json-server의 조회 방식(배열 반환)을 모방
    URL 쿼리 파라미터에서 email 추출
    중복 시: 유저 객체가 담긴 배열 반환 (length >= 1)
    미중복 시: 빈 배열 반환 (length === 0)
   */
	http.get('*/users', ({ request }) => {
		const url = new URL(request.url);
		const email = url.searchParams.get('email');

		console.log(`[MSW] 중복 확인 요청옴: ${email}`);

		// [테스트 시나리오] 중복된 이메일
		if (email === 'fail@test.com') {
			return HttpResponse.json([
				{ id: 1, email: 'fail@test.com', name: '기존유저' },
			]);
		}

		// [테스트 시나리오] 사용 가능한 이메일 (결과 없음)
		return HttpResponse.json([]);
	}),
];
