# [TCS] 주식 서비스 단위 테스트 명세서

| 문서 ID | **TCS-STK-001**                         |
| :--- |:----------------------------------------|
| **문서 버전** | 1.0                                     |
| **프로젝트** | AssetMind                               |
| **작성자** | 이재석                                     |
| **작성일** | 2026년 02월 13일                           |
| **대상 모듈** | `server-stock/application/StockService` |

## 1. 개요 (Overview)

본 문서는 실시간 주가 데이터 처리 및 조회를 담당하는 `StockService`의 비즈니스 로직을 검증하기 위한 단위 테스트 명세이다.
외부 의존성(Redis Repository, JPA Repository, Metadata Provider, Mapper)을 **Mocking**하여 데이터 흐름 제어, 예외 처리(Validation), 저장소 호출 여부가 의도대로 동작하는지 확인한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Mockito
- **Test Class:** `StockServiceTest`
- **Mock Objects:**
    - `StockSnapshotRepository`: Redis 기반 실시간 데이터 저장/조회 모의
    - `StockHistoryRepository`: DB 기반 시계열 데이터 저장/조회 모의
    - `StockMetadataProvider`: 인메모리 주식 메타데이터(종목명) 제공 모의
    - `StockMapper`: Event 객체와 Entity 간의 변환 모의

---

## 2. 실시간 주가 처리 테스트 (`processRealTimeTrade`)

실시간으로 유입되는 주가 데이터를 검증하고, 메타데이터와 결합하여 Redis(스냅샷)와 DB(이력)에 저장하는 프로세스를 검증한다.

| ID | 시나리오                                          | Given (사전 조건) | When (실행) | Then (기대 결과)                                                                                                                                                                                                                                                                  |
| :--- |:----------------------------------------------| :--- | :--- |:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **SVC-STK-001** | **정상 처리**<br>(Redis/DB 저장 성공 및 2개의 이벤트 발행 성공) | 1. 유효한 `Event` 객체<br>2. `MetadataProvider`: 종목명 반환<br>3. `Mapper`: Entity 변환 성공 | `processRealTimeTrade(event)` 호출 | 1. `MetadataProvider.getStockName()` 호출<br>2. `StockSnapshotRepository.save()` 1회 호출<br>3. `StockHistoryRepository.save()` 1회 호출<br>4.`eventPublisher.publishEvent(StockHistorySavedEvent.class)` 1회 호출<br>5.`eventPublisher.publishEvent(StockRankingUpdatedEvent.class)` 1회 호출 |
| **SVC-STK-002** | **실패: 이벤트 Null**                              | 1. 입력 `Event`가 `null` | `processRealTimeTrade(null)` 호출 | 1. `InvalidStockParameterException` 예외 발생<br>2. ErrorCode: `INVALID_STOCK_PARAMETER`                                                                                                                                                                                          |
| **SVC-STK-003** | **실패: 종목코드 Null**                             | 1. `Event` 내부 `stockCode`가 `null` | `processRealTimeTrade(event)` 호출 | 1. `InvalidStockParameterException` 예외 발생<br>2. 저장소 메서드는 호출되지 않아야 한다.                                                                                                                                                                                                         |
| **SVC-STK-004** | **실패: 종목코드 빈 값**                              | 1. `Event` 내부 `stockCode`가 `""` (Empty) | `processRealTimeTrade(event)` 호출 | 1. `InvalidStockParameterException` 예외 발생<br>2. 저장소 메서드는 호출되지 않아야 한다.                                                                                                                                                                                                         |

---

## 3. 주식 랭킹 조회 테스트 (`Ranking`)

Redis에 저장된 누적 거래대금 및 거래량을 기준으로 상위 종목을 조회하는 로직을 검증한다.

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-STK-005** | **거래대금 순 조회 성공** | 1. `limit` = 10<br>2. `SnapshotRepo`: Redis Entity 리스트 반환 | `getTopStocksByTradeValue(limit)` 호출 | 1. `SnapshotRepo.getTopStocksByTradeValue(limit)`가 호출되어야 한다.<br>2. 반환된 리스트가 예상 결과와 일치해야 한다. |
| **SVC-STK-006** | **거래량 순 조회 성공** | 1. `limit` = 5<br>2. `SnapshotRepo`: Redis Entity 리스트 반환 | `getTopStocksByTradeVolume(limit)` 호출 | 1. `SnapshotRepo.getTopStocksByTradeVolume(limit)`가 호출되어야 한다.<br>2. 반환된 리스트가 예상 결과와 일치해야 한다. |

---

## 4. 시계열 데이터 조회 테스트 (`History`)

특정 종목의 최근 주가 흐름(차트 데이터)을 DB에서 조회하는 로직을 검증한다.

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-STK-007** | **시계열 조회 성공** | 1. 유효한 `stockCode`, `limit`<br>2. `HistoryRepo`: DB Entity 리스트 반환 | `getStockRecentHistory(code, limit)` 호출 | 1. `HistoryRepo.findRecentData(code, limit)`가 호출되어야 한다.<br>2. 반환된 리스트가 예상 결과와 일치해야 한다. |
| **SVC-STK-008** | **실패: 종목코드 Null** | 1. `stockCode`가 `null`<br>2. `limit` = 10 | `getStockRecentHistory(null, limit)` 호출 | 1. `InvalidStockParameterException` 예외 발생<br>2. DB 조회 메서드는 호출되지 않아야 한다. |
| **SVC-STK-009** | **실패: 종목코드 빈 값** | 1. `stockCode`가 `"  "` (Blank)<br>2. `limit` = 10 | `getStockRecentHistory(" ", limit)` 호출 | 1. `InvalidStockParameterException` 예외 발생<br>2. DB 조회 메서드는 호출되지 않아야 한다. |

---

## 5. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고                                                              |
| :--- | :---: | :---: | :---: |:----------------------------------------------------------------|
| **Real-Time Process** | 4 | 4 | 0 | 데이터 파이프라인(Event -> Redis/DB -> New Event 발행) 및 Validation 검증 완료 |
| **Ranking Logic** | 2 | 2 | 0 | Redis 조회 위임 로직 검증 완료                                            |
| **History Logic** | 3 | 3 | 0 | DB 조회 위임 및 파라미터 검증 완료                                           |
| **합계** | **9** | **9** | **0** | **Pass** ✅                                                      |