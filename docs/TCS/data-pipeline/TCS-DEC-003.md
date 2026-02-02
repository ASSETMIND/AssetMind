# Rate Limit Decorator - Test Specification

## 1. 개요

- **Target Module:** `rate_limit_decorator.py`
- **Purpose:** API 호출 속도 제한(Throttling) 기능의 정확성, 동시성 안전성, 자원 관리 효율성을 검증.
- **Scope:** 동기(Sync)/비동기(Async) 래퍼, 전역 상태 관리(Bucket Sharing), 에러 핸들링.

## 2. 테스트 전략

- **Mocking:** `time.time`, `time.sleep`, `asyncio.sleep`을 Mocking하여 실제 시간을 기다리지 않고 밀리초 단위로 제어 및 검증.
- **Concurrency:** `asyncio.gather` 및 `ThreadPoolExecutor`를 사용하여 Race Condition 시뮬레이션.
- **Verification:** 실행 시간(Duration) 측정 및 내부 `Bucket` 상태 검사를 통한 검증.

## 3. 테스트 케이스 명세

|  Test ID   |      Category       | Given (Preconditions)                                           | When (Action)                                                            | Then (Expected Outcome)                                                                                                  | Input Data                | Priority |
| :--------: | :-----------------: | :-------------------------------------------------------------- | :----------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------- | :------------------------ | :------: |
| **TC-001** |     Unit (Sync)     | `limit=5`, `period=1.0`으로 설정된 동기 함수.                   | 루프를 통해 함수를 **5회 연속** 호출한다.                                | 1. 모든 호출이 즉시 반환된다.<br>2. 총 소요 시간이 0.1초 미만이다.                                                       | `limit=5`, `period=1.0`   |   High   |
| **TC-002** |    Unit (Async)     | `limit=5`, `period=1.0`으로 설정된 **비동기** 함수.             | `await`를 사용하여 함수를 **5회 연속** 호출한다.                         | 1. 모든 호출이 즉시 반환된다.<br>2. `asyncio.sleep`이 호출되지 않는다.                                                   | `limit=5`, `period=1.0`   |   High   |
| **TC-003** |     Unit (Sync)     | `limit=1`, `period=1.0`으로 설정된 동기 함수.                   | 함수를 **2회 연속** 호출한다.                                            | 1. 첫 번째 호출은 즉시 반환된다.<br>2. 두 번째 호출은 약 1.0초 지연 후 반환된다.<br>3. `time.sleep`이 1회 호출된다.      | `limit=1`, `period=1.0`   |   High   |
| **TC-004** |    Unit (Async)     | `limit=1`, `period=1.0`으로 설정된 **비동기** 함수.             | `await`를 사용하여 함수를 **2회 연속** 호출한다.                         | 1. 두 번째 호출 시 지연이 발생한다.<br>2. `asyncio.sleep`이 정확한 대기 시간만큼 호출된다.                               | `limit=1`, `period=1.0`   |   High   |
| **TC-005** |      Boundary       | `limit=5`인 함수.                                               | 함수를 **6회** 호출한다.                                                 | 1. 1~5회 호출은 즉시 성공한다.<br>2. **정확히 6번째** 호출에서만 스로틀링이 발생한다 (Off-by-one 체크).                  | `limit=5`, `period=1.0`   | Critical |
| **TC-006** |      Boundary       | `limit` 횟수만큼 호출하여 버킷을 소진한 상태.                   | `period` 시간이 **지난 후** 다시 호출한다 (Time Travel).                 | 버킷이 초기화되어, 즉시 실행되어야 한다 (대기 시간 0).                                                                   | `limit=1`, `period=1.0`   |   High   |
| **TC-007** |   Logic (Config)    | `bucket_key=None`으로 설정된 서로 다른 두 함수 A, B.            | A를 `limit`만큼 호출한 뒤, 즉시 B를 호출한다.                            | A의 호출 횟수가 B에 영향을 주지 않아, B는 즉시 실행된다 (독립 버킷).                                                     | `key=None`                |   Med    |
| **TC-008** |   Logic (Config)    | `bucket_key="API_KEY_1"`을 **공유**하는 서로 다른 두 함수 A, B. | A를 `limit`만큼 호출한 뒤, 즉시 B를 호출한다.                            | B는 A와 제한을 공유하므로, **실행이 지연(Throttle)**되어야 한다.                                                         | `key="SHARED"`            |   High   |
| **TC-009** |    Logic (Math)     | 이미 `limit`에 도달한 상태.                                     | 현재 시간이 타임스탬프보다 아주 미세하게 경과함 (`wait_time` 계산 검증). | `wait_time`이 음수가 되지 않고, `0.0` 또는 양수로 보정되어 반환된다.                                                     | `limit=1`                 |   Med    |
| **TC-010** |      Resource       | `limit`가 매우 크고, `period`가 긴 상황.                        | 장시간 동안 수천 번 호출을 시뮬레이션한다.                               | 내부 `deque`의 크기가 무한히 늘어나지 않고, `_cleanup`에 의해 관리된다.                                                  | `limit=100`               |   Low    |
| **TC-011** |      Exception      | `LogManager` 모듈이 없는 환경 (ImportError).                    | 스로틀링을 유발하여 로그 출력을 시도한다.                                | 예외(Crash) 없이 함수가 정상 실행되어야 한다 (Silent Fail).                                                              | `limit=1`                 |   Med    |
| **TC-012** |     Integration     | `LogManager`가 정상적으로 존재하는 환경.                        | 스로틀링을 유발한다.                                                     | `LogManager.get_logger`가 호출되고, "Throttling active" 로그가 기록된다.                                                 | `limit=1`                 |   Low    |
| **TC-013** |    Logic (Wait)     | `wait_time`이 매우 짧은 경우 (예: 0.0001초).                    | 함수를 호출한다.                                                         | `_log_throttling` 내부 로직에 의해 로그가 남지 않아야 한다 (Noise 감소).                                                 | `wait_time=0.05`          |   Low    |
| **TC-014** | Concurrency (Async) | `limit=5`인 비동기 함수.                                        | `asyncio.gather`로 **10개의 요청을 동시**에 보낸다.                      | 1. 5개는 즉시 완료, 5개는 지연된다.<br>2. 내부 `timestamps` 덱의 길이가 10을 초과하지 않고 꼬이지 않는다.                | `limit=5`, `Concurrent`   | Critical |
| **TC-015** | Concurrency (Sync)  | `limit=5`인 동기 함수.                                          | `ThreadPoolExecutor`로 **10개의 스레드**에서 동시에 호출한다.            | 1. (현재 코드의 결함 예상) Race Condition 없이 정확히 5개만 즉시 통과하는지 검증.<br>2. `timestamps` 데이터 무결성 확인. | `limit=5`, `Multi-Thread` | Critical |
