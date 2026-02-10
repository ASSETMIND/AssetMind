# Auth 테스트 명세서

## 1. 문서 정보 및 전략

- **대상 모듈:** `auth.KISAuthStrategy`, `auth.UPBITAuthStrategy`
- **복잡도 수준:** **최상 (Critical)** (금융 거래 인증, 자산 접근 권한 관리)
- **커버리지 목표:** 분기 커버리지 100%, 구문 커버리지 100%
- **적용 전략:**
  - [x] **경계값 분석 (BVA):** 토큰 만료 시간(KIS), 파라미터 유무(UPBIT).
  - [x] **MC/DC (수정 조건/결정 커버리지):** 갱신 로직의 조건 분기(KIS), 설정값 검증 분기(UPBIT).
  - [x] **상태 전이 (State Transition):** 토큰 수명주기 관리(KIS).
  - [x] **동시성 (Concurrency):** Async Lock 검증(KIS).
  - [x] **암호화 무결성 (Crypto Integrity):** JWT 서명(UPBIT), Payload 구성(UPBIT), SHA512 해시 일치 여부 검증(UPBIT).

## 2. 로직 흐름도 (참조)

### 2-1. KISAuthStrategy (Stateful Manager)

```
stateDiagram-v2
    [*] --> CheckState: get_token() called

    state CheckState {
        [*] --> IsTokenValid
        IsTokenValid --> Valid: Yes (Time > Buffer)
        IsTokenValid --> Invalid: No (None or Time <= Buffer)
    }

    Valid --> ReturnToken: Return Cached Token

    state RefreshProcess {
        Invalid --> AcquireLock: Async Lock
        AcquireLock --> DoubleCheck: Double-Checked Locking

        DoubleCheck --> Valid_2: Token already refreshed?
        Valid_2 --> ReturnToken

        DoubleCheck --> IssueToken: No, proceed to refresh
        IssueToken --> API_Call: POST /oauth2/tokenP

        state API_Call {
            [*] --> Success
            [*] --> NetworkError_4xx: 401/403 (Fail-Fast)
            [*] --> NetworkError_5xx: 500/Timeout (Retry)
        }

        Success --> UpdateState: Update Token & Expiry
        NetworkError_4xx --> Raise_AuthError: Stop
        NetworkError_5xx --> Raise_NetworkError: Retry Logic
    }

    UpdateState --> ReturnToken
    ReturnToken --> [*]
```

### 2-2. UPBITAuthStrategy (Stateless Manufacturer)

## 3. BDD 테스트 시나리오

### 3-1. KISAuthStrategy (Stateful Manager)

```
flowchart LR
    Start([get_token]) --> Init[Init Payload & Generate Nonce]
    Init --> CheckQuery{Query params exist?}

    CheckQuery -- Yes --> Hash[SHA512 Hashing]
    Hash --> Append[Add query_hash to Payload]

    CheckQuery -- No --> Sign
    Append --> Sign[JWT Sign (HS256)]

    Sign --> Format["Bearer {Token}"]
    Format --> End([Return])
```

**시나리오 요약:**

- **초기화 (Initialization):** 3건 (설정 및 보안 키 처리)
- **토큰 수명주기 (Lifecycle):** 4건 (초기 구동, 캐시 적중, 지연 갱신, 만료)
- **동시성 (Concurrency):** 1건 (경합 조건 방지)
- **API 상호작용 (API Interaction):** 4건 (응답 파싱 및 검증)
- **에러 처리 (Error Handling):** 5건 (조기 실패, 재시도, 예외 래핑, 침묵 실패 방지)

