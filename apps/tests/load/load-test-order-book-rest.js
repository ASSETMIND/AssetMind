import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 500 },  // 30초 동안 500명까지
    { duration: '1m', target: 1000 },  // 1분 동안 1000명 유지
    { duration: '30s', target: 0 },    // 30초 동안 0명으로 쿨다운
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'], // 95%의 요청이 200ms 이내여야 통과
  },
};

const BASE_URL = 'http://localhost:9090';

export default function () {
  const stockCode = '005930'
  const res = http.get(`${BASE_URL}/api/stocks/${stockCode}/orderbook`);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(1); // 무한 루프 방지 및 유저 씽크타임 모사
}