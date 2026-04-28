# [TCS] Stock Presentation(Web API) 계층 테스트 명세서

| 문서 ID | **TCS-WEB-001** |
| :--- |:----------------------------------------|
| **문서 버전** | 1.0                                     |
| **프로젝트** | AssetMind                               |
| **작성자** | 이재석                                     |
| **작성일** | 2026년 04월 06일                           |
| **대상 모듈** | `server-stock/presentation` (Web Layer) |

## 1. 개요 (Overview)

본 문서는 AssetMind Stock 시스템의 클라이언트 요청을 직접 맞이하는 **Presentation(Controller) 계층**의 단위 테스트 명세이다.
`@WebMvcTest`를 사용하여 비즈니스 로직(Service)은 Mocking으로 격리하고, 오직 **HTTP 웹 계층의 역할(URL 매핑, 파라미터 유효성 검증, 공통 응답 포맷, REST Docs 문서화)이** 의도대로 동작하는지 집중적으로 검증한다.

### 1.1. 대상 컨트롤러 및 검증 목표
- **`ChartController`**: 주식 차트(N분봉, 일/주/월/년봉) 동적 데이터 서빙 및 Spring REST Docs 스니펫 생성 검증
- **`StockController`**: 주식 랭킹(거래대금/거래량) 및 특정 종목 최근 시계열 데이터 조회 검증
- **Verification Focus:**
  - **Validation:** `@Valid`, `@Min`, `@Max`, `@NotBlank` 등을 통한 파라미터 경계값(Boundary) 방어 로직 확인
  - **Exception Handling:** 유효성 위반 시 `GlobalExceptionHandler`를 통해 일관된 `400 Bad Request` 및 `ApiResponse.fail()` 구조가 반환되는지 확인
  - **Documentation:** 테스트 성공 시 API 명세서(Asciidoc) 생성이 정상적으로 트리거 되는지 확인

---

## 2. 주식 차트 조회 API (`ChartController`)

프론트엔드 차트 라이브러리 연동을 위한 캔들 데이터 제공 API의 파라미터 검증 및 문서화 동작을 확인한다.

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-CHT-001** | **[성공] 조회 및 REST Docs 생성** | Service가 정상적인 `ChartResponseDto` 반환 | `GET /.../charts/candles` (정상 파라미터) | 1. HTTP **200 OK** 및 `success=true` 확인<br>2. 응답 데이터(O,H,L,C,V) 매핑 확인<br>3. **Spring REST Docs 스니펫 정상 생성 완료** |
| **WEB-CHT-002** | **[실패] 필수 파라미터 누락** | `timeframe` 파라미터 누락 | `GET /.../charts/candles` | 1. HTTP **400 Bad Request**<br>2. `ApiResponse` 포맷(`success=false`, `data` 비어있음) 반환 |
| **WEB-CHT-003** | **[실패] Limit 범위 미달 (Boundary)** | `limit=0` (최소 1 이상 요구) | `GET /.../charts/candles` | 1. HTTP **400 Bad Request**<br>2. `GlobalExceptionHandler` 예외 포맷 정상 동작 확인 |

---

## 3. 주식 랭킹 조회 API (`StockController`)

### 3.1. 거래대금/거래량 순 랭킹 조회
**Endpoint:** `GET /api/stocks/ranking/value` & `GET /api/stocks/ranking/volume`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-STK-001** | **[성공] 랭킹 조회 성공** | Service가 정상적인 랭킹 리스트 반환 | `GET /ranking/...`<br>(param: limit=10) | HTTP **200 OK** 및 응답 Body `data` 필드에 랭킹 정보 일치 확인 |
| **WEB-STK-002** | **[실패] Limit 범위 미달 (Boundary)** | Mocking 불필요 | `GET /ranking/...`<br>(param: limit=0) | HTTP **400 Bad Request**, `success=false` 확인 |
| **WEB-STK-003** | **[실패] Limit 초과 (Boundary)** | Mocking 불필요 | `GET /ranking/...`<br>(param: limit=101) | HTTP **400 Bad Request** (최대 100 제한 위반), `success=false` 확인 |
| **WEB-STK-004** | **[성공] 디폴트 파라미터 동작** | Service가 limit=10으로 호출됨 모킹 | `GET /ranking/...`<br>(param 없음) | HTTP **200 OK** 및 Service 계층에 디폴트 값(10)이 정상 전달됨을 검증 |

---

## 4. 특정 종목 시계열 데이터 조회 API (`StockController`)

### 4.1. 종목 상세 시계열 조회
**Endpoint:** `GET /api/stocks/{stockCode}/history`

| ID | 시나리오 | Given (사전 조건) | When (실행) | Then (기대 결과) |
| :--- | :--- | :--- | :--- | :--- |
| **WEB-STK-005** | **[성공] 시계열 데이터 조회** | Service가 시계열 데이터 반환 | `GET /005930/history`<br>(param: limit=50) | HTTP **200 OK** 및 응답 `data`의 `stockCode` 일치 확인 |
| **WEB-STK-006** | **[실패] Limit 범위 미달 (Boundary)** | Mocking 불필요 | `GET /005930/history`<br>(param: limit=0) | HTTP **400 Bad Request**, `success=false` 확인 |
| **WEB-STK-007** | **[실패] Limit 초과 (Boundary)** | Mocking 불필요 | `GET /005930/history`<br>(param: limit=121) | HTTP **400 Bad Request** (최대 120 제한 위반) 확인 |
| **WEB-STK-008** | **[실패] 종목 코드 유효성 위반** | Mocking 불필요 | `GET /%20/history`<br>(공백 전송) | HTTP **400 Bad Request** (`@NotBlank` 위반 검증 완료) |
| **WEB-STK-009** | **[성공] 디폴트 파라미터 동작** | Service가 limit=30으로 호출됨 모킹 | `GET /005930/history`<br>(param 없음) | HTTP **200 OK** 및 Service 계층에 디폴트 값(30)이 전달되었는지 확인 |

---

## 5. 종합 결과

| 항목 | 전체 케이스 | Pass | Fail | 비고 (특이사항) |
| :--- | :---: | :---: | :---: | :--- |
| **ChartController** | 3 | 3 | 0 | 400 방어 및 **REST Docs 생성** 로직 검증 완료 |
| **StockController** | 13 | 13 | 0 | 랭킹 및 시계열 조회 **파라미터 Boundary 제어** 완벽 방어 |
| **합계** | **16** | **16** | **0** | **Pass** ✅ |