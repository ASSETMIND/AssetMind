# 실시간 주식 데이터 수집 명세서

| 문서 ID     | ETL-KIS-001   |
|:----------|:--------------|
| **문서 버전** | 1.1           |
| **프로젝트**  | AssetMind     |
| **작성자**   | 이재석           |
| **작성일**   | 2026년 01월 08일 |

## 1. 개요
본 문서는 한국투자증권(KIS) 실시간 웹소켓 API(`H0UNCNT0`)를 통해 수신되는 주식 체결 데이터 중, 서비스 구현에 필수적인 필드와 처리 규칙을 정의한다.

## 2. 수집 대상 필드 (Raw Data Specification)
> KIS API (국내주식 실시간체결가) 참조: https://apiportal.koreainvestment.com/apiservice-apiservice?/tryitout/H0UNCNT0
* **Source**: 한국투자증권 WebSocket (Realtime)
* **TR ID**: `H0UNCNT0` (주식체결가)
* **Format**: `|` 구분자 문자열

| Index | 필드 ID | 필드명 (Logical) | 타입 (Raw) | 설명                        | 비고 |
| :--- | :--- | :--- | :--- |:--------------------------| :--- |
| **0** | `MKSC_SHRN_ISCD` | **종목코드** | String | 종목 식별자 (예: 005930 [삼성전자]) | PK 역할 |
| **2** | `STCK_PRPR` | **현재가** | String | 실시간 체결 가격                 | `BigDecimal` 변환 필수 |
| **5** | `PRDY_CTRT` | **등락률** | String | 전일 대비 등락률 (%)             | 화면 색상 결정 (Red/Blue) |
| **12** | `ACML_VOL` | **누적거래량** | String | 당일 장 시작 후 총 거래량           | 거래대금 산출 보조 |
| **14** | `ACML_TR_PBMN` | **누적거래대금** | String | 당일 장 시작 후 총 거래 금액         | **정렬(Ranking) 기준 데이터** |

## 3. 데이터 처리 규칙 (Business Rules)

### 3.1 거래대금(Trade Value) 산출 로직
일부 데이터 패킷에서 **누적거래대금(Index 14)** 필드가 null이거나 `0`으로 수신될 수 있다. 데이터의 정합성을 위해 아래 우선순위에 따라 값을 결정한다.
* **1순위:** `누적거래대금(Index 14)` 값이 존재하면 해당 값을 사용.
* **2순위:** 값이 없을 경우, **`현재가(Index 2) * 누적거래랑(Index 12)`** 공식을 사용하여 근사치 계산.

### 3.2 데이터 타입 및 예외 처리
* **정밀도 보장:** 모든 금액 및 비율 데이터는 부동소수점 오차 방지를 위해 Java `BicDecimal` 타입을 사용한다.
* **Null Safety:** 파싱 중 `null`, `Empty String`, `NumberFormatError` 발생 시 시스템 중단 없이 해당 필드를 `0`(default)으로 처리한다.