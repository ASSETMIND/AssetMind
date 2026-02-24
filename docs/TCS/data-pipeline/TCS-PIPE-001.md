# 2단계. 정식 테스트 명세서 (TCS-PIPE-001)

## 1. 문서 정보 및 전략

- **대상 모듈:** `src.pipeline_service.PipelineService`
- **복잡도 수준:** **최상 (Critical)** (ETL 오케스트레이션, 다중 예외 처리 및 래핑, 비동기 컨텍스트 관리)
- **커버리지 목표:** **분기 커버리지(Branch Coverage) 100%**, 구문 커버리지 100%
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

**시나리오 요약 (총 11건):**

1.  **자원 생명주기 (Lifecycle):** 1건 (Context Manager 전파)
2.  **배치 실행 (Batch Execution):** 2건 (정상 실행, 빈 설정 방어)
3.  **데이터 무결성 (Data Integrity):** 1건 (빈 데이터 수집 시 처리)
4.  **결함 격리 및 예외 처리 (Fault Tolerance):** 6건 (단계별 실패, 에러 래핑, 시스템 에러)
5.  **복합 시나리오 (Combination):** 1건 (성공/실패 혼합 집계)

|   테스트 ID   | 분류 |     기법     | 전제 조건 (Given)                          | 수행 (When)                    | 검증 (Then)                                                                       | 입력 데이터 / 상황                  |
| :-----------: | :--: | :----------: | :----------------------------------------- | :----------------------------- | :-------------------------------------------------------------------------------- | :---------------------------------- |
|  **LIFE-01**  | 통합 |     상태     | `PipelineService` 인스턴스 생성            | `async with` 구문 진입 및 종료 | 하위 `ExtractorService`의 `__aenter__`와 `__aexit__`가 순차적으로 호출됨          | `task_name="demo"`                  |
| **BATCH-01**  | 단위 |     표준     | 정상 Job ID 1건이 포함된 설정              | `run_batch()` 호출             | 1. 수집->변환->적재 순차 실행<br>2. 최종 상태 `SUCCESS` 기록                      | `jobs=["job_A"]`                    |
| **CONFIG-01** | 단위 |     BVA      | `extraction_policy`가 비어있는 설정        | `run_batch()` 호출             | 1. 하위 서비스 호출 없이 즉시 리턴<br>2. `status`: "empty", `total`: 0 반환       | `jobs=[]`                           |
|  **DATA-01**  | 단위 |     BVA      | 수집은 성공했으나 데이터가 비어있음 (None) | `run_batch()` 호출             | 에러 없이 변환/적재 단계를 통과(Pass-through)하며 `SUCCESS` 처리됨                | `ExtractedDTO(data=None)`           |
| **FAIL-E-01** | 단위 |    MC/DC     | 수집 단계(`Extract`)에서 에러 객체 반환    | `run_batch()` 호출             | 1. 변환/적재 단계 **호출되지 않음**<br>2. 결과 상태 `FAIL_EXTRACT` 기록           | Mock: `Result -> Exception`         |
| **FAIL-T-01** | 단위 |    MC/DC     | 변환 단계에서 `ETLError`(Known) 발생       | `run_batch()` 호출             | 1. 적재 단계 호출되지 않음<br>2. 결과 상태 `FAIL_TRANSFORM` 기록                  | Mock: `Transform -> ETLError`       |
| **FAIL-T-02** | 단위 | **예외래핑** | 변환 단계에서 `ValueError`(Unknown) 발생   | `run_batch()` 호출             | 1. `TransformerError`로 래핑되어 상위 전파<br>2. 결과 상태 `FAIL_TRANSFORM` 기록  | Mock: `Transform -> ValueError`     |
| **FAIL-L-01** | 단위 |    MC/DC     | 적재 단계에서 `ETLError`(Known) 발생       | `run_batch()` 호출             | 1. 변환 단계는 성공했음 확인<br>2. 결과 상태 `FAIL_LOAD` 기록                     | Mock: `Load -> ETLError`            |
| **FAIL-L-02** | 단위 | **예외래핑** | 적재 단계에서 `ConnectionError` 발생       | `run_batch()` 호출             | 1. `LoaderError`로 래핑되어 상위 전파<br>2. 결과 상태 `FAIL_LOAD` 기록            | Mock: `Load -> ConnectionError`     |
|  **CRIT-01**  | 예외 |    System    | 로직 수행 중 치명적 시스템 에러 발생       | `run_batch()` 호출             | 1. 파이프라인 죽지 않음 (Loop 계속)<br>2. 결과 상태 `CRITICAL_SYSTEM_ERROR` 기록  | Mock: `Loop 내부 -> MemoryError`    |
|  **MIX-01**   | 통합 |     조합     | [성공, 수집실패, 적재실패] 3건 혼합        | `run_batch()` 호출             | 1. 전체 프로세스 완료<br>2. 집계: `Total: 3`, `Success: 1`, `Fail: 2` 정확성 검증 | Mock: `[OK, Err_Extract, Err_Load]` |
