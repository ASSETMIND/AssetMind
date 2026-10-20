import ws from 'k6/ws';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 100 }, // 1분 동안 100명까지 증가
    { duration: '2m', target: 500 }, // 2분 동안 500명까지 증가
    { duration: '2m', target: 1000 }, // 2분동안 1000명까지 증가
    { duration: '1m', target: 0 }, // 1분동안 0명으로 감소
  ],
};

const WS_URL = 'ws://localhost:9090/ws-stock/websocket';

// STOMP 프로토콜 유틸리티 힘수
const stompConnectFrame = () =>
    `CONNECT\naccept-version:1.1,1.2\nheart-beat:10000,10000\n\n\0`;

const stompSubscribeFrame = (destination, id) =>
    `SUBSCRIBE\nid:${id}\ndestination:${destination}\n\n\0`;

export default function () {
  const stockCode = '005930';

  const res = ws.connect(WS_URL, function(socket) {
    socket.on('open', function () {
      socket.send(stompConnectFrame());
    });

    socket.on('message', function(msg) {
      if (msg.includes('CONNECTED')) {
        const subId = `sub-${__VU}-${stockCode}`;
        socket.send(stompSubscribeFrame(`/topic/orderbook/${stockCode}`, subId));
      }
    });

    // 120초 동안 세션 유지 후 정상 종료
    socket.setTimeout(function () {
      socket.close();
    }, 120000);
  });

  check(res, {
    'WS status is 101': (r) => r && r.status === 101,
  });

  if (res && res.status !== 101) {
    console.log(`[연결 실패] HTTP Status: ${res.status}, 에러: ${res.error}`);
  }
}

