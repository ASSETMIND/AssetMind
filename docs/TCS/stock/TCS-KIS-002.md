# [TCS] KIS 실시간 웹소켓 핸들러(WebSocket Handler) 테스트 명세서

| 문서 ID | **TCS-KIS-002**                             |
| :--- |:--------------------------------------------|
| **문서 버전** | 1.0                                         |
| **프로젝트** | AssetMind                                   |
| **작성자** | 이재석                                         |
| **작성일** | 2026년 02월 05일                               |
| **관련 모듈** | `KisWebSocketHandler`, `KisWebsocketAdapter` |

## 1. 개요 (Overview)

본 문서는 한국투자증권(KIS) 실시간 주식 데이터를 처리하는 **웹소켓 모듈 전체**에 대한 단위 테스트(Unit Test) 명세이다.
연결을 관리하는 **어댑터(Adapter)**와 데이터를 처리하는 **핸들러(Handler)**의 기능을 다루며, 비동기 환경에서의 안정성 확보를 목표로 한다.

### 1.1. 테스트 대상 및 도구
| 구분 | 대상 클래스 | 주요 검증 항목 | Mocking 도구 |
|:---:|:---|:---|:---|
| **Connection** | `KisWebSocketAdapter` | 연결/재접속, 구독 위임, 자원 해제 | `ReflectionTestUtils`, `CompletableFuture` |
| **Logic** | `KisWebSocketHandler` | 구독 버퍼링, 데이터 파싱, 포맷 방어("H"), 예외 처리 | `WebSocketSession`, `ObjectMapper` |

---

## 2.  KisWebSocketHandler 테스트 명세
> **대상 클래스:** `KisWebSocketHandlerTest`
> **검증 목표:** 데이터의 흐름 제어 및 파싱 정확성 검증

### 2.1. 구독 요청 및 버퍼링 (Subscription & Buffering)

| ID          | 테스트 메서드 / 시나리오                                                                                                                        | Given (사전 조건)                                                       | When (수행 행동)                                 | Then (검증 결과)                                                                                       |
|:------------|:--------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------|:---------------------------------------------|:---------------------------------------------------------------------------------------------------|
| **WSH-001** | `givenNoSession_whenSubscribeNewStock_`<br>`thenSendAfterConnection`<br>👉 **세션 연결 전 구독 요청은 대기열에 저장되었다가, 연결 후 한꺼번에 전송되어야 한다.** | **세션 없음 (Null)**<br>연결되지 않은 초기 상태                                | 1. **구독 요청** (`subscribe`)<br>2. **연결 성공 이벤트 발생** (`afterConnectionEstablished`) | 1. 구독 요청 시점엔 전송 메서드가 호출되지 않음 (`never`).<br>2. 대기열(`pendingList`)에 요청이 저장됨.<br>3. 연결 직후 메시지가 전송됨 (`verify`). |
| **WSH-002** | `givenSession_whenSubscribeNewStock_`<br>`thenSendSubscribeRequest`<br>👉 **이미 연결된 상태에서는 대기열 없이 바로 전송해야 한다.** | **세션 활성 (Open)**<br>`afterConnectionEstablished`가 이미 호출된 상태       | **구독 요청** (`subscribe`)                      | 1. 대기열을 거치지 않고 즉시 `sendMessage`가 호출된다 (`times(1)`).                                         |

### 2.2. 데이터 파싱 및 방어 로직 (Data Parsing & Defense)

