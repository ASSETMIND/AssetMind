# [TCS] 사용자(User) 영속성 어댑터 테스트 명세서

| 문서 ID | **TCS-INFRA-USR-001**                              |
| :--- |:---------------------------------------------------|
| **문서 버전** | 1.1                                                |
| **프로젝트** | AssetMind                                          |
| **작성자** | 이재석                                                |
| **작성일** | 2026년 01월 17일                                      |
| **관련 모듈** | `apps/server-auth/user/infrastructure/persistence` |

## 1. 개요 (Overview)

본 문서는 AssetMind 인증 서버의 도메인 객체를 영속화하는 **`UserRepositoryImpl`** (Adapter)의 동작을 검증하기 위한 슬라이스 테스트(Slice Test) 명세이다.
`@DataJpaTest`를 사용하여 H2 인메모리 DB 환경에서 수행되며, 도메인 객체와 JPA 엔티티 간의 매핑 및 DB 제약조건 동작을 중점적으로 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Spring Data JPA
- **Target Class:** `UserRepositoryImplTest`
- **Key Verification:**
    - **Mapping:** Domain(User) ↔ Entity(UserEntity) 간 필드 매핑 및 변환 검증
    - **Nullable:** GUEST(소셜 정보 없음)와 USER(소셜 정보 있음) 간의 저장 로직 분기 검증
    - **Constraints:** 이메일 및 소셜 계정의 유니크(Unique) 제약조건 위반 시 예외 발생 여부 검증
    - **Reconstitution:** 저장된 데이터를 조회하여 도메인 객체로 완벽하게 재구성되는지 검증

---

## 2. Infrastructure Adapter 테스트 명세
> **대상 클래스:** `UserRepositoryImplTest`
> **검증 목표:** 도메인 객체가 DB에 올바르게 저장되고, 제약조건을 준수하며, 조회 시 원본 상태로 복원됨을 보장

### 2.1. 저장 (Save) 검증

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-001** | `givenGuestRoleUser_`<br>`whenSave_thenSaved`<br>👉 **소셜 정보가 없는 1차 가입자(GUEST)를 저장한다.** | **User(GUEST)**<br>(SocialID 필드 `null`) | **`userRepository.save()`** | 1. 저장된 객체의 ID가 반환된다.<br>2. **`socialID` 필드는 `null`로 저장된다.**<br>3. `userRole`은 **GUEST**이다. |
| **INF-002** | `givenUserRoleUser_`<br>`whenSave_thenSaved`<br>👉 **소셜 정보가 있는 정회원(USER)을 저장한다.** | **User(USER)**<br>(Valid SocialID 포함) | **`userRepository.save()`** | 1. 저장된 객체의 ID가 반환된다.<br>2. **`socialID` 정보가 DB에 정상 매핑된다.**<br>3. `userRole`은 **USER**이다. |
| **INF-003** | `givenDuplicatedEmailUser_`<br>`whenSave_thenThrowException`<br>👉 **이미 존재하는 이메일로 저장 시 예외가 발생한다.** | **기존 유저 저장됨**<br>(이메일: A)<br>**신규 유저 생성**<br>(이메일: A, 동일) | **`userRepository.save()`**<br>+ `em.flush()` (DB 반영) | 1. `ConstraintViolationException` 발생.<br>(DB Unique Key 제약조건 위반) |
| **INF-004** | `givenAlreadySocialUser_`<br>`whenSave_thenThrowException`<br>👉 **이미 연동된 소셜 계정으로 저장 시 예외가 발생한다.** | **기존 유저 저장됨**<br>(Provider: P, ID: 1)<br>**신규 유저 생성**<br>(Provider: P, ID: 1, 동일) | **`userRepository.save()`**<br>+ `em.flush()` (DB 반영) | 1. `ConstraintViolationException` 발생.<br>(DB Unique Key 제약조건 위반) |

### 2.2. 조회 (Find) 검증

| ID          | 테스트 메서드 / 시나리오                                                                                                 | Given (사전 조건)                    | When (수행 행동)                                             | Then (검증 결과)                                                          |
|:------------|:---------------------------------------------------------------------------------------------------------------|:---------------------------------|:---------------------------------------------------------|:----------------------------------------------------------------------|
| **INF-005** | `givenValidUserId_`<br>`whenFindById_thenReturnSavedUser`<br>👉 **저장된 ID(UUID)로 유저를 조회한다.**                    | **유저 저장 완료**<br>(UUID: id_A)     | **`userRepository.findById(id_A)`**                      | 1. `Optional`이 비어있지 않다(`isPresent`).<br>2. 조회된 유저의 ID 및 필드 값이 일치한다.   |
| **INF-006** | `givenInvalidUserId_`<br>`whenFindById_thenReturnEmpty`<br>👉 **존재하지 않는 ID로 조회 시 빈 결과를 반환한다.**                 | **랜덤 UUID 생성**<br>(DB에 없음)       | **`userRepository.findById(randomId)`**                  | 1. `Optional`이 비어있다(`isEmpty`).                                       |
| **INF-007** | `givenValidSocialId_`<br>`whenFindBySocialId_thenReturnSavedUser`<br>👉 **일치하는 소셜 정보(Provider+ID)로 유저를 조회한다.** | **유저 저장 완료**<br>(KAKAO, id_123)  | **`userRepository.findBySocialId`**<br>`(KAKAO, id_123)` | 1. `Optional`이 비어있지 않다.<br>2. 조회된 유저의 `socialID` 값이 일치한다.             |
| **INF-008** | `givenInvalidSocialId_`<br>`whenFindBySocialId_thenReturnEmpty`<br>👉 **소셜 정보가 일치하지 않으면 빈 결과를 반환한다.**          | **유저 저장 완료**<br>(GOOGLE, id_999) | **`userRepository.findBySocialId`**<br>`(KAKAO, id_999)` | 1. `Optional`이 비어있다(`isEmpty`).<br>(Provider 불일치 케이스 등)               |
| **INF-009** | `givenEmail_`<br>`whenExistsByEmail_thenReturnBoolean`<br>👉 **해당 이메일이 존재하는지 조회한다. 존재하면 True를, 존재하지 않으면 False를 반환한다.**                   | **유저 저장 완료 및 타겟 이메일**            | **`userRepository.existsByEamil`**<br>`(email)`          | 1. 해당 이메일이 존재하면 `True`를 반환한다. <br> 2. 해당 이메일이 존재하지 않으면 `False`를 반환한다. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass  | Fail | 비고 |
| :--- |:------:|:-----:| :---: | :--- |
| **Save (저장)** |   4    |   4   | 0 | Nullable 처리 및 Unique 제약조건 검증 완료 |
| **Find (조회)** |   5    |   5   | 0 | PK 및 복합 인덱스 조회 검증 완료 |
| **합계** | **9**  | **9** | **0** | **Pass** ✅ |