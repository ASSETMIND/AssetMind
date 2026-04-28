# [TCS] Stock 실시간 메시징(WebSocket/STOMP) 테스트 명세서

| 문서 ID | **TCS-WS-001** |
| :--- |:----------------------------------------|
| **문서 버전** | 1.0                                     |
| **프로젝트** | AssetMind                               |
| **작성자** | 이재석                                     |
| **작성일** | 2026년 04월 06일                           |
| **대상 모듈** | `server-stock/presentation` (WebSocket) |

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템에서 발생하는 실시간 이벤트(시계열 갱신, 랭킹 변동, 급등락 알림)를 클라이언트에게 브로드캐스트(Push)하는 **WebSocket/STOMP Presentation 계층**의 단위 테스트 명세이다.
`Mockito`와 `OutputCaptureExtension`을 활용하여, 메시지 브로커(`SimpMessagingTemplate`)로의 토픽(Topic) 라우팅 정확성 및 전송 중 장애 발생 시 프로세스 중단 방지(Fault Tolerance) 로직을 중점적으로 검증한다.

### 1.1. 대상 컴포넌트 및 검증 목표
- **`StockWebSocketEventHandler`**: 애플리케이션 이벤트(History, Ranking)를 구독하여 STOMP 메시지로 변환 및 전송
- **`StompAlertMessagingAdapter`**: 급등락 알림 포트(Port)의 구현체로, 외부 브로커를 통한 알림 브로드캐스트
- **Verification Focus:**
    - **Topic Routing:** 각 데이터 성격에 맞는 엔드포인트(`/topic/stocks/...`, `/topic/ranking`, `/topic/surge-alerts`)로 정확히 전송되는지 검증
    - **Exception Swallowing (내결함성):** 메시지 브로커 전송 중 예외(`MessagingException`)가 발생하더라도 메인 비즈니스 스레드가 죽지 않고 안전하게 에러 로그만 남기는지 검증
    - **Payload Mapping:** `ArgumentCaptor`를 활용하여 전송 전 응답 DTO로의 매핑 무결성 검증

---

## 2. 실시간 시계열 및 랭킹 이벤트 핸들러 (`StockWebSocketEventHandler`)

### 2.1. 시계열 데이터(History) 브로드캐스트
| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WS-EVT-001** | **[성공] 토픽 전송** | `StockHistorySavedEvent` 객체 생성 | `handleSavedHistory()` | `SimpMessagingTemplate`을 통해 **`/topic/stocks/{stockCode}`** 토픽으로 데이터가 1회 전송됨을 확인 |
| **WS-EVT-002** | **[실패] 전송 장애 방어** | STOMP 전송 시 `MessagingException`이 발생하도록 모킹 | `handleSavedHistory()` | 1. 예외가 밖으로 던져지지 않음 (`doesNotThrowAnyException`)<br>2. 콘솔에 `[Stock WebSocket Event Handler] 특정 종목 시계열 데이터 전송 에러` 로그가 정상 기록됨 |

### 2.2. 랭킹 데이터(Ranking) 브로드캐스트
| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WS-EVT-003** | **[성공] 토픽 전송** | `StockRankingUpdatedEvent` 객체 생성 | `handleUpdatedRanking()` | `SimpMessagingTemplate`을 통해 **`/topic/ranking`** 토픽으로 데이터가 1회 전송됨을 확인 |
| **WS-EVT-004** | **[실패] 전송 장애 방어** | STOMP 전송 시 `MessagingException`이 발생하도록 모킹 | `handleUpdatedRanking()` | 1. 예외가 밖으로 던져지지 않음 (`doesNotThrowAnyException`)<br>2. 콘솔에 `[Stock WebSocket Event Handler] 랭킹 데이터 전송 에러` 로그가 정상 기록됨 |

---

## 3. 급등락 알림 메시징 어댑터 (`StompAlertMessagingAdapter`)

### 3.1. 알림 브로드캐스트
| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WS-ALT-001** | **[성공] 알림 DTO 매핑 및 토픽 전송** | 실시간 체결 이벤트 및 트렌드("급등") 입력, 메타데이터 모킹 | `send(event, trend)` | 1. **`/topic/surge-alerts`** 토픽으로 전송됨<br>2. `ArgumentCaptor` 검증: DTO 내부에 `stockCode`, `stockName`, `rate(급등)`, `currentPrice`, `changeRate`가 완벽하게 매핑되어 전송됨을 확인 |

---

## 4. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고 (특이사항) |
| :--- | :---: | :---: | :---: | :--- |
| **WebSocket EventHandler** | 4 | 4 | 0 | STOMP 라우팅 및 예외 삼키기(Fault Tolerance) 검증 완료 |
| **AlertMessaging Adapter** | 1 | 1 | 0 | `ArgumentCaptor` 기반 DTO 매핑 100% 검증 완료 |
| **합계** | **5** | **5** | **0** | **Pass** ✅ |