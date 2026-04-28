# [TCS] KIS 실시간 웹소켓 핸들러(WebSocket Handler) 테스트 명세서

| 문서 ID | **TCS-KIS-002**                              |
| :--- |:---------------------------------------------|
| **문서 버전** | 1.2                                          |
| **프로젝트** | AssetMind                                    |
| **작성자** | 이재석                                          |
| **작성일** | 2026년 02월 05일                                |
| **관련 모듈** | `KisWebSocketHandler`, `KisWebsocketAdapter` |

## 1. 개요 (Overview)

본 문서는 한국투자증권(KIS) 실시간 주식 데이터를 처리하는 **웹소켓 모듈 전체**에 대한 단위 테스트(Unit Test) 명세이다.
연결을 관리하는 `어댑터(Adapter)`와 데이터를 처리하는 `핸들러(Handler)`의 기능을 다루며, 비동기 환경에서의 안정성 확보를 목표로 한다.

### 1.1. 테스트 대상 및 도구
| 구분 | 대상 클래스 | 주요 검증 항목 | Mocking 도구                                                   |
|:---:|:---|:---|:-------------------------------------------------------------|
| **Connection** | `KisWebSocketAdapter` | 연결/재접속, 구독 위임, 자원 해제 | `ReflectionTestUtils`, `CompletableFuture`                   |
| **Logic** | `KisWebSocketHandler` | 구독 버퍼링, 데이터 파싱, 포맷 방어("H"), 예외 처리 | `WebSocketSession`, `ObjectMapper`, `CapturedOutput(로그 확인용)` |

---

## 2.  KisWebSocketHandler 테스트 명세
> **대상 클래스:** `KisWebSocketHandlerTest`
> **검증 목표:** 데이터의 흐름 제어 및 파싱 정확성 검증, 스레드 생존성 및 로깅 검증

### 2.1. 구독 요청 및 버퍼링 (Subscription & Buffering)

| ID          | 테스트 메서드 / 시나리오                                                                                                                        | Given (사전 조건)                                                       | When (수행 행동)                                 | Then (검증 결과)                                                                                       |
|:------------|:--------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------|:---------------------------------------------|:---------------------------------------------------------------------------------------------------|
| **WSH-001** | `givenNoSession_whenSubscribeNewStock_`<br>`thenSendAfterConnection`<br>👉 **세션 연결 전 구독 요청은 대기열에 저장되었다가, 연결 후 한꺼번에 전송되어야 한다.** | **세션 없음 (Null)**<br>연결되지 않은 초기 상태                                | 1. **구독 요청** (`subscribe`)<br>2. **연결 성공 이벤트 발생** (`afterConnectionEstablished`) | 1. 구독 요청 시점엔 전송 메서드가 호출되지 않음 (`never`).<br>2. 대기열(`pendingList`)에 요청이 저장됨.<br>3. 연결 직후 메시지가 전송됨 (`verify`). |
| **WSH-002** | `givenSession_whenSubscribeNewStock_`<br>`thenSendSubscribeRequest`<br>👉 **이미 연결된 상태에서는 대기열 없이 바로 전송해야 한다.** | **세션 활성 (Open)**<br>`afterConnectionEstablished`가 이미 호출된 상태       | **구독 요청** (`subscribe`)                      | 1. 대기열을 거치지 않고 즉시 `sendMessage`가 호출된다 (`times(1)`).                                         |

### 2.2. 실시간 데이터 처리 (Data Parsing)

