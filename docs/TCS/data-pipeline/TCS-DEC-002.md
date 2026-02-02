# 테스트 명세서: Retry Decorator Module

## 1. 개요 (Overview)

- **대상 모듈:** `retry_decorator.py`
- **작성 목적:** \* 재시도 로직(Exponential Backoff, Jitter)의 수학적 정확성 검증.
  - 동기(Sync) 및 비동기(Async) 함수의 투명한 래핑(Wrapping) 보장.
  - 예외 처리 전략(Whitelist, Blacklist) 및 로깅 동작 확인.
- **테스트 범위:** \* `RetryDecorator` 클래스의 단위 테스트(Unit Test).
  - 시간 지연(`time.sleep`, `asyncio.sleep`) 및 로깅(`LogManager`)은 Mocking을 통해 검증하여 테스트 속도와 격리성 확보.

## 2. 테스트 환경 및 전략 (Test Environment & Strategy)

- **Test Framework:** `pytest`, `pytest-asyncio`
- **Mocking:** `unittest.mock.MagicMock`, `pytest-mock`을 사용하여 외부 의존성 제거.
- **Validation Strategy:**
  - **Behavior Verification:** 함수가 `max_retries`만큼 호출되었는가? (`call_count`)
  - **State Verification:** 반환된 대기 시간이 수식과 일치하는가?
  - **Logging Verification:** 경고(Warning) 및 에러(Error) 로그가 적절한 시점에 기록되었는가?

## 3. 테스트 케이스 명세 (Test Case Specification)

| Test ID |  Category   | Given (Preconditions)                                               | When (Action)                                                              | Then (Expected Outcome)                                                                              | Input Data             | Priority |
| :-----: | :---------: | :------------------------------------------------------------------ | :------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :--------------------- | :------- |
| TC-001  | Happy Path  | 동기(Sync) 함수가 정상 동작하도록 설정됨                            | 데코레이터가 적용된 동기 함수를 호출함                                     | 1. 원본 함수가 정확히 1회 실행됨<br>2. 원본 반환값을 리턴함<br>3. 재시도 로직(sleep)이 수행되지 않음 | `args=(10, 20)`        | High     |
| TC-002  | Happy Path  | 비동기(Async) 코루틴이 정상 동작하도록 설정됨                       | 데코레이터가 적용된 비동기 함수를 `await`로 호출함                         | 1. 원본 코루틴이 정확히 1회 실행됨<br>2. 원본 반환값을 리턴함<br>3. `await`가 정상 처리됨            | `args=("data",)`       | High     |
| TC-003  | Happy Path  | 동기 함수가 2회 실패 후 3회째 성공하도록 설정됨 (`max_retries=3`)   | 데코레이터가 적용된 함수를 호출함                                          | 1. 원본 함수가 총 3회 실행됨<br>2. 최종적으로 성공 결과를 반환함<br>3. 예외가 외부로 전파되지 않음   | `Fail, Fail, Success`  | High     |
| TC-004  | Happy Path  | 비동기 함수가 1회 실패 후 2회째 성공하도록 설정됨 (`max_retries=3`) | 데코레이터가 적용된 비동기 함수를 호출함                                   | 1. 원본 코루틴이 총 2회 실행됨<br>2. 최종적으로 성공 결과를 반환함                                   | `Fail, Success`        | High     |
| TC-005  |  Boundary   | 재시도 횟수가 0으로 설정됨 (`max_retries=0`)                        | 함수가 무조건 예외를 발생시키도록 호출함                                   | 1. 함수가 단 1회만 실행됨<br>2. 즉시 예외가 발생함 (재시도 없음)                                     | `max_retries=0`        | Medium   |
| TC-006  |  Boundary   | 최대 대기 시간이 0.5초로 제한됨 (`max_delay=0.5`)                   | 계산된 백오프 시간이 제한을 초과하는 차수(예: 10회차)의 대기 시간을 계산함 | 1. 반환된 대기 시간이 `0.5 + jitter`를 초과하지 않음                                                 | `base=1, factor=2`     | Medium   |
| TC-007  |  Boundary   | 기본 대기 시간 1초, 배수 2.0으로 설정됨                             | 3번째 시도(attempt=3)의 대기 시간을 계산함                                 | 1. 대기 시간이 `1.0 * (2.0 ^ 2) = 4.0초` 근사값인지 확인함 (Jitter 고려)                             | `attempt=3`            | Medium   |
| TC-008  | Null & Type | 인자를 그대로 반환하는 함수가 정의됨                                | 위치 인자(`args`)와 키워드 인자(`kwargs`)를 섞어서 호출함                  | 1. 원본 함수에 인자가 변형 없이 그대로 전달됨을 확인함                                               | `(1, b=2)`             | High     |
| TC-009  | Null & Type | `None` 또는 복잡한 객체를 반환하는 함수가 정의됨                    | 함수를 호출하여 반환값을 받음                                              | 1. 데코레이터가 반환값을 가로채거나 변경하지 않고 그대로 반환함                                      | `return None`          | Medium   |
| TC-010  | Null & Type | 인자 없이 데코레이터 클래스를 초기화함                              | 인스턴스의 속성(`max_retries`, `base_delay`)을 확인함                      | 1. 정의된 상수(Constants) 값이 기본값으로 설정됨                                                     | `RetryDecorator()`     | Low      |
| TC-011  |  Exception  | 함수가 `max_retries` 횟수보다 많이 실패하도록 설정됨                | 함수를 호출함                                                              | 1. `max_retries + 1`회 실행됨 (최초 + 재시도)<br>2. 마지막에 발생한 예외가 호출자에게 전파됨         | `All Fail`             | High     |
| TC-012  |  Exception  | `ValueError`에 대해서만 재시도하도록 설정됨                         | 함수가 `ValueError`를 발생시키다가 성공하도록 호출함                       | 1. 정상적으로 재시도를 수행하고 성공함                                                               | `exception=ValueError` | Medium   |
| TC-013  |  Exception  | `ValueError`에 대해서만 재시도하도록 설정됨                         | 함수가 `KeyError` (설정되지 않은 예외)를 발생시킴                          | 1. 재시도 없이 즉시 `KeyError`가 전파됨<br>2. 실행 횟수는 1회여야 함                                 | `exception=ValueError` | Medium   |
| TC-014  |  Exception  | `(ValueError, KeyError)` 두 가지 예외를 허용하도록 설정됨           | 함수가 `KeyError` 발생 후 성공하도록 호출함                                | 1. `KeyError`를 잡아서 재시도를 수행하고 성공함                                                      | `exceptions=(VE, KE)`  | Medium   |
| TC-015  |  Resource   | `jitter=True`로 설정됨                                              | 동일한 차수(attempt=1)로 대기 시간을 2회 계산함                            | 1. 두 결과값이 서로 달라야 함 (Randomness 검증)<br>2. 차이가 0.1초 이내여야 함                       | `jitter=True`          | Low      |
| TC-016  |  Resource   | 로거(Logger)가 Mocking 됨                                           | 함수가 1회 실패 후 재시도하도록 호출함                                     | 1. `logger.warning`이 호출됨<br>2. 로그 메시지에 "RETRY", 현재 횟수, 대기 시간이 포함됨              | `LogManager`           | Medium   |
| TC-017  |  Resource   | 로거(Logger)가 Mocking 됨                                           | 함수가 모든 재시도를 실패하도록 호출함                                     | 1. 마지막에 `logger.error`가 호출됨<br>2. 로그 메시지에 "GAVE UP"이 포함됨                           | `LogManager`           | Medium   |
