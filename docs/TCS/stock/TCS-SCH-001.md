# [TCS] Stock 스케줄러(배치 파이프라인) 테스트 명세서

| 문서 ID | **TCS-SCH-001** |
| :--- |:----------------------------------------|
| **문서 버전** | 1.0                                     |
| **프로젝트** | AssetMind                               |
| **작성자** | 이재석                                     |
| **작성일** | 2026년 04월 06일                           |
| **관련 모듈** | `stock/application/scheduler`           |

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템에서 주기적으로 실행되는 백그라운드 배치 작업(`CandleFlushScheduler`, `PartitionCreationScheduler`)에 대한 단위 테스트 명세이다.
`Mockito`를 활용하여 외부 인프라(DB, Redis) 의존성을 완벽히 격리하고, 비즈니스 흐름(데이터 조회 -> 롤업 처리 -> 저장 위임)과 스케줄러의 실행 시점에 따른 컴포넌트 호출(Behavior)이 정확한지 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Mockito (`@ExtendWith(MockitoExtension.class)`)
- **Target Classes:** - `CandleFlushSchedulerTest` (1분봉 Redis Flush 및 1일봉 롤업 배치)
    - `PartitionCreationSchedulerTest` (틱 데이터 파티션 자동 생성 로직)
- **Verification Focus:**
    - **Behavior Verification:** `verify(..., times(N))`를 활용하여 하위 Port(Repository, Service)의 메서드가 조건에 맞춰 정확히 호출되는지 검증
    - **Edge Case (Empty Data):** 처리할 데이터가 없는 상황(빈 리스트)에서 NullPointerException 없이 안전하게 방어되는지 검증
    - **Event & Time Triggers:** 서버 기동 시점(`ApplicationReadyEvent`)과 정규 스케줄링 시점에 올바른 날짜 파라미터가 전달되는지 검증

---

## 2. Application Scheduler 테스트 명세

### 2.1. 캔들 파이프라인 스케줄러 검증
> **대상 클래스:** `CandleFlushSchedulerTest`
> **검증 목표:** 인메모리 버퍼(Redis) 비우기 및 1분봉 → 1일봉 압축 배치의 흐름 제어 확인

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **APP-SCH-001** | `givenFlushedCandles_whenFlush1Minute...`<br>👉 **1분봉 Flush (정상 처리)** | 1. Mocking: Redis 어댑터에서 데이터가 존재하는 DTO 리스트(Size 1)를 반환하도록 세팅 | `flush1MinuteCandles()` 호출 | 1. `ohlcv1mRepository.saveAll()` 메서드가 추출된 데이터 리스트와 함께 **정확히 1회 호출**됨을 검증. |
| **APP-SCH-002** | `givenEmptyCandles_whenFlush1Minute...`<br>👉 **1분봉 Flush (데이터 없음 방어)** | 1. Mocking: Redis 어댑터가 빈 리스트(`List.of()`)를 반환하도록 세팅 | `flush1MinuteCandles()` 호출 | 1. 처리할 데이터가 없으므로 `saveAll()`이 **절대 호출되지 않음(`never()`)**을 검증. |
| **APP-SCH-003** | `givenStockCodesAnd1mCandles_when...`<br>👉 **1일봉 롤업 일괄 처리 (복수 종목)** | 1. 메타데이터 프로바이더가 삼성전자, SK하이닉스 반환<br>2. 각 종목의 1분봉 데이터 Mocking 세팅<br>3. 롤업 서비스가 각 종목의 1일봉 DTO를 반환하도록 Mocking | `flushDailyCandles()` 호출 | 1. 2개 종목의 롤업 결과가 하나의 리스트로 합쳐짐.<br>2. 합쳐진 리스트가 `ohlcv1dRepository.saveAll()`을 통해 **단 1회 호출**되어 DB I/O 부하를 최소화했는지 검증. |
| **APP-SCH-004** | `givenNoStockCodes_whenFlushDaily...`<br>👉 **1일봉 롤업 (상장 종목 없음)** | 1. 메타데이터 프로바이더가 빈 리스트 반환 (조회된 종목 없음) | `flushDailyCandles()` 호출 | 1. 1분봉 조회(`findCandlesByDate`) 로직 호출 안 됨(`never`).<br>2. 롤업 로직(`rollup`) 호출 안 됨(`never`).<br>3. 빈 리스트로 `saveAll()`이 1회 호출되며 에러 없이 정상 종료됨을 검증. |

---

### 2.2. 파티션 테이블 생성 스케줄러 검증
> **대상 클래스:** `PartitionCreationSchedulerTest`
> **검증 목표:** 파티션 누락으로 인한 DB Insert 장애를 방지하기 위한 이중화 스케줄링 시점 검증

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **APP-SCH-005** | `givenApplicationReady_whenInit...`<br>👉 **서버 기동 시 파티션 강제 초기화** | 1. 기준일(Today) 및 익일(Tomorrow) 날짜 객체 세팅 | `initPartitionsOnReady()` 호출 (ApplicationReady 이벤트 모사) | 1. 어댑터의 `createTickPartitionTable()`이 **오늘 날짜로 1회**, **내일 날짜로 1회** 총 2번 정상적으로 호출되었는지 검증 (무중단 배포 시 사각지대 방어). |
| **APP-SCH-006** | `givenScheduledTime_whenSchedule...`<br>👉 **정규 야간 배치 파티션 생성** | 1. 익일(Tomorrow) 날짜 객체 세팅 | `scheduleCreationNextDayPartition()` 호출 (야간 정규 배치 모사) | 1. 어댑터의 `createTickPartitionTable()`이 **내일 날짜로 정확히 1회** 호출됨을 검증. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass  | Fail | 비고 |
| :--- |:------:|:-----:| :---: | :--- |
| **Candle Pipeline** |   4    |   4   | 0 | 1분봉 Flush 및 1일봉 Roll-up 위임 로직 검증 완료 |
| **Partition DDL** |   2    |   2   | 0 | 스케줄러 이중화(기동 시점 + 정규 배치) 로직 검증 완료 |
| **합계** | **6** | **6** | **0** | **Pass** ✅ |

---

**💡 비고 (리뷰 포인트):**
본 테스트는 스케줄러 내부에서 복잡한 연산을 직접 수행하지 않고, 각 Port(Repository, Service)로 책임을 위임(Delegation)하는 **헥사고날 아키텍처(Hexagonal Architecture)**의 특징이 잘 드러나 있습니다.
따라서 상태(State) 검증이 아닌 Mockito의 `verify`를 활용한 **행위(Behavior) 검증**에 초점을 맞추어 문서화를 진행하였습니다.