|     테스트 ID      | 분류 |   기법   | 전제 조건 (Given)                           | 수행 (When)                               | 검증 (Then)                                                                        | 입력 데이터 / 상황          |
| :----------------: | :--: | :------: | :------------------------------------------ | :---------------------------------------- | :--------------------------------------------------------------------------------- | :-------------------------- |
|  **KIS-INIT-01**   | 단위 |   표준   | 유효한 `AppConfig` 객체                     | `KISAuthStrategy(config)` 초기화          | 인스턴스 정상 생성 및 `base_url` 매핑 확인                                         | `base_url="https://api..."` |
|  **KIS-INIT-02**   | 단위 |   BVA    | `base_url`이 비어있는 설정                  | `KISAuthStrategy(config)` 초기화          | `ValueError` 발생 (방어 로직 작동)                                                 | `base_url=""` 또는 `None`   |
|  **KIS-INIT-03**   | 단위 |   보안   | `SecretStr` 타입의 키/비밀값                | `KISAuthStrategy(config)` 초기화          | 내부 변수(`self.app_key`)에는 **평문(str)**으로 복호화되어 저장됨                  | `app_key=SecretStr("xyz")`  |
|  **KIS-LIFE-01**   | 단위 |   상태   | `_access_token`이 `None` (초기 구동)        | `get_token(client)` 호출                  | 1. API 호출 발생<br>2. 토큰 및 만료시간 갱신<br>3. 유효한 토큰 문자열 반환         | Mock API: `200 OK`          |
|  **KIS-LIFE-02**   | 단위 |   BVA    | 토큰 유효, 만료 **11분** 남음 (버퍼 초과)   | `get_token(client)` 호출                  | **API 호출 없음** (메모리 캐시 반환)                                               | `expires_at = 현재 + 11분`  |
|  **KIS-LIFE-03**   | 단위 |   BVA    | 토큰 유효, 만료 **9분** 남음 (버퍼 진입)    | `get_token(client)` 호출                  | 1. API 호출 발생 (지연 갱신)<br>2. 새로운 토큰으로 교체됨                          | `expires_at = 현재 + 9분`   |
|  **KIS-LIFE-04**   | 단위 |   상태   | 토큰 존재하나, 시간상 **이미 만료됨**       | `get_token(client)` 호출                  | 1. API 호출 발생<br>2. 새로운 토큰으로 교체됨                                      | `expires_at = 현재 - 1분`   |
|  **KIS-CONC-01**   | 통합 |  동시성  | 토큰 만료 상태, 5개 코루틴 대기 중          | `asyncio.gather(get_token * 5)` 동시 실행 | 1. **실제 API 호출 횟수 == 1** (Locking 작동)<br>2. 5개 요청 모두 동일한 토큰 반환 | `Tasks = 5`                 |
| **KIS-KIS-API-01** | 단위 |   표준   | 표준 응답 (토큰 + 만료시간 포함)            | `_update_state(response)` 실행            | `_expires_at`이 응답값(`KIS_DATE_FORMAT`)에 맞춰 파싱됨                            | `expired="2025-12-31..."`   |
|   **KIS-API-02**   | 단위 |  견고성  | 응답에 `access_token_token_expired` 키 누락 | `_update_state(response)` 실행            | 1. 에러 없음<br>2. `_expires_at` = 현재 + 12시간 (기본값 설정)                     | `expired=None`              |
|   **KIS-API-03**   | 단위 |  견고성  | HTTP 200이나 본문에 `access_token` 없음     | `_validate_response(response)` 실행       | `AuthError` 발생 (유효성 검증 실패)                                                | Body: `{"msg": "실패"}`     |
|   **KIS-API-04**   | 단위 |  MC/DC   | 만료시간이 **비표준 형식** 문자열           | `_update_state(response)` 실행            | 1. `ValueError` 내부 처리(Catch)<br>2. 기본값(12시간) 적용                         | `expired="Invalid-Date"`    |
|   **KIS-ERR-01**   | 예외 | 조기실패 | API가 **401 Unauthorized** 응답             | `get_token(client)` 호출                  | 1. `AuthError` 발생<br>2. `NetworkError`로 감싸지지 않음 (재시도 중단)             | Mock API: `401 Error`       |
|   **KIS-ERR-02**   | 예외 | 조기실패 | API가 **403 Forbidden** 응답                | `get_token(client)` 호출                  | 1. `AuthError` 발생<br>2. 로그에 "Permanent Auth Failure" 기록                     | Mock API: `403 Error`       |
|   **KIS-ERR-03**   | 예외 |  견고성  | `_issue_token` 중 알 수 없는 예외 발생      | `get_token(client)` 호출                  | `AuthError`로 래핑되어 전파 (문맥 보존)                                            | Mock: `raise KeyError`      |
|   **KIS-ERR-04**   | 예외 |   로직   | `_issue_token` 수행 후에도 토큰이 `None`    | `get_token(client)` 호출                  | `AuthError("Failed to retrieve...")` 발생                                          | Mock: `_access_token=None`  |
|   **KIS-ERR-05**   | 예외 |  재시도  | API가 **500 Internal Error** 응답           | `_issue_token(client)` 직접 호출          | `NetworkError`가 **그대로 전파됨** (AuthError 변환 안 함 -> 재시도 트리거)         | Mock API: `500 Error`       |

