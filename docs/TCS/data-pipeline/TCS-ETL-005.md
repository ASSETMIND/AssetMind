# UPBIT Extractor 테스트 명세서

## 1. 문서 정보 및 전략

- **대상 모듈:** `extractor.upbit_extractor.UPBITExtractor`
- **복잡도 수준:** **최상 (Critical)** (외부 가상화폐 거래소 API 연동 및 시세 데이터 수집)
- **커버리지 목표:** 분기 커버리지(Branch Coverage) 100%, 구문 커버리지(Statement Coverage) 100%
- **적용 전략:**
  - [x] **MC/DC (수정 조건/결정 커버리지):** `_validate_request` 내 필수 파라미터(`market`, `markets`) 조합에 따른 경고 로직의 독립적 검증.
  - [x] **Fail-Fast (조기 실패):** `base_url` 설정 누락 및 잘못된 정책 요청 시 즉각적인 예외 발생 여부 검증.
  - [x] **Mocking & Stubbing:** `IHttpClient`, `IAuthStrategy`의 응답 제어를 통한 네트워크/인증 격리 테스트.
  - [x] **Data Integrity:** Request 파라미터의 Policy 덮어쓰기(Override) 및 에러 객체(`error`) 감지 로직 검증.

## 2. BDD 테스트 시나리오 (전체 목록)

**시나리오 요약:**

- **초기화 (Initialization):** 1건 (설정 검증)
- **요청 검증 (Validation):** 4건 (MC/DC 적용 - JobID, Policy, Provider, Params)
- **정상 흐름 (Functional):** 2건 (파라미터 병합, URL 구성)
- **보안 (Security):** 2건 (토큰 존재/미존재 시 헤더 구성)
- **데이터 안정성 (Robustness):** 2건 (API 에러 응답 처리, 정상 응답 매핑)
- **예외 및 데코레이터 (Exception):** 3건 (인증 예외 전파, 시스템 예외 래핑, 데코레이터 적용)

|  테스트 ID  | 분류 | 기법  | 전제 조건 (Given)                         | 수행 (When)                          | 검증 (Then)                                                     | 입력 데이터 / 상황               |
| :---------: | :--: | :---: | :---------------------------------------- | :----------------------------------- | :-------------------------------------------------------------- | :------------------------------- |
| **INIT-01** | 단위 |  BVA  | `upbit.base_url`이 비어있는 설정 객체     | `UPBITExtractor(config)` 초기화      | `ExtractorError` 발생 (Critical Config Error)                   | `base_url=""`                    |
| **REQ-01**  | 단위 | MC/DC | `job_id`가 없는 요청 객체                 | `extract(request)` 호출              | `ExtractorError` 발생 (Invalid Request)                         | `job_id=None`                    |
| **REQ-02**  | 단위 | MC/DC | 설정 파일에 정의되지 않은 `job_id` 요청   | `extract(request)` 호출              | `ExtractorError` 발생 (Policy not found)                        | `job_id="UNKNOWN"`               |
| **REQ-03**  | 단위 | MC/DC | Provider가 'KIS'로 설정된 정책 요청       | `extract(request)` 호출              | `ExtractorError` 발생 (Provider Mismatch)                       | `provider="KIS"`                 |
| **REQ-04**  | 단위 | MC/DC | 정책/요청에 `market`, `markets` 모두 없음 | `extract(request)` 호출              | **Logger.warning 호출됨** (Parameter Warning)                   | `params={}`                      |
| **FLOW-01** | 단위 |  BVA  | 정책 파라미터와 요청 파라미터 중복        | `extract(request)` 호출              | **요청 파라미터가 우선순위**를 가져 정책값을 덮어씀             | Policy:`{cnt:1}`, Req:`{cnt:10}` |
| **FLOW-02** | 단위 | 표준  | `base_url`과 `path`가 설정됨              | `_fetch_raw_data` 내부 호출 URL 확인 | 두 문자열이 결합된 **완전한 URL**로 호출됨                      | `url="host/v1/candles..."`       |
| **SEC-01**  | 단위 | 보안  | `AuthStrategy`가 유효 토큰 반환           | `_fetch_raw_data` 헤더 검사          | `authorization` 헤더에 토큰 값이 포함됨                         | `headers["authorization"]` 존재  |
| **SEC-02**  | 단위 | 보안  | `AuthStrategy`가 `None` 반환 (Public)     | `_fetch_raw_data` 헤더 검사          | `authorization` 헤더가 **포함되지 않음**                        | `token=None`                     |
| **DATA-01** | 단위 |  BVA  | API 응답 본문에 `error` 키 존재           | `extract(request)` 호출              | `ExtractorError` 발생 (UPBIT API Failed)                        | `{"error": {"message": "Fail"}}` |
| **DATA-02** | 단위 | 표준  | 정상 JSON 응답 수신                       | `extract(request)` 호출              | 1. `ResponseDTO` 반환<br>2. 메타데이터(`source`, `job_id`) 검증 | `{"market": "KRW-BTC"}`          |
| **ERR-01**  | 예외 | 전파  | `AuthStrategy`에서 예외 발생              | `extract(request)` 호출              | 예외가 **그대로 상위로 전파됨** (로그 기록 확인)                | Raise `AuthError`                |
| **ERR-02**  | 예외 | 래핑  | 수집 중 예상치 못한 `KeyError` 발생       | `extract(request)` 호출              | `ExtractorError`로 래핑되어 던져짐 (System Error)               | Raise `KeyError`                 |
| **DEC-01**  | 단위 | 메타  | `@retry`, `@rate_limit` 데코레이터 적용   | `_fetch_raw_data` 속성 검사          | 데코레이터 래퍼가 적용되어 있음 (실제 동작은 Stub으로 검증)     | `__wrapped__` 속성 확인          |
