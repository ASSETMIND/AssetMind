# [TCS] 사용자(User) 도메인 모듈 테스트 명세서

| 문서 ID | **TCS-USR-001**                |
| :--- |:-------------------------------|
| **문서 버전** | 1.0                            |
| **프로젝트** | AssetMind                      |
| **작성자** | 이재석                            |
| **작성일** | 2026년 01월 15일                  |
| **관련 모듈** | `apps/server-auth/user/domain` |

## 1. 개요 (Overview)

본 문서는 AssetMind 인증 서버의 핵심 애그리거트 루트인 **`User`** 객체의 비즈니스 로직 및 팩토리 메서드를 검증하기 위한 단위 테스트(Unit Test) 명세이다.
모든 테스트는 외부 의존성(DB, Network)을 배제한 상태에서 수행되며, **BDD(Given-When-Then)** 스타일을 따른다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ
- **Target Class:** `UserTest`
- **Key Verification:**
    - **Creation:** 신규 가입 시 ID 주입 및 초기 상태(GUEST) 검증
    - **Validation:** 필수 정보 누락 시 방어 로직(Null Check) 검증
    - **State Transition:** 권한 승격 로직 및 중복 승격 방지 검증
    - **Reconstitution:** DB 데이터 기반 객체 복원 검증

---

## 2. Domain Entity 테스트 명세
> **대상 클래스:** `UserTest`
> **검증 목표:** 애그리거트 루트(`User`)의 무결성 및 비즈니스 규칙 준수 보장

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **ENT-001** | `givenValidInfo_whenCreateGuest_`<br>`thenCreated`<br>👉 **유효한 정보로 GUEST 유저를 생성한다.** | **Stub Generator**<br>(고정된 UUID 반환)<br>**Valid VOs**<br>(UserInfo, SocialID) | **`User.createGuest()`** | 1. `id`가 Stubbing된 UUID와 일치한다.<br>2. `userRole`이 **GUEST**이다.<br>3. `socialID`, `userInfo` 필드가 정상 매핑된다. |
| **ENT-002** | `givenNullUserInfo_whenCreateGuest_`<br>`thenThrowException`<br>👉 **필수 정보(UserInfo)가 없으면 생성할 수 없다.** | **UserInfo 누락**<br>(`null` 주입) | **`User.createGuest()`** | 1. `NullPointerException` 발생. |
| **ENT-003** | `givenNullSocialID_whenCreateGuest_`<br>`thenThrowException`<br>👉 **필수 정보(SocialID)가 없으면 생성할 수 없다.** | **SocialID 누락**<br>(`null` 주입) | **`User.createGuest()`** | 1. `NullPointerException` 발생. |
| **ENT-004** | `givenGuestRoleUser_whenUpgradeRole_`<br>`thenUpgradeToUser`<br>👉 **GUEST 상태인 유저가 USER로 승격된다.** | **GUEST 유저**<br>(`createGuest`로 생성됨) | **`upgradeToRoleUser()`** | 1. `userRole` 상태가 **USER**로 변경된다. |
| **ENT-005** | `givenUserRoleUser_whenUpgradeRole_`<br>`thenThrowException`<br>👉 **이미 USER인 경우 중복 승격 시 예외가 발생한다.** | **USER 유저**<br>(이미 승격 완료된 상태) | **`upgradeToRoleUser()`** | 1. `BusinessException` 발생.<br>2. ErrorCode: `ALREADY_GET_USER_PERMISSION` 확인. |
| **ENT-006** | `givenStoredUserId_whenWithId_`<br>`thenGetValidUser`<br>👉 **DB 데이터 복원 시 ID와 상태를 그대로 유지한다.** | **DB 데이터 가정**<br>(Random UUID, Role=USER) | **`User.withId()`** | 1. ID가 새로 생성되지 않고 **입력값(DB ID)**과 일치한다.<br>2. Role 상태가 **USER**로 유지된다. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass | Fail | 비고 |
| :--- | :---: | :---: | :---: | :--- |
| **User Entity** | 6 | 6 | 0 | 팩토리 메서드, Null 방어, 상태 변경 로직 검증 완료 |
| **합계** | **6** | **6** | **0** | **Pass** ✅ |