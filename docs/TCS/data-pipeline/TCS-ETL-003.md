# FRED Extractor Test Specification

## 1. 개요

- **Target Module:** `src.extractor.providers.fred_extractor.FREDExtractor`
- **Purpose:** FRED API 호출 로직의 정합성, 파라미터 병합 우선순위, JSON 강제 변환 로직 및 예외 처리를 검증.
- **Reference:** `kis_extractor_test.py` (구조적 일관성 유지)

## 2. 테스트 환경 및 전략

- **Mocking:**
  - `IHttpClient`: 실제 외부 API 호출 차단 및 응답 조작.
  - `AppConfig`: Pydantic 검증 로직 격리 및 테스트용 정책(Policy) 주입.
  - `LogManager`: `src.extractor.providers.abstract_extractor` 내부의 로거 호출을 Patch하여 Global Config 의존성 제거 (Critical).
- **Assertions:**
  - `RequestDTO` -> `Params Merge` -> `HttpClient Call` -> `ResponseDTO` 흐름 검증.
  - `file_type=json` 및 `api_key` 주입 여부 필수 검증.

## 3. 테스트 케이스 명세

|  Test ID   | Category  | Given (Preconditions)                                                                                 | When (Action)           | Then (Expected Outcome)                                                                             | Input Data                    | Priority |
| :--------: | :-------: | :---------------------------------------------------------------------------------------------------- | :---------------------- | :-------------------------------------------------------------------------------------------------- | :---------------------------- | :------- |
| **TC-001** |   Unit    | 1. Config 정상 설정<br>2. Policy에 `series_id` 존재<br>3. API가 정상 JSON 반환 (`error_message` 없음) | `extract(request)` 호출 | 1. `ResponseDTO` 반환 성공<br>2. `source`="FRED"<br>3. `status_code`="200"<br>4. HTTP 호출 1회 발생 | `job_id="valid_job"`          | High     |
| **TC-002** |   Unit    | 1. Policy Params: `{'freq': 'm'}`<br>2. Request Params: `{'start': '2020'}`                           | `extract(request)` 호출 | HTTP 호출 시 파라미터가 `{freq, start, api_key, file_type}` 모두 포함되어야 함                      | `params={'start': '2020'}`    | Medium   |
| **TC-003** |   Unit    | 1. Request Params에 `file_type='xml'` 포함                                                            | `extract(request)` 호출 | **[FRED 특화]**<br>HTTP 호출 시 `file_type` 파라미터가 반드시 `'json'`으로 강제 변환되어야 함       | `params={'file_type': 'xml'}` | High     |
| **TC-004** |   Unit    | 1. Config API Key = `'SECRET'`                                                                        | `extract(request)` 호출 | **[FRED 특화]**<br>HTTP 호출 파라미터에 `api_key='SECRET'`가 포함되어야 함                          | `job_id="valid_job"`          | High     |
| **TC-005** |   Unit    | 1. Policy Params에 `series_id` 없음<br>2. Request Params에 `series_id` 존재                           | `extract(request)` 호출 | 정상 처리 (Request 파라미터로 필수값 충족)                                                          | `params={'series_id': 'GDP'}` | Medium   |
| **TC-006** |   Edge    | 1. Request Params가 `{}` (Empty)                                                                      | `extract(request)` 호출 | Policy에 정의된 기본 파라미터만 사용하여 호출                                                       | `params={}`                   | Low      |
| **TC-007** |   Unit    | 1. Config의 `fred.base_url`이 비어있음                                                                | `FREDExtractor` 초기화  | `ExtractorError("Critical Config Error...")` 발생                                                   | `Config(base_url="")`         | High     |
| **TC-008** | Exception | 1. Request의 `job_id`가 `None`                                                                        | `extract(request)` 호출 | `ExtractorError("Invalid Request...")` 발생                                                         | `request(job_id=None)`        | Medium   |
| **TC-009** | Exception | 1. 요청한 `job_id`가 Config Policy에 없음                                                             | `extract(request)` 호출 | `ExtractorError("Policy not found...")` 발생                                                        | `job_id="unknown"`            | Medium   |
| **TC-010** | Exception | 1. Policy의 Provider가 "FRED"가 아님 (예: "KIS")                                                      | `extract(request)` 호출 | `ExtractorError("Provider Mismatch...")` 발생                                                       | `job_id="kis_job"`            | Medium   |
| **TC-011** | Exception | 1. Policy와 Request 양쪽 모두 `series_id` 누락                                                        | `extract(request)` 호출 | `ExtractorError("Missing Parameter: 'series_id'...")` 발생                                          | `params={}`                   | High     |
| **TC-012** | Exception | 1. API 응답(200 OK) Body에 `{"error_message": "Bad Request"}` 포함                                    | `extract(request)` 호출 | **[FRED 특화]**<br>`ExtractorError("FRED API Failed: Bad Request...")` 발생                         | `job_id="valid_job"`          | High     |
| **TC-013** | Exception | 1. HTTP Client가 예기치 않은 Exception 발생                                                           | `extract(request)` 호출 | 로깅 후 `ExtractorError("System Error: ...")` 래핑 발생                                             | `job_id="valid_job"`          | Low      |
