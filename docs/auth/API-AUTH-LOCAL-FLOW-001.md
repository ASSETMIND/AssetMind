# API-AUTH-LOCAL-FLOW-001
회원가입 / 로그인 API 흐름 정의 (Local Login)

| 문서 ID | API-AUTH-LOCAL-FLOW-001 |
|:------|:------------------------|
| 문서 버전 | 1.0                     |
| 프로젝트 | AssetMind               |
| 작성자 | 김광래                     |
| 작성일 | 2026년 1월 7일             |

---

## 1. 회원가입(Signup) API 흐름

### 정상 흐름

1. 클라이언트가 본인 인증을 먼저 수행한다. (포트원 방식)
2. 본인 인증 성공 시, CI/DI 값을 포함한 회원가입 요청을 전송한다.
3. 서버는 CI/DI 값을 검증하고, 중복 가입 여부를 확인한다.
4. 계정 ID 중복 여부를 검증한다.
5. 비밀번호 정책을 검증한다. (최소 8자, 영문/숫자/특수문자 포함)
6. 비밀번호를 **Argon2** 알고리즘으로 해싱한다.
7. User 엔티티를 생성하고 CI/DI 값을 암호화하여 저장한다.
8. 기본 권한(Role: USER)을 할당한다. (**트랜잭션 범위: 7~8 단계**)
9. 회원가입 성공 응답을 반환한다.

회원가입 과정에서는 토큰을 발급하지 않는다.

---

### 실패 흐름

- CI/DI 검증에 실패한 경우 회원가입에 실패한다. (본인 인증 미완료 또는 위조)
- CI/DI 값이 이미 존재하는 경우 회원가입에 실패한다. (중복 가입 방지)
- 계정 ID가 이미 존재하는 경우 회원가입에 실패한다.
- 비밀번호 정책을 만족하지 못하는 경우 회원가입에 실패한다.
- **데이터 무결성 위반 시** (Duplicate Entry 등) 회원가입에 실패하고 구체적인 오류를 반환한다.
- **시스템 장애 발생 시** (DB Connection Fail 등) 사용자에게는 "일시적 오류"로 알리고, 내부 로그에 Stack Trace를 기록한다.

---

## 2. 로그인(Login) API 흐름

### 정상 흐름

1. 클라이언트가 로그인 요청을 전송한다.
2. 서버는 계정 ID와 비밀번호를 동시에 검증한다.
3. 인증이 성공하면 사용자 상태(ACTIVE/INACTIVE)를 확인한다.
4. 로그인 실패 카운터를 초기화한다.
5. 마지막 로그인 시각을 갱신한다.
6. Access Token을 생성한다. (유효 기간: 1시간)
7. Refresh Token을 생성하거나 기존 토큰을 폐기 후 재발급한다. (유효 기간: 2주)
8. Refresh Token의 해시값을 MySQL에 저장한다.
9. 클라이언트 IP와 User-Agent를 함께 저장한다.
10. Access Token은 응답 Body로, Refresh Token은 HttpOnly Cookie로 반환한다.

---

### 실패 흐름

- **자격 증명 실패:** 계정 ID 또는 비밀번호가 일치하지 않는 경우 로그인에 실패한다.
  - 클라이언트에는 "로그인 정보가 올바르지 않습니다"라는 통합 메시지를 반환한다. (**계정 열거 공격 방지**)
  - 로그인 실패 카운터를 증가시킨다.
- **계정 잠금:** 로그인 실패 횟수가 5회를 초과한 경우 계정이 잠긴다.
- **비활성 계정:** 사용자 상태가 INACTIVE인 경우 로그인에 실패한다.

---

## 3. 토큰 처리 기준

### Access Token
- **유효 기간:** 1시간
- **서버 저장 위치:** Stateless (서버에 저장하지 않음)
- **클라이언트 저장 위치:** React Context (메모리)
  - XSS 공격 시 LocalStorage/Cookie는 쉽게 탈취되지만, 메모리 변수는 탈취가 매우 어려움
  - 새로고침 시 휘발되므로 Refresh Token으로 재발급 필요
- **전달 방식:** HTTP Response Body (JSON)
- **만료 시 처리:** 클라이언트가 `/api/auth/refresh`를 호출하여 재발급

### Refresh Token
- **유효 기간:** 2주
- **저장 위치:** MySQL (RDB - JPA Entity)
- **저장 형식:** 해시(Hash)값만 저장 (DB 탈취 시 세션 하이재킹 방지)
- **전달 방식:** HttpOnly Cookie (`Set-Cookie` 헤더)
- **Cookie 설정:**
  - `Path=/api/auth/refresh`
  - `Secure` (HTTPS 환경에서만 전송)
  - `HttpOnly` (JavaScript 접근 차단)
  - `SameSite=Strict` (CSRF 방어)
- **만료 시 처리:** 재로그인 필요
- **정책:** 사용자당 1개만 유효 (재로그인 시 기존 토큰 폐기)
- **유지보수:** 만료된 토큰은 배치 작업으로 주기적 삭제

### RTR (Refresh Token Rotation)
- 토큰 재발급 시 기존 Refresh Token을 폐기하고 새로운 Refresh Token을 발급한다.
- 탈취된 토큰의 재사용을 방지한다.

---

## 4. 책임 분리 기준

### Controller (Presentation Layer)
- 요청 수신 및 응답 반환
- 인증 결과 전달
- DTO 검증 (Validation)

### Application (Service Layer)
- 회원가입 및 로그인 흐름 제어
- 토큰 발급 시점 제어
- 트랜잭션 경계 관리

### Domain Layer
- 사용자 및 토큰 생성 규칙
- 비즈니스 제약 조건 관리
- 도메인 이벤트 발행

### Infrastructure Layer
- **Persistence:** JPA Entity를 통한 DB 접근 (User, RefreshToken)
- **Security:** JWT 생성, 검증, SecurityContext 처리
- **External API:** 본인 인증(포트원) 연동
- **Batch:** 만료된 RefreshToken 주기적 삭제