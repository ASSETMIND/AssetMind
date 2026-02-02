# ECOS Extractor Test Specification

## 1. 개요

- **Target Module:** `src.extractor.providers.ecos_extractor.ECOSExtractor`
- **Purpose:** ECOS API 특유의 Path Variable 기반 URL 조립 정합성, 필수 날짜 파라미터 검증, 그리고 응답 코드(INFO-000) 처리 및 예외 매핑을 검증.
- **Reference:** `kis_extractor_test.py` (구조적 일관성 유지)

## 2. 테스트 환경 및 전략

- **Mocking:**
  - `IHttpClient`: 실제 네트워크 요청 차단 및 응답 조작.
  - `AppConfig`: 설정(URL, Key) 주입 및 정책(Policy) 격리.
  - `LogManager`: `src.extractor.providers.abstract_extractor` 내부의 로거 호출을 Patch하여 의존성 제거.
- **Assertions:**
  - URL 조립 결과 검증 (Strict Path Variable Order).
  - Pydantic DTO 변환 및 메타데이터 검증.
  - ECOS 고유 에러 코드 및 네트워크 예외 매핑 검증.

## 3. 테스트 케이스 명세

|  Test ID   | Category  | Given (Preconditions)                                                 | When (Action)                                       | Then (Expected Outcome)                                                                                         | Input Data                                                          | Priority |
| :--------: | :-------: | :-------------------------------------------------------------------- | :-------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------ | :------- |
| **TC-001** |   Unit    | 정상적인 Config(URL, Key), 유효한 Policy(StatCode, Cycle 등)가 설정됨 | `extract` 메서드 호출 (정상 Job ID, 날짜 범위 포함) | 1. `INFO-000` 응답 파싱 성공.<br>2. 반환된 DTO의 data가 Mock 응답과 일치.<br>3. `http_client.get`이 1회 호출됨. | `job_id="ecos_job"`, `start_date="20240101"`, `end_date="20240102"` | **High** |
| **TC-002** |   Unit    | 상동. (URL 조립 로직 검증)                                            | `extract` 메서드 호출                               | **[중요]** 호출된 URL이 지정된 순서(/Key/Type/.../Start/End/...)와 정확히 일치하는지 검증.                      | `policy={"stat_code":"100Y", "cycle":"D" ...}`                      | **High** |
| **TC-003** | Exception | `config.ecos.base_url`이 비어 있음 ("")                               | `ECOSExtractor` 인스턴스 생성 시도 (`__init__`)     | `ExtractorError` 발생 (Critical Config Error).                                                                  | `config.ecos.base_url = ""`                                         | Medium   |
| **TC-004** | Exception | `config.ecos.api_key`가 누락됨                                        | `ECOSExtractor` 인스턴스 생성 시도 (`__init__`)     | `ExtractorError` 발생 (Critical Config Error).                                                                  | `config.ecos.api_key = None`                                        | Medium   |
| **TC-005** | Exception | 정상 Config                                                           | `extract` 호출 시 `job_id` 누락                     | `ExtractorError` 발생 (Invalid Request).                                                                        | `job_id=None`                                                       | Medium   |
| **TC-006** | Exception | 정상 Config                                                           | `extract` 호출 시 `start_date` 파라미터 누락        | `ExtractorError` 발생 (Mandatory for ECOS).                                                                     | `params={"end_date": "..."}`                                        | **High** |
| **TC-007** | Exception | 정상 Config                                                           | `extract` 호출 시 `end_date` 파라미터 누락          | `ExtractorError` 발생 (Mandatory for ECOS).                                                                     | `params={"start_date": "..."}`                                      | **High** |
| **TC-008** | Exception | Config에 정의되지 않은 `job_id`                                       | `extract` 호출                                      | `ExtractorError` 발생 (Policy not found).                                                                       | `job_id="unknown_job"`                                              | Low      |
| **TC-009** | Exception | 해당 `job_id`의 Policy Provider가 "KIS"로 설정됨                      | `extract` 호출                                      | `ExtractorError` 발생 (Provider Mismatch).                                                                      | `policy.provider="KIS"`                                             | Medium   |
| **TC-010** |   Unit    | API 응답 Root 레벨에 `RESULT.CODE`가 `INFO-200` (에러)임              | `extract` 호출 및 응답 수신                         | `ExtractorError` 발생 (ECOS API Failed).                                                                        | API Res: `{"RESULT": {"CODE": "INFO-200", "MESSAGE": "Error"}}`     | High     |
| **TC-011** |   Unit    | API 응답 서비스(Service) 레벨 `RESULT.CODE`가 `INFO-200`임            | `extract` 호출 및 응답 수신                         | `ExtractorError` 발생 (Business Failure).                                                                       | API Res: `{"StatSearch": {"RESULT": {"CODE": "INFO-200"}}}`         | High     |
| **TC-012** |   Unit    | API 응답에 예상된 서비스명(Key)이 없음                                | `extract` 호출 및 응답 수신                         | `ExtractorError` 발생 (Invalid Response).                                                                       | API Res: `{"WrongService": {...}}`                                  | Medium   |
| **TC-013** | Exception | HttpClient에서 네트워크 예외 발생                                     | `extract` 호출                                      | `ExtractorError`로 래핑되어 발생 (System Error).                                                                | `SideEffect=Exception("Timeout")`                                   | Medium   |
