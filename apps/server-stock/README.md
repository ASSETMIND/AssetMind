# 📈 주식 실시간 체결 데이터 웹소켓 (STOMP) API 명세서

본 API는 STOMP 프로토콜을 사용하여 주식의 실시간 체결 데이터 및 랭킹 데이터를 클라이언트(프론트엔드)로 브로드캐스트합니다.
모든 데이터는 서버에서 클라이언트로 단방향 전송(Subscribe)되며, 별도의 발행(Publish) 요청은 필요하지 않습니다.

## 1. 연결 설정 (Connection)

* **Endpoint URL:** `ws://{domain}/ws-stock` (예: `ws://localhost:8080/ws-stock`)
* **Protocol:** STOMP over WebSocket (SockJS Fallback 지원)
* **인증(Authorization):** 필요 없음 (Public 뷰 전용)

---

## 2. 구독 채널 (Subscribe Topics)

### A. 개별 종목 실시간 상세 데이터 (상세 차트/호가용)
특정 종목의 체결 이벤트가 발생할 때마다 해당 채널을 구독 중인 클라이언트에게 실시간으로 JSON 데이터를 전송합니다.

* **Destination:** `/topic/stocks/{stockCode}`
    * *예시: 삼성전자 구독 시 `/topic/stocks/005930`*
* **Response Payload (JSON):**
```json
{
  "stockCode": "005930",
  "currentPrice": "75200",
  "openPrice": "74000",
  "highPrice": "76000",
  "lowPrice": "73000",
  "priceChange": "1000",
  "changeRate": "1.35",
  "executionVolume": "500",
  "cumulativeAmount": "112500000000",
  "cumulativeVolume": "1500000",
  "time": "120000"
}
```
* **필드 설명:**
  * `stockCode`: 종목코드 (String)
  * `currentPrice`: 현재가 (String)
  * `openPrice`: 시가 (String)
  * `highPrice`: 고가 (String)
  * `lowPrice`: 저가 (String)
  * `priceChange`: 전일 대비 증감액 (String)
  * `changeRate`: 전일 대비 등락률 (String)
  * `executionVolume`: 순간 체결량 (String)
  * `cumulativeAmount`: 누적 거래대금 (String)
  * `cumulativeVolume`: 누적 거래량 (String)
  * `time`: 체결 시간 (String, HHMMSS 형식)
> 모든 필드는 String 타입입니다.

---

### B. 메인 페이지 랭킹 데이터 (거래대금/거래량 랭킹용)
시장의 주요 체결 이벤트가 발생하여 랭킹 정보가 업데이트될 때마다 메인 차트를 보고 있는 클라이언트에게 전송합니다.

* **Destination:** `/topic/ranking`
* **Response Payload (JSON):**
```json
{
  "stockCode": "005930",
  "stockName": "삼성전자",
  "currentPrice": "75200",
  "priceChange": "1000",
  "changeRate": "1.35",
  "cumulativeAmount": "112500000000",
  "cumulativeVolume": "1500000"
}
```
* **필드 설명:**
    * `stockCode`: 종목코드 (String)
    * `stockName` : 종목 이름 (String)
    * `currentPrice`: 현재가 (String)
    * `priceChange`: 전일 대비 증감액 (String)
    * `changeRate`: 전일 대비 등락률 (String)
    * `cumulativeAmount`: 누적 거래대금 (String)
    * `cumulativeVolume`: 누적 거래량 (String)
> 모든 필드는 String 타입입니다.