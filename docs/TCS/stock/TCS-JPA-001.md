# [TCS] Stock JPA 어댑터(캔들 및 틱 데이터) 테스트 명세서

| 문서 ID | **TCS-JPA-001**                        |
| :--- |:---------------------------------------|
| **문서 버전** | 1.1                                    |
| **프로젝트** | AssetMind                              |
| **작성자** | 이재석                                    |
| **작성일** | 2026년 04월 06일                          |
| **관련 모듈** | `stock/infrastructure/persistence/jpa` |

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템의 주식 데이터 영속성 계층(`Ohlcv1dJpaAdapter`, `Ohlcv1mJpaAdapter`, `RawTickJpaAdapter`)에 대한 슬라이스 테스트 명세이다.
`Testcontainers`를 사용하여 실제 **PostgreSQL** 환경을 도커 컨테이너로 구성하고, JPA 리포지토리 및 네이티브 집계 쿼리(`date_bin`, `date_trunc`, `array_agg`)가 실제 데이터베이스와 어떻게 상호작용하는지 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Spring Boot Test (`@DataJpaTest`)
- **Infrastructure:** Testcontainers (PostgreSQL 16-alpine)
- **Target Classes:** - `Ohlcv1dJpaAdapterTest` (1일봉 어댑터)
  - `Ohlcv1mJpaAdapterTest` (1분봉 어댑터)
  - `RawTickJpaAdapterTest` (실시간 틱 어댑터)
- **Verification Focus:**
  - **Persistence:** 순수 DTO가 엔티티로 변환되어 DB에 정상 저장(단건/일괄)되는지 검증
  - **Dynamic Aggregation:** N분봉/N일봉/월/년봉 등 동적 롤업 시 시가(Open), 고가(High), 저가(Low), 종가(Close), 거래량(Volume)이 DB 레벨에서 오차 없이 계산되는지 검증
  - **Ordering & Filtering:** 시계열 데이터가 조건(날짜, 종목코드)에 맞게 필터링되고 최신순(DESC) 정렬되는지 검증

---

## 2. Infrastructure Adapter 테스트 명세

### 2.1. 1일봉 (Ohlcv1d) 어댑터 검증
> **대상 클래스:** `Ohlcv1dJpaAdapterTest`

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-JPA-001** | `givenDtoList_whenSaveAll...`<br>👉 **일괄 저장 (SaveAll)** | 1. 1일봉 DTO 리스트 (2개) 생성 | `adapter.saveAll(dtoList)` 호출 | 1. DB에 저장된 데이터 크기가 **2개**인지 검증. |
| **INF-JPA-002** | `givenSingleDto_whenSave...`<br>👉 **단건 저장 (Save)** | 1. 1일봉 DTO 단건 생성 | `adapter.save(dto)` 호출 | 1. DB에 1건이 저장되며, 종목코드와 종가가 일치하는지 검증. |
| **INF-JPA-003** | `givenDate_whenFindCandleByDay...`<br>👉 **특정 날짜 단건 조회 (성공)** | 1. 3/30일 1일봉 데이터 DB 저장<br>2. 조회 대상: 3/30일 | `adapter.findCandleByDay(date)` 호출 | 1. `Optional`에 데이터가 존재해야 함.<br>2. 반환된 DTO의 타임스탬프와 가격 정보가 정확한지 검증. |
| **INF-JPA-004** | `givenDateWithNoData_when...`<br>👉 **특정 날짜 단건 조회 (데이터 없음)** | 1. DB 텅 빈 상태<br>2. 조회 대상: 3/31일 | `adapter.findCandleByDay(date)` 호출 | 1. `Optional.empty()`가 반환됨을 검증. |
| **INF-JPA-005** | `givenDailyCandles_whenFindDynamic...`<br>👉 **N일봉 동적 집계 (`date_bin`)** | 1. 1/1일 ~ 1/3일 (3일간) 1일봉 저장 | `adapter.findDynamicDailyCandles("3 days")` 호출 | 1. 3개의 1일봉이 1개의 3일봉으로 병합됨.<br>2. **OHLCV 검증:** 시가(1/1), 최고점(3일 중), 최저점(3일 중), 종가(1/3), 거래량(총합)이 완벽히 일치하는지 확인. |
| **INF-JPA-006** | `givenCandlesAcrossMonths_when...`<br>👉 **월봉 집계 (`date_trunc`)** | 1. 3월 데이터 2건, 4월 데이터 1건 저장 | `adapter.findMonthlyCandles()` 호출 | 1. 총 2개의 월봉이 DESC 순으로 반환.<br>2. 각 캔들의 시간이 매월 1일로 버림(trunc) 되었는지 확인.<br>3. 3월의 2건이 하나로 정상 집계되었는지 검증. |
| **INF-JPA-007** | `givenCandlesAcrossYears_when...`<br>👉 **년봉 집계 (`date_trunc`)** | 1. 2025년 데이터 1건, 2026년 데이터 1건 저장 | `adapter.findYearlyCandles()` 호출 | 1. 총 2개의 년봉이 DESC 순으로 반환.<br>2. 각 캔들의 시간이 매년 1월 1일로 버림(trunc) 되었는지 확인. |

