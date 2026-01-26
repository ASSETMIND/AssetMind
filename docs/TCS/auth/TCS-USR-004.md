# [TCS] 회원가입 컨트롤러 단위 테스트 명세서

| 문서 ID | **TCS-USR-004**          |
| :--- |:-------------------------|
| **문서 버전** | 1.0                      |
| **프로젝트** | AssetMind                |
| **작성자** | 이재석                      |
| **작성일** | 2026년 01월 25일            |
| **대상 모듈** | `UserRegisterController` |

## 1. 개요 (Overview)

본 문서는 클라이언트의 HTTP 요청을 처리하는 **Web Adapter 계층(`UserRegisterController`)**을 검증하기 위한 단위 테스트 명세이다.
`@WebMvcTest`를 사용하여 컨트롤러를 슬라이스 테스트하며, **Request DTO 유효성 검증(@Valid)**, **Service 호출 여부**, **GlobalExceptionHandler를 통한 공통 응답 포맷(ApiResponse)을** 중점적으로 확인한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, Mockito (`@MockitoBean`), MockMvc
- **Test Class:** `UserRegisterControllerTest`
- **Configuration:** `@AutoConfigureMockMvc(addFilters = false)` (Security Filter 비활성화)
- **Mock Objects:**
    - `UserRegisterUseCase`: 비즈니스 로직(Service) 모의

---

## 2. 테스트 케이스 상세 (Test Cases)

### 2.1. 이메일 중복 체크 (Check Email Duplicate)
**Endpoint:** `GET /api/auth/check-email`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-REG-001** | **사용 가능한 이메일 확인** | Service가 `false` 반환 | `GET /check-email` 호출<br>(param: validEmail) | 1. HTTP 상태 코드 **200 OK**<br>2. 응답 Body `success`는 `true`<br>3. 응답 Body `data`는 `false` |
| **WEB-REG-002** | **중복된 이메일 확인** | Service가 `true` 반환 | `GET /check-email` 호출<br>(param: duplicatedEmail) | 1. HTTP 상태 코드 **200 OK**<br>2. 응답 Body `success`는 `true`<br>3. 응답 Body `data`는 `true` |

### 2.2. 인증 코드 전송 (Send Verification Code)
**Endpoint:** `POST /api/auth/code`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-REG-003** | **전송 성공**<br>(유효한 형식) | Service 메서드 정상 동작 (void) | `POST /code` 호출<br>(body: validEmail) | 1. HTTP 상태 코드 **200 OK**<br>2. `message`에 "전송 성공" 포함<br>3. Service `sendVerificationCode` 호출됨 |
| **WEB-REG-004** | **전송 실패**<br>(이메일 형식 오류) | (Mocking 불필요) | `POST /code` 호출<br>(body: "invalid-email") | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `message`에 "형식이 아닙니다" 포함<br>3. Service는 **호출되지 않음** (`never()`) |
| **WEB-REG-005** | **전송 실패**<br>(이미 가입된 이메일) | Service가 `UserDuplicatedEmail` 예외 발생 | `POST /code` 호출<br>(body: duplicatedEmail) | 1. HTTP 상태 코드 **409 Conflict**<br>2. `success`는 `false`<br>3. GlobalExceptionHandler 동작 확인 |

### 2.3. 인증 코드 검증 (Verify Code)
**Endpoint:** `POST /api/auth/code/verify`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-REG-006** | **검증 성공**<br>(코드 일치) | Service가 토큰(`"ey..."`) 반환 | `POST /code/verify` 호출<br>(body: email, code) | 1. HTTP 상태 코드 **200 OK**<br>2. `success`는 `true`<br>3. `data` 필드에 토큰 값 존재 확인 |
| **WEB-REG-007** | **검증 실패**<br>(이메일 형식 오류) | (Mocking 불필요) | `POST /code/verify` 호출<br>(body: "invalid", code) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `message`에 "형식이 아닙니다" 포함<br>3. Service는 **호출되지 않음** |
| **WEB-REG-008** | **검증 실패**<br>(코드 불일치) | Service가 `InvalidVerificationCode` 예외 발생 | `POST /code/verify` 호출<br>(body: email, wrongCode) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `message`에 "유효하지 않은" 포함 |

### 2.4. 회원가입 (Register)
**Endpoint:** `POST /api/auth/register`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-REG-009** | **가입 성공**<br>(모든 데이터 유효) | Service가 생성된 UUID 반환 | `POST /register` 호출<br>(body: validUserReq) | 1. HTTP 상태 코드 **201 Created**<br>2. `success`는 `true`<br>3. `data` 필드에 UUID(String) 반환 |
| **WEB-REG-010** | **가입 실패**<br>(비밀번호 정책 위반) | (Mocking 불필요) | `POST /register` 호출<br>(body: weakPassword) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `message`에 비밀번호 정책 안내 문구 포함 |
| **WEB-REG-011** | **가입 실패**<br>(토큰/이메일 불일치) | Service가 `IllegalArgumentException` 예외 발생 | `POST /register` 호출<br>(body: mismatchEmail) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `success`는 `false` |
| **WEB-REG-012** | **가입 실패**<br>(가입 직전 중복 발견) | Service가 `UserDuplicatedEmail` 예외 발생 | `POST /register` 호출<br>(body: duplicatedEmail) | 1. HTTP 상태 코드 **409 Conflict**<br>2. `success`는 `false` |

---

## 3. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고 |
| :--- | :---: | :---: | :---: | :--- |
| **Controller Logic** | 12 | 12 | 0 | Validation 및 ExceptionHandler 검증 완료 |
| **합계** | **12** | **12** | **0** | **Pass** ✅ |