### 3-2. UPBITAuthStrategy (Stateless Manufacturer) - [신규 추가]

**시나리오 요약:**

- **초기화 (Initialization):** 2건 (설정 누락 및 속성 부재 방어)
- **토큰 수명주기 및 무결성 (Lifecycle & Integrity):** 2건 (기본 토큰, 쿼리 해시 포함 토큰)
- **데이터 견고성 (Robustness):** 1건 (빈 파라미터 처리)
- **호환성 (Compatibility):** 1건 (PyJWT 라이브러리 버전별 반환 타입 대응)
- **보안 로직 (Security Logic):** 2건 (서명 알고리즘, 키 검증)
- **상태 및 보안 (State & Security):** 1건 (Nonce 유일성 - Replay Attack 방지)

|      테스트 ID      | 분류 |  기법  | 전제 조건 (Given)                          | 수행 (When)                                       | 검증 (Then)                                                                        | 입력 데이터 / 상황               |
| :-----------------: | :--: | :----: | :----------------------------------------- | :------------------------------------------------ | :--------------------------------------------------------------------------------- | :------------------------------- |
|  **UPBIT-INIT-01**  | 단위 |  BVA   | `base_url`이 비어있는 설정                 | `UPBITAuthStrategy(config)` 초기화                | `ValueError` 발생 (필수 설정 누락 방어)                                            | `base_url=""`                    |
|  **UPBIT-INIT-02**  | 단위 | 견고성 | 설정 객체에 `secret_key` 속성 자체가 없음  | `UPBITAuthStrategy(config)` 초기화                | `ValueError` 발생 (AttributeError 방지 및 명시적 에러)                             | Config without `secret_key` attr |
|  **UPBIT-LIFE-01**  | 단위 |  표준  | 정상 설정 완료                             | `get_token(client)` 호출 (인자 없음)              | 1. `Bearer {Token}` 형식 반환<br>2. Payload에 `access_key`, `nonce` 포함 확인      | `kwargs={}`                      |
|  **UPBIT-LIFE-02**  | 단위 | 무결성 | 쿼리 파라미터가 존재하는 요청              | `get_token(..., query_params=params)` 호출        | 1. Payload에 `query_hash` 필드 존재<br>2. **SHA512 해시값**이 실제 파라미터와 일치 | `params={'market': 'KRW-BTC'}`   |
|  **UPBIT-DATA-01**  | 단위 |  BVA   | 쿼리 파라미터가 비어있는 딕셔너리          | `get_token(..., query_params={})` 호출            | Payload에 `query_hash` 필드가 **포함되지 않음** (None과 동일 처리)                 | `params={}`                      |
| **UPBIT-COMPAT-01** | 단위 |  분기  | `jwt.encode`가 **bytes 타입**을 반환(Mock) | `get_token(client)` 호출                          | 내부적으로 `utf-8` 디코딩이 수행되어 최종적으로 **str 타입**의 토큰 반환           | `return_value=b"token"`          |
| **UPBIT-LOGIC-01**  | 단위 |  보안  | 토큰 생성 완료                             | JWT 헤더 디코딩                                   | 서명 알고리즘(`alg`)이 `HS256`으로 설정되어 있음                                   | `jwt.get_unverified_header()`    |
| **UPBIT-LOGIC-02**  | 단위 |  보안  | 서로 다른 Secret Key 사용                  | 생성된 토큰을 **잘못된 Key**로 디코딩 시도        | `jwt.InvalidSignatureError` 발생 (올바른 Key로 서명되었음을 역검증)                | `decode(token, wrong_key)`       |
|  **UPBIT-SEC-01**   | 단위 |  보안  | 정상 설정 완료                             | `get_token`을 **연속 2회** 호출하여 토큰 2개 확보 | 두 토큰의 Payload 내 **`nonce` 값이 서로 다름** (Replay Attack 방지)               | `token1 != token2`               |
