# [TCS] Stock Snapshot Redis 어댑터 테스트 명세서

| 문서 ID | **TCS-REDIS-001**                        |
| :--- |:-----------------------------------------|
| **문서 버전** | 1.0                                      |
| **프로젝트** | AssetMind                                |
| **작성자** | 이재석                                      |
| **작성일** | 2026년 02월 10일                            |
| **관련 모듈** | `stock/infrastructure/persistence/redis` |

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템의 실시간 주식 시세 스냅샷 및 랭킹 저장소(`StockSnapshotRedisAdapter`)에 대한 슬라이스 테스트 명세이다.
`Testcontainers`를 사용하여 실제 **Redis** 환경을 도커 컨테이너로 구성하고, Redis Hash(상세 정보)와 ZSet(랭킹 점수) 간의 데이터 동기화 및 정렬 조회가 올바르게 동작하는지 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Spring Boot Test (`@DataRedisTest`)
- **Infrastructure:** Testcontainers (Redis:alpine)
- **Target Class:** `StockSnapshotRedisAdapterTest`
- **Verification Focus:**
    - **Dual Write:** `save` 시 Hash(상세)와 ZSet(랭킹)에 동시에 데이터가 적재되는지 검증
    - **Ranking Logic:** 거래대금(TradeValue)과 거래량(TradeVolume) 기준 내림차순 정렬 검증
    - **Limit:** 요청한 개수만큼 상위 데이터를 잘라오는지 검증
    - **Edge Case:** 데이터가 없을 때의 빈 리스트 반환 처리 검증

---

## 2. Infrastructure Adapter 테스트 명세 - 주식 스냅샷 및 랭킹
> **대상 클래스:** `StockSnapshotRedisAdapterTest`
> **검증 목표:** 실시간 시세 데이터의 저장 구조(Hash+ZSet) 일관성과 랭킹 조회 로직의 정확성 확인

### 2.1. 저장 및 랭킹 조회 (Save & Ranking) 검증

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-REDIS-001** | `givenStockData_`<br>`whenSave_`<br>`thenSavedStockDataAndRanking`<br>👉 **저장 검증: Hash 상세 저장 및 ZSet 점수 등록 확인** | **데이터 준비**<br>종목: 삼성전자<br>거래대금: 1,000,000<br>거래량: 500 | **`adapter.save(entity)`** | 1. **Hash:** Repository 조회 시 종목명("삼성전자")과 대금 일치 확인.<br>2. **ZSet(Value):** `ranking:trade_value` 키에 점수 1,000,000 등록 확인.<br>3. **ZSet(Volume):** `ranking:trade_volume` 키에 점수 500 등록 확인. |
| **INF-REDIS-002** | `givenLimitCount_`<br>`whenGetTopStocksByTradeValue_`<br>`thenReturnTradeValueRankingData`<br>👉 **거래대금 랭킹 검증: 대금 기준 내림차순 정렬** | **데이터 준비**<br>A(1000원), B(3000원), C(2000원)<br>→ 순서 섞어서 저장 | **`adapter.getTopStocksByTradeValue(3)`** | 1. 반환된 리스트 크기 3 확인.<br>2. 순서가 **B(1등) -> C(2등) -> A(3등)** 인지 검증.<br>3. 각 항목의 누적 거래대금 값 일치 확인. |
| **INF-REDIS-003** | `givenLimitCount_`<br>`whenGetTopStocksByTradeVolume_`<br>`thenReturnTradeVolumeRankingData`<br>👉 **거래량 랭킹 검증: 거래량 기준 내림차순 정렬** | **데이터 준비**<br>A(대금 3등, **거래량 1등**)<br>B(대금 1등, **거래량 3등**)<br>C(대금 2등, **거래량 2등**) | **`adapter.getTopStocksByTradeVolume(3)`** | 1. 반환된 리스트 크기 3 확인.<br>2. 대금 순위와 무관하게 **A -> C -> B** 순서로 정렬되었는지 검증. |
| **INF-REDIS-004** | `givenLimitCount_`<br>`whenGet_`<br>`thenReturnCollectLimitCountData`<br>👉 **Limit 검증: 상위 N개 데이터 절삭** | **데이터 준비**<br>데이터 5개 저장 (CODE1 ~ CODE5) | **`adapter.getTopStocksByTradeValue(2)`** | 1. 반환된 리스트 크기가 **2개**인지 확인.<br>2. 가장 점수가 높은 상위 2개(CODE5, CODE4)만 포함되었는지 확인. |
| **INF-REDIS-005** | `givenNoDataInRedis_`<br>`whenGet_`<br>`thenEmptyList`<br>👉 **예외 검증: 데이터 없음 처리** | **데이터 준비**<br>Redis 데이터 없음 (Empty) | **`adapter.getTopStocksByTradeValue(10)`** | 1. `null`이 아닌 **빈 리스트(`isEmpty()`)**가 반환되는지 확인. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass  | Fail | 비고 |
| :--- |:------:|:-----:| :---: | :--- |
| **Stock Snapshot (Redis)** |   5    |   5   | 0 | Testcontainers(Redis) 연동 성공 |
| **합계** | **5** | **5** | **0** | **Pass** ✅ |

---

**💡 비고:**
본 테스트는 `Mockito`를 사용하지 않고, **`Testcontainers`를 활용한 슬라이스 테스트(Slice Test)**입니다.
실제 Redis 인스턴스를 도커로 띄워 실행하므로, `StringRedisTemplate`을 통한 ZSet 연산과 `CrudRepository`를 통한 Hash 연산이 실제 환경과 동일하게 동작함을 보장합니다.