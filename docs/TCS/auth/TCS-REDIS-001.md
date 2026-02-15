# [TCS] Redis 영속성 어댑터 테스트 명세서

| 문서 ID | **TCS-INFRA-REDIS-001**                 |
| :--- |:----------------------------------------|
| **문서 버전** | 1.1                                     |
| **프로젝트** | AssetMind                               |
| **작성자** | 이재석                                     |
| **작성일** | 2026년 01월 21일                           |
| **관련 모듈** | `user/infrastructure/persistence/redis` |

## 1. 개요 (Overview)

본 문서는 AssetMind Auth 시스템의 Redis 기반 저장소 어댑터들의 단위 테스트 명세이다.
대상은 **이메일 인증 코드 저장소**(`RedisVerificationCodeAdapter`)와 **리프레시 토큰 저장소**(`RedisRefreshTokenAdapter`)이다.
외부 시스템인 Redis와의 통신을 담당하는 `StringRedisTemplate`을 **Mocking**하여, 실제 Redis 서버 없이 비즈니스 로직에서 요구하는 저장, 조회, 삭제 명령이 올바른 파라미터(Key Prefix, TTL 등)와 함께 호출되는지 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Mockito
- **Target Class:** `RedisVerificationCodeAdapterTest`, `RedisRefreshTokenAdapterTest`
- **Key Verification:**
    - **Key Naming Policy:** 모든 키에 접두사(`AUTH_CODE:`, `REFRESH_TOKEN:`)가 올바르게 붙는지 검증
    - **Data Integrity:** 저장하려는 데이터(Code)가 변조 없이 전달되는지 검증
    - **TTL (Time To Live):** 유효 시간이 `Duration` 객체로 올바르게 변환되어 설정되는지 검증

---

## 2. Infrastructure Adapter 테스트 명세 1 - 회원가입용 인증 코드
> **대상 클래스:** `RedisVerificationCodeAdapterTest`
> **검증 목표:** 서비스 계층의 요청이 Redis 클라이언트 명령어로 올바르게 변환(Adapt)되는지 확인

### 2.1. CRUD 동작 검증

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-REDIS-001** | `givenEmailCodeTTL_`<br>`whenSave_thenSavedCorrectData`<br>👉 **저장 검증: Key Prefix와 만료 시간(TTL) 설정 확인** | **Mock 설정**<br>`redisTemplate.opsForValue()` 호출 시<br>Mock `ValueOperations` 반환 | **`adapter.save(EMAIL, CODE, TTL)`**<br>(TTL: 180초) | 1. `ops.set()` 메서드가 호출된다.<br>2. **Key:** `"AUTH_CODE:" + EMAIL` 형태인지 확인.<br>3. **Value:** 입력한 코드(`123456`)와 일치 확인.<br>4. **Timeout:** `Duration.ofSeconds(180)`으로 정확히 변환되었는지 확인. |
| **INF-REDIS-002** | `givenSavedKey_`<br>`whenGetCode_thenReturnSavedCode`<br>👉 **조회 검증: 올바른 Key로 조회하고 값을 반환하는지 확인** | **Mock 설정**<br>Mock `ValueOperations`가 특정 Key 조회 시<br>`"123456"`(Code) 반환하도록 설정 | **`adapter.getCode(EMAIL)`** | 1. 반환된 값이 예상 코드(`"123456"`)와 일치한다.<br>2. `ops.get()` 호출 시 사용된 Key가 접두사(`AUTH_CODE:`)를 포함하고 있는지 검증한다. |
| **INF-REDIS-003** | `givenSavedKey_`<br>`whenDelete_thenDeleted`<br>👉 **삭제 검증: 올바른 Key로 삭제 명령을 내리는지 확인** | **Mock 설정**<br>(별도 Stubbing 불필요) | **`adapter.remove(EMAIL)`** | 1. `redisTemplate.delete()` 메서드가 **1회** 호출된다.<br>2. 삭제 요청된 Key가 접두사(`AUTH_CODE:`)를 포함하고 있는지 검증한다. |

---

## 3. Infrastructure Adapter 테스트 명세 2 - 리프레시 토큰
> **대상 클래스:** `RedisRefreshTokenAdapterTest`
> **검증 목표:** 로그인 유지를 위한 장기 데이터(Token)의 Redis 명령 변환 검증

### 3.1. CRUD 동작 검증

| ID | 테스트 메서드 / 시나리오                                                                                        | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- |:------------------------------------------------------------------------------------------------------| :--- | :--- | :--- |
| **INF-REDIS-004** | `givenInfo_`<br> `whenSave_thenSaveToken` <br>👉 **저장 검증: UUID 키 변환 및 장기 TTL 설정 확인**                  | **Mock 설정**<br>`opsForValue()` Mocking | **`adapter.save(UUID, TOKEN, TTL)`**<br>(TTL: 7일) | 1. `ops.set()` 메서드가 호출된다.<br>2. **Key:** `"REFRESH_TOKEN:" + UUID.toString()` 형태 확인.<br>3. **Value:** 리프레시 토큰 문자열 일치 확인.<br>4. **Timeout:** `Duration` 변환 정확성 확인. |
| **INF-REDIS-005** | `givenSavedKey_`<br> `whenGetRefreshToken_thenReturnRefreshToken` <br>👉 **조회 검증: UUID 키로 토큰을 조회한다.** | **Mock 설정**<br>특정 UUID 키 조회 시<br>토큰 문자열 반환 설정 | **`adapter.getRefreshToken(UUID)`** | 1. 반환된 토큰 값이 예상값과 일치한다.<br>2. `ops.get()` 호출 시 사용된 Key가 접두사(`REFRESH_TOKEN:`)와 `UUID` 문자열을 포함하는지 검증한다. |
| **INF-REDIS-006** | `givenSavedKey_`<br> `whenDelete_thenDeleteToken` <br>👉 **삭제 검증: 로그아웃 시 해당 토큰을 삭제한다.**               | **Mock 설정**<br>(별도 Stubbing 불필요) | **`adapter.delete(UUID)`** | 1. `redisTemplate.delete()` 메서드가 **1회** 호출된다.<br>2. 삭제 요청된 Key가 `UUID` 기반으로 정확히 생성되었는지 검증한다. |

---

## 4. 테스트 결과 요약

### 4.1. 수행 결과
| 구분 | 전체 케이스 | Pass  | Fail | 비고 |
| :--- |:------:|:-----:| :---: | :--- |
| **Verification Code (Email)** |   3    |   3   | 0 | Prefix(`AUTH_CODE:`) 검증 완료 |
| **Refresh Token (Login)** |   3    |   3   | 0 | Prefix(`REFRESH_TOKEN:`) 및 UUID 변환 검증 완료 |
| **합계** | **6**  | **6** | **0** | **Pass** ✅ |

---

**💡 비고:**
본 테스트는 `Mockito`를 사용한 `단위 테스트(Unit Test)`입니다. 실제 Redis 서버 연결 상태나 네트워크 장애 상황 등을 검증하지 않으며, 이는 추후 통합 테스트(Integration Test) 단계에서 `TestContainers` 등을 활용하여 검증할 예정입니다.