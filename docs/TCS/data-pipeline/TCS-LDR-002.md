# S3Loader 테스트 문서

## 1. 문서 정보 및 전략

- **대상 모듈:** `src.loader.providers.s3_loader.S3Loader`
- **복잡도 수준:** **높음 (High)** (외부 Boto3 의존성 제어, Zstd 바이너리 스트림 처리, 다단계 예외 래핑)
- **커버리지 목표:** 분기 커버리지 100%, 구문 커버리지 100%
- **적용 전략:**
  - **의존성 격리 (Dependency Isolation):** AWS 인프라(S3)와의 통신을 완벽히 차단하기 위해 `boto3.client`를 Mocking하여 멱등성 보장.
  - **경계값 분석 (BVA):** 멀티파트 업로드 임계값(`10MB`) 기준 전/후 바이트 크기에 따른 동작 검증.
  - **예외 래핑 (Exception Mapping):** `TypeError`, `MemoryError`, `ClientError` 등 네이티브/라이브러리 에러가 도메인 에러(`ZstdCompressionError`, `S3UploadError`)로 정확히 변환되는지 확인.
  - **동등 분할 (Equivalence Partitioning):** DTO의 `data` 타입(str, bytes, dict)에 따른 분기 직렬화 로직 검증.

## 3. BDD 테스트 시나리오 명세서

**시나리오 요약 (총 14건):**

1. **초기화 및 설정 (Init):** 5건 (정상, 환경변수 분기, 인자 누락, 예외 래핑)
2. **무결성 검증 (Validation):** 4건 (정상, 빈 데이터, 타입 오류, 스키마 누락)
3. **키 생성 및 파이프라인 (Orchestration):** 2건 (S3 경로 생성, 통합 흐름)
4. **직렬화 및 압축 (Compression):** 4건 (타입별 정상, 직렬화 불가, OOM, 시스템 에러)
5. **S3 적재 (Upload):** 3건 (정상, AWS ClientError, Native Exception)

