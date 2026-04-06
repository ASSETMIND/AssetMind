# [TCS] Stock Partition JDBC 어댑터 테스트 명세서

| 문서 ID | **TCS-JDBC-001** |
| :--- |:---------------------------------------|
| **문서 버전** | 1.0                                    |
| **프로젝트** | AssetMind                              |
| **작성자** | 이재석                                    |
| **작성일** | 2026년 04월 06일                          |
| **관련 모듈** | `stock/infrastructure/persistence/jdbc` |

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템의 대용량 틱 데이터 관리를 위한 파티션 테이블 자동 생성 어댑터(`PartitionJdbcAdapter`)에 대한 단위 테스트 명세이다.
순수 `Mockito`를 활용하여 `JdbcTemplate`을 모킹(Mocking)함으로써, 날짜별 동적 DDL(Data Definition Language) 쿼리가 정확히 생성되는지 검증하고, DB 장애 시 스케줄러를 보호하기 위한 예외 방어 로직이 올바르게 동작하는지 확인한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Mockito (`@ExtendWith(MockitoExtension.class)`)
- **Infrastructure:** 모킹된 JdbcTemplate (실제 DB 연결 없음)
- **Target Class:** `PartitionJdbcAdapterTest`
- **Verification Focus:**
    - **Dynamic SQL Generation:** `ArgumentCaptor`를 활용하여 런타임에 동적으로 조합되는 파티션 생성 쿼리의 문법적 정확성 검증
    - **Fault Tolerance (장애 격리):** DB 연결 에러나 문법 에러 발생 시 예외가 스케줄러 계층으로 전파되지 않고 내부에서 안전하게 Catch 되는지 검증

---

## 2. Infrastructure Adapter 테스트 명세 - 파티셔닝 DDL 계층

### 2.1. 동적 파티션 테이블 생성 및 예외 처리 검증
> **대상 클래스:** `PartitionJdbcAdapterTest`

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-JDBC-001** | `givenDate_whenCreateTickPartitionTable_thenExecutesCorrectSql`<br>👉 **동적 DDL 쿼리 생성 및 실행 검증** | 1. 파티션 생성 타겟 날짜 객체 세팅 (예: 2026년 3월 31일) | `adapter.createTickPartitionTable(targetDate)` 호출 | 1. `JdbcTemplate.execute()`가 정확히 1회 호출됨을 확인.<br>2. `ArgumentCaptor`로 낚아챈 SQL 문자열에 다음 구문이 완벽히 포함되는지 검증:<br>  - `CREATE TABLE IF NOT EXISTS raw_tick_20260331`<br>  - `PARTITION OF raw_tick`<br>  - `FOR VALUES FROM ('2026-03-31 00:00:00') TO ('2026-04-01 00:00:00')` |
| **INF-JDBC-002** | `givenDbException_whenCreateTickPartitionTable_thenCatchesException...`<br>👉 **스케줄러 장애 전파 방어 (예외 삼키기) 검증** | 1. 파티션 생성 타겟 날짜 세팅<br>2. Mocking: `JdbcTemplate`이 어떤 SQL을 받든 무조건 `DataAccessException` (DB 연결 실패 등)을 던지도록 조작 | `adapter.createTickPartitionTable(targetDate)` 호출 | 1. 어댑터 호출 시 밖으로 에러가 터져 나오지 않음 (`assertDoesNotThrow`).<br>2. 내부적으로 `execute()`가 1회 시도되었음을 검증 (예외 방어 로직의 정확한 동작 증명). |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass  | Fail | 비고 |
| :--- |:------:|:-----:| :---: | :--- |
| **Partition DDL (JDBC)** |   2    |   2   | 0 | Mockito 기반 DDL 쿼리 캡처 및 예외 억제 검증 완료 |
| **합계** | **2** | **2** | **0** | **Pass** ✅ |

---

**💡 비고 (리뷰 포인트):**
본 테스트는 스케줄러 배치 작업의 안정성에 직결되는 핵심 검증입니다.
파티션 테이블 생성 로직이 실패하더라도 전체 애플리케이션이나 다른 스케줄러 체인에 영향을 주지 않도록 `try-catch`로 예외를 억제한 점(Fault Tolerance)을 명시적으로 테스트(`INF-JDBC-002`)하여 시스템의 견고함을 증명하였습니다.