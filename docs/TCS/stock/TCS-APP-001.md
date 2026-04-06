# [TCS] Stock Application(비즈니스 로직) 계층 테스트 명세서

| 문서 ID | **TCS-APP-001** |
| :--- |:----------------------------------------|
| **문서 버전** | 1.0                                     |
| **프로젝트** | AssetMind                               |
| **작성자** | 이재석                                     |
| **작성일** | 2026년 04월 06일                           |
| **대상 모듈** | `server-stock/application` (Service Layer)|

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템의 핵심 비즈니스 로직을 담당하는 **Application 계층**의 단위 테스트 명세이다.
외부 인프라(DB, Redis) 의존성을 `Mockito`로 완벽히 격리하여 서비스 간의 데이터 흐름(라우팅, 알림 제어)을 검증하며, 특히 `CandleRollupService`와 같은 순수 도메인 로직은 Mocking 없이 POJO 상태에서 연산의 정확성을 독립적으로 검증한다.

### 1.1. 대상 서비스 및 검증 목표
- **`StockService`**: 실시간 주가 데이터 파이프라인(Event -> Redis/DB) 및 랭킹/시계열 조회 위임 로직
- **`ChartService`**: 타임프레임(1m, 1d, 1mo 등)에 따른 동적 Repository 라우팅 및 예외 처리
- **`CandleRollupService`**: 1분봉/1일봉 데이터를 N분/주/월/년봉으로 압축(Roll-up)하는 순수 비즈니스 연산
- **`StockSurgeAlertService`**: 급등락(±10%) 판단 및 스로틀링(Throttling)을 통한 알림 제어 로직

---

## 2. 실시간 주가 파이프라인 및 조회 (`StockService`)

실시간 유입 데이터의 파이프라인 저장 및 랭킹, 과거 시계열 조회의 흐름을 검증한다.

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-STK-001** | **실시간 주가 정상 처리** | 유효한 `Event` 객체, 메타데이터/Mapper 모킹 | `processRealTimeTrade(event)` | Redis/DB 저장 메서드 1회씩 호출, History/Ranking 이벤트 2개 정상 발행 확인 |
| **SVC-STK-002** | **실시간 주가 처리 실패 (Parameter Null/Empty)** | `Event` 객체가 `null`이거나 `stockCode`가 비어있음 | `processRealTimeTrade()` | `IllegalArgumentException` 발생, 하위 저장소 로직 호출 안 됨(`never`) |
| **SVC-STK-003** | **랭킹 조회 성공 (거래대금/거래량)** | `limit` 개수 지정, Redis Repo 리스트 반환 모킹 | `getTopStocksByTradeValue()`, `Volume()` | Redis 조회 로직 정상 위임 확인 및 응답 DTO(`StockRankingResponse`) 매핑 검증 |
| **SVC-STK-004** | **시계열 조회 성공 및 예외 처리** | 유효/무효한 `stockCode` 입력 | `getStockRecentHistory()` | 정상 시 JPA Repo 위임 확인, 누락/빈 값 시 `StockNotFoundException` 에러 발생 |

---

## 3. 동적 차트 서빙 라우팅 (`ChartService`)

클라이언트가 요청한 타임프레임에 맞춰 올바른 DB 어댑터(1분봉 vs 1일봉)로 트래픽을 분기(Routing)하는지 검증한다.

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-CHT-001** | **기준 시간(endTime) 편의성 제공** | `endTime`을 `null`로 세팅 | `getCandles(..., null, ...)` | 서버의 현재 시간(`LocalDateTime.now()`)이 쿼리 파라미터로 주입되어 라우팅됨을 검증 |
| **SVC-CHT-002** | **분봉(Minutes) 라우팅 성공** | `1m`, `3m`, `5m`, `15m` 타임프레임 입력 | `getCandles()` | `Ohlcv1mRepository`(1분봉)의 동적 집계 쿼리로 정확한 간격(Interval) 문자열이 전달됨 |
| **SVC-CHT-003** | **일/주/월/년봉(Daily+) 라우팅 성공** | `1d`, `1w`, `1mo`, `1y` 타임프레임 입력 | `getCandles()` | `Ohlcv1dRepository`(1일봉)의 각각 알맞은 메서드(`findDynamic...`, `findMonthly...`, `findYearly...`)로 분기됨을 검증 |
| **SVC-CHT-004** | **잘못된 타임프레임 요청 예외 (Validation)** | `23m`, `99h` 등 미지원 규격 입력 | `getCandles()` | `InvalidChartParameterException` 발생 및 "지원하지 않는 타임프레임" 에러 메시지 반환 |
| **SVC-CHT-005** | **응답 DTO 완벽 매핑 검증** | 원본 `OhlcvDto` 모킹 반환 | `getCandles()` | 프론트엔드 규격인 `ChartResponseDto.CandleDto`로 데이터(O,H,L,C,V) 누락 없이 100% 매핑됨 |

