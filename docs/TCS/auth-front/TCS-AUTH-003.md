# [TCS] 소셜 로그인 비즈니스 로직(Unit) 테스트 명세서

| 문서 ID       | **TCS-AUTH-003**                    |
| :------------ | :---------------------------------- |
| **문서 버전** | 1.0                                 |
| **프로젝트**  | AssetMind                           |
| **작성자**    | 양윤기                              |
| **작성일**    | 2026년 01월 28일                    |
| **관련 모듈** | `hooks/auth/use-social-login-logic` |

## 1. 개요 (Overview)

본 문서는 AssetMind 소셜 로그인 프로세스(OAuth 2.0 Flow)의 핵심 로직을 담당하는 커스텀 훅 `useSocialLoginLogic`의 동작을 검증하기 위한 단위 테스트(Unit Test) 명세이다.
사용자 리다이렉트(Redirect) 처리, 인가 코드(Authorization Code) 파싱, 백엔드 API 연동, 그리고 결과에 따른 상태 처리(성공/실패)가 의도대로 동작하는지 확인한다.

### 1.1. 테스트 환경

- **Framework:** Jest, `@testing-library/react` (React Hooks Testing Library)
- **Mocking Strategy:**
  - `window.location` (Browser Navigation) 격리 및 제어
  - `useMutation` (React Query) 격리 및 콜백 수동 트리거
  - `react-router-dom` (Navigation, SearchParams) 격리
  - `libs/constants/auth` (Environment Variables) 격리
- **Key Verification:**
  - **Redirect Logic:** 각 Provider(Kakao, Google)별 올바른 인증 URL 생성 및 이동 확인
  - **Callback Handling:** URL 파라미터(`code`) 파싱 및 비정상 접근 차단 확인
  - **API Response:** 로그인 성공 시 토큰 처리 및 실패 시 에러 피드백 검증

---

## 2. 상세 테스트 명세 (`useSocialLoginLogic`)

> **대상 모듈:** `src/hooks/auth/use-social-login-logic.ts`
> **검증 목표:** OAuth 인증 흐름의 각 단계(요청 -> 응답 -> 처리)별 로직 무결성 검증

### 2.1. 소셜 로그인 리다이렉트 (Social Login Redirect)

| ID                  | 테스트 메서드 / 시나리오                                                                                      | Given (사전 조건)                                                                     | When (수행 행동)                       | Then (검증 결과)                                                                                         |
| :------------------ | :------------------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------ | :------------------------------------- | :------------------------------------------------------------------------------------------------------- |
| **AUTH-SOCIAL-001** | `handleSocialLogin_Kakao`<br>👉 **Kakao provider 전달 시 Kakao 인증 URL로 이동하고 상태를 변경해야 한다.**    | **환경 설정**<br>`window.location` 모킹 완료<br>**입력 설정**<br>Provider: `'kakao'`  | **`handleSocialLogin('kakao')`** 실행  | 1. `state.isRedirecting`이 `true`로 변경된다.<br>2. `window.location.href`가 Kakao 인증 URL로 변경된다.  |
| **AUTH-SOCIAL-002** | `handleSocialLogin_Google`<br>👉 **Google provider 전달 시 Google 인증 URL로 이동하고 상태를 변경해야 한다.** | **환경 설정**<br>`window.location` 모킹 완료<br>**입력 설정**<br>Provider: `'google'` | **`handleSocialLogin('google')`** 실행 | 1. `state.isRedirecting`이 `true`로 변경된다.<br>2. `window.location.href`가 Google 인증 URL로 변경된다. |

### 2.2. 소셜 로그인 콜백 처리 (Callback Handling)

| ID                  | 테스트 메서드 / 시나리오                                                                            | Given (사전 조건)                                      | When (수행 행동)                  | Then (검증 결과)                                                                                                                     |
| :------------------ | :-------------------------------------------------------------------------------------------------- | :----------------------------------------------------- | :-------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------- |
| **AUTH-SOCIAL-003** | `handleSocialCallback_NoCode`<br>👉 **URL에 code가 없으면 경고창을 띄우고 메인으로 이동해야 한다.** | **환경 설정**<br>URL 파라미터(Query String)가 비어있음 | **`handleSocialCallback()`** 실행 | 1. `window.alert`으로 "잘못된 접근입니다." 경고가 출력된다.<br>2. 메인 페이지(`/`)로 이동한다.<br>3. API Mutation은 실행되지 않는다. |
| **AUTH-SOCIAL-004** | `handleSocialCallback_WithCode`<br>👉 **URL에 code가 있으면 mutation을 실행해야 한다.**             | **환경 설정**<br>URL 파라미터에 유효한 `code` 존재     | **`handleSocialCallback()`** 실행 | 1. `processLogin` (Mutation) 함수가 실행된다.<br>2. 이때 Provider와 Code가 올바르게 인자로 전달된다.                                 |

