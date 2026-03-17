# 컴포넌트 인벤토리 및 구현 우선순위 정의서

> 스프린트 6 / 작성일: 2026-03-17
> 목적: 스프린트 4·5 Figma 컴포넌트를 Storybook UI 컴포넌트로 구현하기 위한 범위 확정

---

## 1. 기존 구현 컴포넌트 (스프린트 3)

| 컴포넌트 | 경로 | Story 여부 |
|---|---|---|
| Button | `components/common` | ✅ |
| Input | `components/common` | ✅ |
| Modal | `components/common` | ✅ |
| Toast / ToastItem | `components/common/Toast` | ✅ |
| CodeSnippet | `components/common` | ✅ |
| LoginModal | `components/auth` | ✅ |
| SignUpModal | `components/auth` | ✅ |
| ColorPalette | `stories/DesignTokens` | ✅ |
| TypographyViewer / SpacingViewer | `stories/DesignTokens` | ✅ |

---

## 2. 스프린트 6 신규·확장 컴포넌트 분류표

| 컴포넌트 | 분류 | 근거 | 담당 이슈 |
|---|---|---|---|
| Tab | 신규 | 기존 없음 | 이슈 2 |
| Skeleton | 신규 | 기존 없음 | 이슈 2 |
| MobileTabSwitcher (Sticky) | 신규 | 기존 Tab과 별개. 스크롤 인터랙션 포함 | 이슈 2 |
| PriceChangeToken (등락률) | 확장 | 기존 색상 토큰 연동. Badge/Text 레벨 확장 | 이슈 2 |
| StockTable | 신규 | 기존 없음 | 이슈 3 |
| TickerAnimation | 신규 | 기존 없음 | 이슈 3 |
| LinearGauge | 신규 | 기존 없음 | 이슈 3 |
| LocalError | 신규 | Modal/Toast와 다름. 인라인 부분 오류 UI | 이슈 3 |
| OrderbookEmptyState | 신규 | 기존 없음. 호가창 전용 오버레이 | 이슈 3 |
| TradingViewWrapper | 신규 | 외부 위젯 래퍼. 기존 없음 | 이슈 4 |
| OrderbookTable | 신규 | 기존 없음 | 이슈 4 |
| TradeTickerList | 신규 | TickerAnimation 재사용 가능성 있음 | 이슈 4 |
| InvestorTable | 신규 | StockTable 구조 재사용 가능성 있음 | 이슈 4 |
| SparklineChart | 신규 | 기존 없음 | 이슈 5 |
| PredictionRangeBar | 신규 | LinearGauge 구조 참고 가능 | 이슈 5 |
| PredictionAnalysisWidget | 신규 | 기존 없음 | 이슈 5 |

---

## 3. 구현 우선순위

### P0 — 공통 의존성 (이슈 2, 가장 먼저 구현)
다른 컴포넌트에서 공통으로 사용되므로 이슈 3 시작 전 완료 필수.

- Tab
- Skeleton
- MobileTabSwitcher (Sticky)
- PriceChangeToken (등락률)

### P1 — 주가 데이터 페이지 (이슈 3)
P0 완료 후 순차 구현.

- StockTable
- TickerAnimation
- LinearGauge
- LocalError
- GlobalEmptyState

### P2 — 종목 세부 페이지 차트·호가·거래현황 탭 (이슈 4)
P1 완료 후 구현. TradeTickerList는 TickerAnimation 완성 후 조합.

- TradingViewWrapper
- OrderbookTable
- TradeTickerList ← TickerAnimation 의존
- InvestorTable ← StockTable 구조 참고

### P3 — AI 예측 패널 (이슈 5)
P2 완료 후 구현. PredictionRangeBar는 LinearGauge 로직 참고.

- SparklineChart
- PredictionRangeBar ← LinearGauge 참고
- PredictionAnalysisWidget

---

## 4. Story 작성 범위 정의

| 컴포넌트 | Story 작성 여부 | 비고 |
|---|---|---|
| Tab | ✅ | 기간 필터 / 세부 탭 variant 포함 |
| Skeleton | ✅ | 테이블 행·카드·차트 영역 variant 포함 |
| MobileTabSwitcher | ✅ | Sticky 스크롤 인터랙션 데모 포함 |
| PriceChangeToken | ✅ | 상승·하락·보합 + 다크모드 variant 포함 |
| StockTable | ✅ | 정렬·등락률·로딩 상태 Controls 포함 |
| TickerAnimation | ✅ | 깜빡임·배경색 변화 인터랙션 데모 포함 |
| LinearGauge | ✅ | 극단값(99:1) 처리 케이스 포함 |
| LocalError | ✅ | 재시도 액션 포함 |
| GlobalEmptyState | ✅ | 시장 휴장 오버레이 케이스 포함 |
| TradingViewWrapper | ✅ | 기간 선택 Tab 연동 데모 포함 |
| OrderbookTable | ✅ | 매도/매수 호가 + 등락률 토큰 포함 |
| TradeTickerList | ✅ | 실시간 체결 내역 애니메이션 데모 포함 |
| InvestorTable | ✅ | 투자자 유형별 데이터 Controls 포함 |
| SparklineChart | ✅ | 패널 너비 제약 variant 포함 |
| PredictionRangeBar | ✅ | 예측 가격 구간·신뢰도 표시 포함 |
| PredictionAnalysisWidget | ✅ | 기술적·시장 심리·수급 분석 항목 포함, 데이터 바인딩 명세 연동 |

---

## 5. 재사용 관계 메모

```
TickerAnimation
  └─ TradeTickerList (조합)

StockTable
  └─ InvestorTable (구조 재사용 검토)

LinearGauge
  └─ PredictionRangeBar (min-width 규칙 로직 참고)

Skeleton
  └─ 모든 페이지 로딩 상태에서 공통 사용
```

---

## 6. 신규 컴포넌트 배치 경로 (안)

```
src/
└─ components/
   ├─ common/
   │  ├─ Tab/
   │  ├─ Skeleton/
   │  ├─ MobileTabSwitcher/
   │  ├─ PriceChangeToken/
   │  ├─ LocalError/
   │  └─ GlobalEmptyState/
   ├─ stock/
   │  ├─ StockTable/
   │  ├─ TickerAnimation/
   │  ├─ LinearGauge/
   │  ├─ TradingViewWrapper/
   │  ├─ OrderbookTable/
   │  ├─ TradeTickerList/
   │  └─ InvestorTable/
   └─ ai-panel/
      ├─ SparklineChart/
      ├─ PredictionRangeBar/
      └─ PredictionAnalysisWidget/
```