# PipelineService 테스트 문서

## 1. 문서 정보 및 전략

- **대상 모듈:** `src.pipeline_service.PipelineService`
- **복잡도 수준:** **최상 (Critical)** (ETL 오케스트레이션, 다중 예외 처리 및 래핑, 비동기 컨텍스트 관리)
- **커버리지 목표:** 분기 커버리지100%, 구문 커버리지 100%
- **적용 전략:**
  - [x] **생명주기 전파 (Lifecycle Propagation):** `Pipeline`의 Context 진입/종료가 `Extractor` 등 하위 서비스로 올바르게 전파되는지 검증.
  - [x] **결함 격리 (Fault Tolerance):** 개별 Job의 실패가 전체 배치를 중단시키지 않는지 검증 (Loop 내 Try-Except).
  - [x] **예외 매핑 (Exception Mapping):** 알 수 없는 에러(Unknown Exception)가 도메인 에러(`TransformerError`, `LoaderError`)로 올바르게 래핑(Wrapping)되는지 검증.
  - [x] **MC/DC (수정 조건/결정 커버리지):** `FAIL_EXTRACT`, `FAIL_TRANSFORM`, `FAIL_LOAD`, `CRITICAL_ERROR` 등 모든 상태 분기 검증.
  - [x] **경계값 분석 (BVA):** 설정 파일이 비어있거나, 수집된 데이터가 비어있는 경우(Empty Payload)의 처리.

## 2. 로직 흐름도

```mermaid
stateDiagram-v2
stateDiagram-v2
    [*] --> Init: __init__(task_name)
    Init --> ContextEnter: async with

    state ContextEnter {
        [*] --> ExtractorInit: Init Extractor
        ExtractorInit --> ResourceReady: Await __aenter__
    }

    ContextEnter --> RunBatch: run_batch()

    state RunBatch {
        [*] --> CheckConfig: Config.extraction_policy
        CheckConfig --> EarlyExit: Empty Config
        CheckConfig --> Step1_Extract: Valid Jobs

        state Step1_Extract {
            [*] --> CallExtractor: extract_batch(ids)
            CallExtractor --> IterateResults: Loop Results
        }

        IterateResults --> TryBlock: Start Processing Job

        state TryBlock {
            [*] --> CheckExtractError: Result is Exception?
            CheckExtractError --> Raise_Extract: Yes (Raise)
            CheckExtractError --> Step2_Transform: No

            state Step2_Transform {
                [*] --> CallTransform: _mock_transform()
                CallTransform --> Catch_T_Unknown: Exception?
                Catch_T_Unknown --> Wrap_T_Error: Wrap as TransformerError
                CallTransform --> Step3_Load: Success
            }

            state Step3_Load {
                [*] --> CallLoad: _mock_load()
                CallLoad --> Catch_L_Unknown: Exception?
                Catch_L_Unknown --> Wrap_L_Error: Wrap as LoaderError
                CallLoad --> Success_Mark: Success
            }
        }

        TryBlock --> Catch_ETL: Catch ETLError
        TryBlock --> Catch_Crit: Catch Exception (Critical)

        Catch_ETL --> DetermineStatus: Extract/Transform/Load Type Check
        DetermineStatus --> Record_Fail: Set Status (FAIL_*)

        Catch_Crit --> Record_Crit: Set Status (CRITICAL)

        Success_Mark --> NextJob
        Record_Fail --> NextJob
        Record_Crit --> NextJob
    }

    RunBatch --> ContextExit: async with exit
    ContextExit --> [*]: ExtractorService.__aexit__
```

## 3. BDD 테스트 시나리오

**시나리오 요약 (총 10건):**

1.  **초기화 및 검증 (Initialization):** 2건 (파라미터 검증, 설정 로드 실패)
2.  **자원 생명주기 (Lifecycle):** 1건 (Context Manager 전파)
3.  **배치 실행 (Batch Execution):** 2건 (정상 실행, 빈 작업 목록 방어)
4.  **수집 결함 격리 (Extract Fault Tolerance):** 2건 (알려진 에러, 알 수 없는 에러 분기)
5.  **적재 결함 격리 (Load Fault Tolerance):** 3건 (반환값 실패, 적재 에러, 치명적 시스템 에러)

|   테스트 ID   | 분류 | 기법  | 전제 조건 (Given)                                 | 수행 (When)                         | 검증 (Then)                                                      | 입력 데이터 / 상황                               |
| :-----------: | :--: | :---: | :------------------------------------------------ | :---------------------------------- | :--------------------------------------------------------------- | :----------------------------------------------- |
|  **INIT-01**  | 단위 |  BVA  | `task_name`이 빈 문자열 또는 None                 | `PipelineService(task_name)` 초기화 | `AssertionError` 발생 (조기 차단)                                | `task_name=""`                                   |
|  **INIT-02**  | 단위 | 예외  | 설정 파일에서 해당 `task_name`을 찾을 수 없음     | `PipelineService(task_name)` 초기화 | `ConfigurationError` 래핑 및 발생                                | `task_name="invalid_task"`                       |
|  **LIFE-01**  | 통합 | 상태  | 정상 생성된 `PipelineService` 인스턴스            | `async with` 구문 진입 및 종료      | `ExtractorService`의 `__aenter__` / `__aexit__` 순차 호출 확인   | `task_name="test_task"`                          |
| **BATCH-01**  | 단위 |  BVA  | `extract_jobs` 정책이 비어있음 (작업 없음)        | `run_batch()` 호출                  | 하위 호출 없이 `STATUS_EMPTY` 상태 반환 및 조기 종료             | `extract_jobs=[]`                                |
| **BATCH-02**  | 통합 | 표준  | 정상 Job 1건, 수집 및 적재 모두 정상 동작         | `run_batch()` 호출                  | 통계 결과 `success=1`, `fail=0` 및 개별 상태 `SUCCESS` 반환      | `extract_batch -> [DTO]`, `execute_load -> True` |
| **FAIL-E-01** | 단위 | MC/DC | 수집 단계에서 도메인 예외(`ETLError`) 객체 반환   | `run_batch()` 호출                  | 적재 미수행. 에러 포맷에 `to_dict()` 적용 및 `FAIL_EXTRACT` 기록 | `extract_batch -> [ETLError()]`                  |
| **FAIL-E-02** | 단위 | MC/DC | 수집 단계에서 시스템 예외(`ValueError`) 반환      | `run_batch()` 호출                  | 적재 미수행. 기본 `str()` 포맷 적용 및 `FAIL_EXTRACT` 기록       | `extract_batch -> [ValueError()]`                |
| **FAIL-L-01** | 단위 | 분기  | 적재 단계(`execute_load`)에서 `False` 반환        | `run_batch()` 호출                  | 예외가 없더라도 결과 상태 `FAIL_LOAD` 기록                       | `execute_load -> False`                          |
| **FAIL-L-02** | 단위 | 예외  | 적재 단계에서 도메인 예외(`LoaderError`) 발생     | `run_batch()` 호출                  | 에러 격리, `FAIL_LOAD` 기록 및 `to_dict()` 에러 메시지 래핑      | `execute_load -> raises LoaderError`             |
| **FAIL-L-03** | 단위 | 예외  | 적재 중 예측 못한 시스템 예외(`MemoryError`) 발생 | `run_batch()` 호출                  | 에러 격리 및 상태 `CRITICAL_SYSTEM_ERROR` 기록                   | `execute_load -> raises MemoryError`             |
