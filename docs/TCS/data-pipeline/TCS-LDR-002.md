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

**시나리오 요약 (총 12건):**

1. **초기화 및 설정 (Init):** 3건
2. **무결성 검증 (Validation):** 4건
3. **직렬화 및 압축 (Compression):** 3건
4. **S3 적재 (Upload):** 2건

|  테스트 ID  | 분류 |   기법   | 전제 조건 (Given)                                      | 수행 (When)                        | 검증 (Then)                                     | 입력 데이터 / 상황                                             |
| :---------: | :--: | :------: | :----------------------------------------------------- | :--------------------------------- | :---------------------------------------------- | :------------------------------------------------------------- |
| **INIT-01** | 단위 |   정상   | `bucket_name`이 포함된 정상 설정 주입                  | `S3Loader` 인스턴스 생성           | 에러 없이 Boto3 클라이언트가 초기화됨           | `aws.s3.bucket_name="toss-datalake"`                           |
| **INIT-02** | 단위 |   예외   | `bucket_name`이 누락된 설정 주입                       | `S3Loader` 인스턴스 생성           | `ConfigurationError` 발생 (조기 실패)           | `aws.s3.bucket_name=None`                                      |
| **INIT-03** | 단위 |   래핑   | Boto3 클라이언트 생성 시 `BotoCoreError` 발생 조건     | `S3Loader` 인스턴스 생성           | `ConfigurationError`로 래핑되어 발생            | Mock: `boto3.client -> BotoCoreError`                          |
| **VAL-01**  | 단위 |   정상   | `data`, `meta(provider, job_id)`가 모두 유효한 DTO     | `_validate_dto(dto)` 호출          | `True` 반환                                     | `ExtractedDTO(data="{}", meta={"provider":"a", "job_id":"1"})` |
| **VAL-02**  | 단위 |   BVA    | `data` 속성이 `None`인 DTO                             | `_validate_dto(dto)` 호출          | `False` 반환 (로깅 동반)                        | `ExtractedDTO(data=None, meta={...})`                          |
| **VAL-03**  | 단위 |   타입   | `meta` 속성이 `dict`가 아닌 DTO (예: 리스트)           | `_validate_dto(dto)` 호출          | `False` 반환                                    | `ExtractedDTO(data="{}", meta=["provider", "job_id"])`         |
| **VAL-04**  | 단위 |  스키마  | `meta`에 `provider` 또는 `job_id`가 누락된 DTO         | `_validate_dto(dto)` 호출          | `False` 반환                                    | `ExtractedDTO(data="{}", meta={"provider":"a"})`               |
| **COMP-01** | 단위 | 동등분할 | `data`가 각각 `dict`, `str`, `bytes`인 DTO 3종         | `_compress_to_zstd_stream()` 호출  | 에러 없이 Zstd 바이너리(`bytes`) 반환           | Input: `{"a":1}`, `"text"`, `b"bytes"`                         |
| **COMP-02** | 단위 |   래핑   | JSON 직렬화가 불가한 객체(예: 커스텀 클래스) 주입      | `_compress_to_zstd_stream()` 호출  | `TypeError`가 `ZstdCompressionError`로 래핑됨   | `data = object()`                                              |
| **COMP-03** | 예외 |   래핑   | 압축 과정에서 시스템 메모리 부족(`MemoryError`) 발생   | `_compress_to_zstd_stream()` 호출  | `MemoryError`가 `ZstdCompressionError`로 래핑됨 | Mock: `compressor.compress -> MemoryError`                     |
| **UPL-01**  | 통합 |   BVA    | 10MB 미만 및 10MB 이상의 Zstd 바이너리 스트림          | `_execute_multipart_upload()` 호출 | `upload_fileobj`가 정상 호출되고 `True` 반환    | `stream = b"0" * 100`, `b"0" * (11*1024*1024)`                 |
| **UPL-02**  | 단위 |   래핑   | Boto3 업로드 중 `ClientError` (예: 403 Forbidden) 발생 | `_execute_multipart_upload()` 호출 | 에러 코드 추출 후 `S3UploadError`로 래핑됨      | Mock: `upload_fileobj -> ClientError`                          |
