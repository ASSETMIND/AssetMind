# [TCS] Stock History JPA 어댑터 테스트 명세서

| 문서 ID | **TCS-JPA-001**                        |
| :--- |:---------------------------------------|
| **문서 버전** | 1.0                                    |
| **프로젝트** | AssetMind                              |
| **작성자** | 이재석                                    |
| **작성일** | 2026년 02월 10일                          |
| **관련 모듈** | `stock/infrastructure/persistence/jpa` |

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템의 주식 체결 내역 저장소(`StockHistoryJpaAdapter`)에 대한 슬라이스 테스트 명세이다.
`Testcontainers`를 사용하여 실제 **PostgreSQL** 환경을 도커 컨테이너로 구성하고, JPA 리포지토리가 실제 데이터베이스와 상호작용(저장, 조회, 정렬, 필터링)하는 로직을 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Spring Boot Test (`@DataJpaTest`)
- **Infrastructure:** Testcontainers (PostgreSQL 16-alpine)
- **Target Class:** `StockHistoryJpaAdapterTest`
- **Verification Focus:**
    - **Persistence:** 엔티티가 DB에 정상적으로 Insert 되는지 검증
    - **Ordering:** 시계열 데이터가 `createdAt` 기준 내림차순(최신순)으로 정렬되는지 검증
    - **Pagination (Limit):** 요청한 개수(`limit`)만큼만 데이터를 가져오는지 검증
    - **Isolation:** 특정 종목 코드(`stockCode`)에 해당하는 데이터만 정확히 필터링되는지 검증

---

## 2. Infrastructure Adapter 테스트 명세 - 주식 체결 내역
> **대상 클래스:** `StockHistoryJpaAdapterTest`
> **검증 목표:** `JpaRepository`와 연동하여 과거 체결 데이터를 저장하고, 비즈니스 요구사항(최신순, 개수 제한)에 맞춰 조회하는지 확인

### 2.1. 저장 및 조회 (Save & Find) 검증

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-JPA-001** | `givenStockData_`<br>`whenSaveAndFindData_`<br>`thenReturnSavedDataOrderByCreatedAt`<br>👉 **정렬 및 개수 제한 검증: 최신순 정렬과 Limit 동작 확인** | **데이터 준비**<br>1. 10분 전 데이터 (Old)<br>2. **현재 데이터 (Recent)**<br>3. 1시간 전 데이터 (VeryOld)<br>→ 순서 섞어서 저장 | **`adapter.findRecentData(CODE, 2)`**<br>(최신 2개 조회 요청) | 1. 반환된 리스트의 크기가 **2개**인지 확인.<br>2. **첫 번째:** 가장 최신 데이터(`Recent`)인지 확인.<br>3. **두 번째:** 그 다음 최신 데이터(`Old`)인지 확인.<br>4. 가장 오래된 데이터(`VeryOld`)는 포함되지 않았음을 검증. |
| **INF-JPA-002** | `givenOtherStockCode_`<br>`whenSaveAndFindData_`<br>`thenReturnOnlySavedData`<br>👉 **필터링 검증: 타 종목 데이터 격리 확인** | **데이터 준비**<br>1. 삼성전자(`005930`) 데이터<br>2. 네이버(`035420`) 데이터<br>→ 모두 저장 | **`adapter.findRecentData("005930", 10)`**<br>(삼성전자 조회 요청) | 1. 반환된 리스트의 크기가 **1개**인지 확인.<br>2. 조회된 데이터의 종목 코드가 요청한 코드(`005930`)와 일치하는지 검증.<br>3. 타 종목(`035420`) 데이터가 섞이지 않았음을 확인. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass  | Fail | 비고 |
| :--- |:------:|:-----:| :---: | :--- |
| **Stock History (JPA)** |   2    |   2   | 0 | PostgreSQL 컨테이너 연동 성공 |
| **합계** | **2** | **2** | **0** | **Pass** ✅ |

---

**💡 비고:**
본 테스트는 `Mockito`를 사용한 Mock 테스트가 아닌, **`Testcontainers`를 활용한 슬라이스 테스트(Slice Test)**입니다.
실제 PostgreSQL 인스턴스를 도커로 띄워 실행하므로, `ddl-auto=create-drop` 설정을 통해 스키마 생성 및 데이터 적재가 정상적으로 이루어지는지까지 포함하여 검증하였습니다.