---

## 4. 캔들 데이터 동적 롤업 연산 (`CandleRollupService`)

외부 의존성 없이 순수 Java 로직으로 N분, N일, N월봉의 날짜 경계선 계산 및 OHLCV 병합이 완벽히 수행되는지 검증한다.

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-ROL-001** | **N분봉 롤업 (OHLCV 정확도)** | 연속된 1분봉 3개 데이터 세팅 | `rollup(candles, MIN_5)` | 시가(첫 분), 고가(최고가), 저가(최저가), 종가(마지막 분), 거래량(총합) 연산 일치 확인 |
| **SVC-ROL-002** | **주봉(Weekly) 달력 경계 연산** | 같은 주에 속한 수요일, 금요일 1일봉 세팅 | `rollup(candles, WEEK_1)` | 해당 캔들의 기준 시간이 **해당 주의 월요일(`DayOfWeek.MONDAY`)**로 정확히 맞춰짐 |
| **SVC-ROL-003** | **월/년봉(Monthly, Yearly) 경계 연산** | 여러 날짜의 1일봉 세팅 | `rollup(..., MONTH_1/YEAR_1)` | 기준 시간이 **해당 월의 1일** 또는 **해당 연도의 1월 1일**로 정확히 버림(Truncate) 처리됨 |
| **SVC-ROL-004** | **빈 데이터 방어 로직** | 빈 리스트(`List.of()`) 입력 | `rollup(emptyList, ...)` | 에러 발생 없이 안전하게 빈 리스트 반환 |

---

## 5. 급등락 알림 및 스로틀링 제어 (`StockSurgeAlertService`)

주가 등락률(±10%) 비즈니스 규칙과 알림 도배 방지(Throttling) 로직이 올바르게 맞물려 동작하는지 검증한다.

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **SVC-ALT-001** | **급등/급락 알림 발송 성공** | 등락률 +11% / -11%, 스로틀링 허용(`true`) 모킹 | `processSurgeAlert()` | 1. 스로틀링 포트 1회 검증 통과<br>2. 메시징 포트 1회 호출 완료 (`"급등"` / `"급락"` 키워드 전달) |
| **SVC-ALT-002** | **알림 조건 미달 (임계치 방어)** | 등락률 Null 또는 절댓값 10% 미만(예: 1.0%) | `processSurgeAlert()` | 조건 미달로 스로틀링 및 알림 발송 로직이 아예 호출되지 않음(`never`) |
| **SVC-ALT-003** | **스로틀링 방어 (단기간 중복 알림 차단)** | 등락률 11%(조건 충족), 스로틀링 거부(`false`) 모킹 | `processSurgeAlert()` | 조건은 넘었으나 스로틀링에 막혀 메시징 포트(발송)가 호출되지 않음(`never`) |

---

## 6. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고 (특이사항) |
| :--- | :---: | :---: | :---: | :--- |
| **StockService** (실시간/조회) | 7 | 7 | 0 | Event 기반 파이프라인 위임 검증 |
| **ChartService** (차트 라우팅) | 7 | 7 | 0 | Timeframe 분기 분기점 100% 커버 |
| **CandleRollup** (순수 롤업 연산) | 5 | 5 | 0 | Mocking 없는 순수 도메인 비즈니스 연산 검증 |
| **SurgeAlert** (알림 조건/방어) | 5 | 5 | 0 | ±10% 엣지 케이스 및 중복 차단 검증 |
| **합계** | **24** | **24** | **0** | **Pass** ✅ |