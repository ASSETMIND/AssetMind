# KISExtractor Test Specification

## 1. 개요

- **대상 모듈:** `KISExtractor` (kis_extractor.py)
- **작성 목적:** 외부 설정 의존성이 높은 수집기의 초기화, 요청 검증, API 통신, 응답 처리 로직의 무결성 검증.
- **테스트 범위:**
  - `__init__`: 설정 유효성 검사.
  - `_validate_request`: 정책 매핑 및 필수 키 검사.
  - `_fetch_raw_data`: 파라미터 병합 및 HTTP 요청 구성.
  - `_create_response`: `rt_cd` 기반의 비즈니스 성공/실패 판별.

## 2. 테스트 환경 및 전략

- **Mocking:** `IHttpClient`, `IAuthStrategy`, `AppConfig`는 모두 Mock 객체로 대체.
- **Async Testing:** `pytest-asyncio` 사용.

## 3. 테스트 케이스 명세

|  Test ID   | Category  | Given (Preconditions)                                                        | When (Action)                                           | Then (Expected Outcome)                                                                                | Input Data                                     | Priority |
| :--------: | :-------: | :--------------------------------------------------------------------------- | :------------------------------------------------------ | :----------------------------------------------------------------------------------------------------- | :--------------------------------------------- | :------: |
| **TC-001** |   Unit    | 유효한 BaseURL, Policy가 설정된 Config와 토큰 발급 가능한 Auth 전략이 주어짐 | `_fetch_raw_data(request)` 호출                         | 1. AuthStrategy가 1회 호출됨<br>2. HTTP Client가 1회 호출됨<br>3. 반환된 Raw Data가 Mock 응답과 일치함 | `request(job_id="daily_price")`                |   High   |
| **TC-002** |   Unit    | Policy에 `params={'a': 1}`이 있고, Request에 `params={'a': 99}`가 있음       | `_fetch_raw_data(request)` 호출                         | HTTP 호출 시 Params가 `{'a': 99}`로 전달됨 (Request 파라미터가 덮어씀)                                 | `request(params={'a': 99})`                    |  Medium  |
| **TC-003** |   Unit    | Policy에 `extra_headers={'X-Test': '1'}`이 정의됨                            | `_fetch_raw_data(request)` 호출                         | HTTP 호출 헤더에 `X-Test: 1`과 `authorization` 토큰이 모두 포함됨                                      | `request(job_id="custom_header_job")`          |   Low    |
| **TC-004** |   Unit    | Config 객체에 `kis_base_url` 속성이 없거나 비어있음                          | `KISExtractor(client, auth, config)` 인스턴스 생성 시도 | `ExtractorError` 예외 발생 ("Critical Config Error" 포함)                                              | `config(kis_base_url=None)`                    |   High   |
| **TC-005** |   Unit    | Config 객체에 `extraction_policy`가 딕셔너리가 아님                          | `KISExtractor` 인스턴스 생성 시도                       | `ExtractorError` 예외 발생 ("extraction_policy dictionary is missing" 포함)                            | `config(extraction_policy=None)`               |   High   |
| **TC-006** | Exception | `request.job_id`가 `None`임                                                  | `_validate_request(request)` 호출                       | `ExtractorError` 예외 발생 ("Invalid Request" 포함)                                                    | `request(job_id=None)`                         |   High   |
| **TC-007** | Exception | `request.job_id`에 해당하는 키가 Policy 설정에 없음                          | `_validate_request(request)` 호출                       | `ExtractorError` 예외 발생 ("Policy not found" 포함)                                                   | `request(job_id="unknown_job")`                |  Medium  |
| **TC-008** | Exception | Policy는 존재하나 필수 키(`path` 혹은 `tr_id`)가 누락됨                      | `_validate_request(request)` 호출                       | `ExtractorError` 예외 발생 ("Policy ... is incomplete" 포함)                                           | `policy={"params": {}}`                        |  Medium  |
| **TC-009** | Exception | `auth_strategy.get_token()`이 예외를 발생시킴                                | `_fetch_raw_data(request)` 호출                         | 예외가 처리되지 않고 상위로 전파됨 (Fail Fast)                                                         | `auth_mock.side_effect=Exception`              |  Medium  |
| **TC-010** | Exception | API 응답(`raw_data`)의 `rt_cd`가 "0"이 아님 (예: "1")                        | `_create_response(raw_data)` 호출                       | `ExtractorError` 예외 발생 (메시지에 `msg1` 내용 포함)                                                 | `raw={"rt_cd": "1", "msg1": "Limit Exceeded"}` |   High   |
| **TC-011** | Exception | API 응답(`raw_data`)에 `rt_cd` 필드가 없음                                   | `_create_response(raw_data)` 호출                       | `ExtractorError` 예외 발생                                                                             | `raw={"data": []}` (Empty meta)                |  Medium  |
| **TC-012** |   Unit    | API 응답의 `rt_cd`가 "0"임                                                   | `_create_response(raw_data)` 호출                       | 1. `ResponseDTO` 반환<br>2. `meta.status_code`가 "0"임<br>3. `data` 필드가 원본과 동일함               | `raw={"rt_cd": "0", "output": []}`             |   High   |