| ID          | 테스트 메서드 / 시나리오                                                                                                                        | Given (사전 조건)                                                       | When (수행 행동)                                 | Then (검증 결과)                                                                                       |
|:------------|:--------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------|:---------------------------------------------|:---------------------------------------------------------------------------------------------------|
| **WSH-003** | `givenNormalStockData_whenHandleMessage_`<br>`thenParsingPayload`<br>👉 **일반적인 주식 체결 데이터(Count=1)를 정상적으로 파싱해야 한다.** | **정상 텍스트 패킷**<br>`0|ID|001|데이터...` (파이프 구분자 포함)                 | **메시지 수신** (`handleMessage`)                | 1. 예외가 발생하지 않음 (`assertDoesNotThrow`).<br>2. 내부 파싱 로직을 통해 데이터 로그가 정상 출력됨.                       |
| **WSH-004** | `givenMultiStockData_whenHandleMessage_`<br>`thenParsingPayload`<br>👉 **멀티 레코드(Count=2 이상) 데이터가 와도 반복문을 통해 모두 처리해야 한다.** | **멀티 텍스트 패킷**<br>`0|ID|002|데이터1^데이터2` (데이터 2건 포함)              | **메시지 수신** (`handleMessage`)                | 1. 반복문이 2회 실행되어 두 종목의 데이터를 모두 처리함.<br>2. 오프셋 계산이 정확하여 데이터가 섞이지 않음.                        |
| **WSH-005** | `givenErrorStockData_whenHandleMessage_`<br>`thenParsingPayload`<br>👉 **'H' 에러 데이터(개수 필드 누락)가 와도 시스템이 죽지 않고 방어 처리해야 한다.** | **비정상 패킷 ("H" 에러)**<br>`0|ID|데이터...` (가운데 개수 필드 생략됨)             | **메시지 수신** (`handleMessage`)                | 1. `NumberFormatException`이 발생하지 않음.<br>2. 개수를 1개로 간주하고 정상적으로 데이터를 추출함.                         |
| **WSH-006** | `givenJsonOperatorData_whenHandleMessage_`<br>`thenParsingPayload`<br>👉 **JSON 제어 메시지(PINGPONG, 구독응답)는 JSON으로 처리해야 한다.** | **JSON 패킷**<br>`{"header": {"tr_id": "PINGPONG"}}`                | **메시지 수신** (`handleMessage`)                | 1. 첫 글자가 `{`임을 감지하고 JSON 파서로 분기함.<br>2. 텍스트 파싱 로직을 타지 않고 정상 처리됨.                             |

### 2.3. 예외 처리 및 자원 정리 (Exception & Cleanup)

| ID          | 테스트 메서드 / 시나리오                                                                                                                        | Given (사전 조건)                                                       | When (수행 행동)                                 | Then (검증 결과)                                                                                       |
|:------------|:--------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------|:---------------------------------------------|:---------------------------------------------------------------------------------------------------|
| **WSH-007** | `givenJsonError_whenSubscribeNewStock_`<br>`thenNotExitSystem`<br>👉 **객체 변환(JSON) 실패 시 시스템이 죽지 않고 로그만 남겨야 한다.** | **Mapper 고장 (Mock)**<br>`writeValueAsString` 호출 시 예외 발생 설정         | **구독 요청** (`subscribe`)                      | 1. 예외가 `catch` 블록에서 처리되어 시스템 종료를 방지함.<br>2. `sendMessage`는 호출되지 않음 (`never`).                  |
| **WSH-008** | `givenTransportError_whenSubscribeNewStock_`<br>`thenNotExitSystem`<br>👉 **전송 중 IO 예외가 발생해도 다음 종목 처리는 계속되어야 한다.** | **네트워크 불안정 (Mock)**<br>첫 번째 전송 시 `IOException` 발생 설정              | **다수 종목 구독 요청** | 1. 첫 번째 종목 전송 실패 로그 출력.<br>2. 반복문이 중단되지 않고 **두 번째 종목 전송을 시도**함 (`times(2)`).               |
| **WSH-009** | `whenCloseConnection_`<br>`thenCleanUpSessionAndFiled`<br>👉 **연결 종료 요청 시 세션을 닫고 내부 상태 변수를 초기화해야 한다.** | **세션 활성 (Open)**<br>구독 목록(`Set`)에 데이터가 존재하는 상태                   | **연결 종료** (`closeConnection`)                | 1. `session.close()`가 호출됨.<br>2. `currentSession`이 `null`로 초기화됨.<br>3. `subscribedStock`이 비워짐. |
| **WSH-010** | `givenCloseError_whenCloseConnection_`<br>`thenCleanUpSessionAndFiled`<br>👉 **종료 중 에러가 발생해도 자원 정리는 수행되어야 한다 (Finally 검증).** | **종료 실패 (Mock)**<br>`close()` 호출 시 `IOException` 발생 설정             | **연결 종료** (`closeConnection`)                | 1. 예외가 발생하지만 무시됨.<br>2. `finally` 블록이 실행되어 내부 변수(`null`, `clear`) 초기화가 보장됨.                 |

---

데이터의 흐름 제어 및 파싱 정확성 검증

### 2.1. 구독 요청 및 버퍼링 (Subscription)

| ID | 테스트 메서드 / 시나리오 | Given | When | Then |
|:---:|:---|:---|:---|:---|
| **WSH-001** | `givenNoSession_...`<br>👉 **세션 연결 전 요청은 대기열에 저장 후 일괄 전송한다.** | 세션 없음 (Null) | 1. 구독 요청<br>2. 연결 성공 이벤트 | 1. 요청 시점 전송 X (`never`)<br>2. 연결 직후 전송 O (`verify`) |
| **WSH-002** | `givenSession_...`<br>👉 **연결된 상태에서는 대기열 없이 즉시 전송한다.** | 세션 활성 (Open) | 구독 요청 | 1. 즉시 `sendMessage` 호출됨. |

