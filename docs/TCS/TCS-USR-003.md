# [TCS] 회원가입 서비스 단위 테스트 명세서

| 문서 ID | **TCS-USR-003**       |
| :--- |:----------------------|
| **문서 버전** | 1.0                   |
| **프로젝트** | AssetMind             |
| **작성자** | 이재석                   |
| **작성일** | 2026년 01월 22일         |
| **대상 모듈** | `UserRegisterService` |

## 1. 개요 (Overview)

본 문서는 회원가입 프로세스를 담당하는 `UserRegisterService`의 비즈니스 로직을 검증하기 위한 단위 테스트 명세이다.
외부 의존성(Repository, Redis Port, Mail Port 등)을 **Mocking**하여 순수 서비스 로직의 흐름과 예외 처리(Unhappy Path)가 의도대로 동작하는지 확인한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Mockito
- **Test Class:** `UserRegisterServiceTest`
- **Mock Objects:**
    - `UserRepository`: DB 조회/저장 모의
    - `VerificationCodePort` / `VerificationCodeGenerator`: 인증 코드 저장/조회/생성 모의
    - `EmailSendPort`: 메일 발송 모의
    - `SignUpTokenProvider`: JWT 토큰 처리 모의
    - `PasswordEncoder` / `UserIdGenerator`: 암호화 및 ID 생성 모의

---

## 2. 테스트 케이스 상세 (Test Cases)

### 2.1. 이메일 중복 체크 (Check Email Duplicate)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-REG-001** | **중복되지 않은 이메일 확인** | `Repository.existsByEmail()`이 `false` 반환 | `checkEmailDuplicate(validEmail)` 호출 | 1. 반환값이 `false`여야 한다. |
| **SVC-REG-002** | **중복된 이메일 확인** | `Repository.existsByEmail()`이 `true` 반환 | `checkEmailDuplicate(duplicateEmail)` 호출 | 1. 반환값이 `true`여야 한다. |

### 2.2. 인증 코드 발송 (Send Verification Code)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-REG-003** | **정상 발송**<br>(가입되지 않은 이메일) | 1. 이메일 중복 없음 (`false`)<br>2. 생성기가 코드 `"123456"` 반환 | `sendVerificationCode(email)` 호출 | 1. `VerificationCodePort.save()`가 호출되어야 한다.<br>2. `EmailSendPort.sendEmail()`이 호출되어야 한다. |
| **SVC-REG-004** | **발송 실패**<br>(이미 가입된 이메일) | 1. 이메일 중복 있음 (`true`) | `sendVerificationCode(email)` 호출 | 1. `UserDuplicatedEmail` 예외가 발생해야 한다.<br>2. 메일 발송 및 저장은 실행되지 않아야 한다. |

### 2.3. 인증 코드 검증 (Verify Code)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-REG-005** | **검증 성공**<br>(코드 일치) | 1. Port에 저장된 코드가 입력 코드와 **일치**함<br>2. TokenProvider가 유효한 토큰 반환 | `verifyCode(email, code)` 호출 | 1. `VerificationCodePort.remove()`가 호출되어 삭제되어야 한다.<br>2. 회원가입용 **JWT 토큰**이 반환되어야 한다. |
| **SVC-REG-006** | **검증 실패**<br>(코드 불일치) | 1. Port에 저장된 코드가 입력 코드와 **다름** (또는 null) | `verifyCode(email, code)` 호출 | 1. `InvalidVerificationCode` 예외가 발생해야 한다.<br>2. `remove()` 메서드는 호출되지 않아야 한다. |

### 2.4. 최종 회원가입 (Register)

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-REG-007** | **가입 성공**<br>(모든 데이터 유효) | 1. 토큰 내 이메일 == 요청 이메일<br>2. 이메일 중복 없음<br>3. ID 생성기/암호화 정상 동작 | `register(command)` 호출 | 1. `UserRepository.save()`가 1회 호출되어야 한다.<br>2. `PasswordEncoder.encode()`가 호출되어야 한다.<br>3. 생성된 유저의 **UUID**가 반환되어야 한다. |
| **SVC-REG-008** | **가입 실패**<br>(토큰/요청 이메일 불일치) | 1. 토큰 내 이메일(`invalid`) != 요청 이메일(`valid`) | `register(command)` 호출 | 1. `IllegalArgumentException` 예외가 발생해야 한다.<br>2. `save()`는 호출되지 않아야 한다. |
| **SVC-REG-009** | **가입 실패**<br>(가입 직전 중복 발견) | 1. 토큰 검증 통과<br>2. `Repository.existsByEmail()`이 `true` 반환 | `register(command)` 호출 | 1. `UserDuplicatedEmail` 예외가 발생해야 한다.<br>2. `save()`는 호출되지 않아야 한다. |

---

## 3. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고 |
| :--- | :---: | :---: | :---: | :--- |
| **Service Logic** | 9 | 9 | 0 | Happy/Unhappy Path 검증 완료 |
| **합계** | **9** | **9** | **0** | **Pass** ✅ |