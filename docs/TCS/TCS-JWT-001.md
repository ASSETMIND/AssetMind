# [TCS] JWT 보안 모듈 및 가입 토큰 제공자 테스트 명세서

| 문서 ID | **TCS-AUTH-JWT-001**                |
| :--- |:------------------------------------|
| **문서 버전** | 1.0                                 |
| **프로젝트** | AssetMind                           |
| **작성자** | 이재석                                 |
| **작성일** | 2026년 01월 20일                       |
| **관련 모듈** | `global/common`, `user/application` |

## 1. 개요 (Overview)

본 문서는 AssetMind 인증 시스템의 핵심 보안 요소인 **JWT 처리 모듈**(`JwtProcessor`)과 회원가입 전용 **토큰 관리자**(`SignUpTokenProvider`)의 동작을 검증하기 위한 단위 테스트(Unit Test) 명세이다.  
`JJWT 0.13.0` 라이브러리의 동작 검증과 더불어, 회원가입 비즈니스 로직(토큰 용도 구분)이 올바르게 수행되는지 중점적으로 확인한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Mockito
- **Target Classes:** `JwtProcessorTest`, `SignUpTokenProviderTest`
- **Key Verification:**
    - **Security & Integrity:** 생성된 토큰의 서명(Signature) 검증 및 만료(Expiration) 처리 확인
    - **Data Consistency:** Payload(Claims)에 저장된 데이터의 손실 없는 복원 확인
    - **Business Logic:** 가입용 토큰(`SIGN_UP`)과 로그인용 토큰(`ACCESS`)의 명확한 구분 및 예외 처리

---

## 2. Common Utility 테스트 명세 (`JwtProcessor`)
> **대상 클래스:** `JwtProcessorTest`  
> **검증 목표:** 비즈니스 로직과 무관하게, 순수하게 JWT를 생성하고 파싱하는 기술적 기능이 정상 동작하는지 검증

### 2.1. 생성 및 파싱 (Generate & Parse)

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **COM-JWT-001** | `generateAndParse`<br>👉 **정상적인 데이터를 담아 토큰을 생성하고, 다시 파싱한다.** | **데이터 준비**<br>- Subject: 이메일<br>- Claims: `{role: USER, age: 25}`<br>- 만료시간: 1분 | **`jwtProcessor.generate()`**<br>호출 후<br>**`jwtProcessor.parse()`** 호출 | 1. 파싱된 결과(`Claims`)의 Subject가 입력값과 일치한다.<br>2. Custom Claims(`role`, `age`) 데이터가 정확히 복원된다. |
| **COM-JWT-002** | `expiredToken`<br>👉 **만료된 토큰을 파싱하면 예외가 발생해야 한다.** | **만료 토큰 생성**<br>유효기간을 매우 짧게(10ms) 설정 후, `Thread.sleep`으로 만료 시킴 | **`jwtProcessor.parse()`** | 1. **`ExpiredJwtException`** 예외가 발생한다.<br>2. 만료된 토큰은 절대 비즈니스 로직으로 진입해서는 안 된다. |
| **COM-JWT-003** | `tamperedToken`<br>👉 **위변조된(서명이 다른) 토큰은 거부되어야 한다.** | **위조 토큰 준비**<br>정상 토큰 생성 후, 문자열 끝에 임의의 값("fake")을 덧붙임 | **`jwtProcessor.parse()`** | 1. **`security.SignatureException`** (혹은 `JwtException`)이 발생한다.<br>2. 서명이 깨진 토큰은 파싱 단계에서 차단된다. |

---

## 3. Business Service 테스트 명세 (`SignUpTokenProvider`)
> **대상 클래스:** `SignUpTokenProviderTest`  
> **검증 목표:** `JwtProcessor`(Mock)를 사용하여, 회원가입이라는 비즈니스 목적에 맞는 토큰을 발급하고 검증하는지 확인

### 3.1. 토큰 발급 및 검증 (Create & Validate)

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **BIZ-SIGN-001** | `createToken`<br>👉 **가입 토큰 생성 시 'SIGN_UP' 타입이 자동으로 포함된다.** | **Mock 설정**<br>`jwtProcessor.generate` 호출 시 미리 정의된 토큰 문자열 반환 | **`provider.createToken(EMAIL)`** | 1. 반환된 토큰 문자열이 예상값과 일치한다.<br>2. `verify()` 검증: `jwtProcessor`에게 전달된 Claims 맵에 **`"type": "SIGN_UP"`** 이 정확히 포함되었는지 확인한다. |
| **BIZ-SIGN-002** | `getEmailFromToken_Success`<br>👉 **'SIGN_UP' 타입의 토큰은 정상적으로 이메일을 반환한다.** | **Mock 설정**<br>`jwtProcessor.parse` 호출 시<br>`{sub: EMAIL, type: "SIGN_UP"}`을 담은 Claims 반환 | **`provider.getEmailFromToken()`** | 1. 메서드가 예외 없이 실행된다.<br>2. 반환된 값이 입력했던 이메일과 일치한다. |
| **BIZ-SIGN-003** | `givenNotSignUpType...`<br>👉 **다른 용도(예: ACCESS)의 토큰을 넣으면 거절된다.** | **Mock 설정 (Unhappy Case)**<br>`jwtProcessor.parse` 호출 시<br>`{sub: EMAIL, type: "ACCESS"}`를 담은 Claims 반환 | **`provider.getEmailFromToken()`** | 1. **`InvalidSignUpTokenException`** 커스텀 예외가 발생한다.<br>2. 로그인 토큰 등으로 가입을 시도하는 보안 허점을 방어한다. |
| **BIZ-SIGN-004** | `givenNoType...`<br>👉 **용도(type)가 없는 토큰도 거절된다.** | **Mock 설정 (Unhappy Case)**<br>`jwtProcessor.parse` 호출 시<br>`{sub: EMAIL}` (type 없음) 반환 | **`provider.getEmailFromToken()`** | 1. **`InvalidSignUpTokenException`** 커스텀 예외가 발생한다. |

---

## 4. 테스트 결과 요약

### 4.1. 수행 결과
| 구분 | 전체 케이스 | Pass | Fail | 비고 |
| :--- | :---: | :---: | :---: | :--- |
| **Common (JwtProcessor)** | 3 | 3 | 0 | 0.13.0 스펙 준수 및 보안 예외 검증 완료 |
| **Business (Provider)** | 4 | 4 | 0 | 타입 검증 로직(Mock 활용) 완료 |
| **합계** | **7** | **7** | **0** | **Pass** ✅ |