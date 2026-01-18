# [TCS] 시장 접근 권한 관리(Market Access) 모듈 테스트 명세서

| 문서 ID | **TCS-KIS-001**                   |
| :--- |:----------------------------------|
| **문서 버전** | 1.0                               |
| **프로젝트** | AssetMind                         |
| **작성자** | 이재석                               |
| **작성일** | 2026년 01월 07일                     |
| **관련 모듈** | `apps/server-stock/market-access` |

## 1. 개요 (Overview)

본 문서는 한국투자증권(KIS) Open API 연동 및 토큰 생명주기 관리를 담당하는 `market-access` 모듈의 단위 테스트(Unit Test) 명세이다.
테스트 코드는 **BDD(Behavior Driven Development)** 스타일의 `Given-When-Then` 패턴을 따르며, 외부 네트워크 의존성을 완벽히 격리(Mocking)한 상태에서 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, Spring Boot Test, AssertJ
- **Mocking Tools:**
    - **Service:** Mockito (`MarketAccessServiceTest`)
    - **Adapter:** OkHttp MockWebServer (`KisAuthAdapterTest`)

---

## 2. Application Layer 테스트 명세
> **대상 클래스:** `MarketAccessServiceTest`
> **검증 목표:** 토큰 캐싱(Caching), 자동 갱신(Scheduling), 예외 복구(Fail-safe)

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-001** | `givenStartApplication_whenInit_thenCachedToken`<br>👉 **애플리케이션 Init 시에 토큰을 발급받아 캐싱한다.** | **Mock Provider 설정**<br>(`fetchToken` 호출 시 유효한 토큰 반환) | **앱 구동 (`init`)** | 1. Provider `fetchToken()`이 정확히 **1회** 호출된다 (`verify`).<br>2. 반환된 토큰이 서비스 내부에 캐싱된다 (`assertThat`). |
| **SVC-002** | `givenAlreadyHaveCachedToken_whenGetAccessToken_`<br>`thenReturnCachedToken`<br>👉 **캐싱된 토큰이 있으면 Provider를 호출하지 않고 캐싱되어 있는 값을 반환한다.** | **캐시 존재 (Hit)**<br>(`init` 호출로 이미 토큰이 캐싱된 상태) | **`getAccessToken()`**<br>(다회 호출) | 1. Provider가 **추가로 호출되지 않는다** (`times(1)`).<br>2. 메모리에 저장된 **기존 캐시 값**을 반환한다. |
| **SVC-003** | `givenNotHaveCachedToken_whenGetAccessToken_`<br>`thenReturnNewToken`<br>👉 **캐싱된 토큰이 없으면 Provider를 호출하여 새 토큰을 캐싱하고 반환한다.** | **캐시 없음 (Miss)**<br>(`init` 미수행 또는 캐시 만료 상태) | **`getAccessToken()`** | 1. Provider를 호출하여 **새 토큰**을 받아온다.<br>2. 받아온 토큰을 캐싱하고 반환한다. |
| **SVC-004** | `givenValidOldToken_whenScheduleTokenRefresh_`<br>`thenUpdateToken`<br>👉 **스케줄러에 의해 토큰 갱신 시 토큰 값이 업데이트된다.** | **기존 토큰(Old) 존재**<br>(Provider가 첫 번째는 Old, 두 번째는 New 반환 설정) | **`scheduleTokenRefresh()`**<br>(스케줄러 강제 실행) | 1. Provider가 재호출된다 (`times(2)`).<br>2. 캐시 값이 **새 토큰(New)**으로 업데이트된다. |
| **SVC-005** | `givenValidOldToken_whenRefreshAccessTokenFail_`<br>`thenKeepValidOldToken`<br>👉 **토큰 갱신 중 에러가 발생하면 기존 토큰을 유지한다.** | **갱신 실패 가정**<br>(Provider 호출 시 `MarketAccessFailedException` 발생 설정) | **`scheduleTokenRefresh()`** | 1. 예외 발생 시 `catch` 블록에서 처리된다.<br>2. 캐시 변수가 오염되지 않고 **기존 토큰(Old)을 유지**한다. |

---

## 3. Infrastructure Layer 테스트 명세
> **대상 클래스:** `KisAuthAdapterTest`
> **검증 목표:** KIS API 요청 규격 준수, 응답 파싱, 네트워크 엣지 케이스 처리

| ID | 테스트 메서드 / 시나리오 | Given (Mock Server 설정) | When (API 요청) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **ADP-001** | `whenFetchTokenSuccess_thenReturnCorrectAccessToken`<br>👉 **KIS 접근토큰발급 API 호출 성공 시 올바른 AccessToken을 반환해야한다.** | **성공 응답 (200 OK)**<br>- Body: `access_token`, `expires_in` 포함<br>- Header: `application/json` | **`fetchToken()`** | **[Response]** `ApiAccessToken` 파싱 성공<br>**[Request]** `takeRequest()` 검증:<br>1. Method: `POST`, Path: `/oauth2/tokenP`<br>2. Body: `grant_type`, `appkey`, `appsecret` 포함 확인 |
| **ADP-002** | `whenFetchTokenFail400_thenThrowMarketAccessFailedException`<br>👉 **API 응답이 4xx 에러일 경우 MarketAccessFailedException 예외를 던져야 한다.** | **클라이언트 에러 (400)**<br>- Body: `{"error_code": "E1234"}` | **`fetchToken()`** | 1. `MarketAccessFailedException` 발생.<br>2. 에러 메시지에 **"KIS API Error"** 포함. |
| **ADP-003** | `whenFetchTokenFail500_thenThrowMarketAccessFailedException`<br>👉 **API 응답이 5xx 에러일 경우 MarketAccessFailedException 예외를 던져야 한다.** | **서버 에러 (500)**<br>- Body: `{"error_description": "Server Error"}` | **`fetchToken()`** | 1. `MarketAccessFailedException` 발생.<br>2. 에러 메시지에 **"KIS API Error"** 포함. |
| **ADP-004** | `givenShutdownKIS_whenFetchToken_thenThrowMarketAccessFailedException`<br>👉 **KIS 서버가 꺼져있어서 연결 거부가 발생하면 예외를 던져야한다.** | **서버 다운 (Shutdown)**<br>- `mockWebServer.shutdown()` 호출 | **`fetchToken()`** | 1. `MarketAccessFailedException` 발생.<br>2. 예외 메시지에 **"KIS 서버 연결 불가"** 포함 (Connection Refused). |
| **ADP-005** | `givenNetworkProblem_whenFetchToken_thenThrowMarketAccessFailedException`<br>👉 **응답 도중 네트워크가 끊기면 예외를 던져야한다.** | **네트워크 끊김 (Cut)**<br>- `SocketPolicy.DISCONNECT_AT_START` 설정 | **`fetchToken()`** | 1. `MarketAccessFailedException` 발생.<br>2. 예외 메시지에 **"KIS 서버 연결 불가"** 포함. |

---

## 4. 테스트 결과 요약

### 4.1. 수행 결과
| 구분                       | 전체 케이스 | Pass | Fail | 비고 |
|:-------------------------| :---: | :---: | :---: | :--- |
| **Application Layer**    | 5 | 5 | 0 | 모든 정책 로직(캐싱, 갱신, 방어) 정상 동작 |
| **Infrastructure Layer** | 5 | 5 | 0 | 요청/응답 정합성 및 장애 대응 로직 검증 완료 |
| **합계**                   | **10** | **10** | **0** | **Pass** ✅ |