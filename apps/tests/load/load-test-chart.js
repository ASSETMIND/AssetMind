import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 500}, // 1분동안 VU(가상 유저)를 0에서 50까지 점진적 증가
    { duration: '5m', target: 500}, // 3분 동안 50명 유지
    { duration: '10m', target: 1000}, // 100명으로 증가
    { duration: '2m', target: 0}, // 종료
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'], // 에러율 1% 미만 유지
    http_req_duration: ['p(95)<200'] // 95% 응답 속도 200ms 미만 유지
  },
};

const STOCK_SERVER_BASE_URL = 'http://127.0.0.1:9090'; // Stock 서버 주소

const TARGET_STOCKS = ['005930', '000660', '035420', '035720', '005380', '000270'];

export default function () {
  // 각 VU(가상 유저)는 자신만의 독립적인 endTime 상태를 가짐
  const stockCode = TARGET_STOCKS[Math.floor(Math.random() * TARGET_STOCKS.length)];
  let lastEndTime = new Date().toISOString().split('.')[0];

  // VU(가상 유저)가 5페이지까지 무한 스크롤을 시도하는 시나리오
  for (let page = 0; page < 5; page++) {
    const url = `${STOCK_SERVER_BASE_URL}/api/stocks/${stockCode}/charts/candles?timeframe=1m&endTime=${lastEndTime}&limit=20`;

    // tags.name을 통해 동적 URL을 하나의 API 메트릭으로 논리적 그룹화
    const res = http.get(url, {
      tags: { name: 'GET /api/stocks/{code}/charts/candles' }
    });

    const isOk = check(res, {
      'is status 200': (r) => r.status === 200,
    });

    if (!isOk) {
      console.log(`[Error] Status: ${res.status}, URL: ${url}, Body: ${res.body}`);
      break;
    }

    // 200 OK일 때만 안전하게 JSON 파싱
    if (isOk) {
      try {
        const candles = res.json();
        if (candles && candles.length > 0) {
          lastEndTime = candles[candles.length - 1].dateTime;

          // Think Time: 다음 페이지를 스크롤하기 전 유저가 차트를 보는 시간 모사
          sleep(Math.random() * 1 + 0.5); // 0.5초 ~ 1.5초 대기
        } else {
          break; // 데이터가 더 없으면 무한스크롤 종료
        }
      } catch (e) {
        // 응답이 JSON이 아닌 경우 (ex: 프록시 에러 등)
        console.error("JSON parsing failed, Status: " + res.status);
        break;
      }
    } else {
      break; // 200이 아니면 불필요한 연속 요청 방지
    }
  }

  sleep(1);
}