# [TCS] Stock Redis 어댑터 (스냅샷, 캔들 버퍼, 스로틀링) 테스트 명세서

| 문서 ID | **TCS-REDIS-001**                        |
| :--- |:-----------------------------------------|
| **문서 버전** | 1.2                                      |
| **프로젝트** | AssetMind                                |
| **작성자** | 이재석                                      |
| **작성일** | 2026년 04월 06일                            |
| **관련 모듈** | `stock/infrastructure/persistence/redis` |

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템의 Redis 인프라 계층(`StockSnapshotRedisAdapter`, `CandleRedisAdapter`, `RedisAlertThrottlingAdapter`)에 대한 테스트 명세이다.
`Testcontainers`를 활용한 실제 Redis 통합 테스트와 `Mockito`를 활용한 단위 테스트를 병행하여, 데이터 동기화, 동시성 정합성, 분산 락 로직이 의도대로 동작하는지 검증한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, AssertJ, Spring Boot Test (`@DataRedisTest`), Mockito
- **Infrastructure:** Testcontainers (Redis:alpine)
- **Target Classes:** - `StockSnapshotRedisAdapterTest` (실시간 스냅샷 및 랭킹 - Testcontainers)
  - `CandleRedisAdapterTest` (1분봉 버퍼 및 동시성 제어 - Testcontainers)
  - `RedisAlertThrottlingAdapterTest` (급등락 알림 제어 - Mockito)
- **Verification Focus:**
  - **Data Structure:** Hash, ZSet 데이터 구조의 올바른 적재 및 TTL 만료 검증
  - **Concurrency:** 멀티스레드 환경에서 Lua 스크립트를 통한 원자적(Atomic) OHLCV 롤업 연산 검증
  - **Throttling:** `setIfAbsent`를 이용한 중복 알림 방지(Lock) 획득 성공/실패 검증

---

## 2. Infrastructure Adapter 테스트 명세 - Redis 계층

### 2.1. 주식 스냅샷 및 랭킹 (StockSnapshot) 검증
> **대상 클래스:** `StockSnapshotRedisAdapterTest` (Testcontainers 적용)

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-REDIS-001** | `givenStockData_whenSave...`<br>👉 **저장 검증: Hash 상세 저장 및 ZSet 점수 등록 확인** | **데이터 준비**<br>종목: 삼성전자<br>거래대금: 1,000,000<br>거래량: 500 | `adapter.save(entity)` | 1. **Hash:** Repository 조회 시 종목명과 대금 일치 확인.<br>2. **ZSet(Value):** `ranking:trade_value` 키에 점수 1,000,000 등록 확인.<br>3. **ZSet(Volume):** `ranking:trade_volume` 키에 점수 500 등록 확인. |
| **INF-REDIS-002** | `givenLimitCount_whenGetTopStocksByTradeValue...`<br>👉 **거래대금 랭킹 검증: 내림차순 정렬** | **데이터 준비**<br>A(1000원), B(3000원), C(2000원) 저장 | `adapter.getTopStocksByTradeValue(3)` | 1. 반환 리스트 크기 3 확인.<br>2. 순서가 **B -> C -> A** 인지 검증. |
| **INF-REDIS-003** | `givenLimitCount_whenGetTopStocksByTradeVolume...`<br>👉 **거래량 랭킹 검증: 내림차순 정렬** | **데이터 준비**<br>A(거래량 1등), B(거래량 3등), C(거래량 2등) | `adapter.getTopStocksByTradeVolume(3)` | 1. 반환 리스트 크기 3 확인.<br>2. 대금 순위와 무관하게 **A -> C -> B** 정렬 검증. |
| **INF-REDIS-004** | `givenLimitCount_whenGet...`<br>👉 **Limit 검증: 상위 N개 데이터 절삭** | **데이터 준비**<br>데이터 5개 저장 | `adapter.getTopStocksByTradeValue(2)` | 1. 반환 리스트 크기 **2개** 확인.<br>2. 상위 2개만 포함되었는지 확인. |
| **INF-REDIS-005** | `givenNoDataInRedis_whenGet...`<br>👉 **예외 검증: 데이터 없음 처리** | **데이터 준비**<br>Redis 비어있음 | `adapter.getTopStocksByTradeValue(10)` | 1. `null`이 아닌 **빈 리스트(`isEmpty()`)** 반환 확인. |

---