### 2.2. 데이터 파싱 및 방어 (Parsing & Defense)

| ID | 테스트 메서드 / 시나리오 | Given | When | Then |
|:---:|:---|:---|:---|:---|
| **WSH-003** | `givenNormalStockData_...`<br>👉 **정상 체결 데이터(Count=1)를 파싱한다.** | 정상 텍스트 패킷 | 메시지 수신 | 예외 없이 로그 출력 확인. |
| **WSH-004** | `givenMultiStockData_...`<br>👉 **멀티 레코드(Count=2+)를 반복 처리한다.** | 멀티 텍스트 패킷 | 메시지 수신 | 반복문 2회 실행 확인. |
| **WSH-005** | `givenErrorStockData_...`<br>👉 **'H' 에러(개수 누락) 데이터도 방어 처리한다.** | 비정상 패킷 | 메시지 수신 | `NumberFormatEx` 없이 정상 처리. |
| **WSH-006** | `givenJsonOperatorData_...`<br>👉 **JSON 제어 메시지는 별도로 처리한다.** | JSON 패킷 | 메시지 수신 | JSON 파서로 분기 처리됨. |

### 2.3. 예외 및 정리 (Exception & Cleanup)

| ID | 테스트 메서드 / 시나리오 | Given | When | Then |
|:---:|:---|:---|:---|:---|
| **WSH-007** | `givenJsonError_...`<br>👉 **변환 실패 시 시스템은 죽지 않아야 한다.** | Mapper 에러 설정 | 구독 요청 | `catch` 블록 처리, 시스템 유지. |
| **WSH-008** | `givenTransportError_...`<br>👉 **전송 실패 시 다음 종목을 계속 처리한다.** | IO 에러 설정 | 다수 구독 요청 | 반복문 중단 없이 계속 진행. |
| **WSH-009** | `whenCloseConnection_...`<br>👉 **종료 시 세션을 닫고 변수를 초기화한다.** | 세션 활성 | 연결 종료 | `close()` 호출 및 변수 `null` 확인. |

---

## 3. Adapter Layer 테스트 명세 (Connection Lifecycle)
> **대상:** `KisWebSocketAdapterTest`
> **목표:** 연결 생명주기 및 외부 클라이언트 제어 검증

### 3.1. 연결 및 재접속 (Connect & Auto-Reconnect)

| ID | 테스트 메서드 / 시나리오 | Given | When | Then |
|:---:|:---|:---|:---|:---|
| **ADP-001** | `givenMockSuccess_...`<br>👉 **연결 성공 시 재접속을 예약하지 않는다.** | 연결 성공 가정 | 연결 요청 | 1. 핸들러 키 주입.<br>2. 스케줄러 호출 X (`never`). |
| **ADP-002** | `givenMockFail_...`<br>👉 **연결 실패 시 3초 뒤 재접속을 예약한다.** | 연결 실패 가정 | 연결 요청 | 1. 에러 로그.<br>2. 스케줄러 작업 예약 O (`verify`). |

### 3.2. 위임 및 종료 (Delegation & Cleanup)

| ID | 테스트 메서드 / 시나리오 | Given | When | Then |
|:---:|:---|:---|:---|:---|
| **ADP-003** | `whenSubscribe_...`<br>👉 **구독 요청을 핸들러에게 위임한다.** | - | 구독 요청 | `handler.subscribe` 호출 확인. |
| **ADP-004** | `givenScheduledTask_...`<br>👉 **종료 시 재접속 예약을 취소한다.** | 예약된 태스크 존재 | 연결 종료 | 1. 태스크 `cancel` 호출.<br>2. `handler.close` 호출. |

---

## 4. 테스트 결과 요약

### 4.1. 수행 결과
| 구분                       | 전체 케이스 |  Pass  | Fail | 비고 |
|:-------------------------|:------:|:------:| :---: | :--- |
| **Subscription** |   2    |   2    | 0 | 연결 전/후 구독 요청 타이밍 검증 완료 |
| **Parsing Logic** |   4    |   4    | 0 | 정상/비정상/멀티 패킷 파싱 완벽 대응 |
| **Exception & Cleanup** |   4    |   4    | 0 | 장애 상황에서의 복구 및 자원 누수 방지 확인 |
| **합계** | **10** | **10** | **0** | **Pass** ✅ |