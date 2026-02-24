# [TCS] 사용자(User) 도메인 모듈 테스트 명세서

| 문서 ID | **TCS-USR-001**                |
| :--- |:-------------------------------|
| **문서 버전** | 1.1                            |
| **프로젝트** | AssetMind                      |
| **작성자** | 이재석                            |
| **작성일** | 2026년 01월 16일                  |
| **관련 모듈** | `apps/server-auth/user/domain` |

## 1. 개요 (Overview)

본 문서는 AssetMind 인증 서버의 핵심 애그리거트 루트인 **`User`** 객체의 비즈니스 로직 및 팩토리 메서드를 검증하기 위한 단위 테스트(Unit Test) 명세이다.
모든 테스트는 외부 의존성(DB, Network)을 배제한 상태에서 수행되며, **BDD(Given-When-Then)** 스타일을 따른다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ
- **Target Class:** `UserTest`
- **Key Verification:**
  - **Creation:** 1차 가입(이메일+비밀번호) 시 ID 주입 및 초기 상태(GUEST) 검증
  - **Validation:** 필수 정보(UserInfo, Password, SocialID) 누락 시 방어 로직 검증
  - **State Transition:** 2차 인증(소셜 연동)을 통한 권한 승격 및 데이터 주입 검증
  - **Reconstitution:** DB 데이터 기반 객체 복원 검증

---

## 2. Domain Entity 테스트 명세
> **대상 클래스:** `UserTest`
> **검증 목표:** 애그리거트 루트(`User`)의 무결성 및 비즈니스 규칙(가입 절차 분리) 준수 보장

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **ENT-001** | `givenValidInfo_whenCreateGuest_`<br>`thenCreated`<br>👉 **유효한 정보로 1차 가입(GUEST)을 진행한다.** | **Stub Generator**<br>(UUID 반환)<br>**Valid VOs**<br>(UserInfo, Password) | **`User.createGuest()`** | 1. `userRole`이 **GUEST**이다.<br>2. `password`와 `userInfo`가 저장된다.<br>3. **`socialID`는 `null`이어야 한다.** |
| **ENT-002** | `givenNullUserInfo_whenCreateGuest_`<br>`thenThrowException`<br>👉 **필수 정보(UserInfo)가 없으면 생성할 수 없다.** | **UserInfo 누락**<br>(`null` 주입) | **`User.createGuest()`** | 1. `NullPointerException` 발생. |
| **ENT-003** | `givenNullPassword_whenCreateGuest_`<br>`thenThrowException`<br>👉 **필수 정보(Password)가 없으면 생성할 수 없다.** | **Password 누락**<br>(`null` 주입) | **`User.createGuest()`** | 1. `NullPointerException` 발생. |
| **ENT-004** | `givenGuestRoleUser_`<br>`whenLinkSocialAndUpgrade_thenUpgradeToUser`<br>👉 **소셜 계정을 연동하면 USER로 승격된다.** | **GUEST 유저**<br>(`createGuest`로 생성됨)<br>**Valid SocialID** | **`linkSocialAndUpgrade()`** | 1. `userRole` 상태가 **USER**로 변경된다.<br>2. 입력한 `socialID`가 유저 객체에 주입된다. |
| **ENT-005** | `givenUserRoleUser_`<br>`whenLinkSocialAndUpgrade_thenThrowException`<br>👉 **이미 USER인 경우 중복 승격 시 예외가 발생한다.** | **USER 유저**<br>(이미 승격 완료된 상태) | **`linkSocialAndUpgrade()`** | 1. `BusinessException` 발생.<br>2. ErrorCode: `ALREADY_GET_USER_PERMISSION` 확인. |
| **ENT-006** | `givenNullSocialID_`<br>`whenLinkSocialAndUpgrade_thenThrowException`<br>👉 **연동할 소셜 정보가 없으면 예외가 발생한다.** | **GUEST 유저**<br>**SocialID 누락** (`null`) | **`linkSocialAndUpgrade()`** | 1. `IllegalArgumentException` 발생.<br>2. "연동할 소셜 정보가 없습니다" 메시지 확인. |
| **ENT-007** | `givenStoredUserId_whenWithId_`<br>`thenGetValidUser`<br>👉 **DB 데이터 복원 시 ID와 모든 필드 상태를 유지한다.** | **DB 데이터 가정**<br>(UUID, Role, Password, SocialID 등) | **`User.withId()`** | 1. ID가 새로 생성되지 않고 유지된다.<br>2. Password, SocialID 등 모든 필드가 그대로 복원된다. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass | Fail | 비고 |
| :--- | :---: | :---: | :---: | :--- |
| **User Entity** | 7 | 7 | 0 | 1차 가입, 2차 승격, Null 방어, DB 복원 로직 검증 완료 |
| **합계** | **7** | **7** | **0** | **Pass** ✅ |