### 2.2. 1분봉 인메모리 버퍼 (CandleRedis) 검증
> **대상 클래스:** `CandleRedisAdapterTest` (Testcontainers 적용)

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-REDIS-006** | `givenEventAndType_whenSave_thenSaved`<br>👉 **체결 데이터 단건 저장 및 TTL 검증** | 1. 실시간 틱 이벤트 객체 생성 (180,000원 / 거래량 10) | `adapter.save(event, MIN_1)` | 1. Redis Hash 키가 정상 생성됨 (`candle:1m:...`).<br>2. Hash 내 O,H,L,C 값이 모두 180,000으로 세팅됨.<br>3. TTL(만료 시간)이 300초 이하로 정상 부여됨을 검증. |
| **INF-REDIS-007** | `givenTargetTimeAndType_whenFlushCandles...`<br>👉 **타겟 시간 Flush 및 메모리 완전 삭제 검증** | 1. 특정 TargetTime 명시<br>2. Redis에 가상의 1분봉 데이터 강제 주입 | `adapter.flushCandles(targetTime, MIN_1)` | 1. 원본 데이터와 일치하는 DTO 리스트(Size 1)가 반환됨.<br>2. Flush 완료 후 Redis 메모리에서 해당 Key가 **완전히 삭제(`hasKey=false`)**됨을 검증. |
| **INF-REDIS-008** | `givenEmptyKey_whenFlushCandles...`<br>👉 **빈 바구니 Flush 예외 처리 검증** | 1. 데이터가 존재하지 않는 TargetTime 명시 | `adapter.flushCandles(targetTime, MIN_1)` | 1. 에러가 발생하지 않고 **빈 리스트(`isEmpty()`)**가 반환됨을 검증. |
| **INF-REDIS-009** | `givenConcurrentRequests_whenSave...`<br>👉 **동시성(Concurrency) 및 정합성 검증** | 1. 100개의 스레드 생성<br>2. 1,000,000원 ~ 1,000,099원까지 가격을 증가시키며 동시 요청 세팅 | `adapter.save(event, MIN_1)` 동시 100회 실행 | 1. Race Condition 없이 단 1개의 Key에 데이터가 정상 취합됨.<br>2. **로직 정확도:** 최고가(High) = 1000099, 최저가(Low) = 1000000, 누적 거래량(Volume) = 1000 이 정확하게 연산됨을 증명. |

---

### 2.3. 급등락 알림 스로틀링 (AlertThrottling) 검증
> **대상 클래스:** `RedisAlertThrottlingAdapterTest` (Mockito 적용)

| ID | 테스트 메서드 / 시나리오 | Given (사전 조건) | When (수행 행동) | Then (검증 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **INF-REDIS-010** | `givenStockCode_whenAllowAlert...`<br>👉 **스로틀링 통과 (최초 알림 발생 시)** | 1. Redis 연산 모킹: `setIfAbsent` 호출 시 **true**를 반환하도록 세팅 (해당 키가 존재하지 않음) | `adapter.allowAlert(stockCode)` | 1. 락 획득에 성공하여 **true**를 반환함. |
| **INF-REDIS-011** | `givenExistsKeyStockCode_whenAllowAlert...`<br>👉 **스로틀링 방어 (단기간 중복 알림 발생 시)** | 1. Redis 연산 모킹: `setIfAbsent` 호출 시 **false**를 반환하도록 세팅 (이미 쿨타임 락이 존재함) | `adapter.allowAlert(stockCode)` | 1. 락 획득에 실패하여 **false**를 반환하여 중복 알림을 방지함. |

---

## 3. 테스트 결과 요약

### 3.1. 수행 결과
| 구분 | 전체 케이스 | Pass  | Fail | 비고 |
| :--- |:------:|:-----:| :---: | :--- |
| **Stock Snapshot (TC)** |   5    |   5   | 0 | Testcontainers(Redis) - Hash 및 ZSet 검증 |
| **Candle Buffer (TC)** |   4    |   4   | 0 | Testcontainers(Redis) - 100 스레드 동시성 로직 통과 |
| **Alert Throttling (Mock)** |   2    |   2   | 0 | Mockito - `setIfAbsent` 기반 Lock 획득/실패 검증 |
| **합계** | **11** | **11** | **0** | **Pass** ✅ |

---

**💡 비고:**
- **Testcontainers 연동:** 스냅샷(`StockSnapshotRedisAdapter`)과 1분봉 버퍼(`CandleRedisAdapter`)는 데이터 무결성과 멀티스레딩 동시성 방어 로직이 핵심이므로, 실제 Redis 컨테이너를 띄우는 슬라이스 테스트로 진행하여 신뢰성을 극대화하였습니다.
- **Mockito 연동:** 알림 스로틀링(`RedisAlertThrottlingAdapter`)은 Redis 자체의 명령어 동작(`setIfAbsent`)에 의존하므로, 테스트 속도 최적화를 위해 의존성을 Mocking하여 단위 테스트로 작성하였습니다.