# [TCS] 보안 필터 단위 테스트 명세서

| 문서 ID | **TCS-SEC-001** |
| :--- |:-----------------------------------------|
| **문서 버전** | 1.0                                      |
| **프로젝트** | AssetMind                                |
| **작성자** | 이재석                                      |
| **작성일** | 2026년 01월 30일                            |
| **대상 모듈** | `JwtAuthenticationFilter` (Global Security) |

## 1. 개요 (Overview)

본 문서는 HTTP 요청의 헤더(`Authorization`)를 가로채어 JWT 토큰을 검증하고, 인증 정보를 `SecurityContext`에 적재하는 **인증 필터(Filter)**의 동작을 검증하기 위한 단위 테스트 명세이다.
`SecurityContextHolder`의 상태 변화와 `FilterChain`의 흐름 제어를 중점적으로 확인한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, Mockito
- **Test Class:** `JwtAuthenticationFilterTest`
- **Mock Objects:**
    - `AuthTokenProvider`: 토큰 유효성 검증 및 파싱 모의
    - `HttpServletRequest` / `Response`: HTTP 요청/응답 모의
    - `FilterChain`: 다음 필터 실행 여부 검증
    - `SecurityContext`: 인증 객체(`Authentication`) 저장 여부 확인

---

## 2. 테스트 케이스 상세 (Test Cases)

### 2.1. 인증 성공 처리 (Authentication Success)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-FIL-001** | **유효한 토큰 요청**<br>(정상 로그인 상태) | 1. 헤더: `Bearer {valid_token}`<br>2. Provider: 검증 통과(Void) 및 ID/Role 반환 | `doFilterInternal` 호출 | 1. `SecurityContext`에 **Authentication 객체**가 존재해야 한다.<br>2. Principal(ID)과 Authorities(Role)가 일치해야 한다.<br>3. `filterChain.doFilter()`가 호출되어야 한다. |

### 2.2. 인증 건너뛰기 (Pass Through)
> **Note:** 필터는 토큰이 없거나 형식이 맞지 않으면 예외를 던지지 않고, **인증 객체 없이** 다음 단계로 넘겨야 한다. (이후 `SecurityConfig`가 접근 허용 여부를 결정함)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-FIL-002** | **토큰 없음**<br>(로그인/회원가입 접근) | 1. 헤더: `Authorization` 값이 `null` | `doFilterInternal` 호출 | 1. `SecurityContext`의 Authentication은 `null`이어야 한다.<br>2. `Provider`는 호출되지 않아야 한다.<br>3. `filterChain.doFilter()`가 호출되어야 한다. |
| **SEC-FIL-003** | **잘못된 헤더 형식**<br>(Basic Auth 등) | 1. 헤더: `Basic {token}`<br>(Bearer 아님) | `doFilterInternal` 호출 | 1. `SecurityContext`의 Authentication은 `null`이어야 한다.<br>2. `filterChain.doFilter()`가 호출되어야 한다. |

### 2.3. 예외 처리 (Exception Handling)
> **Note:** 토큰 검증 중 예외가 발생하면, 필터는 멈추지 않고 **Context를 비운 채** 다음 필터로 넘겨야 한다. (결국 `EntryPoint`에서 401 처리됨)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-FIL-004** | **유효하지 않은 토큰**<br>(만료/위조/손상) | 1. 헤더: `Bearer {invalid_token}`<br>2. Provider: `validateToken` 호출 시 **예외 발생** | `doFilterInternal` 호출 | 1. `SecurityContext`의 Authentication은 `null`이어야 한다. (또는 `clearContext` 호출됨)<br>2. `filterChain.doFilter()`가 호출되어야 한다.<br>3. 서버 내부 에러(500)가 발생하지 않아야 한다. |

---

## 3. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고 |
| :--- | :---: | :---: | :---: | :--- |
| **Security Filter** | 4 | 4 | 0 | 인증 흐름 및 예외 격리 검증 완료 |
| **합계** | **4** | **4** | **0** | **Pass** ✅ |