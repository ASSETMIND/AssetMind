# KIS Extractor Test Specification (Fixed)

## 1. 개요 (Overview)

- **대상 모듈:** `kis_extractor.py` (KISExtractor 클래스)
- **테스트 목적:** KIS 데이터 수집기의 설정 로딩, 요청 검증, 파라미터 병합 로직, 외부 API 호출, 응답 처리 및 모든 예외 상황에 대한 방어 로직 검증.
- **테스트 범위:** `__init__`, `extract`, `_validate_request`, `_fetch_raw_data`, `_create_response` 메서드 전체.

## 2. 테스트 환경 및 전략 (Environment & Strategy)

- **Test Runner:** Pytest (Asyncio plugin required)
- **Mocking:** `IHttpClient`, `IAuthStrategy`, `AppConfig` (Pydantic Model)
- **Coverage:** 13 Scenarios (Happy Path, Boundary, Null/Type, Logical Exception, Resource/State)

## 3. 테스트 케이스 명세 (Test Cases)

|  Test ID   |   Category    | Source Scenario | Given (Preconditions)                                                                                                                    | When (Action)                         | Then (Expected Outcome)                                                                 | Input Data             | Priority |
| :--------: | :-----------: | :-------------: | :--------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------ | :-------------------------------------------------------------------------------------- | :--------------------- | :------: |
| **TC-001** | Unit (Happy)  |      SC-01      | 1. 정상 Config(KIS Provider, 필수값 포함) 로드됨.<br>2. AuthStrategy가 유효 토큰 반환.<br>3. HttpClient가 `rt_cd: "0"`인 정상 JSON 응답. | `extract(request)` 호출               | 1. `ResponseDTO` 반환.<br>2. `data`가 Mock 응답과 일치.<br>3. `meta.status_code`가 "0". | `job_id="valid_job"`   |   High   |
| **TC-002** | Unit (Logic)  |      SC-02      | 1. Policy에 `{count: 10}` 존재.<br>2. Request에 `{date: '20240101'}` 존재 (서로 다른 키).                                                | `extract(request)` 호출               | 1. HttpClient 호출 시 파라미터가 `{count: 10, date: '20240101'}`로 병합됨.              | `params={'date':...}`  |  Medium  |
| **TC-003** |  Unit (Edge)  |      SC-03      | 1. Policy에 `{count: 10}` 존재.<br>2. Request에 `{count: 50}` 존재 (동일 키).                                                            | `extract(request)` 호출               | 1. HttpClient 호출 시 파라미터가 `{count: 50}`으로 Request 값이 우선 적용됨.            | `params={'count': 50}` |  Medium  |
| **TC-004** |  Unit (Edge)  |      SC-04      | 1. Policy에 `{count: 10}` 존재.<br>2. Request params가 비어있음(Empty Dict).                                                             | `extract(request)` 호출               | 1. HttpClient 호출 시 Policy 파라미터 `{count: 10}`이 그대로 사용됨.                    | `params={}`            |  Medium  |
| **TC-005** | Unit (Valid)  |      SC-05      | 1. 정상 Config 로드됨.                                                                                                                   | `extract(request)` 호출 (job_id 누락) | `ExtractorError` 발생 ("Invalid Request: 'job_id' is mandatory").                       | `job_id=None`          |   High   |
| **TC-006** |  Unit (Edge)  |      SC-06      | 1. HttpClient가 `rt_cd` 키가 없는 정상 JSON(`{"msg": "ok"}`)을 반환.                                                                     | `extract(request)` 호출               | `ExtractorError` 발생 (rt_cd="0"이 아니므로 실패로 간주).                               | `job_id="valid_job"`   |   Low    |
| **TC-007** | Unit (Config) |      SC-07      | 1. `kis.base_url`이 비어있는(`""`) Config 객체 준비.                                                                                     | `KISExtractor` 인스턴스 생성 시도     | 생성자(`__init__`) 실행 중 `ExtractorError` 발생 ("Critical Config Error...").          | `base_url=""`          |   High   |
| **TC-008** | Unit (Config) |      SC-08      | 1. 요청한 `job_id`가 Config의 `extraction_policy` 딕셔너리에 없음.                                                                       | `extract(request)` 호출               | `ExtractorError` 발생 ("Policy not found...").                                          | `job_id="unknown"`     |  Medium  |
| **TC-009** | Unit (Config) |      SC-09      | 1. 해당 `job_id`의 Policy Provider가 "FRED"로 설정됨.                                                                                    | `extract(request)` 호출               | `ExtractorError` 발생 ("Provider Mismatch...").                                         | `job_id="fred_job"`    |  Medium  |
| **TC-010** | Unit (Config) |      SC-10      | 1. 해당 `job_id`의 Policy가 존재하나, `tr_id` 필드가 누락됨(None).                                                                       | `extract(request)` 호출               | `ExtractorError` 발생 ("'tr_id' is missing...").                                        | `job_id="no_tr_id"`    |  Medium  |
| **TC-011** |  Unit (Biz)   |      SC-11      | 1. HttpClient가 `rt_cd: "1"` (실패) 및 에러 메시지(`msg1`)를 반환.                                                                       | `extract(request)` 호출               | `ExtractorError` 발생 (메시지에 API 응답 `msg1` 내용 포함).                             | `rt_cd="1"`            |   High   |
| **TC-012** | Unit (Error)  |      SC-12      | 1. `auth_strategy.get_token()` 메서드가 `Exception`을 발생시킴.                                                                          | `extract(request)` 호출               | `ExtractorError`로 래핑되어 발생 ("System Error...").                                   | `job_id="valid_job"`   |  Medium  |
| **TC-013** | Unit (Error)  |      SC-13      | 1. `http_client.get()` 호출 시 네트워크 에러(Timeout 등) 발생.                                                                           | `extract(request)` 호출               | `ExtractorError`로 래핑되어 발생 ("System Error...").                                   | `Exception(...)`       |   High   |