### 2.3. 로그인 API 응답 처리 (API Response Handling)

| ID                  | 테스트 메서드 / 시나리오                                                                                        | Given (사전 조건)                                                 | When (수행 행동)                | Then (검증 결과)                                                                                                                                   |
| :------------------ | :-------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------- | :------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------- |
| **AUTH-SOCIAL-005** | `onSuccess_Full`<br>👉 **로그인 성공(onSuccess) 시 토큰 저장, 스토어 업데이트, 페이지 이동이 수행되어야 한다.** | **Mock 설정**<br>API 성공 응답에 `accessToken`과 `user` 정보 포함 | **Mutation `onSuccess`** 트리거 | 1. `setAccessToken`으로 토큰이 저장된다.<br>2. `useAuthStore.login` 액션이 실행된다.<br>3. 메인 페이지(`/`)로 `replace` 이동한다.                  |
| **AUTH-SOCIAL-006** | `onSuccess_NoToken`<br>👉 **로그인 성공 시 accessToken이 응답에 없으면 토큰 저장을 건너뛰어야 한다.**           | **Mock 설정**<br>API 성공 응답에 `accessToken` 누락 (예외 케이스) | **Mutation `onSuccess`** 트리거 | 1. `setAccessToken` 함수가 호출되지 않는다.<br>2. 나머지 로그인 처리(스토어 업데이트, 이동)는 정상 수행된다.                                       |
| **AUTH-SOCIAL-007** | `onError`<br>👉 **로그인 실패(onError) 시 에러 로그 출력, 경고창, 페이지 이동이 수행되어야 한다.**              | **Mock 설정**<br>API 에러 객체 반환                               | **Mutation `onError`** 트리거   | 1. `console.error`로 에러 내용이 출력된다.<br>2. `window.alert`으로 실패 메시지가 출력된다.<br>3. 메인 페이지(`/`)로 이동하여 프로세스를 종료한다. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과

| 구분               | 전체 케이스 | Pass  | Fail  |    상태     | 비고                              |
| :----------------- | :---------: | :---: | :---: | :---------: | :-------------------------------- |
| **Redirect Logic** |      2      |   2   |   0   | **Pass** ✅ | Provider별 분기 확인              |
| **Callback Logic** |      2      |   2   |   0   | **Pass** ✅ | Code 유무에 따른 방어 로직 확인   |
| **API Response**   |      3      |   3   |   0   | **Pass** ✅ | Mutation 옵션(Callback) 검증 완료 |
| **합계**           |    **7**    | **7** | **0** | **Pass** ✅ |                                   |

### 3.2. 코드 커버리지 (Code Coverage)

| File                          |  % Stmts   | % Branch |  % Funcs   |  % Lines   | Uncovered Lines |
| :---------------------------- | :--------: | :------: | :--------: | :--------: | :-------------: |
| **use-social-login-logic.ts** | **96.87%** | **100%** | **83.33%** | **96.87%** |       33        |

- **분석:**
  - **Branch (100%):** 모든 조건문(if/else, 삼항연산자) 분기가 테스트됨.
  - **Statements / Lines (96.87%):**
    - Uncovered Line 33: `socialLogin` API 함수 호출부. Mocking 된 `useMutation` 내부 동작이라 직접 호출 커버리지가 잡히지 않았으나, `handleSocialCallback` 테스트(AUTH-SOCIAL-004)를 통해 호출 여부는 간접 검증됨.
  - **Functions (83.33%):**
    - `mutationFn` 내부의 익명 함수가 직접 실행되지 않아 수치가 낮게 잡혔으나, 핵심 비즈니스 로직 함수들은 모두 실행됨.

### 3.3. 결론

`useSocialLoginLogic` 모듈은 소셜 로그인 인증 흐름의 핵심인 리다이렉트와 콜백 처리를 정확하게 수행하고 있으며, 예외 상황(코드 누락, API 실패 등)에 대한 방어 로직도 견고하게 구현되어 있음. 높은 커버리지와 함께 모든 테스트 케이스를 통과하여 배포 가능한 수준의 안정성을 확보함.
