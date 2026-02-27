# [TCS] 실시간 주가 데이터 이벤트 통합 테스트 명세서

| 문서 ID | **TCS-EVENT-001**                             |
| :--- |:----------------------------------------------|
| **문서 버전** | 1.1                                           |
| **프로젝트** | AssetMind                                     |
| **작성자** | 이재석                                           |
| **작성일** | 2026년 02월 11일                                 |
| **대상 모듈** | Stock Event Pipeline (`Handler` → `Listener`) |

## 1. 개요 (Overview)

본 문서는 외부(KIS)로부터 수신된 웹소켓 메시지가 내부 로직을 거쳐 **Spring Event**로 발행되고, 이를 `리스너(Listener)`가 정상적으로 수신하는지 확인하기 위한 통합 테스트 명세이다.
`KisWebSocketHandler`(발행자)와 `StockTradeEventListener`(수신자) 간의 데이터 흐름과 매핑 정확성을 중점적으로 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, Mockito, Spring Boot Test
- **Test Class:** `RealTimeStockEventLightTest`
- **Context Configuration:**
    - `KisWebSocketHandler`: 웹소켓 메시지 수신 및 이벤트 발행 (Subject)
    - `StockTradeEventListener`: 이벤트 수신 및 예외 방어 로직 확인 (`@SpyBean`)
    - `KisRealTimeDataParser`: 원본 데이터 파싱 모의 (`@MockBean`)
    - `KisEventMapper`: DTO 변환 로직 (Real Bean)

---

## 2. 테스트 케이스 상세 (Test Cases)

### 2.1. 이벤트 발행 및 구독 흐름 (Publish & Subscribe Flow)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **STK-INT-001** | **정상적인 주가 데이터 수신 및 이벤트 전파**<br>(Golden Path) | 1. **Mock Data 생성:**<br> - 종목코드: `005930` (삼성전자)<br> - 현재가: `160,000`<br> - 등락부호: `"1"` (상한/상승)<br>2. **Parser Stubbing:**<br> - `parser.parse()` 호출 시 위 데이터를 반환하도록 설정 (`given`) | `webSocketHandler`<br>`.handleMessage()` 호출<br>(Dummy Payload 주입) | 1. `eventListener.handleStockTradeEvent()` 메서드가 **1회 호출**되어야 한다. (`verify`)<br>2. 리스너가 수신한 이벤트(`RealTimeStockTradeEvent`)의 필드값이 검증되어야 한다.<br> - `stockCode`: `"005930"` 일치<br> - `changeSign`: `"1"` 일치 |

### 2.2. 예외 처리 및 스레드 생존 (Exception Handling & Stability)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **STK-INT-002** | **서비스 계층 예외 발생 시 리스너 생존 및 로깅**<br>(Exception Path) | 1. **Mock Event 생성:**<br>종목코드 `005930` 더미 이벤트<br>2. **Service Stubbing:**<br>`stockService.processRealTimeTrade()` 호출 시 `RuntimeException("DB Connection Timeout!")` 발생 강제 | `eventListener.handleStockTradeEvent()` 직접 호출 | 1. 예외가 리스너 외부로 던져지지 않음 (`assertDoesNotThrow`, 스레드 생존 보장)<br>2. 캡처된 콘솔 로그(`CapturedOutput`)에 정확한 에러 메시지와 원인이 기록됨 |

---

## 3. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고 |
| :--- | :---: | :---: | :---: | :--- |
| **이벤트 파이프라인 흐름** | 1 | 1 | 0 | 정상 수신 및 데이터 매핑 검증 완료 |
| **비동기 예외 방어** | 1 | 1 | 0 | **DB 장애 등 치명적 에러 발생 시 스레드 생존 및 로깅 완벽 검증** |
| **합계** | **2** | **2** | **0** | **Pass** ✅ |