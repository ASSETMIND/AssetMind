# [TCS] 주식 데이터 조회 컨트롤러 단위 테스트 명세서

| 문서 ID | **TCS-STK-002**   |
| :--- |:------------------|
| **문서 버전** | 1.0               |
| **프로젝트** | AssetMind         |
| **작성자** | 이재석               |
| **작성일** | 2026년 02월 14일     |
| **대상 모듈** | `StockController` |

## 1. 개요 (Overview)

본 문서는 실시간 주식 데이터(랭킹, 시계열)를 제공하는 **Web Adapter 계층(`StockController`)을** 검증하기 위한 단위 테스트 명세이다.
`@WebMvcTest`를 사용하여 컨트롤러를 슬라이스 테스트하며, **파라미터 경계값 분석(@Min, @Max)**, **디폴트 파라미터 동작**, **Service 호출 및 DTO 반환**, **GlobalExceptionHandler를 통한 예외 처리(400 Bad Request)를** 중점적으로 확인한다.

### 1.1. 테스트 환경
- **Framework:** JUnit 5, Mockito (`@MockitoBean`), MockMvc
- **Test Class:** `StockControllerTest`
- **Configuration:** `@Import(GlobalExceptionHandler.class)` (유효성 검증 예외 처리용)
- **Mock Objects:**
    - `StockService`: 주식 데이터 조회 비즈니스 로직 모의 객체

---

## 2. 주식 랭킹 조회 테스트 (`StockController`)

### 2.1. 거래대금 순 랭킹 (Ranking by Trade Value)
**Endpoint:** `GET /api/stocks/ranking/value`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-STK-001** | **조회 성공**<br>(유효한 Limit) | Service가 `List<StockRankingResponse>` 반환 | `GET /ranking/value` 호출<br>(param: limit=10) | 1. HTTP 상태 코드 **200 OK**<br>2. 응답 Body `data` 필드 검증<br>(`stockCode`, `stockName` 일치) |
| **WEB-STK-002** | **조회 실패**<br>(Limit 미만 - Boundary) | (Mocking 불필요) | `GET /ranking/value` 호출<br>(param: limit=0) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `success`는 `false`<br>3. `data`는 `empty` 확인 |
| **WEB-STK-003** | **조회 실패**<br>(Limit 초과 - Boundary) | (Mocking 불필요) | `GET /ranking/value` 호출<br>(param: limit=101) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `success`는 `false`<br>3. `data`는 `empty` 확인 |
| **WEB-STK-004** | **디폴트 파라미터 동작** | Service가 limit=10으로 호출됨 | `GET /ranking/value` 호출<br>(param 없음) | 1. HTTP 상태 코드 **200 OK**<br>2. Service 호출 및 정상 응답 확인 |

### 2.2. 거래량 순 랭킹 (Ranking by Trade Volume)
**Endpoint:** `GET /api/stocks/ranking/volume`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-STK-005** | **조회 성공**<br>(유효한 Limit) | Service가 `List<StockRankingResponse>` 반환 | `GET /ranking/volume` 호출<br>(param: limit=10) | 1. HTTP 상태 코드 **200 OK**<br>2. 응답 Body `data` 필드 검증 확인 |
| **WEB-STK-006** | **조회 실패**<br>(Limit 미만 - Boundary) | (Mocking 불필요) | `GET /ranking/volume` 호출<br>(param: limit=0) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `success`는 `false`<br>3. `data`는 `empty` 확인 |
| **WEB-STK-007** | **조회 실패**<br>(Limit 초과 - Boundary) | (Mocking 불필요) | `GET /ranking/volume` 호출<br>(param: limit=101) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `success`는 `false`<br>3. `data`는 `empty` 확인 |
| **WEB-STK-008** | **디폴트 파라미터 동작** | Service가 limit=10으로 호출됨 | `GET /ranking/volume` 호출<br>(param 없음) | 1. HTTP 상태 코드 **200 OK**<br>2. 정상 응답 확인 |

---

## 3. 주식 시계열 데이터 조회 테스트 (`StockController`)

### 3.1. 특정 종목 상세 조회 (Stock History)
**Endpoint:** `GET /api/stocks/{stockCode}/history`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-STK-009** | **조회 성공**<br>(정상 요청) | Service가 `List<StockHistoryResponse>` 반환 | `GET /005930/history` 호출<br>(param: limit=50) | 1. HTTP 상태 코드 **200 OK**<br>2. 응답 `data`의 `stockCode` 일치 확인 |
| **WEB-STK-010** | **조회 실패**<br>(Limit 미만 - Boundary) | (Mocking 불필요) | `GET /005930/history` 호출<br>(param: limit=0) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `success`는 `false`<br>3. `data`는 `empty` 확인 |
| **WEB-STK-011** | **조회 실패**<br>(Limit 초과 - Boundary) | (Mocking 불필요) | `GET /005930/history` 호출<br>(param: limit=121) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `success`는 `false`<br>3. `data`는 `empty` 확인 |
| **WEB-STK-012** | **조회 실패**<br>(종목 코드 누락/공백) | (Mocking 불필요) | `GET /%20/history` 호출<br>(공백 문자 전송) | 1. HTTP 상태 코드 **400 Bad Request**<br>2. `@NotBlank` 위반에 따른 예외 처리 확인 |
| **WEB-STK-013** | **디폴트 파라미터 동작** | Service가 limit=30으로 호출됨 | `GET /005930/history` 호출<br>(param 없음) | 1. HTTP 상태 코드 **200 OK**<br>2. Service에 `30`이 인자로 전달되었는지 확인 |

---

## 4. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고                          |
| :--- | :---: | :---: | :---: |:----------------------------|
| **StockController** | 13 | 13 | 0 | 랭킹(거래대금/거래량) 및 시계열 조회 검증 완료 |
| **합계** | **13** | **13** | **0** | **Pass**                    |