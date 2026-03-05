/**
 * @jest-environment node
 */
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handler';

// MSW 서버 설정: 작성된 핸들러들을 기반으로 모의 서버를 생성
const server = setupServer(...handlers);

describe('MSW Handler Verification (Stock API)', () => {
	// 테스트 시작 전: MSW 서버 연결
	beforeAll(() => server.listen());

	// 개별 테스트 종료 후: 핸들러 상태 초기화 (다른 테스트에 영향을 주지 않기 위함)
	afterEach(() => server.resetHandlers());

	// 모든 테스트 종료 후: MSW 서버 정지
	afterAll(() => server.close());

	it('GET /api/stocks/ranking/value 요청 시 모의 데이터를 반환해야 한다', async () => {
		/**
		 * @Given 테스트를 위한 환경 설정
		 * - 가져올 주식 데이터의 개수(limit)를 5로 설정
		 * - 호출할 API 엔드포인트 URL 준비
		 */
		const limit = 5;
		const url = `http://localhost:8080/api/stocks/ranking/value?limit=${limit}`;

		/**
		 * @When 동작 수행
		 * - fetch API를 사용하여 해당 URL로 네트워크 요청 발생
		 * - 응답 결과를 JSON 형태로 변환
		 */
		const response = await fetch(url);
		const data = await response.json();

		/**
		 * @Then 결과 검증
		 * - HTTP 응답 상태 코드가 200(OK)인지 확인
		 * - 반환된 데이터가 배열 형태이며, 길이가 5인지 확인
		 * - 데이터의 첫 번째 요소가 주식 정보 스키마(코드, 이름, 가격 등)를 모두 포함하는지 확인
		 */
		expect(response.status).toBe(200);
		expect(Array.isArray(data)).toBe(true);
		expect(data).toHaveLength(limit);

		const firstItem = data[0];
		expect(firstItem).toHaveProperty('stockCode');
		expect(firstItem).toHaveProperty('stockName');
		expect(firstItem).toHaveProperty('currentPrice');
		expect(firstItem).toHaveProperty('changeRate');
		expect(firstItem).toHaveProperty('cumulativeAmount');
		expect(firstItem).toHaveProperty('cumulativeVolume');
	});

	it('limit 파라미터가 없으면 기본값(10개)을 반환해야 한다', async () => {
		/**
		 * @Given
		 * - 쿼리 파라미터(limit)를 제외한 API 엔드포인트 URL 준비
		 */
		const url = 'http://localhost:8080/api/stocks/ranking/value';

		/**
		 * @When
		 * - 서버에 데이터 요청 및 응답 데이터 파싱
		 */
		const response = await fetch(url);
		const data = await response.json();

		/**
		 * @Then
		 * - 기본 설정값인 10개의 데이터가 반환되는지 확인
		 */
		expect(data).toHaveLength(10);
	});
});
