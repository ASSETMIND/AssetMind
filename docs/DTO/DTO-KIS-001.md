# StockTickDto 클래스 구조 설계

| 문서 ID | DTO-KIS-001   |
| :--- |:--------------|
| **문서 버전** | 1.0           |
| **프로젝트** | AssetMind     |
| **작성자** | 이재석           |
| **작성일** | 2026년 01월 08일 |

## 1. 개요
`StockTickDto`는 **실시간 주식 체결 원천 데이터 DTO** 로써, 파서(Parser)를 통해 Raw String을 시스템 내부에서 사용 가능한 형태(Object)로 변환한 불변 객체(Immutable Record)이다. 
`List<StockTickDto>` 형식으로 프론트로 응답할 객체이다.

## 2. 클래스 명세
* **Package**: `com.assetmind.server_stokc.stock.dto` (상황에 따라 약간의 변경 가능성 있음)
* **Type**: Java `record`
* **Dependency**: Lombok (`@Builder`)

## 3. 구현 코드 (초안)

```java
import java.math.BigDecimal;
import lombok.Builder;

/**
 * 실시간 주식 체결 원천 데이터 DTO
 * 한국투자증권 WebSocket 데이터를 파싱하여 저장
 * record 타입으로 인한 불변성(Immutable) 보장
 */
@Builder
public record StockTickDto(
    String symbol,                   // 종목코드 (MKSC_SHRN_ISCD)
    BigDecimal currentPrice,         // 현재가 (STCK_PRPR)
    BigDecimal changeRate,           // 등락률 (PRDY_CTRT)
    BigDecimal accumulatedVolume,    // 누적 거래량 (ACML_VOL)
    BigDecimal accumulatedTradeValue // 누적 거래대금 (ACML_TR_PBMN)
) {

    /**
     * 거래대금 조회 유틸리티 메서드 (Null-Safe)
     * API 원본 데이터에 거래대금이 누락된 경우, [현재가 * 거래량]으로 대체 계산하여 반환
     * 랭킹 정렬 및 화면 표시 시 이 메서드를 호출하여 사용
     */
    public BigDecimal getTradeValue() {
        // + 원본 데이터가 유효하면 우선 사용 로직
        ...
        // + 방어 로직: 필수 값이 누락된 경우 0 반환
        ...
        
        // + 계산된 거래대금 반환로직
        return currentPrice.multiply(accumulatedVolume);
    }
}