# UPBIT Extractor Test Specification

## 1. 개요

- **대상 모듈:** `src.extractor.providers.upbit_extractor.UPBITExtractor`
- **작성 목적:** Upbit Open API 수집 로직의 정합성 검증 및 예외 처리 견고성 확보.
- **테스트 범위:** 인증 전략 연동, 파라미터 동적 병합, URL/Header 조립, Upbit 고유 에러 핸들링, Request/Config 유효성 검사.

## 2. 테스트 환경 및 전략

- **Mocking:** `IHttpClient`, `IAuthStrategy`, `AppConfig`는 철저히 Mocking하여 외부 의존성을 격리합니다.
- **Logging:** `LogManager`를 Patch하여 테스트 중 불필요한 I/O를 방지하고, 특정 상황(Warning)에서의 로그 호출 여부를 검증합니다.
- **Assertions:** 결과값(DTO) 뿐만 아니라, 호출된 URL, Header, Log Message를 검증하여 내부 로직의 정확성을 보장합니다.

## 3. 테스트 케이스 명세

|  Test ID   |         Category         | Given (Preconditions)                                                 | When (Action)                                 | Then (Expected Outcome)                                                                                      | Input Data                   | Priority |
| :--------: | :----------------------: | :-------------------------------------------------------------------- | :-------------------------------------------- | :----------------------------------------------------------------------------------------------------------- | :--------------------------- | :------- |
| **TC-001** |    **Unit (Config)**     | `config.upbit.base_url`이 비어있는 상태("")                           | `UPBITExtractor` 인스턴스 초기화 (`__init__`) | `ExtractorError` 발생 ("Critical Config Error").                                                             | `base_url=""`                | High     |
| **TC-002** |  **Unit (Happy Path)**   | 정상 Config, Policy, AuthToken 존재. API는 정상 Dict 응답 반환.       | `extract(request)` 호출                       | status='OK', data=원본응답 반환. Info 로그 호출 확인.                                                        | `job_id="upbit_job"`         | High     |
| **TC-003** |  **Unit (Happy Path)**   | 정상 Config, Policy 존재.                                             | `extract(request)` 호출                       | **URL**(`base+path`), **Header**(`Bearer Token`), **Params**가 순서대로 조립되어 `client.get` 호출됨을 검증. | `job_id="upbit_job"`, params | High     |
| **TC-004** |     **Unit (Logic)**     | `AuthStrategy`가 `None`을 반환 (Public API).                          | `extract(request)` 호출                       | `client.get` 호출 시 헤더에 `Authorization` 필드가 **없어야 함**.                                            | `job_id="public_job"`        | Medium   |
| **TC-005** |     **Unit (Logic)**     | Policy Params(`count=1`)와 Request Params(`count=100`)가 중복.        | `extract(request)` 호출                       | `client.get` 호출 시 **Request Param(`count=100`)이 우선** 적용되었는지 검증.                                | `params={'count': 100}`      | Medium   |
| **TC-006** |     **Unit (Logic)**     | Request와 Policy 양쪽 모두 `market` 파라미터 없음.                    | `extract(request)` 호출                       | 예외 없이 진행되나, **Warning 로그**가 기록됨을 검증.                                                        | `params={}` (No market)      | Medium   |
| **TC-007** |     **Unit (Logic)**     | API가 Dict가 아닌 **List** (예: 캔들 데이터)를 반환.                  | `extract(request)` 호출                       | 에러 없이 정상 처리되며 `ResponseDTO.data`가 List인지 검증.                                                  | API Resp: `[{}, {}]`         | Medium   |
| **TC-008** | **Exception (Request)**  | `request.job_id`가 `None`.                                            | `extract(request)` 호출                       | `ExtractorError` 발생 ("Invalid Request").                                                                   | `job_id=None`                | High     |
| **TC-009** |  **Exception (Policy)**  | 요청한 `job_id`가 Config Policy 맵에 없음.                            | `extract(request)` 호출                       | `ExtractorError` 발생 ("Policy not found").                                                                  | `job_id="unknown"`           | High     |
| **TC-010** |  **Exception (Policy)**  | 해당 Policy의 Provider가 "UPBIT"가 아님 (예: "KIS").                  | `extract(request)` 호출                       | `ExtractorError` 발생 ("Provider Mismatch").                                                                 | `provider="KIS"`             | High     |
| **TC-011** | **Exception (Response)** | API 응답 Body에 `error` 객체 포함 (`{"error": {"message": "Fail"}}`). | `extract(request)` 호출                       | `ExtractorError` 발생 (메시지 포함).                                                                         | API Resp: `{"error": ...}`   | High     |
| **TC-012** | **Exception (Response)** | API 응답 Body에 `error` 키가 있으나 내부 필드 누락.                   | `extract(request)` 호출                       | `ExtractorError` 발생 (기본 메시지 "UnknownError" 등 확인).                                                  | API Resp: `{"error": {}}`    | Low      |
| **TC-013** |       **Resource**       | `http_client.get` 호출 시 `ConnectionError` 발생.                     | `extract(request)` 호출                       | `ExtractorError`로 래핑되어 던져짐 ("System Error").                                                         | `client.get` raises Ex       | High     |