|  테스트 ID  | 분류 |   기법   | 전제 조건 (Given)                                    | 수행 (When)                           | 검증 (Then)                                                     | 입력 데이터 / 상황                                           |
| :---------: | :--: | :------: | :--------------------------------------------------- | :------------------------------------ | :-------------------------------------------------------------- | :----------------------------------------------------------- |
| **INIT-01** | 단위 |   정상   | `bucket_name`, `region`이 정상적으로 주어짐          | `S3Loader` 인스턴스 생성              | 에러 없이 Boto3 클라이언트가 실제 AWS 설정으로 초기화됨         | `bucket="prd-raw"`, `region="ap-northeast-2"`                |
| **INIT-02** | 단위 |   BVA    | `bucket_name`이 빈 문자열 또는 `None`으로 주어짐     | `S3Loader` 인스턴스 생성              | `ConfigurationError` 조기 발생 (Fail-Fast)                      | `bucket="", region="ap-northeast-2"`                         |
| **INIT-03** | 단위 |   BVA    | `region`이 빈 문자열 또는 `None`으로 주어짐          | `S3Loader` 인스턴스 생성              | `ConfigurationError` 조기 발생 (Fail-Fast)                      | `bucket="prd-raw", region=None`                              |
| **INIT-04** | 단위 |   분기   | `LOCAL_S3_ENDPOINT` 환경 변수가 설정된 상태          | `S3Loader` 인스턴스 생성              | LocalStack용 Endpoint 설정으로 Boto3 클라이언트가 초기화됨      | `os.environ["LOCAL_S3_ENDPOINT"] = "http://localhost:4566"`  |
| **INIT-05** | 단위 |   래핑   | Boto3 클라이언트 생성 시 `BotoCoreError` 발생        | `S3Loader` 인스턴스 생성              | `ConfigurationError`로 래핑되어 예외 전파됨                     | Mock: `boto3.client -> BotoCoreError`                        |
| **VAL-01**  | 단위 |   정상   | `data`, `meta(source, job_id)`가 모두 유효한 DTO     | `_validate_dto(dto)` 호출             | `True` 반환                                                     | `ExtractedDTO(data="{}", meta={"source":"A", "job_id":"B"})` |
| **VAL-02**  | 단위 |   BVA    | `data` 속성이 `None`인 DTO                           | `_validate_dto(dto)` 호출             | `False` 반환 (로깅 동반)                                        | `ExtractedDTO(data=None, meta={...})`                        |
| **VAL-03**  | 단위 |   타입   | `meta` 속성이 `dict`가 아닌 DTO (예: 리스트)         | `_validate_dto(dto)` 호출             | `False` 반환                                                    | `ExtractedDTO(data="{}", meta=["source", "job_id"])`         |
| **VAL-04**  | 단위 |  스키마  | `meta`에 `source` 또는 `job_id`가 누락된 DTO         | `_validate_dto(dto)` 호출             | `False` 반환                                                    | `ExtractedDTO(data="{}", meta={"source":"A"})`               |
| **KEY-01**  | 단위 |   정상   | `source`와 `job_id`가 포함된 DTO                     | `_generate_s3_key(dto)` 호출          | Hive 파티셔닝 포맷(`raw/provider=.../job=...`) 경로 문자열 반환 | `ExtractedDTO(..., meta={"source":"KIS", "job_id":"kospi"})` |
| **ORCH-01** | 통합 |   정상   | 사전 검증된 DTO 주입                                 | `_apply_load(dto)` 호출               | 키 생성 -> 압축 -> S3 멀티파트 업로드 연계 수행 후 `True` 반환  | `ExtractedDTO(...)` Mock 객체                                |
| **COMP-01** | 단위 | 동등분할 | `data`가 각각 `dict`, `str`, `bytes`인 상태          | `_compress_to_zstd_stream(data)` 호출 | 에러 없이 직렬화 및 Zstd 바이너리(`bytes`) 반환                 | Input: `{"a":1}`, `"text"`, `b"bytes"`                       |
| **COMP-02** | 단위 |   래핑   | JSON 직렬화가 불가한 커스텀 객체 주입                | `_compress_to_zstd_stream(data)` 호출 | `TypeError`가 `ZstdCompressionError`로 래핑됨                   | `data = UnserializableObject()`                              |
| **COMP-03** | 예외 |   래핑   | Zstd 압축 과정 중 시스템 메모리 부족(`MemoryError`)  | `_compress_to_zstd_stream(data)` 호출 | `MemoryError`가 `ZstdCompressionError`로 래핑됨                 | Mock: `compressor.compress -> MemoryError`                   |
| **COMP-04** | 예외 |   래핑   | Zstd 압축 과정 중 알 수 없는 시스템 예외             | `_compress_to_zstd_stream(data)` 호출 | 범용 `Exception`이 `ZstdCompressionError`로 래핑됨              | Mock: `compressor.compress -> Exception`                     |
| **UPL-01**  | 통합 |   BVA    | 10MB 미만 및 10MB 이상의 Zstd 바이너리 스트림        | `_execute_multipart_upload()` 호출    | `upload_fileobj` 정상 호출 및 `True` 반환                       | `stream = b"0" * 100`, `b"0" * (11*1024*1024)`               |
| **UPL-02**  | 단위 |   래핑   | S3 업로드 중 `ClientError` (예: 403 Forbidden) 발생  | `_execute_multipart_upload()` 호출    | `is_multipart` 플래그 계산 및 `S3UploadError`로 래핑            | Mock: `upload_fileobj -> ClientError`                        |
| **UPL-03**  | 단위 |   래핑   | S3 업로드 중 네이티브 에러 (`Connection Reset`) 발생 | `_execute_multipart_upload()` 호출    | 일반 예외도 `S3UploadError`로 철저히 래핑됨                     | Mock: `upload_fileobj -> Exception`                          |