---

### 2.2. 1분봉 (Ohlcv1m) 어댑터 검증
> **대상 클래스:** `Ohlcv1mJpaAdapterTest`

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-JPA-008** | `givenDtoList_whenSaveAll...`<br>👉 **일괄 저장 (SaveAll)** | 1. 1분봉 DTO 리스트 (2개) 생성 | `adapter.saveAll(dtoList)` 호출 | 1. DB에 저장된 데이터 크기가 **2개**인지 검증.<br>2. 종목 및 종가/거래량 데이터 무결성 검증. |
| **INF-JPA-009** | `givenSpecificDate_whenFindCandles...`<br>👉 **특정 날짜 범위 내 캔들 조회** | 1. 어제, 오늘(2건), 내일 1분봉 데이터 저장 | `adapter.findCandlesByDate(today)` 호출 | 1. 결과가 정확히 **2개**만 반환됨.<br>2. 어제와 내일 데이터가 철저히 배제되었는지 검증 (00:00:00 ~ 23:59:59 범위 확인). |
| **INF-JPA-010** | `givenMinuteCandles_whenFindDynamic...`<br>👉 **N분봉 동적 집계 (`date_bin`)** | 1. 00:00~00:02 구간(3건)과 00:03 구간(1건) 데이터 저장 | `adapter.findDynamicMinuteCandles("3 minutes", limit=10)` 호출 | 1. 2개의 바구니(3분봉 2개)가 최신순(DESC)으로 조회됨.<br>2. 과거 바구니(00:00~00:02)의 OHLCV가 3개의 원본을 바탕으로 정확히 롤업되었는지 검증. |

---

### 2.3. 실시간 틱 (RawTick) 어댑터 검증
> **대상 클래스:** `RawTickJpaAdapterTest`

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-JPA-011** | `givenStockData_whenSaveAndFind...`<br>👉 **최신 틱 데이터 조회 및 정렬/격리** | 1. 1분 전, 5분 전, 10분 전 틱 데이터 생성<br>2. 타 종목 노이즈 데이터 생성<br>→ 모두 일괄 저장 | `adapter.findRecentData(code, 2)` 호출 (최신 2건 요청) | 1. 타 종목 데이터 및 10분 전 데이터가 배제되고 **2건**만 반환됨.<br>2. **정렬 검증:** 첫 번째가 1분 전, 두 번째가 5분 전 데이터로 내림차순(DESC) 정렬되었는지 확인. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass  | Fail | 비고 |
| :--- |:------:|:-----:| :---: | :--- |
| **Ohlcv1d (1일봉)** |   7    |   7   | 0 | 일/월/년 단위 네이티브 집계 쿼리 검증 완료 |
| **Ohlcv1m (1분봉)** |   3    |   3   | 0 | N분봉 네이티브 집계 쿼리 검증 완료 |
| **RawTick (틱 체결)** |   1    |   1   | 0 | 최신순 정렬 및 타 종목 필터링 쿼리 검증 완료 |
| **합계** | **11** | **11** | **0** | **Pass** ✅ |

---

**💡 비고:**
본 테스트는 `Mockito`를 사용한 Mock 테스트가 아닌, **`Testcontainers`를 활용한 데이터베이스 슬라이스 테스트(Slice Test)**입니다.
실제 PostgreSQL 16 인스턴스를 도커 컨테이너로 띄워 실행하며, 특히 `date_bin`, `date_trunc`, `array_agg`와 같은 PostgreSQL 특화 네이티브 함수들이 실제 환경에서 오차 없이 동작하는지를 집중적으로 검증하였습니다.