| ID          | 테스트 메서드 / 시나리오                                                                                               | Given (사전 조건)                                      | When (수행 행동)                                 | Then (검증 결과)         |
|:------------|:-------------------------------------------------------------------------------------------------------------|:---------------------------------------------------|:---------------------------------------------|:---------------------|
| **WSH-003** | `givenRealTimePayload_whenHandleMessage_`<br>`thenInvokeParser`<br>👉 **실시간 데이터 수신 시 파서를 호출하고 데이터를 처리해야 한다** | **정상 텍스트 패킷**<br>`0\|ID\| 001\|데이터... (파이프 구분자 포함) | **메시지 수신** (`handleMessage`)                | 1. 파서가 한번 호출 되었는지 검증 |


### 2.3. 예외 처리 및 스레드 생존 (Exception & Stability)

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
|:---:|:---|:---|:---|:---|
| **WSH-004** | `givenJsonError_whenSubscribeNewStock_`<br>`thenNotExitSystem`<br>👉 **구독 페이로드(JSON) 변환 실패 시 시스템은 죽지 않아야 한다.** | Mapper 에러 설정 (Mock) | 구독 요청 | 예외 발생 없이(`catch`) 구독 전송만 건너뜀 |
| **WSH-005** | `givenTransportError_whenSubscribeNewStock_`<br>`thenNotExitSystem`<br>👉 **연속 구독 요청 중 일부 전송 실패 시, 다음 종목은 계속 처리한다.** | 첫 번째 전송 IO 에러 설정 | 2개 종목 동시 구독 요청 | 반복문 중단 없이 2번 모두 전송 시도함 (`times(2)`) |
| **WSH-006** | `givenMultipleData_whenOneFails_`<br>`thenContinuePublishing`<br>👉 **[부분 실패] 다건 데이터 중 1건 매핑 실패 시, 나머지는 정상 발행된다.** | 2건 데이터 파싱 중 1건 매핑 시 예외 발생 강제 | 메시지 수신 | 1. 반복문 중단 없이 두 번째 데이터 이벤트 정상 발행<br>2. 실패 데이터에 대한 ERROR 로그 출력 (`CapturedOutput` 확인) |
| **WSH-007** | `givenFatalError_whenHandleMessage_`<br>`thenCatchAndLog`<br>👉 **수신 메시지 파싱 중 치명적 에러 발생 시 세션 유지 및 로깅한다.** | 파서에서 `NullPointerException` 강제 발생 | 메시지 수신 | 1. 웹소켓 스레드 종료 안 됨 (`assertDoesNotThrow`)<br>2. 원인 추적을 위한 에러 로그 기록 확인 |

### 2.4. 자원 정리 (Cleanup)

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
|:---:|:---|:---|:---|:---|
| **WSH-008** | `whenCloseConnection_thenCleanUpSessionAndFiled`<br>👉 **종료 시 세션을 닫고 내부 상태 변수를 초기화한다.** | 세션 활성 및 구독 목록 존재 | 연결 종료 | `close()` 호출 및 변수 초기화 (`null`, `clear`) |
| **WSH-009** | `givenCloseError_whenCloseConnection_`<br>`thenCleanUpSessionAndFiled`<br>👉 **종료 중 에러가 발생해도 자원 정리는 수행되어야 한다.** | `close()` 호출 시 예외 강제 | 연결 종료 | 예외 무시, `finally` 블록에서 변수 초기화 보장됨 |

---

## 3. Adapter Layer 테스트 명세 (Connection Lifecycle)
> **대상:** `KisWebSocketAdapterTest`
> **목표:** 연결 생명주기 및 외부 클라이언트 제어 검증
### 3.1. 연결 및 재접속 (Connect & Auto-Reconnect)

| ID | 테스트 메서드 / 시나리오 | Given | When | Then |
|:---:|:---|:---|:---|:---|
| **ADP-001** | `givenMockSuccess_whenConnect_thenLogSuccessAndNoReconnect`<br>👉 **연결 성공 시 재접속을 예약하지 않는다.** | 연결 성공 가정 | 연결 요청 | 1. 핸들러 키 주입.<br>2. 스케줄러 호출 X (`never`). |
| **ADP-002** | `givenMockFail_whenConnect_thenScheduleReconnect`<br>👉 **연결 실패 시 3초 뒤 재접속을 예약한다.** | 연결 실패 가정 | 연결 요청 | 1. 에러 로그.<br>2. 스케줄러 작업 예약 O (`verify`). |

### 3.2. 위임 및 종료 (Delegation & Cleanup)

| ID | 테스트 메서드 / 시나리오 | Given | When | Then |
|:---:|:---|:---|:---|:---|
| **ADP-003** | `whenSubscribe_thenDelegateToHandler`<br>👉 **구독 요청을 핸들러에게 위임한다.** | - | 구독 요청 | `handler.subscribe` 호출 확인. |
| **ADP-004** | `givenScheduledTask_whenDisconnect_thenCancelTaskAndCloseHandler`<br>👉 **종료 시 재접속 예약을 취소한다.** | 예약된 태스크 존재 | 연결 종료 | 1. 태스크 `cancel` 호출.<br>2. `handler.close` 호출. |

---

## 4. 테스트 결과 요약

### 4.1. 수행 결과
| 구분 | 전체 케이스 | Pass | Fail | 비고                         |
|:---|:---:|:---:|:---:|:---------------------------|
| **Subscription** | 2 | 2 | 0 | 연결 전/후 대기열 처리 완벽 검증        |
| **Parsing Logic** | 1 | 1 | 0 | 파서 위임 및 정상 흐름 검증           |
| **Exception & Stability** | 4 | 4 | 0 | 부분 실패 복구, 스레드 생존, 로그 캡처 검증 |
| **Cleanup** | 2 | 2 | 0 | 메모리 누수 방지 (Finally 검증)     |
| **Adapter 연동** | 4 | 4 | 0 | 연결, 재접속 스케줄러 검증            |
| **합계** | **13** | **13** | **0** | **All Pass ✅**             |