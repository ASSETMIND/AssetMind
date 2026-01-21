# [Test Spec] AsyncHttpAdapter

## 1. 개요 (Overview)

- **대상 모듈:** `AsyncHttpAdapter`
- **작성 목적:** `aiohttp` 라이브러리를 감싸는 어댑터 패턴 구현체가 도메인 요구사항(예외 변환, 세션 재사용, 안전한 리소스 관리)을 충실히 이행하는지 검증하기 위함.
- **테스트 범위:** - `aiohttp` 세션 라이프사이클 관리 (Creation, Reuse, Closing)
  - HTTP 메서드(GET/POST) 정상 동작 및 Payload 전달
  - 네트워크 에러 및 HTTP 에러(4xx, 5xx)의 `NetworkError` 변환 로직
  - 응답 데이터 파싱(JSON vs Text) 및 Fallback 로직

## 2. 테스트 환경 및 전략 (Environment & Strategy)

- **Testing Framework:** `pytest` (Runner), `pytest-asyncio` (Async Support)
- **Mocking Tool:** `unittest.mock.MagicMock` 및 `unittest.mock.patch`
  - 외부 네트워크 호출을 차단하고, `aiohttp.ClientSession`의 행위를 모킹하여 결정적인(Deterministic) 테스트 수행.
  - Context Manager (`__aenter__`, `__aexit__`) 동작 검증을 위해 Mock 객체의 매직 메서드 활용.
- **Validation Strategy:** - **Status:** `pytest.raises`를 사용하여 정확한 커스텀 예외(`NetworkError`) 발생 여부 확인.
  - **State:** `id(session)` 비교를 통해 세션 객체의 싱글톤(Singleton-like) 동작 검증.
  - **Data:** 반환된 데이터의 타입(`dict` vs `str`) 및 값 검증.

## 3. 테스트 케이스 명세 (Test Case Specification)

|  Test ID   | Category  | Given (Preconditions)                                                                         | When (Action)                                          | Then (Expected Outcome)                                                                             | Input Data                             | Priority |
| :--------: | :-------: | :-------------------------------------------------------------------------------------------- | :----------------------------------------------------- | :-------------------------------------------------------------------------------------------------- | :------------------------------------- | :------- |
| **TC-001** |   Unit    | 서버가 `200 OK`와 `Content-Type: application/json` 헤더, 유효한 JSON 바디를 반환하도록 설정됨 | `adapter.get(url)`을 호출                              | 1. `NetworkError`가 발생하지 않음<br>2. 반환값이 Python Dict 형태임<br>3. JSON 데이터가 일치함      | `url="http://test.com/json"`           | High     |
| **TC-002** |   Unit    | 서버가 `200 OK`와 JSON 데이터를 반환하도록 설정됨 (POST)                                      | `adapter.post(url, data=payload)`를 호출               | 1. 요청 바디(payload)가 올바르게 전송됨<br>2. 응답이 정상적으로 파싱됨                              | `url="..."`, `data={"key": "val"}`     | High     |
| **TC-003** |   Unit    | Adapter 인스턴스가 생성됨                                                                     | `async with adapter as client:` 구문 실행 후 블록 탈출 | 1. 블록 내부에서 `_session`이 생성됨<br>2. 블록 탈출 후 `_session.closed`가 `True`여야 함           | N/A                                    | Medium   |
| **TC-004** |   Unit    | 서버가 `200 OK`와 `Content-Type: text/html`을 반환하도록 설정됨                               | `adapter.get(url)`을 호출                              | 1. JSON 파싱을 시도하지 않음<br>2. 응답 본문을 `str` (Text) 형태로 반환                             | `url="http://test.com/text"`           | Medium   |
| **TC-005** | Boundary  | 서버가 `204 No Content` (Empty Body)를 반환하도록 설정됨                                      | `adapter.get(url)`을 호출                              | 1. 에러가 발생하지 않음<br>2. 빈 문자열(`""`) 또는 `None` 반환 (구현에 따라 확인)                   | `url="http://test.com/empty"`          | Low      |
| **TC-006** | Boundary  | 서버가 헤더는 `application/json`이나, **깨진 JSON 본문**(`{invalid...`)을 반환함              | `adapter.get(url)`을 호출                              | 1. `JSONDecodeError`가 외부로 전파되지 않음<br>2. 내부 로직이 Fallback하여 Raw Text를 반환함        | `url="http://test.com/bad-json"`       | Medium   |
| **TC-007** |   Unit    | Adapter 초기화 시 `timeout=10` 설정                                                           | `adapter._get_session()` 내부적으로 호출               | 생성된 `aiohttp.ClientSession`의 `timeout.total` 속성이 10이어야 함                                 | `timeout=10`                           | Low      |
| **TC-008** |   Unit    | 입력 파라미터가 모두 `None`인 상태                                                            | `adapter.get(url, headers=None, params=None)` 호출     | 내부적으로 `headers`나 `params` 처리가 `None` 안전하여 크래시가 나지 않음                           | `headers=None`                         | Low      |
| **TC-009** |   Unit    | 서버 응답에 `Content-Type` 헤더가 누락됨                                                      | `adapter.get(url)` 호출                                | Content-Type 확인 로직에서 에러 없이 Text 모드로 동작하여 응답 반환                                 | `Mock Response(headers={})`            | Low      |
| **TC-010** | Exception | 서버가 `404 Not Found` 에러를 반환하도록 설정됨                                               | `adapter.get(url)` 호출                                | 1. `NetworkError` 예외 발생 (Not aiohttp error)<br>2. 에러 메시지에 "404" 및 URL 포함               | `status=404`                           | High     |
| **TC-011** | Exception | 서버가 `500 Internal Server Error`를 반환하도록 설정됨                                        | `adapter.post(url)` 호출                               | 1. `NetworkError` 예외 발생<br>2. 에러 메시지에 "500" 포함                                          | `status=500`                           | High     |
| **TC-012** | Exception | DNS 조회 실패 또는 연결 거부 (`aiohttp.ClientConnectorError`) 상황 모의                       | `adapter.get(url)` 호출                                | 1. `NetworkError` 예외 발생<br>2. 원본 예외(`from e`)가 체이닝되어야 함                             | `Mock SideEffect=ClientConnectorError` | High     |
| **TC-013** | Exception | 요청 시간이 타임아웃 초과 (`asyncio.TimeoutError`) 상황 모의                                  | `adapter.get(url)` 호출                                | 1. `NetworkError` 예외 발생<br>2. 메시지에 타임아웃 관련 내용 포함                                  | `Mock SideEffect=TimeoutError`         | High     |
| **TC-014** |   State   | Adapter 인스턴스 초기화 상태                                                                  | `get()`을 2회 연속 호출                                | 두 호출 시 사용된 `self._session` 객체의 `id()`가 동일해야 함 (세션 재사용 검증)                    | N/A                                    | High     |
| **TC-015** |   State   | `adapter.close()`가 호출되어 세션이 닫힌 상태                                                 | 다시 `adapter.get(url)` 호출                           | 1. `Session is closed` 에러가 나지 않음<br>2. 새로운 세션이 생성되어 요청이 성공함 (Auto Reconnect) | N/A                                    | Medium   |
| **TC-016** |   State   | 이미 닫힌 Adapter                                                                             | `adapter.close()`를 한번 더 호출                       | 중복 호출에도 예외가 발생하지 않고 조용히 처리됨                                                    | N/A                                    | Low      |
