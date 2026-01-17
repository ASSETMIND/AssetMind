# KISAuthStrategy Test Specification

## 1. 개요

- **대상 모듈:** `KISAuthStrategy`
- **테스트 목적:** 토큰 수명 주기 관리(발급, 캐싱, 갱신) 및 예외 상황에 대한 견고성 검증.
- **핵심 전략:** In-Memory 캐싱 로직과 Safety Buffer(10분) 경계값 검증에 집중.

## 2. 테스트 환경 및 전략

- **Testing Framework:** Pytest, Pytest-Asyncio
- **Mocking:** \* `IHttpClient`: 실제 네트워크 요청 차단.
  - `datetime`: `freezegun` 또는 `unittest.mock`을 사용하여 시간 흐름 제어.
- **Date Format:** "2024-01-01 12:00:00" (KIS API Standard)

## 3. 테스트 케이스 명세

|  Test ID   | Category  | Given (Preconditions)                                                 | When (Action)                                | Then (Expected Outcome)                                                            | Input Data (Mock/Args)                                                                       | Priority |
| :--------: | :-------: | :-------------------------------------------------------------------- | :------------------------------------------- | :--------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------- | :------: |
| **TC-001** |   Unit    | 캐시가 비어있는 초기 상태 (`_access_token=None`)                      | `get_token(http_client)` 호출                | 1. API 호출 발생<br>2. 토큰 및 만료시간 업데이트<br>3. "Bearer {token}" 반환       | HTTP Res: `{"access_token": "new_tok", "access_token_token_expired": "2024-01-01 12:00:00"}` |    P0    |
| **TC-002** |   Unit    | 유효한 토큰 존재 (만료까지 15분 남음, Buffer 10분 초과)               | `get_token(http_client)` 호출                | 1. API 호출 **미발생**<br>2. 기존 토큰 반환                                        | Access Token: "existing_tok"<br>Expire: Now + 15min                                          |    P0    |
| **TC-003** |   Unit    | 토큰 존재하나 만료 임박 (만료까지 5분 남음, Buffer 10분 미만)         | `get_token(http_client)` 호출                | 1. API 호출 발생 (갱신)<br>2. 내부 토큰 상태 업데이트<br>3. 새 토큰 반환           | HTTP Res: `{"access_token": "refreshed_tok", ...}`<br>Expire: Now + 5min                     |    P0    |
| **TC-004** |   Unit    | `AppConfig`의 필수값(AppKey, Secret, BaseURL) 중 하나가 누락됨        | `KISAuthStrategy(config)` 인스턴스 생성 시도 | `ValueError` 발생                                                                  | Config: `{key: "", secret: "s", url: "u"}`                                                   |    P1    |
| **TC-005** |   Unit    | 토큰 만료 시간 정확히 **10분 1초** 남음 (경계값 Safe)                 | `get_token(http_client)` 호출                | 1. API 호출 **미발생** (Refresh 안함)                                              | Expire: Now + 10min + 1s                                                                     |    P1    |
| **TC-006** |   Unit    | 토큰 만료 시간 정확히 **9분 59초** 남음 (경계값 Unsafe)               | `get_token(http_client)` 호출                | 1. API 호출 발생 (Refresh 수행)                                                    | Expire: Now + 10min - 1s                                                                     |    P1    |
| **TC-007** | Exception | API 응답에 `access_token` 필드 누락                                   | `get_token(http_client)` 호출                | `AuthError` 발생 ("Invalid token response")                                        | HTTP Res: `{"msg_code": "error", "msg": "fail"}`                                             |    P1    |
| **TC-008** | Exception | API 응답의 만료시간 포맷이 비표준임 (Malformed Date)                  | `get_token(http_client)` 호출                | 1. 에러 없이 토큰 발급 성공<br>2. 만료시간이 **현재+12시간**으로 설정됨 (Fallback) | HTTP Res: `{"access_token": "tok", "access_token_token_expired": "invalid-date"}`            |    P2    |
| **TC-009** | Exception | API 응답에 만료시간 필드 자체가 없음                                  | `get_token(http_client)` 호출                | 1. 에러 없이 토큰 발급 성공<br>2. 만료시간이 **현재+12시간**으로 설정됨 (Fallback) | HTTP Res: `{"access_token": "tok"}` (No expiration key)                                      |    P2    |
| **TC-010** | Exception | 네트워크 연결 실패 (`NetworkError` 발생)                              | `get_token(http_client)` 호출                | `AuthError` 발생 (원인 예외 포함)                                                  | HTTP Client raises `NetworkError("Connection refused")`                                      |    P1    |
| **TC-011** | Exception | 알 수 없는 내부 로직 오류로 토큰 갱신 후에도 `_access_token`이 None임 | `get_token(http_client)` 호출                | `AuthError` 발생 ("Failed to retrieve access token")                               | (Mocking을 통해 `_issue_token`이 상태를 안 바꾸게 조작)                                      |    P2    |
| **TC-012** |   Unit    | 토큰이 완전히 만료됨 (과거 시간)                                      | `get_token(http_client)` 호출                | 1. API 호출 발생 (Refresh 수행)                                                    | Expire: Now - 1min                                                                           |    P0    |
