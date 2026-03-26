# FRED Extractor 테스트 명세서

## 1. 문서 정보 및 전략

- **대상 모듈:** `extractor.providers.fred_extractor.FREDExtractor`
- **복잡도 수준:** **높음 (High)** (파라미터 병합 로직 및 부모 클래스 오버라이딩 포함)
- **커버리지 목표:** 분기 커버리지 100%, 구문 커버리지 100%
- **적용 전략:**
  - [x] **MC/DC (수정 조건/결정 커버리지):** 필수 파라미터(`series_id`)의 소스(Policy vs Request)에 따른 분기 검증.
  - [x] **Data Integrity (데이터 무결성):** 시스템 강제 파라미터(`file_type=json`, `api_key`)의 우선순위 검증.
  - [x] **Fail-Fast (조기 실패):** 설정 누락 및 정책 위반 시 즉각적인 에러 발생 검증.
  - [x] **Decorator Verification:** 재시도(`@retry`) 및 로깅(`@log`) 동작 확인.

## 2. 로직 흐름도

```mermaid
graph TD
    Start([RequestDTO Start]) --> Validate{Validate Request}

    Validate -- No Job ID --> Error_Job[Err: Mandatory JobID]
    Validate -- No Policy --> Error_Policy[Err: Policy Missing]
    Validate -- Wrong Provider --> Error_Prov[Err: Provider Mismatch]

    Validate -- Pass --> CheckParam{Check 'series_id'}
    CheckParam -- In Policy? --> Merge[Merge Params]
    CheckParam -- In Request? --> Merge
    CheckParam -- Neither --> Error_Param[Err: Missing 'series_id']

    Merge --> Inject[Inject System Params]
    Inject --> Fetch[Fetch Raw Data]

    Fetch -- HTTP Error --> Retry{Retry Logic}
    Retry -- Max Retries --> Error_Net[Err: Network Failure]

    Fetch -- Success (200 OK) --> LogicCheck{Contains Error Msg?}
    LogicCheck -- Yes --> Error_Biz[Err: FRED API Error]
    LogicCheck -- No --> CreateRes[Create ResponseDTO]

    CreateRes --> InjectMeta[Inject Metadata: job_id]
    InjectMeta --> End([Return ResponseDTO])
```

## 3. BDD 테스트 시나리오

**시나리오 요약 (총 12건)**

- **초기화 (Initialization):** 3건 (필수 설정값 누락 Fail-Fast 방어)
- **유효성 검증 (Validation - MC/DC):** 6건 (필수 파라미터 조합, 제공자 불일치 및 예외 상태)
- **실행 및 병합 (Execution & Merging):** 1건 (파라미터 우선순위 병합, 시스템 통제값 주입 검증)
- **응답 처리 (Response Parsing):** 2건 (논리적 비즈니스 에러 식별 및 정상 표준 객체 래핑)

|  테스트 ID  | 분류 |   기법    | 전제 조건 (Given)                        | 수행 (When)                   | 검증 (Then)                                               | 입력 데이터 / 상황       |
| :---------: | :--: | :-------: | :--------------------------------------- | :---------------------------- | :-------------------------------------------------------- | :----------------------- |
| **INIT-01** | 단위 | Fail-fast | 설정(Config) 내 `base_url`이 비어있음    | `FREDExtractor` 인스턴스화    | `ExtractorError` 발생 ("base_url가 누락되었습니다.")      | `base_url=""`            |
| **INIT-02** | 단위 | Fail-fast | 설정(Config) 내 `api_key`가 비어있음     | `FREDExtractor` 인스턴스화    | `ExtractorError` 발생 ("api_key가 누락되었습니다.")       | `api_key=""`             |
| **INIT-03** | 단위 |   표준    | 유효한 설정(`base_url`, `api_key` 존재)  | `FREDExtractor` 인스턴스화    | 인스턴스 정상 생성 완료                                   | 정상 Config 객체         |
| **VAL-01**  | 단위 |  경계값   | Request 파라미터에 `job_id`가 누락됨     | `_validate_request(req)` 호출 | `ExtractorError` 발생 ("'job_id'는 필수 항목입니다.")     | `job_id=None`            |
| **VAL-02**  | 단위 |   예외    | 정책 조회 시 예외 발생 (설정 오류)       | `_validate_request(req)` 호출 | `ExtractorError`로 래핑되어 발생 ("설정 오류")            | DB/Network 예외          |
| **VAL-03**  | 단위 |   상태    | 조회된 정책의 `provider`가 FRED가 아님   | `_validate_request(req)` 호출 | `ExtractorError` 발생 ("API 제공자 불일치")               | `provider="ECOS"`        |
| **VAL-04**  | 단위 |   MC/DC   | `series_id`가 Policy와 Request 모두 없음 | `_validate_request(req)` 호출 | `ExtractorError` 발생 ("'series_id'가 필요합니다.")       | Policy:{}, Request:{}    |
| **VAL-05**  | 단위 |   MC/DC   | `series_id`가 **Policy에만** 존재함      | `_validate_request(req)` 호출 | 정상 통과 (예외 미발생)                                   | Policy:`{series_id: A}`  |
| **VAL-06**  | 단위 |   MC/DC   | `series_id`가 **Request에만** 존재함     | `_validate_request(req)` 호출 | 정상 통과 (예외 미발생)                                   | Request:`{series_id: B}` |
| **EXEC-01** | 단위 |   통합    | Policy와 Request에 파라미터가 분산됨     | `_fetch_raw_data(req)` 호출   | Request가 Policy를 덮어쓰고 시스템 파라미터가 강제 병합됨 | Request+Policy 조합      |
| **RES-01**  | 단위 |   논리    | API 응답은 200이나 JSON 내에 에러 포함   | `_create_response(...)` 호출  | `ExtractorError` 발생 ("FRED API 실패")                   | `{"error_message": "X"}` |
| **RES-02**  | 단위 |   표준    | 순수 데이터만 포함된 정상 JSON 응답      | `_create_response(...)` 호출  | `ExtractedDTO` 객체 정상 반환 및 메타데이터 주입          | `{"observations": []}`   |
