# 실시간 주식 데이터 처리 아키텍처

| 문서 ID | ARC-KIS-001   |
| :--- |:--------------|
| **문서 버전** | 1.0           |
| **프로젝트** | AssetMind     |
| **작성자** | 이재석           |
| **작성일** | 2026년 01월 08일 |

## 1. 개요
본 문서는 한국투자증권(KIS) API를 활용하여 실시간 주가 정보를 처리하고 사용자에게 전달하는 **Real-time Data Pipeline**의 아키텍처를 정의한다.
시스템은 `정적 데이터(DB)`와 `동적 데이터(Memory DB)`의 역할을 명확히 분리하여 성능과 데이터 무결성을 동시에 확보한다.

## 2. 핵심 설계 원칙 (Design Principles)
1.  **역할 분리 (Separation of Concerns):** DB는 '구독 대상' 메타데이터 관리, Redis는 '실시간 상태' 캐싱에 집중한다.
2.  **고성능 캐싱 (High Performance Caching):** 고빈도(High-frequency) 체결 데이터는 Redis에 저장하여 DB 부하를 원천 차단한다.
3.  **중앙화된 상태 관리:** 백엔드 서버가 다중 인스턴스로 확장되어도 Redis를 통해 실시간 데이터의 일관성(Consistency)을 유지한다.

## 3. 데이터 흐름도 (Data Flow Sequence Diagram)

![실시간 아키텍처 다이어그램](https://github.com/user-attachments/assets/5b131a4d-298e-4e9f-86bd-e2bb455f0422)

### 3.1 흐름 상세 설명 (Flow Description)
위 시퀀스 다이어그램은 `초기 진입(Initial Load)`부터 `실시간 데이터 서빙(Serving)`까지의 전체 생명주기를 나타낸다.

1.  **메타데이터 조회 (Initialization):**
    * 사용자가 메인 페이지에 접속하면, Server는 **PostgreSQL**에서 관리 중인 '관심 종목 리스트(25개)'의 종목 코드를 조회한다.
    * 이 단계에서는 종목명, 로고 등 변하지 않는 **정적 데이터**만 확보한다.

2.  **실시간 스트림 연결 (Ingestion):**
    * 확보된 종목 코드를 이용해 **KIS Real-time Server**에 WebSocket 구독(Subscribe)을 요청한다.
    * KIS 서버로부터 체결 데이터(Raw String)가 실시간으로 Push 된다.

3.  **데이터 가공 및 캐싱 (Processing & Caching):**
    * **Parsing:** 수신된 Raw Data를 `StockTickDto` 객체로 변환한다.
    * **Caching:** 변환된 데이터를 **Redis**에 `Key-Value` 형태로 즉시 갱신(Update)한다. 이 과정은 DB 트랜잭션 없이 인메모리에서 고속으로 수행된다.

4.  **데이터 서빙 (Serving):**
    * Server는 **Redis**에 저장된 최신 상태의 데이터들을 조회(Get)한다.
    * 거래대금 등 비즈니스 로직에 따라 `정렬(Sorting)`을 수행하여 `StockSummaryDto` 리스트를 생성한다.
    * 최종적으로 Frontend에 완성된 리스트를 반환하여 화면을 렌더링한다.